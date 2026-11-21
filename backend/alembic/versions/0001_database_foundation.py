"""Create the Phase 2 database foundation.

Revision ID: 0001_database_foundation
Revises:
Create Date: 2026-11-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_database_foundation"
down_revision = None
branch_labels = None
depends_on = None


user_role = postgresql.ENUM("MEMBER", "SUPPORT_AGENT", "SUPPORT_HEAD", "SYSTEM", name="user_role", create_type=False)
ticket_category = postgresql.ENUM("PAYMENT", "PROFILE_CHANGE", "SURVEY_ISSUE", "ELIGIBILITY", "OTHER", name="ticket_category", create_type=False)
ticket_priority = postgresql.ENUM("LOW", "MEDIUM", "HIGH", name="ticket_priority", create_type=False)
ticket_status = postgresql.ENUM("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED", "REOPENED", "ESCALATED", name="ticket_status", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE TYPE user_role AS ENUM ('MEMBER', 'SUPPORT_AGENT', 'SUPPORT_HEAD', 'SYSTEM')")
    op.execute("CREATE TYPE ticket_category AS ENUM ('PAYMENT', 'PROFILE_CHANGE', 'SURVEY_ISSUE', 'ELIGIBILITY', 'OTHER')")
    op.execute("CREATE TYPE ticket_priority AS ENUM ('LOW', 'MEDIUM', 'HIGH')")
    op.execute("CREATE TYPE ticket_status AS ENUM ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED', 'REOPENED', 'ESCALATED')")
    op.execute(sa.schema.CreateSequence(sa.Sequence("ticket_number_seq")))
    op.execute("""
        CREATE FUNCTION next_ticket_number() RETURNS text
        LANGUAGE plpgsql VOLATILE AS $$
        DECLARE allocated_number bigint;
        BEGIN
            allocated_number := nextval('ticket_number_seq');
            RETURN 'TKT-' || lpad(
                allocated_number::text,
                GREATEST(4, length(allocated_number::text)),
                '0'
            );
        END;
        $$
    """)

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.CheckConstraint("role <> 'SYSTEM' OR password_hash IS NULL", name="system_password_absent"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index(
        "uq_users_single_system_role",
        "users",
        ["role"],
        unique=True,
        postgresql_where=sa.text("role = 'SYSTEM'::user_role"),
    )
    op.create_table(
        "tickets",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("ticket_number", sa.String(20), server_default=sa.text("next_ticket_number()"), nullable=False),
        sa.Column("member_id", sa.BigInteger(), nullable=False),
        sa.Column("assigned_to_id", sa.BigInteger(), nullable=True),
        sa.Column("category", ticket_category, nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", ticket_priority, nullable=False),
        sa.Column("status", ticket_status, server_default=sa.text("'OPEN'"), nullable=False),
        sa.Column("previous_status", ticket_status, nullable=True),
        sa.Column("reopen_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("reopen_count >= 0", name="reopen_count_nonnegative"),
        sa.ForeignKeyConstraint(["member_id"], ["users.id"], name="fk_tickets_member_id_users", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["users.id"], name="fk_tickets_assigned_to_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_tickets"),
        sa.UniqueConstraint("ticket_number", name="uq_tickets_ticket_number"),
    )
    op.execute("ALTER SEQUENCE ticket_number_seq OWNED BY tickets.ticket_number")
    op.create_table(
        "category_priority_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("category", ticket_category, nullable=False),
        sa.Column("default_priority", ticket_priority, nullable=False),
        sa.Column("updated_by_id", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], name="fk_category_priority_settings_updated_by_id_users", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_category_priority_settings"),
        sa.UniqueConstraint("category", name="uq_category_priority_settings_category"),
    )
    op.create_table(
        "tat_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("priority", ticket_priority, nullable=False),
        sa.Column("resolution_hours", sa.Integer(), nullable=False),
        sa.Column("updated_by_id", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("resolution_hours > 0", name="resolution_hours_positive"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], name="fk_tat_settings_updated_by_id_users", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_tat_settings"),
        sa.UniqueConstraint("priority", name="uq_tat_settings_priority"),
    )
    op.create_table(
        "reopen_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("reopen_window_days", sa.Integer(), nullable=False),
        sa.Column("max_reopens", sa.Integer(), nullable=False),
        sa.Column("updated_by_id", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id = 1", name="singleton_id"),
        sa.CheckConstraint("reopen_window_days >= 0", name="reopen_window_nonnegative"),
        sa.CheckConstraint("max_reopens >= 0", name="max_reopens_nonnegative"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], name="fk_reopen_settings_updated_by_id_users", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_reopen_settings"),
    )
    op.create_table(
        "ticket_replies",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("sender_id", sa.BigInteger(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], name="fk_ticket_replies_ticket_id_tickets", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], name="fk_ticket_replies_sender_id_users", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_ticket_replies"),
    )
    op.create_table(
        "ticket_history",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], name="fk_ticket_history_ticket_id_tickets", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name="fk_ticket_history_actor_id_users", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_ticket_history"),
    )
    op.create_table(
        "ticket_sla",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_paused", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accumulated_pause_duration", sa.BigInteger(), server_default=sa.text("0"), nullable=False, comment="Accumulated paused duration in whole seconds."),
        sa.Column("breached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("accumulated_pause_duration >= 0", name="pause_duration_nonnegative"),
        sa.CheckConstraint("(is_paused AND paused_at IS NOT NULL) OR (NOT is_paused AND paused_at IS NULL)", name="pause_state_consistent"),
        sa.CheckConstraint("due_at >= started_at", name="deadline_not_before_start"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], name="fk_ticket_sla_ticket_id_tickets", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_ticket_sla"),
        sa.UniqueConstraint("ticket_id", name="uq_ticket_sla_ticket_id"),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("recipient_id", sa.BigInteger(), nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), nullable=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], name="fk_notifications_recipient_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], name="fk_notifications_ticket_id_tickets", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
    )

    for table, column in (
        ("tickets", "member_id"), ("tickets", "assigned_to_id"), ("tickets", "category"),
        ("tickets", "priority"), ("tickets", "status"), ("tickets", "created_at"),
        ("ticket_replies", "ticket_id"), ("ticket_replies", "sender_id"), ("ticket_replies", "created_at"),
        ("ticket_history", "ticket_id"), ("ticket_history", "actor_id"), ("ticket_history", "created_at"),
        ("ticket_sla", "due_at"),
        ("notifications", "recipient_id"), ("notifications", "ticket_id"), ("notifications", "created_at"),
    ):
        op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_index("ix_tickets_status_priority", "tickets", ["status", "priority"])
    op.create_index("ix_tickets_category_status", "tickets", ["category", "status"])
    op.create_index("ix_tickets_member_created", "tickets", ["member_id", "created_at"])


def downgrade() -> None:
    for table in ("notifications", "ticket_sla", "ticket_history", "ticket_replies", "reopen_settings", "tat_settings", "category_priority_settings", "tickets", "users"):
        op.drop_table(table)
    op.execute("DROP FUNCTION next_ticket_number()")
    op.execute("DROP TYPE ticket_status")
    op.execute("DROP TYPE ticket_priority")
    op.execute("DROP TYPE ticket_category")
    op.execute("DROP TYPE user_role")
