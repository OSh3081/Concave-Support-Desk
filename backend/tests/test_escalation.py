from concurrent.futures import ThreadPoolExecutor
import asyncio
from contextlib import AsyncExitStack
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

import app.main as main_module
from app.db.session import SessionLocal, engine
from app.main import lifespan
from app.models import (
    Notification,
    Ticket,
    TicketCategory,
    TicketHistory,
    TicketPriority,
    TicketSLA,
    TicketStatus,
    User,
    UserRole,
)
from app.services import escalation as escalation_service
from app.services.escalation import AUTOMATIC_ESCALATION_REASON


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def actors(db_session):
    suffix = uuid4().hex
    system = User(
        name="System",
        email="system@concave.internal",
        role=UserRole.SYSTEM,
        is_active=True,
        password_hash=None,
    )
    head = User(
        name="Active Head",
        email=f"head-{suffix}@example.test",
        role=UserRole.SUPPORT_HEAD,
        is_active=True,
    )
    inactive_head = User(
        name="Inactive Head",
        email=f"inactive-head-{suffix}@example.test",
        role=UserRole.SUPPORT_HEAD,
        is_active=False,
    )
    member = User(
        name="Member",
        email=f"member-{suffix}@example.test",
        role=UserRole.MEMBER,
        is_active=True,
    )
    db_session.add_all([system, head, inactive_head, member])
    db_session.flush()
    return {"system": system, "head": head, "inactive_head": inactive_head, "member": member}


def make_ticket(db, member, status, due_at, paused=False, resolved_at=None, closed_at=None):
    ticket = Ticket(
        member_id=member.id,
        category=TicketCategory.OTHER,
        subject=f"Escalation test {uuid4().hex}",
        description="Automatic escalation test ticket",
        priority=TicketPriority.LOW,
        status=status,
        resolved_at=resolved_at,
        closed_at=closed_at,
    )
    db.add(ticket)
    db.flush()
    db.add(
        TicketSLA(
            ticket_id=ticket.id,
            started_at=due_at - timedelta(hours=1),
            due_at=due_at,
            is_paused=paused,
            paused_at=due_at if paused else None,
        )
    )
    db.flush()
    return ticket


