"""Periodic escalation of unresolved tickets with expired active SLAs."""

import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import SessionLocal
from app.models import Ticket, TicketSLA, TicketStatus, User, UserRole
from app.services.tickets import _apply_escalation


logger = logging.getLogger(__name__)
AUTOMATIC_ESCALATION_REASON = "SLA deadline exceeded (automatic timeout)"
ELIGIBLE_STATUSES = (
    TicketStatus.OPEN,
    TicketStatus.IN_PROGRESS,
    TicketStatus.REOPENED,
)
SessionFactory = Callable[[], Session]


def _find_candidate_ids(session: Session, now: datetime) -> list[int]:
    return list(
        session.scalars(
            select(Ticket.id)
            .join(TicketSLA, TicketSLA.ticket_id == Ticket.id)
            .where(
                Ticket.status.in_(ELIGIBLE_STATUSES),
                Ticket.resolved_at.is_(None),
                Ticket.closed_at.is_(None),
                TicketSLA.is_paused.is_(False),
                TicketSLA.due_at < now,
            )
            .order_by(TicketSLA.due_at, Ticket.id)
        ).all()
    )


def escalate_overdue_tickets(
    session_factory: sessionmaker = SessionLocal,
    now: Optional[datetime] = None,
) -> int:
    """Escalate eligible tickets independently, committing one ticket at a time.

    A discovery query avoids holding a long transaction. Each ticket is then
    locked with SKIP LOCKED and eligibility is rechecked under the lock. This
    makes overlapping scheduler invocations safe without a distributed lease.
    """
    now = now or datetime.now(timezone.utc)
    with session_factory() as discovery_session:
        candidate_ids = _find_candidate_ids(discovery_session, now)

    escalated_count = 0
    for ticket_id in candidate_ids:
        escalated = False
        try:
            with session_factory.begin() as session:
                ticket = session.scalar(
                    select(Ticket)
                    .where(Ticket.id == ticket_id)
                    .with_for_update(skip_locked=True)
                )
                if ticket is None:
                    # Another invocation currently owns this row, or it was
                    # removed after the discovery query.
                    continue

                sla = session.scalar(
                    select(TicketSLA)
                    .where(TicketSLA.ticket_id == ticket.id)
                    .with_for_update()
                )
                if (
                    ticket.status not in ELIGIBLE_STATUSES
                    or ticket.resolved_at is not None
                    or ticket.closed_at is not None
                    or sla is None
                    or sla.is_paused
                    or sla.due_at >= now
                ):
                    continue

                system_user = session.scalar(
                    select(User).where(
                        User.email == "system@concave.internal",
                        User.role == UserRole.SYSTEM,
                        User.is_active.is_(True),
                        User.password_hash.is_(None),
                    )
                )
                if system_user is None:
                    raise RuntimeError(
                        "Automatic SLA escalation requires the active, passwordless "
                        "system@concave.internal SYSTEM user; run the database seed."
                    )

                _apply_escalation(
                    session,
                    ticket,
                    system_user,
                    AUTOMATIC_ESCALATION_REASON,
                    now,
                )
                escalated = True
            # Count only after the per-ticket transaction commits successfully.
            escalated_count += int(escalated)
        except Exception:
            # Keep independent ticket failures from suppressing other due
            # tickets. The failed transaction rolls back state, history, and
            # notifications together and will be retried on the next interval.
            logger.exception("Automatic SLA escalation failed for ticket_id=%s", ticket_id)

    return escalated_count
