from datetime import datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    CategoryPrioritySetting,
    Notification,
    ReopenSetting,
    TATSetting,
    Ticket,
    TicketCategory,
    TicketHistory,
    TicketPriority,
    TicketReply,
    TicketSLA,
    TicketSLACycle,
    TicketStatus,
    User,
    UserRole,
)
from app.schemas.tickets import (
    DashboardResponse,
    HistoryResponse,
    ReplyResponse,
    TicketDetail,
    TicketList,
    TicketSummary,
    UserSummary,
)


OPEN_COUNT_STATUSES = {
    TicketStatus.OPEN,
    TicketStatus.IN_PROGRESS,
    TicketStatus.REOPENED,
}
NON_TERMINAL_STATUSES = OPEN_COUNT_STATUSES | {TicketStatus.ESCALATED}
UNRESOLVED_STATUSES = OPEN_COUNT_STATUSES | {TicketStatus.ESCALATED}
SUPPORT_ROLES = {UserRole.SUPPORT_AGENT, UserRole.SUPPORT_HEAD}
ALLOWED_TRANSITIONS = {
    TicketStatus.OPEN: {TicketStatus.IN_PROGRESS, TicketStatus.ESCALATED},
    TicketStatus.IN_PROGRESS: {TicketStatus.RESOLVED, TicketStatus.ESCALATED},
    TicketStatus.REOPENED: {TicketStatus.IN_PROGRESS, TicketStatus.ESCALATED},
    TicketStatus.ESCALATED: {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED},
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _http_error(code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


def _require_member(actor: User) -> None:
    if actor.role is not UserRole.MEMBER:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Member role required")


def _require_support(actor: User) -> None:
    if actor.role not in SUPPORT_ROLES:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Support Agent or Support Head role required")


def _active_sla_cycle(db: Session, ticket_id: int, lock: bool = False) -> TicketSLACycle:
    statement = select(TicketSLACycle).where(
        TicketSLACycle.ticket_id == ticket_id,
        TicketSLACycle.resolved_at.is_(None),
    )
    if lock:
        statement = statement.with_for_update()
    cycle = db.scalar(statement)
    if cycle is None:
        raise _http_error(status.HTTP_409_CONFLICT, "Ticket has no active SLA cycle")
    return cycle


def _summary(user: Optional[User]) -> Optional[UserSummary]:
    if user is None:
        return None
    return UserSummary(id=user.id, name=user.name, email=user.email, role=user.role)


def _record_history(
    db: Session,
    ticket: Ticket,
    actor: User,
    action: str,
    old_value=None,
    new_value=None,
    reason: Optional[str] = None,
) -> None:
    ticket.history.append(
        TicketHistory(
            actor=actor,
            action=action,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
        )
    )


def _notify(db: Session, user: User, ticket: Ticket, kind: str, message: str) -> None:
    db.add(
        Notification(
            recipient_id=user.id,
            ticket_id=ticket.id,
            type=kind,
            message=message,
        )
    )


def _notify_support_heads(db: Session, ticket: Ticket, kind: str, message: str) -> None:
    heads = db.scalars(
        select(User).where(User.role == UserRole.SUPPORT_HEAD, User.is_active.is_(True))
    ).all()
    for head in heads:
        _notify(db, head, ticket, kind, message)


def _get_ticket(db: Session, ticket_id: int, lock: bool = False) -> Ticket:
    statement = (
        select(Ticket)
        .options(
            selectinload(Ticket.member),
            selectinload(Ticket.assigned_to),
            selectinload(Ticket.sla),
            selectinload(Ticket.replies).selectinload(TicketReply.sender),
            selectinload(Ticket.history).selectinload(TicketHistory.actor),
        )
        .where(Ticket.id == ticket_id)
    )
    if lock:
        statement = statement.with_for_update()
    ticket = db.scalar(statement)
    if ticket is None:
        raise _http_error(status.HTTP_404_NOT_FOUND, "Ticket not found")
    return ticket


def get_authorized_ticket(db: Session, ticket_id: int, user: User) -> Ticket:
    if user.role is not UserRole.MEMBER and user.role not in SUPPORT_ROLES:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Role cannot access ticket data")
    ticket = _get_ticket(db, ticket_id)
    if user.role is UserRole.MEMBER and ticket.member_id != user.id:
        raise _http_error(status.HTTP_404_NOT_FOUND, "Ticket not found")
    return ticket


def _ticket_summary(ticket: Ticket, now: Optional[datetime] = None) -> TicketSummary:
    now = now or utc_now()
    sla = ticket.sla
    if sla is None:
        raise _http_error(
            status.HTTP_409_CONFLICT,
            "Ticket SLA data is missing; restore verified SLA state before continuing.",
        )
    overdue = bool(
        not sla.is_paused
        and sla.due_at <= now
        and ticket.status in UNRESOLVED_STATUSES
    )
    return TicketSummary(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        category=ticket.category,
        subject=ticket.subject,
        priority=ticket.priority,
        status=ticket.status,
        assigned_to=_summary(ticket.assigned_to),
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        due_at=sla.due_at,
        is_overdue=overdue,
    )


def _ticket_detail(ticket: Ticket, show_internal: bool) -> TicketDetail:
    now = utc_now()
    replies = sorted(ticket.replies, key=lambda item: (item.created_at, item.id))
    history = sorted(ticket.history, key=lambda item: (item.created_at, item.id))
    return TicketDetail(
        **_ticket_summary(ticket, now).model_dump(),
        member=UserSummary(
            id=ticket.member.id,
            name=ticket.member.name,
            email=ticket.member.email,
            role=ticket.member.role,
        ),
        description=ticket.description,
        reopen_count=ticket.reopen_count,
        resolved_at=ticket.resolved_at,
        closed_at=ticket.closed_at,
        is_sla_paused=bool(ticket.sla and ticket.sla.is_paused),
        replies=[
            ReplyResponse(
                id=reply.id,
                sender=UserSummary(
                    id=reply.sender.id,
                    name=reply.sender.name,
                    email=reply.sender.email,
                    role=reply.sender.role,
                ),
                message=reply.message,
                is_internal=reply.is_internal,
                created_at=reply.created_at,
            )
            for reply in replies
            if show_internal or not reply.is_internal
        ],
        history=[
            HistoryResponse(
                id=event.id,
                actor=UserSummary(
                    id=event.actor.id,
                    name=event.actor.name,
                    email=event.actor.email,
                    role=event.actor.role,
                ),
                action=event.action,
                old_value=event.old_value,
                new_value=event.new_value,
                reason=event.reason,
                created_at=event.created_at,
            )
            for event in history
            if show_internal
            or not (
                event.action == "REPLY_ADDED"
                and isinstance(event.new_value, dict)
                and event.new_value.get("is_internal") is True
            )
        ],
    )


def _ensure_reply_allowed(ticket: Ticket) -> None:
    if ticket.status in {TicketStatus.CLOSED, TicketStatus.RESOLVED}:
        raise _http_error(status.HTTP_409_CONFLICT, "Replies are not allowed for this ticket status")


def _apply_escalation(
    db: Session,
    ticket: Ticket,
    actor: User,
    reason: str,
    now: datetime,
) -> None:
    """Apply the common escalation state, history, and notification changes."""
    old_status = ticket.status
    ticket.previous_status = old_status
    ticket.status = TicketStatus.ESCALATED
    ticket.updated_at = now
    if ticket.sla is not None:
        ticket.sla.escalated_at = now
    _record_history(
        db,
        ticket,
        actor,
        "TICKET_ESCALATED",
        old_value={"status": old_status.value},
        new_value={"status": TicketStatus.ESCALATED.value},
        reason=reason,
    )
    _notify_support_heads(
        db, ticket, "TICKET_ESCALATED", f"Ticket {ticket.ticket_number} was escalated"
    )
    _record_history(
        db,
        ticket,
        actor,
        "STATUS_CHANGED",
        old_value={"status": old_status.value},
        new_value={"status": TicketStatus.ESCALATED.value},
        reason=reason,
    )
    db.flush()


def _get_tat_hours(db: Session, priority: TicketPriority) -> int:
    setting = db.scalar(select(TATSetting).where(TATSetting.priority == priority))
    if setting is None:
        raise _http_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "TAT settings are not configured")
    return setting.resolution_hours


def create_ticket(db: Session, member: User, category: TicketCategory, subject: str, description: str) -> TicketDetail:
    _require_member(member)
    subject = subject.strip()
    description = description.strip()
    if not subject or not description:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Subject and description must not be blank")
    priority_setting = db.scalar(
        select(CategoryPrioritySetting).where(CategoryPrioritySetting.category == category)
    )
    if priority_setting is None:
        raise _http_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "Category priority settings are not configured")
    now = utc_now()
    hours = _get_tat_hours(db, priority_setting.default_priority)
    ticket = Ticket(
        member_id=member.id,
        category=category,
        subject=subject.strip(),
        description=description.strip(),
        priority=priority_setting.default_priority,
        status=TicketStatus.OPEN,
    )
    db.add(ticket)
    db.flush()
    ticket.sla = TicketSLA(
        started_at=now,
        due_at=now + timedelta(hours=hours),
        is_paused=False,
        accumulated_pause_duration=0,
    )
    ticket.sla_cycles.append(
        TicketSLACycle(
            cycle_number=1,
            priority=ticket.priority,
            started_at=now,
            accumulated_pause_duration_seconds=0,
        )
    )
    _record_history(
        db,
        ticket,
        member,
        "TICKET_CREATED",
        new_value={"ticket_number": ticket.ticket_number, "status": TicketStatus.OPEN.value},
    )
    _notify_support_heads(db, ticket, "TICKET_CREATED", f"New ticket {ticket.ticket_number} was created")
    db.flush()
    return _ticket_detail(ticket, show_internal=False)


