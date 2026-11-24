from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import re

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.passwords import hash_password
from app.core.tokens import create_access_token
from app.services import ticket_settings, tickets as ticket_service
from app.models import (
    CategoryPrioritySetting,
    ConfigurationAudit,
    Notification,
    ReopenSetting,
    TATSetting,
    Ticket,
    TicketCategory,
    TicketHistory,
    TicketPriority,
    TicketSLA,
    TicketSLACycle,
    TicketStatus,
    User,
    UserRole,
)


_migration_path = Path(__file__).resolve().parents[1] / "alembic/versions/0002_sla_cycles_and_configuration_audit.py"
_migration_spec = importlib.util.spec_from_file_location("stage_d2_migration", _migration_path)
_migration = importlib.util.module_from_spec(_migration_spec)
_migration_spec.loader.exec_module(_migration)


def user(db, role, email):
    row = User(
        name=f"Test {role.value}",
        email=email,
        role=role,
        password_hash=hash_password("TestPassword!2026") if role is not UserRole.SYSTEM else None,
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def bearer(user_row):
    token, _ = create_access_token(user_row.id, user_row.role)
    return {"Authorization": f"Bearer {token}"}


def configure(db, actor):
    db.add_all(
        [
            CategoryPrioritySetting(
                category=TicketCategory.PAYMENT,
                default_priority=TicketPriority.HIGH,
                updated_by_id=actor.id,
            ),
            CategoryPrioritySetting(
                category=TicketCategory.PROFILE_CHANGE,
                default_priority=TicketPriority.MEDIUM,
                updated_by_id=actor.id,
            ),
            CategoryPrioritySetting(
                category=TicketCategory.SURVEY_ISSUE,
                default_priority=TicketPriority.HIGH,
                updated_by_id=actor.id,
            ),
            CategoryPrioritySetting(
                category=TicketCategory.ELIGIBILITY,
                default_priority=TicketPriority.MEDIUM,
                updated_by_id=actor.id,
            ),
            CategoryPrioritySetting(
                category=TicketCategory.OTHER,
                default_priority=TicketPriority.LOW,
                updated_by_id=actor.id,
            ),
            TATSetting(priority=TicketPriority.HIGH, resolution_hours=4, updated_by_id=actor.id),
            TATSetting(priority=TicketPriority.MEDIUM, resolution_hours=24, updated_by_id=actor.id),
            TATSetting(priority=TicketPriority.LOW, resolution_hours=48, updated_by_id=actor.id),
            ReopenSetting(id=1, reopen_window_days=7, max_reopens=3, updated_by_id=actor.id),
        ]
    )
    db.flush()


@pytest.fixture
def users(db_session):
    system = user(db_session, UserRole.SYSTEM, "system@concave.internal")
    configure(db_session, system)
    return {
        "system": system,
        "member": user(db_session, UserRole.MEMBER, "member-tickets@example.test"),
        "other_member": user(db_session, UserRole.MEMBER, "other-tickets@example.test"),
        "agent": user(db_session, UserRole.SUPPORT_AGENT, "agent-tickets@example.test"),
        "agent2": user(db_session, UserRole.SUPPORT_AGENT, "agent2-tickets@example.test"),
        "head": user(db_session, UserRole.SUPPORT_HEAD, "head-tickets@example.test"),
    }


def create_ticket(client, member, category="PAYMENT"):
    response = client.post(
        "/api/tickets",
        headers=bearer(member),
        json={"category": category, "subject": "Payment issue", "description": "Please help."},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_member_ticket_creation_numbering_isolation_and_history(client, db_session, users):
    blank = client.post(
        "/api/tickets",
        headers=bearer(users["member"]),
        json={"category": "PAYMENT", "subject": "   ", "description": "Help"},
    )
    assert blank.status_code == 422
    created = create_ticket(client, users["member"])
    assert re.fullmatch(r"TKT-\d{4,}", created["ticket_number"])
    assert created["priority"] == "HIGH"
    assert created["status"] == "OPEN"
    assert created["due_at"]
    assert [event["action"] for event in created["history"]] == ["TICKET_CREATED"]
    assert created["history"][0]["actor"]["id"] == users["member"].id

    own = client.get("/api/tickets", headers=bearer(users["member"]))
    other = client.get("/api/tickets", headers=bearer(users["other_member"]))
    assert own.status_code == other.status_code == 200
    assert own.json()["total"] == 1
    assert other.json()["total"] == 0
    assert client.get(
        "/api/tickets/{}".format(created["id"]), headers=bearer(users["other_member"])
    ).status_code == 404


def test_ticket_number_sequence_is_sequential_and_has_a_sql_default(client, db_session, users):
    first = create_ticket(client, users["member"])
    second = create_ticket(client, users["member"], category="OTHER")
    first_value = int(first["ticket_number"].removeprefix("TKT-"))
    second_value = int(second["ticket_number"].removeprefix("TKT-"))
    assert second_value == first_value + 1

    direct = db_session.execute(
        text(
            """INSERT INTO tickets (member_id, category, subject, description, priority)
            VALUES (:member_id, 'OTHER'::ticket_category, 'Direct SQL', 'Inserted directly', 'LOW'::ticket_priority)
            RETURNING ticket_number"""
        ),
        {"member_id": users["member"].id},
    ).scalar_one()
    assert direct == f"TKT-{second_value + 1:04d}"


def test_ticket_number_expands_past_four_digit_boundary(client, db_session, users):
    db_session.execute(text("SELECT setval('ticket_number_seq', 9998, true)"))
    four_digits = create_ticket(client, users["member"])
    five_digits = db_session.execute(
        text(
            """INSERT INTO tickets (member_id, category, subject, description, priority)
            VALUES (:member_id, 'OTHER'::ticket_category, 'Boundary SQL', 'Boundary insert', 'LOW'::ticket_priority)
            RETURNING ticket_number"""
        ),
        {"member_id": users["member"].id},
    ).scalar_one()

    assert four_digits["ticket_number"] == "TKT-9999"
    assert five_digits == "TKT-10000"
    assert four_digits["ticket_number"] != five_digits


def test_support_queue_roles_assignment_and_filters(client, users):
    created = create_ticket(client, users["member"])
    member_headers = bearer(users["member"])
    assert client.get("/api/support/tickets", headers=member_headers).status_code == 403
    for role_key in ("agent", "head"):
        response = client.get("/api/support/tickets?status=OPEN&category=PAYMENT", headers=bearer(users[role_key]))
        assert response.status_code == 200
        assert response.json()["total"] == 1
    searched = client.get(
        f"/api/support/tickets?search={created['ticket_number']}",
        headers=bearer(users["agent"]),
    )
    assert searched.status_code == 200
    assert searched.json()["items"][0]["id"] == created["id"]
    assigned = client.post(
        f"/api/support/tickets/{created['id']}/assign",
        headers=bearer(users["head"]),
        json={"assigned_to_id": users["agent"].id},
    )
    assert assigned.status_code == 200
    assert assigned.json()["assigned_to"]["id"] == users["agent"].id
    assert assigned.json()["history"][-1]["action"] == "TICKET_ASSIGNED"
    reassigned = client.post(
        f"/api/support/tickets/{created['id']}/assign",
        headers=bearer(users["agent"]),
        json={"assigned_to_id": users["agent2"].id},
    )
    assert reassigned.status_code == 200
    assert reassigned.json()["assigned_to"]["id"] == users["agent2"].id
    assignment_events = [event for event in reassigned.json()["history"] if event["action"] == "TICKET_ASSIGNED"]
    assert len(assignment_events) == 2
    assert assignment_events[-1]["old_value"] == {"assigned_to_id": users["agent"].id}
    assert assignment_events[-1]["new_value"] == {"assigned_to_id": users["agent2"].id}
    assert client.get(f"/api/support/tickets/{created['id']}", headers=bearer(users["head"])).json()["assigned_to"]["id"] == users["agent2"].id
    unassigned = client.post(
        f"/api/support/tickets/{created['id']}/assign",
        headers=bearer(users["head"]),
        json={"assigned_to_id": None},
    )
    assert unassigned.status_code == 200
    assert unassigned.json()["assigned_to"] is None
    unassignment_event = [event for event in unassigned.json()["history"] if event["action"] == "TICKET_ASSIGNED"][-1]
    assert unassignment_event["old_value"] == {"assigned_to_id": users["agent2"].id}
    assert unassignment_event["new_value"] == {"assigned_to_id": None}
    eligible = client.get("/api/support/agents", headers=bearer(users["head"]))
    assert eligible.status_code == 200
    assert {agent["id"] for agent in eligible.json()} == {users["agent"].id, users["agent2"].id}
    bad_assign = client.post(
        f"/api/support/tickets/{created['id']}/assign",
        headers=bearer(users["head"]),
        json={"assigned_to_id": users["member"].id},
    )
    assert bad_assign.status_code == 422


def test_assignment_rejects_unauthorized_missing_and_inactive_targets(client, db_session, users):
    created = create_ticket(client, users["member"])
    inactive = user(db_session, UserRole.SUPPORT_AGENT, "inactive-agent-tickets@example.test")
    inactive.is_active = False
    db_session.flush()

    unauthorized = client.post(
        f"/api/support/tickets/{created['id']}/assign",
        headers=bearer(users["member"]),
        json={"assigned_to_id": users["agent"].id},
    )
    assert unauthorized.status_code == 403
    missing_user = client.post(
        f"/api/support/tickets/{created['id']}/assign",
        headers=bearer(users["head"]),
        json={"assigned_to_id": 99999999},
    )
    assert missing_user.status_code == 422
    inactive_user = client.post(
        f"/api/support/tickets/{created['id']}/assign",
        headers=bearer(users["head"]),
        json={"assigned_to_id": inactive.id},
    )
    assert inactive_user.status_code == 422
    missing_ticket = client.post(
        "/api/support/tickets/99999999/assign",
        headers=bearer(users["head"]),
        json={"assigned_to_id": users["agent"].id},
    )
    assert missing_ticket.status_code == 404
    invalid_id = client.post(
        "/api/support/tickets/not-a-number/assign",
        headers=bearer(users["head"]),
        json={"assigned_to_id": users["agent"].id},
    )
    assert invalid_id.status_code == 422
    assert client.get("/api/support/agents", headers=bearer(users["member"])).status_code == 403
    eligible = client.get("/api/support/agents", headers=bearer(users["head"]))
    assert eligible.status_code == 200
    assert inactive.id not in {agent["id"] for agent in eligible.json()}
    assert eligible.json() == [
        {"id": users["agent"].id, "name": users["agent"].name, "email": users["agent"].email, "role": "SUPPORT_AGENT"},
        {"id": users["agent2"].id, "name": users["agent2"].name, "email": users["agent2"].email, "role": "SUPPORT_AGENT"},
    ]


def test_valid_transitions_resolution_confirmation_and_invalid_transition(client, users):
    ticket = create_ticket(client, users["member"])
    bad = client.patch(
        f"/api/support/tickets/{ticket['id']}/status",
        headers=bearer(users["agent"]),
        json={"status": "RESOLVED"},
    )
    assert bad.status_code == 409
    in_progress = client.patch(
        f"/api/support/tickets/{ticket['id']}/status",
        headers=bearer(users["agent"]),
        json={"status": "IN_PROGRESS"},
    )
    assert in_progress.status_code == 200
    resolved = client.patch(
        f"/api/support/tickets/{ticket['id']}/status",
        headers=bearer(users["agent"]),
        json={"status": "RESOLVED"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["resolved_at"]
    closed = client.post(
        f"/api/tickets/{ticket['id']}/confirm-resolution",
        headers=bearer(users["member"]),
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "CLOSED"
    assert closed.json()["closed_at"]
    actions = {item["action"] for item in closed.json()["history"]}
    assert {"TICKET_CREATED", "STATUS_CHANGED", "TICKET_RESOLVED", "TICKET_CLOSED"} <= actions


def test_manual_escalation_preserves_and_restores_prior_status(client, users):
    ticket = create_ticket(client, users["member"])
    missing_reason = client.patch(
        f"/api/support/tickets/{ticket['id']}/status",
        headers=bearer(users["agent"]),
        json={"status": "ESCALATED"},
    )
    assert missing_reason.status_code == 422
    escalated = client.patch(
        f"/api/support/tickets/{ticket['id']}/status",
        headers=bearer(users["agent"]),
        json={"status": "ESCALATED", "reason": "Requires specialist review"},
    )
    assert escalated.status_code == 200
    assert escalated.json()["status"] == "ESCALATED"
    escalation = next(
        event for event in escalated.json()["history"] if event["action"] == "TICKET_ESCALATED"
    )
    assert escalation["reason"] == "Requires specialist review"
    restored = client.patch(
        f"/api/support/tickets/{ticket['id']}/status",
        headers=bearer(users["agent"]),
        json={"status": "IN_PROGRESS"},
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "OPEN"


def test_reopen_window_limit_and_required_reason(client, db_session, users):
    ticket = create_ticket(client, users["member"])
    client.patch(f"/api/support/tickets/{ticket['id']}/status", headers=bearer(users["agent"]), json={"status": "IN_PROGRESS"})
    client.patch(f"/api/support/tickets/{ticket['id']}/status", headers=bearer(users["agent"]), json={"status": "RESOLVED"})
    client.post(f"/api/tickets/{ticket['id']}/confirm-resolution", headers=bearer(users["member"]))
    no_reason = client.post(f"/api/tickets/{ticket['id']}/reopen", headers=bearer(users["member"]), json={"reason": "  "})
    assert no_reason.status_code == 422
    reopened = client.post(f"/api/tickets/{ticket['id']}/reopen", headers=bearer(users["member"]), json={"reason": "Issue persists"})
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "REOPENED"
    assert reopened.json()["reopen_count"] == 1
    assert reopened.json()["history"][-1]["reason"] == "Issue persists"

    row = db_session.get(Ticket, ticket["id"])
    row.status = TicketStatus.CLOSED
    row.closed_at = datetime.now(timezone.utc) - timedelta(days=1)
    row.resolved_at = datetime.now(timezone.utc) - timedelta(days=8)
    db_session.flush()
    expired = client.post(f"/api/tickets/{ticket['id']}/reopen", headers=bearer(users["member"]), json={"reason": "Too late"})
    assert expired.status_code == 409


def test_reopen_attempt_limit_is_enforced(client, db_session, users):
    db_session.get(ReopenSetting, 1).max_reopens = 1
    ticket = create_ticket(client, users["member"])
    client.patch(f"/api/support/tickets/{ticket['id']}/status", headers=bearer(users["agent"]), json={"status": "IN_PROGRESS"})
    resolved = client.patch(f"/api/support/tickets/{ticket['id']}/status", headers=bearer(users["agent"]), json={"status": "RESOLVED"})
    assert resolved.json()["is_sla_paused"] is False
    client.post(f"/api/tickets/{ticket['id']}/confirm-resolution", headers=bearer(users["member"]))
    first_reopen = client.post(f"/api/tickets/{ticket['id']}/reopen", headers=bearer(users["member"]), json={"reason": "Still broken"})
    assert first_reopen.status_code == 200
    assert first_reopen.json()["is_sla_paused"] is False
    assert "SLA_RESTARTED" in {event["action"] for event in first_reopen.json()["history"]}
    client.patch(f"/api/support/tickets/{ticket['id']}/status", headers=bearer(users["agent"]), json={"status": "IN_PROGRESS"})
    client.patch(f"/api/support/tickets/{ticket['id']}/status", headers=bearer(users["agent"]), json={"status": "RESOLVED"})
    client.post(f"/api/tickets/{ticket['id']}/confirm-resolution", headers=bearer(users["member"]))
    over_limit = client.post(f"/api/tickets/{ticket['id']}/reopen", headers=bearer(users["member"]), json={"reason": "Still not fixed"})
    assert over_limit.status_code == 409


def test_reopen_window_boundary_is_inclusive_of_resolution_deadline(client, monkeypatch, users):
    base = datetime.now(timezone.utc)
    clock = [base]
    monkeypatch.setattr(ticket_service, "utc_now", lambda: clock[0])
    ticket = create_ticket(client, users["member"])
    client.patch(
        f"/api/support/tickets/{ticket['id']}/status",
        headers=bearer(users["agent"]),
        json={"status": "IN_PROGRESS"},
    )
    client.patch(
        f"/api/support/tickets/{ticket['id']}/status",
        headers=bearer(users["agent"]),
        json={"status": "RESOLVED"},
    )
    client.post(f"/api/tickets/{ticket['id']}/confirm-resolution", headers=bearer(users["member"]))

    clock[0] = base + timedelta(days=7, microseconds=-1)
    just_before = client.post(
        f"/api/tickets/{ticket['id']}/reopen",
        headers=bearer(users["member"]),
        json={"reason": "Still unresolved"},
    )
    assert just_before.status_code == 200

    clock[0] = base
    second = create_ticket(client, users["member"])
    client.patch(f"/api/support/tickets/{second['id']}/status", headers=bearer(users["agent"]), json={"status": "IN_PROGRESS"})
    client.patch(f"/api/support/tickets/{second['id']}/status", headers=bearer(users["agent"]), json={"status": "RESOLVED"})
    client.post(f"/api/tickets/{second['id']}/confirm-resolution", headers=bearer(users["member"]))
    clock[0] = base + timedelta(days=7)
    exactly_at = client.post(
        f"/api/tickets/{second['id']}/reopen",
        headers=bearer(users["member"]),
        json={"reason": "Still unresolved"},
    )
    assert exactly_at.status_code == 200

    clock[0] = base
    third = create_ticket(client, users["member"])
    client.patch(f"/api/support/tickets/{third['id']}/status", headers=bearer(users["agent"]), json={"status": "IN_PROGRESS"})
    client.patch(f"/api/support/tickets/{third['id']}/status", headers=bearer(users["agent"]), json={"status": "RESOLVED"})
    client.post(f"/api/tickets/{third['id']}/confirm-resolution", headers=bearer(users["member"]))
    clock[0] = base + timedelta(days=7, microseconds=1)
    just_after = client.post(
        f"/api/tickets/{third['id']}/reopen",
        headers=bearer(users["member"]),
        json={"reason": "Still unresolved"},
    )
    assert just_after.status_code == 409


def test_sla_cycles_finalize_pause_reopen_and_preserve_history(
    client, db_session, users, monkeypatch
):
    base = datetime.now(timezone.utc)
    clock = [base]
    monkeypatch.setattr(ticket_service, "utc_now", lambda: clock[0])
    ticket = create_ticket(client, users["member"])
    cycle_one = db_session.scalar(
        select(TicketSLACycle).where(TicketSLACycle.ticket_id == ticket["id"])
    )
    assert cycle_one.cycle_number == 1
    assert cycle_one.priority is TicketPriority.HIGH
    assert cycle_one.started_at == base

    client.patch(f"/api/support/tickets/{ticket['id']}/status", headers=bearer(users["agent"]), json={"status": "IN_PROGRESS"})
    clock[0] = base + timedelta(seconds=60)
    requested = client.post(
        f"/api/tickets/{ticket['id']}/replies",
        headers=bearer(users["agent"]),
        json={"message": "Please provide details.", "request_information": True},
    )
    assert requested.status_code == 200
    clock[0] = base + timedelta(seconds=120, microseconds=500000)
    resolved = client.patch(
        f"/api/support/tickets/{ticket['id']}/status",
        headers=bearer(users["agent"]),
        json={"status": "RESOLVED"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["is_sla_paused"] is False
    assert cycle_one.resolved_at == clock[0]
    assert cycle_one.accumulated_pause_duration_seconds == 60
    assert cycle_one.resolved_at == datetime.fromisoformat(
        resolved.json()["resolved_at"].replace("Z", "+00:00")
    )

    clock[0] = base + timedelta(seconds=130)
    closed = client.post(
        f"/api/tickets/{ticket['id']}/confirm-resolution",
        headers=bearer(users["member"]),
    )
    assert closed.status_code == 200
    assert cycle_one.closed_at == clock[0]
    resolved_today_before_reopen = client.get(
        "/api/support/dashboard", headers=bearer(users["head"])
    ).json()["tickets_resolved_today"]
    assert resolved_today_before_reopen == 1
    first_cycle_snapshot = (
        cycle_one.cycle_number,
        cycle_one.priority,
        cycle_one.started_at,
        cycle_one.resolved_at,
        cycle_one.closed_at,
        cycle_one.accumulated_pause_duration_seconds,
    )

    clock[0] = base + timedelta(seconds=140)
    reopened = client.post(
        f"/api/tickets/{ticket['id']}/reopen",
        headers=bearer(users["member"]),
        json={"reason": "Still broken"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["resolved_at"] is None
    assert reopened.json()["closed_at"] is None
    assert reopened.json()["is_sla_paused"] is False
    assert datetime.fromisoformat(reopened.json()["due_at"].replace("Z", "+00:00")) == (
        clock[0] + timedelta(hours=4)
    )
    reopen_event = next(event for event in reopened.json()["history"] if event["action"] == "TICKET_REOPENED")
    assert reopen_event["old_value"]["resolved_at"] == cycle_one.resolved_at.isoformat()
    assert reopen_event["old_value"]["closed_at"] == cycle_one.closed_at.isoformat()
    assert cycle_one.cycle_number == 1
    assert client.get(
        "/api/support/dashboard", headers=bearer(users["head"])
    ).json()["tickets_resolved_today"] == 0

    cycle_two = db_session.scalar(
        select(TicketSLACycle).where(
            TicketSLACycle.ticket_id == ticket["id"], TicketSLACycle.cycle_number == 2
        )
    )
    assert cycle_two is not None
    assert cycle_two.started_at == clock[0]
    assert cycle_two.priority is TicketPriority.HIGH
    assert cycle_two.accumulated_pause_duration_seconds == 0

    clock[0] = base + timedelta(seconds=150)
    client.patch(f"/api/support/tickets/{ticket['id']}/status", headers=bearer(users["agent"]), json={"status": "IN_PROGRESS"})
    clock[0] = base + timedelta(seconds=240)
    resolved_again = client.patch(
        f"/api/support/tickets/{ticket['id']}/status",
        headers=bearer(users["agent"]),
        json={"status": "RESOLVED"},
    )
    assert resolved_again.status_code == 200
    assert cycle_two.resolved_at == clock[0]
    assert client.get(
        "/api/support/dashboard", headers=bearer(users["head"])
    ).json()["tickets_resolved_today"] == 1
    assert first_cycle_snapshot == (
        cycle_one.cycle_number,
        cycle_one.priority,
        cycle_one.started_at,
        cycle_one.resolved_at,
        cycle_one.closed_at,
        cycle_one.accumulated_pause_duration_seconds,
    )

    clock[0] = base + timedelta(seconds=250)
    assert client.post(
        f"/api/tickets/{ticket['id']}/confirm-resolution",
        headers=bearer(users["member"]),
    ).status_code == 200
    cycle_two_snapshot = (
        cycle_two.cycle_number,
        cycle_two.priority,
        cycle_two.started_at,
        cycle_two.resolved_at,
        cycle_two.closed_at,
        cycle_two.accumulated_pause_duration_seconds,
    )
    clock[0] = base + timedelta(seconds=260)
    reopened_again = client.post(
        f"/api/tickets/{ticket['id']}/reopen",
        headers=bearer(users["member"]),
        json={"reason": "The issue returned"},
    )
    assert reopened_again.status_code == 200
    cycle_three = db_session.scalar(
        select(TicketSLACycle).where(
            TicketSLACycle.ticket_id == ticket["id"], TicketSLACycle.cycle_number == 3
        )
    )
    assert cycle_three is not None
    assert cycle_three.started_at == clock[0]
    clock[0] = base + timedelta(seconds=270)
    changed_priority = client.patch(
        f"/api/support/tickets/{ticket['id']}/priority",
        headers=bearer(users["agent"]),
        json={"priority": "LOW", "reason": "Reassessed in cycle three"},
    )
    assert changed_priority.status_code == 200
    assert cycle_three.priority is TicketPriority.LOW
    assert cycle_two_snapshot == (
        cycle_two.cycle_number,
        cycle_two.priority,
        cycle_two.started_at,
        cycle_two.resolved_at,
        cycle_two.closed_at,
        cycle_two.accumulated_pause_duration_seconds,
    )


def test_repeated_pause_cycles_accumulate_for_current_cycle(client, db_session, users, monkeypatch):
    base = datetime.now(timezone.utc)
    clock = [base]
    monkeypatch.setattr(ticket_service, "utc_now", lambda: clock[0])
    ticket = create_ticket(client, users["member"])
    client.patch(f"/api/support/tickets/{ticket['id']}/status", headers=bearer(users["agent"]), json={"status": "IN_PROGRESS"})
    for pause_at, resume_at in ((base + timedelta(seconds=10), base + timedelta(seconds=20, microseconds=900000)), (base + timedelta(seconds=30), base + timedelta(seconds=55, microseconds=900000))):
        clock[0] = pause_at
        assert client.post(
            f"/api/tickets/{ticket['id']}/replies",
            headers=bearer(users["agent"]),
            json={"message": "Need more information.", "request_information": True},
        ).status_code == 200
        clock[0] = resume_at
        assert client.post(
            f"/api/tickets/{ticket['id']}/replies",
            headers=bearer(users["member"]),
            json={"message": "Here is more information."},
        ).status_code == 200
    cycle = db_session.scalar(
        select(TicketSLACycle).where(TicketSLACycle.ticket_id == ticket["id"])
    )
    assert cycle.accumulated_pause_duration_seconds == 35
    assert db_session.get(Ticket, ticket["id"]).sla.accumulated_pause_duration == 35


def test_priority_override_authorization_reason_and_sla_time_preservation(client, db_session, users):
    ticket = create_ticket(client, users["member"], category="PROFILE_CHANGE")
    row = db_session.get(Ticket, ticket["id"])
    sla = row.sla
    sla.started_at = datetime.now(timezone.utc) - timedelta(hours=2)
    sla.accumulated_pause_duration = 600
    cycle = db_session.scalar(
        select(TicketSLACycle).where(TicketSLACycle.ticket_id == row.id)
    )
    cycle.started_at = sla.started_at
    old_due = sla.due_at
    member_response = client.patch(
        f"/api/support/tickets/{ticket['id']}/priority",
        headers=bearer(users["member"]),
        json={"priority": "HIGH", "reason": "Urgent"},
    )
    assert member_response.status_code == 403
    missing_reason = client.patch(
        f"/api/support/tickets/{ticket['id']}/priority",
        headers=bearer(users["agent"]),
        json={"priority": "HIGH", "reason": " "},
    )
    assert missing_reason.status_code == 422
    changed = client.patch(
        f"/api/support/tickets/{ticket['id']}/priority",
        headers=bearer(users["agent"]),
        json={"priority": "HIGH", "reason": "Customer impact"},
    )
    assert changed.status_code == 200
    assert changed.json()["priority"] == "HIGH"
    assert cycle.priority is TicketPriority.HIGH
    assert sla.started_at == row.sla.started_at
    assert sla.accumulated_pause_duration == 600
    assert sla.due_at == sla.started_at + timedelta(hours=4, seconds=600)
    assert sla.due_at < old_due
    event = next(e for e in changed.json()["history"] if e["action"] == "PRIORITY_CHANGED")
    assert event["reason"] == "Customer impact"


def test_priority_override_while_paused_preserves_pause_and_resume_deadline(
    client, db_session, users, monkeypatch
):
    base = datetime.now(timezone.utc)
    clock = [base]
    monkeypatch.setattr(ticket_service, "utc_now", lambda: clock[0])
    ticket = create_ticket(client, users["member"], category="PROFILE_CHANGE")
    client.patch(f"/api/support/tickets/{ticket['id']}/status", headers=bearer(users["agent"]), json={"status": "IN_PROGRESS"})
    clock[0] = base + timedelta(seconds=1)
    paused = client.post(
        f"/api/tickets/{ticket['id']}/replies",
        headers=bearer(users["agent"]),
        json={"message": "Please clarify.", "request_information": True},
    )
    assert paused.status_code == 200
    sla = db_session.get(Ticket, ticket["id"]).sla
    cycle = db_session.scalar(
        select(TicketSLACycle).where(TicketSLACycle.ticket_id == ticket["id"])
    )
    original_pause_at = sla.paused_at
    cycle_start = cycle.started_at

    clock[0] = base + timedelta(seconds=10)
    changed = client.patch(
        f"/api/support/tickets/{ticket['id']}/priority",
        headers=bearer(users["agent"]),
        json={"priority": "HIGH", "reason": "Higher impact"},
    )
    assert changed.status_code == 200
    assert sla.is_paused is True
    assert sla.paused_at == original_pause_at
    assert cycle.started_at == cycle_start
    assert cycle.priority is TicketPriority.HIGH
    expected_before_resume = cycle_start + timedelta(hours=4)
    assert sla.due_at == expected_before_resume

    clock[0] = base + timedelta(seconds=65, microseconds=900000)
    resumed = client.post(
        f"/api/tickets/{ticket['id']}/replies",
        headers=bearer(users["member"]),
        json={"message": "Clarification provided."},
    )
    assert resumed.status_code == 200
    assert sla.is_paused is False
    assert sla.paused_at is None
    assert sla.accumulated_pause_duration == 64
    assert cycle.accumulated_pause_duration_seconds == 64
    assert sla.due_at == expected_before_resume + timedelta(seconds=64)


def test_request_information_pauses_and_member_reply_resumes_sla_without_status_change(client, db_session, users):
    ticket = create_ticket(client, users["member"])
    client.patch(f"/api/support/tickets/{ticket['id']}/status", headers=bearer(users["agent"]), json={"status": "IN_PROGRESS"})
    request = client.post(
        f"/api/tickets/{ticket['id']}/replies",
        headers=bearer(users["agent"]),
        json={"message": "Please send the receipt.", "request_information": True},
    )
    assert request.status_code == 200
    assert request.json()["status"] == "IN_PROGRESS"
    assert request.json()["is_sla_paused"] is True
    sla = db_session.get(Ticket, ticket["id"]).sla
    paused_at = datetime.now(timezone.utc) - timedelta(seconds=61)
    sla.paused_at = paused_at
    before_due = sla.due_at
    db_session.flush()

    internal = client.post(
        f"/api/tickets/{ticket['id']}/replies",
        headers=bearer(users["agent"]),
        json={"message": "Internal note", "is_internal": True},
    )
    assert internal.status_code == 200
    member_view = client.get(f"/api/tickets/{ticket['id']}", headers=bearer(users["member"]))
    assert member_view.status_code == 200
    assert all(not reply["is_internal"] for reply in member_view.json()["replies"])
    assert all(
        not (
            event["action"] == "REPLY_ADDED"
            and event["new_value"]
            and event["new_value"].get("is_internal")
        )
        for event in member_view.json()["history"]
    )

    member_reply = client.post(
        f"/api/tickets/{ticket['id']}/replies",
        headers=bearer(users["member"]),
        json={"message": "Receipt attached."},
    )
    assert member_reply.status_code == 200
    assert member_reply.json()["status"] == "IN_PROGRESS"
    assert member_reply.json()["is_sla_paused"] is False
    assert 60 <= sla.accumulated_pause_duration <= 62
    assert sla.due_at == before_due + timedelta(seconds=sla.accumulated_pause_duration)
    actions = [event["action"] for event in member_reply.json()["history"]]
    assert "SLA_PAUSED" in actions and "SLA_RESUMED" in actions


@pytest.mark.parametrize(
    "workflow_status",
    [TicketStatus.OPEN, TicketStatus.REOPENED, TicketStatus.ESCALATED],
)
def test_information_request_preserves_other_nonterminal_status_and_resumes(
    client, db_session, users, monkeypatch, workflow_status
):
    ticket = create_ticket(client, users["member"])
    row = db_session.get(Ticket, ticket["id"])
    row.status = workflow_status
    if workflow_status is TicketStatus.ESCALATED:
        row.previous_status = TicketStatus.IN_PROGRESS
    db_session.flush()

    now = datetime.now(timezone.utc)
    clock = [now]
    monkeypatch.setattr(ticket_service, "utc_now", lambda: clock[0])
    original_due_at = row.sla.due_at
    requested = client.post(
        f"/api/tickets/{ticket['id']}/replies",
        headers=bearer(users["agent"]),
        json={"message": "Please clarify this issue.", "request_information": True},
    )
    assert requested.status_code == 200, requested.text
    assert requested.json()["status"] == workflow_status.value
    assert requested.json()["is_sla_paused"] is True
    assert row.status is workflow_status
    assert db_session.scalar(
        select(func.count(Notification.id)).where(
            Notification.ticket_id == ticket["id"],
            Notification.recipient_id == users["member"].id,
            Notification.type == "INFORMATION_REQUESTED",
        )
    ) == 1

    clock[0] = now + timedelta(seconds=61)
    resumed = client.post(
        f"/api/tickets/{ticket['id']}/replies",
        headers=bearer(users["member"]),
        json={"message": "Here is the requested clarification."},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == workflow_status.value
    assert resumed.json()["is_sla_paused"] is False
    assert row.status is workflow_status
    assert row.sla.due_at == original_due_at + timedelta(seconds=61)
    actions = [event["action"] for event in resumed.json()["history"]]
    assert "SLA_PAUSED" in actions and "SLA_RESUMED" in actions


@pytest.mark.parametrize("workflow_status", [TicketStatus.RESOLVED, TicketStatus.CLOSED])
def test_information_request_is_rejected_for_terminal_statuses(
    client, db_session, users, workflow_status
):
    ticket = create_ticket(client, users["member"])
    row = db_session.get(Ticket, ticket["id"])
    now = datetime.now(timezone.utc)
    cycle = db_session.scalar(
        select(TicketSLACycle).where(TicketSLACycle.ticket_id == row.id)
    )
    cycle.started_at = now - timedelta(seconds=2)
    cycle.resolved_at = now - timedelta(seconds=1)
    row.resolved_at = cycle.resolved_at
    row.status = workflow_status
    if workflow_status is TicketStatus.CLOSED:
        cycle.closed_at = now
        row.closed_at = now
    db_session.flush()

    response = client.post(
        f"/api/tickets/{ticket['id']}/replies",
        headers=bearer(users["agent"]),
        json={"message": "Please provide more information.", "request_information": True},
    )
    assert response.status_code == 409
    assert row.status is workflow_status
    assert row.sla.is_paused is False
    assert db_session.scalar(
        select(func.count(Notification.id)).where(
            Notification.ticket_id == ticket["id"],
            Notification.type == "INFORMATION_REQUESTED",
        )
    ) == 0


def test_dashboard_metrics_and_member_isolation(client, db_session, users):
    first = create_ticket(client, users["member"], category="PAYMENT")
    second = create_ticket(client, users["other_member"], category="OTHER")
    first_row = db_session.get(Ticket, first["id"])
    first_row.sla.started_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    first_row.sla.due_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    first_row.status = TicketStatus.IN_PROGRESS
    second_row = db_session.get(Ticket, second["id"])
    second_row.status = TicketStatus.RESOLVED
    second_row.resolved_at = datetime.now(timezone.utc)
    db_session.add(TicketHistory(ticket_id=second_row.id, actor_id=users["agent"].id, action="TICKET_RESOLVED"))
    second_cycle = db_session.scalar(
        select(TicketSLACycle).where(TicketSLACycle.ticket_id == second_row.id)
    )
    second_cycle.resolved_at = second_row.resolved_at
    expired_escalated = create_ticket(client, users["member"], category="OTHER")
    expired_escalated_row = db_session.get(Ticket, expired_escalated["id"])
    expired_escalated_row.status = TicketStatus.ESCALATED
    expired_escalated_row.sla.started_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    expired_escalated_row.sla.due_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    future_escalated = create_ticket(client, users["member"], category="OTHER")
    future_escalated_row = db_session.get(Ticket, future_escalated["id"])
    future_escalated_row.status = TicketStatus.ESCALATED
    future_escalated_row.sla.started_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    future_escalated_row.sla.due_at = datetime.now(timezone.utc) + timedelta(hours=1)
    db_session.flush()

    response = client.get("/api/support/dashboard", headers=bearer(users["head"]))
    assert response.status_code == 200
    data = response.json()
    assert data["open_ticket_count"] == 1
    assert data["overdue_unresolved_count"] == 2
    assert data["escalated_ticket_count"] == 2
    assert data["tickets_resolved_today"] == 1
    assert data["average_resolution_hours"] is not None
    assert data["tickets_by_category"] == {
        "PAYMENT": 1,
        "PROFILE_CHANGE": 0,
        "SURVEY_ISSUE": 0,
        "ELIGIBILITY": 0,
        "OTHER": 0,
    }
    overdue_queue = client.get(
        "/api/support/tickets?overdue=true", headers=bearer(users["agent"])
    )
    assert overdue_queue.status_code == 200
    assert overdue_queue.json()["total"] == 2
    assert client.get("/api/support/dashboard", headers=bearer(users["member"])).status_code == 403


def test_dashboard_average_resolution_time_excludes_recorded_sla_pauses(client, db_session, users):
    ticket = create_ticket(client, users["member"])
    row = db_session.get(Ticket, ticket["id"])
    cycle = db_session.scalar(
        select(TicketSLACycle).where(TicketSLACycle.ticket_id == row.id)
    )
    cycle.resolved_at = datetime.now(timezone.utc)
    cycle.started_at = cycle.resolved_at - timedelta(seconds=5400)
    cycle.accumulated_pause_duration_seconds = 900
    db_session.flush()
    response = client.get("/api/support/dashboard", headers=bearer(users["head"]))
    assert response.status_code == 200
    # 5,400 elapsed seconds less a 900-second pause is 4,500 active seconds.
    assert response.json()["average_resolution_hours"] == 1.25


def test_dashboard_average_is_none_without_completed_cycles(client, users):
    create_ticket(client, users["member"])
    response = client.get("/api/support/dashboard", headers=bearer(users["head"]))
    assert response.status_code == 200
    assert response.json()["average_resolution_hours"] is None


def test_dashboard_average_rounds_completed_cycles_and_ignores_unresolved_cycles(
    client, db_session, users
):
    first = create_ticket(client, users["member"])
    second = create_ticket(client, users["member"])
    unresolved = create_ticket(client, users["member"])
    first_cycle, second_cycle, unresolved_cycle = [
        db_session.scalar(
            select(TicketSLACycle).where(TicketSLACycle.ticket_id == item["id"])
        )
        for item in (first, second, unresolved)
    ]
    now = datetime.now(timezone.utc)
    first_cycle.started_at = now - timedelta(seconds=4500)
    first_cycle.resolved_at = now
    second_cycle.started_at = now - timedelta(seconds=8100)
    second_cycle.resolved_at = now
    unresolved_cycle.started_at = now - timedelta(days=30)
    unresolved_cycle.resolved_at = None
    db_session.flush()
    response = client.get("/api/support/dashboard", headers=bearer(users["head"]))
    assert response.status_code == 200
    assert response.json()["average_resolution_hours"] == 1.75


def test_resolved_today_uses_kolkata_calendar_boundaries_and_cycle_history(
    client, db_session, users, monkeypatch
):
    fixed_now = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(ticket_service, "utc_now", lambda: fixed_now)
    tickets = [create_ticket(client, users["member"]) for _ in range(5)]
    rows = [db_session.get(Ticket, row["id"]) for row in tickets]
    # 00:00 and 23:59:59.999999 in Asia/Kolkata are included.
    rows[0].resolved_at = datetime(2026, 2, 28, 18, 30, tzinfo=timezone.utc)
    rows[1].resolved_at = datetime(2026, 3, 1, 18, 29, 59, 999999, tzinfo=timezone.utc)
    # Immediately before the local day and at the exclusive next-day boundary are excluded.
    rows[2].resolved_at = datetime(2026, 2, 28, 18, 29, 59, 999999, tzinfo=timezone.utc)
    rows[3].resolved_at = datetime(2026, 3, 1, 18, 30, tzinfo=timezone.utc)
    assert rows[4].resolved_at is None
    db_session.flush()
    result = client.get("/api/support/dashboard", headers=bearer(users["head"]))
    assert result.status_code == 200
    assert result.json()["tickets_resolved_today"] == 2


def test_service_layer_role_guards_configuration_and_ticket_actions(client, db_session, users):
    with pytest.raises(HTTPException) as member_queue:
        ticket_service.list_support_tickets(db_session, users["member"], 1, 20)
    assert member_queue.value.status_code == 403
    with pytest.raises(HTTPException) as agent_settings:
        ticket_settings.update_tat(db_session, users["agent"], TicketPriority.HIGH, 6)
    assert agent_settings.value.status_code == 403
    with pytest.raises(HTTPException) as system_dashboard:
        ticket_service.dashboard(db_session, users["system"])
    assert system_dashboard.value.status_code == 403
    ticket = create_ticket(client, users["member"])
    with pytest.raises(HTTPException) as system_ticket:
        ticket_service.read_ticket(db_session, ticket["id"], users["system"])
    assert system_ticket.value.status_code == 403


def test_sla_cycle_constraints_reject_duplicates_negative_pauses_and_ticket_deletion(
    client, db_session, users
):
    ticket_data = create_ticket(client, users["member"])
    ticket_id = ticket_data["id"]
    cycle = db_session.scalar(
        select(TicketSLACycle).where(TicketSLACycle.ticket_id == ticket_id)
    )
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                TicketSLACycle(
                    ticket_id=ticket_id,
                    cycle_number=1,
                    priority=TicketPriority.HIGH,
                    started_at=cycle.started_at,
                    resolved_at=cycle.started_at,
                )
            )
            db_session.flush()
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                TicketSLACycle(
                    ticket_id=ticket_id,
                    cycle_number=2,
                    priority=TicketPriority.HIGH,
                    started_at=cycle.started_at,
                    accumulated_pause_duration_seconds=-1,
                )
            )
            db_session.flush()
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.execute(text("DELETE FROM tickets WHERE id = :id"), {"id": ticket_id})
            db_session.flush()


def test_sla_cycle_constraints_reject_invalid_resolution_and_pause_duration(
    client, db_session, users
):
    ticket = create_ticket(client, users["member"])
    cycle = db_session.scalar(
        select(TicketSLACycle).where(TicketSLACycle.ticket_id == ticket["id"])
    )
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            cycle.resolved_at = cycle.started_at - timedelta(seconds=1)
            db_session.flush()
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            cycle.accumulated_pause_duration_seconds = 11
            cycle.resolved_at = cycle.started_at + timedelta(seconds=10)
            db_session.flush()


def test_migration_refuses_legacy_tickets_without_sla_rows(db_session, users):
    orphaned = Ticket(
        member_id=users["member"].id,
        category=TicketCategory.OTHER,
        subject="Legacy ticket without SLA",
        description="Migration guard test",
        priority=TicketPriority.LOW,
    )
    db_session.add(orphaned)
    db_session.flush()
    with pytest.raises(RuntimeError, match="no ticket_sla rows"):
        _migration.validate_existing_ticket_slas(db_session.connection())


def test_missing_sla_is_reported_without_fabricating_a_deadline():
    with pytest.raises(HTTPException) as error:
        ticket_service._ticket_summary(Ticket())
    assert error.value.status_code == 409
    assert "restore verified SLA state" in error.value.detail


def test_configuration_audit_insert_succeeds_but_update_and_delete_are_blocked(
    db_session, users
):
    audit = ConfigurationAudit(
        actor_id=users["head"].id,
        setting_type="TAT",
        setting_key="HIGH",
        old_value={"resolution_hours": 4},
        new_value={"resolution_hours": 8},
    )
    db_session.add(audit)
    db_session.flush()
    audit_id = audit.id
    with pytest.raises(DBAPIError):
        with db_session.begin_nested():
            db_session.execute(
                text("UPDATE configuration_audit SET setting_key = 'LOW' WHERE id = :id"),
                {"id": audit_id},
            )
    with pytest.raises(DBAPIError):
        with db_session.begin_nested():
            db_session.execute(
                text("DELETE FROM configuration_audit WHERE id = :id"),
                {"id": audit_id},
            )
    assert db_session.get(ConfigurationAudit, audit_id) is not None


def test_configuration_audit_truncate_is_blocked(db_session, users):
    audit = ConfigurationAudit(
        actor_id=users["head"].id,
        setting_type="TAT",
        setting_key="HIGH",
        old_value={"resolution_hours": 4},
        new_value={"resolution_hours": 8},
    )
    db_session.add(audit)
    db_session.flush()

    with pytest.raises(DBAPIError):
        with db_session.begin_nested():
            db_session.execute(text("TRUNCATE TABLE configuration_audit"))

    assert db_session.get(ConfigurationAudit, audit.id) is not None


def test_ticket_and_sla_must_exist_together_at_transaction_end(
    client, db_session, users
):
    created = create_ticket(client, users["member"])
    assert db_session.scalar(
        select(TicketSLA.id).where(TicketSLA.ticket_id == created["id"])
    ) is not None

    with pytest.raises(DBAPIError):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    """INSERT INTO tickets (member_id, category, subject, description, priority)
                    VALUES (:member_id, 'OTHER'::ticket_category, 'No SLA', 'Direct insert', 'LOW'::ticket_priority)"""
                ),
                {"member_id": users["member"].id},
            )
            db_session.execute(text("SET CONSTRAINTS trg_tickets_require_sla IMMEDIATE"))

    with pytest.raises(DBAPIError):
        with db_session.begin_nested():
            db_session.execute(
                text("DELETE FROM ticket_sla WHERE ticket_id = :ticket_id"),
                {"ticket_id": created["id"]},
            )
            db_session.execute(
                text("SET CONSTRAINTS trg_ticket_sla_delete_requires_parent_sla IMMEDIATE")
            )

    assert db_session.scalar(
        select(TicketSLA.id).where(TicketSLA.ticket_id == created["id"])
    ) is not None


def test_truncating_ticket_sla_is_rejected_and_preserves_ticket_data(
    client, db_session, users
):
    created = create_ticket(client, users["member"])
    ticket_id = created["id"]
    sla_before = db_session.scalar(
        select(TicketSLA).where(TicketSLA.ticket_id == ticket_id)
    )
    original_sla_id = sla_before.id
    original_due_at = sla_before.due_at

    with pytest.raises(DBAPIError):
        with db_session.begin_nested():
            db_session.execute(text("TRUNCATE TABLE ticket_sla"))

    assert db_session.get(Ticket, ticket_id) is not None
    sla_after = db_session.scalar(
        select(TicketSLA).where(TicketSLA.ticket_id == ticket_id)
    )
    assert sla_after is not None
    assert sla_after.id == original_sla_id
    assert sla_after.due_at == original_due_at


def test_failed_configuration_update_rolls_back_setting_and_audit(
    db_session, users, monkeypatch
):
    row = db_session.scalar(
        select(TATSetting).where(TATSetting.priority == TicketPriority.HIGH)
    )
    old_hours = row.resolution_hours
    monkeypatch.setattr(
        ticket_settings,
        "read_settings",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("response failure")),
    )
    with pytest.raises(RuntimeError, match="response failure"):
        with db_session.begin_nested():
            ticket_settings.update_tat(db_session, users["head"], TicketPriority.HIGH, old_hours + 1)
    db_session.refresh(row)
    assert row.resolution_hours == old_hours
    assert db_session.scalar(
        select(func.count(ConfigurationAudit.id)).where(ConfigurationAudit.setting_type == "TAT")
    ) == 0


def test_migration_backfill_validation_accepts_ticket_with_sla(db_session, users):
    ticket = Ticket(
        member_id=users["member"].id,
        category=TicketCategory.OTHER,
        subject="Legacy ticket with SLA",
        description="Migration validation test",
        priority=TicketPriority.LOW,
    )
    db_session.add(ticket)
    db_session.flush()
    db_session.add(
        TicketSLA(
            ticket_id=ticket.id,
            started_at=datetime.now(timezone.utc),
            due_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    db_session.flush()
    _migration.validate_existing_ticket_slas(db_session.connection())


def test_configuration_changes_are_audited_with_old_and_new_values(client, db_session, users):
    before_tat = db_session.scalar(
        select(TATSetting).where(TATSetting.priority == TicketPriority.HIGH)
    )
    old_hours = before_tat.resolution_hours
    existing_ticket = create_ticket(client, users["member"])
    previous_due = db_session.get(Ticket, existing_ticket["id"]).sla.due_at
    response = client.patch(
        "/api/support/settings/tat/HIGH",
        headers=bearer(users["head"]),
        json={"resolution_hours": 8},
    )
    assert response.status_code == 200
    audit = db_session.scalar(
        select(ConfigurationAudit).where(ConfigurationAudit.setting_type == "TAT")
    )
    assert audit is not None
    assert audit.actor_id == users["head"].id
    assert audit.setting_key == "HIGH"
    assert audit.old_value == {"resolution_hours": old_hours}
    assert audit.new_value == {"resolution_hours": 8}
    assert db_session.get(Ticket, existing_ticket["id"]).sla.due_at == previous_due
    ticket_settings.update_category_priority(
        db_session, users["head"], TicketCategory.PAYMENT, TicketPriority.MEDIUM
    )
    ticket_settings.update_reopen_settings(db_session, users["head"], days=5, max_reopens=2)
    db_session.flush()
    assert set(
        db_session.scalars(select(ConfigurationAudit.setting_type)).all()
    ) == {"TAT", "CATEGORY_PRIORITY", "REOPEN"}


def test_notification_recipients_and_internal_reply_privacy(client, db_session, users):
    ticket = create_ticket(client, users["member"])
    assert db_session.scalar(
        select(func.count(Notification.id)).where(
            Notification.type == "TICKET_CREATED",
            Notification.recipient_id == users["head"].id,
        )
    ) == 1
    client.post(
        f"/api/tickets/{ticket['id']}/replies",
        headers=bearer(users["agent"]),
        json={"message": "Private investigation note", "is_internal": True},
    )
    assert db_session.scalar(
        select(func.count(Notification.id)).where(
            Notification.type == "SUPPORT_REPLIED",
            Notification.recipient_id == users["member"].id,
        )
    ) == 0
    client.post(
        f"/api/tickets/{ticket['id']}/replies",
        headers=bearer(users["agent"]),
        json={"message": "We are reviewing this."},
    )
    assert db_session.scalar(
        select(func.count(Notification.id)).where(
            Notification.type == "SUPPORT_REPLIED",
            Notification.recipient_id == users["member"].id,
        )
    ) == 1


def test_failed_ticket_operation_rolls_back_all_rows(db_session, users, monkeypatch):
    def fail_notification(*args, **kwargs):
        raise RuntimeError("notification persistence failed")

    monkeypatch.setattr(ticket_service, "_notify_support_heads", fail_notification)
    with pytest.raises(RuntimeError):
        with db_session.begin_nested():
            ticket_service.create_ticket(
                db_session,
                users["member"],
                TicketCategory.PAYMENT,
                "Atomic ticket",
                "Transaction test",
            )
    assert db_session.scalar(select(func.count(Ticket.id))) == 0
    assert db_session.scalar(select(func.count(TicketSLACycle.id))) == 0
    assert db_session.scalar(select(func.count(TicketHistory.id))) == 0


def test_support_head_only_can_manage_configuration(client, users):
    forbidden = client.patch(
        "/api/support/settings/tat/HIGH",
        headers=bearer(users["agent"]),
        json={"resolution_hours": 8},
    )
    assert forbidden.status_code == 403
    allowed = client.patch(
        "/api/support/settings/tat/HIGH",
        headers=bearer(users["head"]),
        json={"resolution_hours": 8},
    )
    assert allowed.status_code == 200
    assert allowed.json()["tat_hours"]["HIGH"] == 8