def test_expired_unpaused_ticket_escalates_with_system_history_and_head_notifications(
    db_session, actors
):
    now = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
    ticket = make_ticket(
        db_session,
        actors["member"],
        TicketStatus.IN_PROGRESS,
        now - timedelta(seconds=1),
    )
    factory = sessionmaker(
        bind=db_session.connection(),
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    assert escalation_service.escalate_overdue_tickets(factory, now) == 1
    db_session.refresh(ticket)
    db_session.refresh(ticket.sla)
    assert ticket.status is TicketStatus.ESCALATED
    assert ticket.previous_status is TicketStatus.IN_PROGRESS
    assert ticket.sla.escalated_at == now
    events = db_session.scalars(
        select(TicketHistory).where(TicketHistory.ticket_id == ticket.id)
    ).all()
    escalation = next(event for event in events if event.action == "TICKET_ESCALATED")
    assert escalation.actor_id == actors["system"].id
    assert escalation.reason == AUTOMATIC_ESCALATION_REASON
    assert any(event.action == "STATUS_CHANGED" for event in events)
    notifications = db_session.scalars(
        select(Notification).where(Notification.ticket_id == ticket.id)
    ).all()
    assert len(notifications) == 1
    assert notifications[0].recipient_id == actors["head"].id
    assert notifications[0].type == "TICKET_ESCALATED"
    assert actors["inactive_head"].id not in {n.recipient_id for n in notifications}


def test_paused_future_already_escalated_resolved_and_closed_tickets_are_ignored(
    db_session, actors
):
    now = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
    expired = now - timedelta(minutes=1)
    future = now + timedelta(minutes=1)
    cases = [
        (TicketStatus.IN_PROGRESS, expired, True, None, None),
        (TicketStatus.OPEN, future, False, None, None),
        (TicketStatus.ESCALATED, expired, False, None, None),
        (TicketStatus.RESOLVED, expired, False, now - timedelta(seconds=2), None),
        (
            TicketStatus.CLOSED,
            expired,
            False,
            now - timedelta(seconds=2),
            now - timedelta(seconds=1),
        ),
    ]
    tickets = [
        make_ticket(db_session, actors["member"], *case)
        for case in cases
    ]
    factory = sessionmaker(
        bind=db_session.connection(),
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    assert escalation_service.escalate_overdue_tickets(factory, now) == 0
    assert all(ticket.status is status for ticket, (status, *_rest) in zip(tickets, cases))
    assert db_session.scalar(select(func.count(TicketHistory.id))) == 0
    assert db_session.scalar(select(func.count(Notification.id))) == 0


def test_repeated_runs_are_idempotent(db_session, actors):
    now = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
    ticket = make_ticket(
        db_session,
        actors["member"],
        TicketStatus.OPEN,
        now - timedelta(minutes=2),
    )
    factory = sessionmaker(
        bind=db_session.connection(),
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    assert escalation_service.escalate_overdue_tickets(factory, now) == 1
    assert escalation_service.escalate_overdue_tickets(factory, now) == 0
    assert db_session.scalar(
        select(func.count(TicketHistory.id)).where(
            TicketHistory.ticket_id == ticket.id,
            TicketHistory.action == "TICKET_ESCALATED",
        )
    ) == 1
    assert db_session.scalar(
        select(func.count(Notification.id)).where(
            Notification.ticket_id == ticket.id,
            Notification.type == "TICKET_ESCALATED",
        )
    ) == 1


def test_ticket_failure_does_not_prevent_other_due_tickets(db_session, actors, monkeypatch):
    now = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
    first = make_ticket(
        db_session, actors["member"], TicketStatus.OPEN, now - timedelta(minutes=3)
    )
    second = make_ticket(
        db_session, actors["member"], TicketStatus.REOPENED, now - timedelta(minutes=2)
    )
    original_apply = escalation_service._apply_escalation

    def fail_first(session, ticket, actor, reason, timestamp):
        if ticket.id == first.id:
            raise RuntimeError("simulated per-ticket failure")
        original_apply(session, ticket, actor, reason, timestamp)

    monkeypatch.setattr(escalation_service, "_apply_escalation", fail_first)
    factory = sessionmaker(
        bind=db_session.connection(),
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    assert escalation_service.escalate_overdue_tickets(factory, now) == 1
    db_session.refresh(first)
    db_session.refresh(second)
    assert first.status is TicketStatus.OPEN
    assert second.status is TicketStatus.ESCALATED


def test_two_concurrent_executions_escalate_a_ticket_once():
    now = datetime.now(timezone.utc)
    suffix = uuid4().hex
    ids = {}
    try:
        with SessionLocal.begin() as session:
            system = User(
                name="Concurrent System",
                email="system@concave.internal",
                role=UserRole.SYSTEM,
                is_active=True,
                password_hash=None,
            )
            head = User(
                name="Concurrent Head",
                email=f"concurrent-head-{suffix}@example.test",
                role=UserRole.SUPPORT_HEAD,
                is_active=True,
            )
            member = User(
                name="Concurrent Member",
                email=f"concurrent-member-{suffix}@example.test",
                role=UserRole.MEMBER,
                is_active=True,
            )
            session.add_all([system, head, member])
            session.flush()
            ticket = make_ticket(
                session,
                member,
                TicketStatus.IN_PROGRESS,
                now - timedelta(minutes=1),
            )
            ids.update(system=system.id, head=head.id, member=member.id, ticket=ticket.id)

        start_barrier = Barrier(2)

        def run_scheduler():
            start_barrier.wait(timeout=5)
            return escalation_service.escalate_overdue_tickets(SessionLocal, now)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: run_scheduler(), range(2)))

        with SessionLocal() as session:
            ticket = session.get(Ticket, ids["ticket"])
            assert ticket.status is TicketStatus.ESCALATED
            assert session.scalar(
                select(func.count(TicketHistory.id)).where(
                    TicketHistory.ticket_id == ticket.id,
                    TicketHistory.action == "TICKET_ESCALATED",
                )
            ) == 1
            assert session.scalar(
                select(func.count(Notification.id)).where(
                    Notification.ticket_id == ticket.id,
                    Notification.type == "TICKET_ESCALATED",
                )
            ) == 1
        assert sum(results) == 1
    finally:
        if ids:
            with SessionLocal.begin() as session:
                session.query(TicketHistory).filter(
                    TicketHistory.ticket_id == ids["ticket"]
                ).delete(synchronize_session=False)
                session.query(Notification).filter(
                    Notification.ticket_id == ids["ticket"]
                ).delete(synchronize_session=False)
                session.query(TicketSLA).filter(
                    TicketSLA.ticket_id == ids["ticket"]
                ).delete(synchronize_session=False)
                session.query(Ticket).filter(Ticket.id == ids["ticket"]).delete(
                    synchronize_session=False
                )
                session.query(User).filter(User.id.in_([ids["system"], ids["head"], ids["member"]])).delete(
                    synchronize_session=False
                )


def test_overlapping_application_lifespans_share_one_scheduler(monkeypatch):
    created = []

    class FakeScheduler:
        def __init__(self, **kwargs):
            self.running = False
            self.start_count = 0
            self.shutdown_count = 0
            created.append(self)

        def add_job(self, *args, **kwargs):
            self.job = (args, kwargs)

        def start(self):
            self.running = True
            self.start_count += 1

        def shutdown(self, wait):
            self.running = False
            self.shutdown_count += 1

    monkeypatch.setattr(
        main_module,
        "settings",
        main_module.settings.model_copy(update={"app_env": "development"}),
    )
    monkeypatch.setattr(main_module, "BackgroundScheduler", FakeScheduler)
    monkeypatch.setattr(main_module, "_sla_scheduler", None)
    monkeypatch.setattr(main_module, "_sla_scheduler_lifespan_users", 0)

    async def exercise_lifespans():
        outer_app, inner_app = FastAPI(), FastAPI()
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(lifespan(outer_app))
            await stack.enter_async_context(lifespan(inner_app))
            assert outer_app.state.sla_scheduler is inner_app.state.sla_scheduler
            assert len(created) == 1
            assert created[0].start_count == 1
            assert created[0].shutdown_count == 0
        assert created[0].shutdown_count == 1

    asyncio.run(exercise_lifespans())