def list_member_tickets(db: Session, member: User, page: int, page_size: int) -> TicketList:
    _require_member(member)
    base = select(Ticket).where(Ticket.member_id == member.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    tickets = db.scalars(
        base.options(selectinload(Ticket.assigned_to), selectinload(Ticket.sla))
        .order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return TicketList(
        items=[_ticket_summary(ticket) for ticket in tickets],
        page=page,
        page_size=page_size,
        total=total,
    )


def list_support_tickets(
    db: Session,
    actor: User,
    page: int,
    page_size: int,
    status_filter: Optional[TicketStatus] = None,
    category_filter: Optional[TicketCategory] = None,
    priority_filter: Optional[TicketPriority] = None,
    overdue: Optional[bool] = None,
    search: Optional[str] = None,
) -> TicketList:
    _require_support(actor)
    now = utc_now()
    statement = select(Ticket).outerjoin(Ticket.sla).join(Ticket.member)
    if status_filter is not None:
        statement = statement.where(Ticket.status == status_filter)
    if category_filter is not None:
        statement = statement.where(Ticket.category == category_filter)
    if priority_filter is not None:
        statement = statement.where(Ticket.priority == priority_filter)
    if overdue is True:
        statement = statement.where(
            TicketSLA.due_at <= now,
            TicketSLA.is_paused.is_(False),
            Ticket.status.in_(UNRESOLVED_STATUSES),
        )
    elif overdue is False:
        statement = statement.where(
            or_(
                Ticket.status.notin_(UNRESOLVED_STATUSES),
                TicketSLA.id.is_(None),
                TicketSLA.is_paused.is_(True),
                TicketSLA.due_at > now,
            )
        )
    if search:
        normalized_search = search.strip()
        term = f"%{normalized_search}%"
        matches = [Ticket.ticket_number.ilike(term), User.name.ilike(term), User.email.ilike(term)]
        if normalized_search.isdigit():
            matches.append(Ticket.id == int(normalized_search))
        statement = statement.where(or_(*matches))
    count_query = select(func.count()).select_from(statement.order_by(None).subquery())
    total = db.scalar(count_query) or 0
    rows = db.scalars(
        statement.options(
            selectinload(Ticket.assigned_to), selectinload(Ticket.sla)
        )
        .order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return TicketList(
        items=[_ticket_summary(ticket, now) for ticket in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


def read_ticket(db: Session, ticket_id: int, user: User) -> TicketDetail:
    ticket = get_authorized_ticket(db, ticket_id, user)
    return _ticket_detail(ticket, show_internal=user.role in SUPPORT_ROLES)


def add_reply(
    db: Session,
    ticket_id: int,
    actor: User,
    message: str,
    is_internal: bool = False,
    request_information: bool = False,
) -> TicketDetail:
    if actor.role is not UserRole.MEMBER and actor.role not in SUPPORT_ROLES:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Role cannot reply to tickets")
    message = message.strip()
    if not message:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Reply message must not be blank")
    ticket = _get_ticket(db, ticket_id, lock=True)
    is_support = actor.role in SUPPORT_ROLES
    if actor.role is UserRole.MEMBER and ticket.member_id != actor.id:
        raise _http_error(status.HTTP_404_NOT_FOUND, "Ticket not found")
    if not is_support and (is_internal or request_information):
        raise _http_error(status.HTTP_403_FORBIDDEN, "Members cannot create internal replies or pause the SLA")
    if request_information and is_internal:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Information requests must be visible to the member")
    _ensure_reply_allowed(ticket)
    if request_information:
        if ticket.status not in NON_TERMINAL_STATUSES:
            raise _http_error(
                status.HTTP_409_CONFLICT,
                "Information can only be requested while a ticket is non-terminal",
            )
        if ticket.sla is None or ticket.sla.is_paused:
            raise _http_error(status.HTTP_409_CONFLICT, "The SLA is already paused or unavailable")
    reply = TicketReply(
        ticket_id=ticket.id,
        sender_id=actor.id,
        message=message,
        is_internal=is_internal,
    )
    ticket.replies.append(reply)
    reply.sender = actor
    db.flush()
    _record_history(
        db,
        ticket,
        actor,
        "REPLY_ADDED",
        new_value={"reply_id": reply.id, "is_internal": is_internal},
    )

    if request_information:
        now = utc_now()
        ticket.sla.is_paused = True
        ticket.sla.paused_at = now
        ticket.sla.last_calculated_at = now
        _record_history(db, ticket, actor, "SLA_PAUSED", new_value={"paused_at": now.isoformat()}, reason="Information requested from member")
        _notify(db, ticket.member, ticket, "INFORMATION_REQUESTED", f"Support requested information for {ticket.ticket_number}")
    elif actor.role is UserRole.MEMBER and ticket.sla and ticket.sla.is_paused:
        now = utc_now()
        paused_at = ticket.sla.paused_at
        paused_seconds = max(0, int((now - paused_at).total_seconds()))
        ticket.sla.accumulated_pause_duration += paused_seconds
        ticket.sla.due_at += timedelta(seconds=paused_seconds)
        cycle = _active_sla_cycle(db, ticket.id, lock=True)
        cycle.accumulated_pause_duration_seconds += paused_seconds
        ticket.sla.is_paused = False
        ticket.sla.paused_at = None
        ticket.sla.last_calculated_at = now
        _record_history(
            db,
            ticket,
            actor,
            "SLA_RESUMED",
            old_value={"paused_at": paused_at.isoformat()},
            new_value={
                "accumulated_pause_duration": ticket.sla.accumulated_pause_duration,
                "pause_duration_seconds": paused_seconds,
            },
        )
        if ticket.assigned_to:
            _notify(db, ticket.assigned_to, ticket, "MEMBER_REPLIED", f"Member replied to {ticket.ticket_number}")
        else:
            _notify_support_heads(db, ticket, "MEMBER_REPLIED", f"Member replied to {ticket.ticket_number}")
    elif actor.role is UserRole.MEMBER:
        if ticket.assigned_to:
            _notify(db, ticket.assigned_to, ticket, "MEMBER_REPLIED", f"Member replied to {ticket.ticket_number}")
        else:
            _notify_support_heads(db, ticket, "MEMBER_REPLIED", f"Member replied to {ticket.ticket_number}")
    elif not is_internal:
        _notify(db, ticket.member, ticket, "SUPPORT_REPLIED", f"Support replied to {ticket.ticket_number}")

    ticket.updated_at = utc_now()
    db.flush()
    return _ticket_detail(ticket, show_internal=is_support)


def assign_ticket(db: Session, ticket_id: int, actor: User, assigned_to_id: Optional[int]) -> TicketDetail:
    _require_support(actor)
    ticket = _get_ticket(db, ticket_id, lock=True)
    if assigned_to_id is None:
        target = None
    else:
        target = db.scalar(
            select(User).where(
                User.id == assigned_to_id,
                User.role == UserRole.SUPPORT_AGENT,
                User.is_active.is_(True),
            )
        )
        if target is None:
            raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Assignee must be an active Support Agent")
    old_id = ticket.assigned_to_id
    ticket.assigned_to = target
    ticket.updated_at = utc_now()
    _record_history(db, ticket, actor, "TICKET_ASSIGNED", old_value={"assigned_to_id": old_id}, new_value={"assigned_to_id": target.id if target else None})
    if target:
        _notify(db, target, ticket, "TICKET_ASSIGNED", f"Ticket {ticket.ticket_number} was assigned to you")
    _notify(db, ticket.member, ticket, "TICKET_ASSIGNED", f"Ticket {ticket.ticket_number} was assigned")
    db.flush()
    return _ticket_detail(ticket, show_internal=True)


def update_status(
    db: Session,
    ticket_id: int,
    actor: User,
    new_status: TicketStatus,
    reason: Optional[str] = None,
) -> TicketDetail:
    _require_support(actor)
    ticket = _get_ticket(db, ticket_id, lock=True)
    if new_status not in ALLOWED_TRANSITIONS.get(ticket.status, set()):
        raise _http_error(
            status.HTTP_409_CONFLICT,
            f"Cannot transition ticket from {ticket.status.value} to {new_status.value}",
        )
    old_status = ticket.status
    if new_status is TicketStatus.ESCALATED:
        reason = (reason or "").strip()
        if not reason:
            raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "An escalation reason is required")
        _apply_escalation(db, ticket, actor, reason, utc_now())
        return _ticket_detail(ticket, show_internal=True)

    target_status = new_status
    if old_status is TicketStatus.ESCALATED and new_status is TicketStatus.IN_PROGRESS:
        if ticket.previous_status in OPEN_COUNT_STATUSES:
            target_status = ticket.previous_status
    now = utc_now()
    if old_status is TicketStatus.ESCALATED:
        ticket.previous_status = None
    else:
        ticket.previous_status = old_status
    ticket.status = target_status
    ticket.updated_at = now
    if target_status is TicketStatus.RESOLVED:
        ticket.resolved_at = now
        cycle = _active_sla_cycle(db, ticket.id, lock=True)
        if ticket.sla is None:
            raise _http_error(status.HTTP_409_CONFLICT, "Ticket SLA state is unavailable")
        open_pause_seconds = 0
        if ticket.sla.is_paused and ticket.sla.paused_at is not None:
            open_pause_seconds = max(0, int((now - ticket.sla.paused_at).total_seconds()))
            ticket.sla.accumulated_pause_duration += open_pause_seconds
            ticket.sla.due_at += timedelta(seconds=open_pause_seconds)
            ticket.sla.is_paused = False
            ticket.sla.paused_at = None
        ticket.sla.last_calculated_at = now
        cycle.accumulated_pause_duration_seconds = ticket.sla.accumulated_pause_duration
        cycle.priority = ticket.priority
        cycle.resolved_at = now
        _record_history(
            db,
            ticket,
            actor,
            "TICKET_RESOLVED",
            old_value={"status": old_status.value},
            new_value={
                "status": target_status.value,
                "resolved_at": now.isoformat(),
                "cycle_number": cycle.cycle_number,
                "pause_duration_at_resolution_seconds": open_pause_seconds,
            },
        )
        _notify(db, ticket.member, ticket, "TICKET_RESOLVED", f"Ticket {ticket.ticket_number} was resolved")
    _record_history(
        db,
        ticket,
        actor,
        "STATUS_CHANGED",
        old_value={"status": old_status.value},
        new_value={"status": target_status.value},
        reason=None,
    )
    db.flush()
    return _ticket_detail(ticket, show_internal=True)


def confirm_resolution(db: Session, ticket_id: int, member: User) -> TicketDetail:
    _require_member(member)
    ticket = _get_ticket(db, ticket_id, lock=True)
    if ticket.member_id != member.id:
        raise _http_error(status.HTTP_404_NOT_FOUND, "Ticket not found")
    if ticket.status is not TicketStatus.RESOLVED:
        raise _http_error(status.HTTP_409_CONFLICT, "Only resolved tickets can be closed by the member")
    now = utc_now()
    cycle = db.scalar(
        select(TicketSLACycle)
        .where(
            TicketSLACycle.ticket_id == ticket.id,
            TicketSLACycle.cycle_number == ticket.reopen_count + 1,
            TicketSLACycle.resolved_at.is_not(None),
        )
        .with_for_update()
    )
    if cycle is None:
        raise _http_error(status.HTTP_409_CONFLICT, "Resolved SLA cycle is unavailable")
    ticket.previous_status = ticket.status
    ticket.status = TicketStatus.CLOSED
    ticket.closed_at = now
    cycle.closed_at = now
    ticket.updated_at = now
    _record_history(
        db,
        ticket,
        member,
        "TICKET_CLOSED",
        old_value={"status": TicketStatus.RESOLVED.value},
        new_value={
            "status": TicketStatus.CLOSED.value,
            "closed_at": now.isoformat(),
            "cycle_number": cycle.cycle_number,
        },
    )
    if ticket.assigned_to:
        _notify(db, ticket.assigned_to, ticket, "TICKET_CLOSED", f"Member confirmed resolution of {ticket.ticket_number}")
    else:
        _notify_support_heads(db, ticket, "TICKET_CLOSED", f"Member confirmed resolution of {ticket.ticket_number}")
    db.flush()
    return _ticket_detail(ticket, show_internal=False)


def reopen_ticket(db: Session, ticket_id: int, member: User, reason: str) -> TicketDetail:
    _require_member(member)
    ticket = _get_ticket(db, ticket_id, lock=True)
    if ticket.member_id != member.id:
        raise _http_error(status.HTTP_404_NOT_FOUND, "Ticket not found")
    if ticket.status is not TicketStatus.CLOSED or ticket.closed_at is None:
        raise _http_error(status.HTTP_409_CONFLICT, "Only closed tickets can be reopened")
    setting = db.scalar(select(ReopenSetting).where(ReopenSetting.id == 1))
    if setting is None:
        raise _http_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "Reopen settings are not configured")
    now = utc_now()
    if ticket.resolved_at is None or now > ticket.resolved_at + timedelta(days=setting.reopen_window_days):
        raise _http_error(status.HTTP_409_CONFLICT, "The ticket reopening window has expired")
    if ticket.reopen_count >= setting.max_reopens:
        raise _http_error(status.HTTP_409_CONFLICT, "The ticket has reached its reopen limit")
    reason = reason.strip()
    if not reason:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "A non-empty reopen reason is required")

    prior_cycle = db.scalar(
        select(TicketSLACycle)
        .where(
            TicketSLACycle.ticket_id == ticket.id,
            TicketSLACycle.cycle_number == ticket.reopen_count + 1,
            TicketSLACycle.resolved_at.is_not(None),
        )
        .with_for_update()
    )
    if prior_cycle is None:
        raise _http_error(status.HTTP_409_CONFLICT, "Resolved SLA cycle history is unavailable")
    if ticket.sla is None:
        raise _http_error(status.HTTP_409_CONFLICT, "Ticket SLA state is unavailable")
    next_priority_hours = _get_tat_hours(db, ticket.priority)

    old_count = ticket.reopen_count
    old_resolved_at = ticket.resolved_at
    old_closed_at = ticket.closed_at
    ticket.previous_status = ticket.status
    ticket.status = TicketStatus.REOPENED
    ticket.closed_at = None
    ticket.resolved_at = None
    ticket.reopen_count += 1
    ticket.updated_at = now
    ticket.sla.started_at = now
    ticket.sla.due_at = now + timedelta(hours=next_priority_hours)
    ticket.sla.accumulated_pause_duration = 0
    ticket.sla.is_paused = False
    ticket.sla.paused_at = None
    ticket.sla.breached_at = None
    ticket.sla.escalated_at = None
    ticket.sla.last_calculated_at = now
    next_cycle_number = prior_cycle.cycle_number + 1
    new_cycle = TicketSLACycle(
        cycle_number=next_cycle_number,
        priority=ticket.priority,
        started_at=now,
        accumulated_pause_duration_seconds=0,
    )
    ticket.sla_cycles.append(new_cycle)
    _record_history(
        db,
        ticket,
        member,
        "SLA_RESTARTED",
        new_value={
            "cycle_number": next_cycle_number,
            "started_at": now.isoformat(),
            "due_at": ticket.sla.due_at.isoformat(),
            "priority": ticket.priority.value,
        },
        reason="New SLA cycle on ticket reopening",
    )
    _record_history(
        db,
        ticket,
        member,
        "TICKET_REOPENED",
        old_value={
            "status": TicketStatus.CLOSED.value,
            "reopen_count": old_count,
            "resolved_at": old_resolved_at.isoformat(),
            "closed_at": old_closed_at.isoformat(),
            "cycle_number": prior_cycle.cycle_number,
        },
        new_value={
            "status": TicketStatus.REOPENED.value,
            "reopen_count": ticket.reopen_count,
            "cycle_number": next_cycle_number,
        },
        reason=reason,
    )
    _notify_support_heads(db, ticket, "TICKET_REOPENED", f"Ticket {ticket.ticket_number} was reopened")
    db.flush()
    return _ticket_detail(ticket, show_internal=False)


def change_priority(db: Session, ticket_id: int, actor: User, priority: TicketPriority, reason: str) -> TicketDetail:
    _require_support(actor)
    ticket = _get_ticket(db, ticket_id, lock=True)
    if ticket.status in {TicketStatus.RESOLVED, TicketStatus.CLOSED}:
        raise _http_error(status.HTTP_409_CONFLICT, "Priority cannot change after resolution")
    reason = reason.strip()
    if not reason:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "A non-empty priority-change reason is required")
    if ticket.priority is priority:
        raise _http_error(status.HTTP_409_CONFLICT, "Ticket already has the requested priority")
    hours = _get_tat_hours(db, priority)
    cycle = _active_sla_cycle(db, ticket.id, lock=True)
    old_priority = ticket.priority
    ticket.priority = priority
    cycle.priority = priority
    ticket.updated_at = utc_now()
    if ticket.sla:
        # Active elapsed time ends at paused_at while paused, otherwise at now.
        # Subtracting prior paused seconds gives the elapsed active budget. The
        # remaining budget is the new TAT minus that elapsed time, which
        # simplifies to started_at + new TAT + accumulated pause seconds.
        # A current pause is extended only when a member reply resumes the SLA.
        ticket.sla.due_at = (
            ticket.sla.started_at
            + timedelta(hours=hours)
            + timedelta(seconds=ticket.sla.accumulated_pause_duration)
        )
    _record_history(db, ticket, actor, "PRIORITY_CHANGED", old_value={"priority": old_priority.value}, new_value={"priority": priority.value}, reason=reason)
    db.flush()
    return _ticket_detail(ticket, show_internal=True)


def dashboard(db: Session, actor: User) -> DashboardResponse:
    _require_support(actor)
    now = utc_now()
    open_statuses = Ticket.status.in_(OPEN_COUNT_STATUSES)
    open_count = db.scalar(select(func.count()).select_from(Ticket).where(open_statuses)) or 0
    unresolved_statuses = Ticket.status.in_(UNRESOLVED_STATUSES)
    overdue_count = db.scalar(
        select(func.count(Ticket.id))
        .select_from(Ticket)
        .join(TicketSLA)
        .where(unresolved_statuses, TicketSLA.is_paused.is_(False), TicketSLA.due_at <= now)
    ) or 0
    escalated_count = db.scalar(
        select(func.count()).select_from(Ticket).where(Ticket.status == TicketStatus.ESCALATED)
    ) or 0
    local_zone = ZoneInfo("Asia/Kolkata")
    local_now = now.astimezone(local_zone)
    local_start = datetime.combine(local_now.date(), time.min, tzinfo=local_zone)
    start_today = local_start.astimezone(timezone.utc)
    end_today = (local_start + timedelta(days=1)).astimezone(timezone.utc)
    resolved_today = db.scalar(
        select(func.count(Ticket.id))
        .select_from(Ticket)
        .where(
            Ticket.resolved_at >= start_today,
            Ticket.resolved_at < end_today,
        )
    ) or 0
    active_elapsed_seconds = (
        func.extract("epoch", TicketSLACycle.resolved_at - TicketSLACycle.started_at)
        - TicketSLACycle.accumulated_pause_duration_seconds
    )
    valid_completed_cycle = (
        TicketSLACycle.resolved_at.is_not(None)
        & (TicketSLACycle.resolved_at >= TicketSLACycle.started_at)
        & (
            TicketSLACycle.accumulated_pause_duration_seconds
            <= func.extract(
                "epoch", TicketSLACycle.resolved_at - TicketSLACycle.started_at
            )
        )
    )
    average_seconds = db.scalar(
        select(func.avg(active_elapsed_seconds)).where(valid_completed_cycle)
    )
    category_rows = db.execute(
        select(Ticket.category, func.count(Ticket.id))
        .where(open_statuses)
        .group_by(Ticket.category)
    ).all()
    category_counts = {category.value: 0 for category in TicketCategory}
    category_counts.update({category.value: count for category, count in category_rows})
    return DashboardResponse(
        open_ticket_count=open_count,
        overdue_unresolved_count=overdue_count,
        escalated_ticket_count=escalated_count,
        tickets_resolved_today=resolved_today,
        average_resolution_hours=(
            round(float(average_seconds) / 3600, 2)
            if average_seconds is not None
            else None
        ),
        tickets_by_category=category_counts,
    )
