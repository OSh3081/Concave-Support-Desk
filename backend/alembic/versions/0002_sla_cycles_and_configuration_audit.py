"""Add historical SLA cycles and configuration audit records.

Revision ID: 0002_sla_cycles_config_audit
Revises: 0001_database_foundation
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_sla_cycles_config_audit"
down_revision = "0001_database_foundation"
branch_labels = None
depends_on = None


ticket_priority = postgresql.ENUM(
    "LOW", "MEDIUM", "HIGH", name="ticket_priority", create_type=False
)


def validate_existing_ticket_slas(connection) -> None:
    """Fail rather than silently omit existing tickets without SLA state."""
    missing_ids = connection.execute(
        sa.text(
            """
            SELECT t.id
            FROM tickets AS t
            LEFT JOIN ticket_sla AS sla ON sla.ticket_id = t.id
            WHERE sla.ticket_id IS NULL
            ORDER BY t.id
            LIMIT 10
            """
        )
    ).scalars().all()
    if missing_ids:
        ids = ", ".join(str(ticket_id) for ticket_id in missing_ids)
        raise RuntimeError(
            "Cannot upgrade to 0002: existing tickets have no ticket_sla rows "
            f"(sample ticket IDs: {ids}). Restore each ticket's truthful SLA state "
            "before retrying; this migration will not invent timestamps or durations."
        )


def upgrade() -> None:
    # Every ticket created through the application receives a TicketSLA in the
    # same transaction. Legacy/manual rows can violate that invariant; stop
    # before schema changes so no ticket is silently omitted from the backfill.
    validate_existing_ticket_slas(op.get_bind())

    op.create_table(
        "ticket_sla_cycles",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("priority", ticket_priority, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "accumulated_pause_duration_seconds",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
            comment="Accumulated paused duration for this SLA cycle in whole seconds.",
        ),
        sa.CheckConstraint("cycle_number > 0", name="cycle_number_positive"),
        sa.CheckConstraint(
            "accumulated_pause_duration_seconds >= 0",
            name="cycle_pause_duration_nonnegative",
        ),
        sa.CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= started_at",
            name="cycle_resolution_not_before_start",
        ),
        sa.CheckConstraint(
            "resolved_at IS NULL OR accumulated_pause_duration_seconds <= "
            "EXTRACT(EPOCH FROM (resolved_at - started_at))",
            name="cycle_pause_not_longer_than_elapsed",
        ),
        sa.CheckConstraint(
            "closed_at IS NULL OR resolved_at IS NOT NULL",
            name="cycle_close_requires_resolution",
        ),
        sa.CheckConstraint(
            "closed_at IS NULL OR closed_at >= resolved_at",
            name="cycle_close_not_before_resolution",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.id"],
            name="fk_ticket_sla_cycles_ticket_id_tickets", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "ticket_id", "cycle_number", name="uq_ticket_sla_cycles_ticket_cycle"
        ),
    )
    op.create_index("ix_ticket_sla_cycles_ticket_id", "ticket_sla_cycles", ["ticket_id"])
    op.create_index("ix_ticket_sla_cycles_resolved_at", "ticket_sla_cycles", ["resolved_at"])
    op.create_index(
        "uq_ticket_sla_cycles_one_active",
        "ticket_sla_cycles",
        ["ticket_id"],
        unique=True,
        postgresql_where=sa.text("resolved_at IS NULL"),
    )

    op.create_table(
        "configuration_audit",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor_id", sa.BigInteger(), nullable=False),
        sa.Column("setting_type", sa.String(length=40), nullable=False),
        sa.Column("setting_key", sa.String(length=100), nullable=False),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "setting_type IN ('CATEGORY_PRIORITY', 'TAT', 'REOPEN')",
            name="configuration_setting_type_valid",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"],
            name="fk_configuration_audit_actor_id_users", ondelete="RESTRICT"
        ),
    )
    op.create_index("ix_configuration_audit_actor_id", "configuration_audit", ["actor_id"])
    op.create_index(
        "ix_configuration_audit_actor_created",
        "configuration_audit",
        ["actor_id", "created_at"],
    )
    op.create_index(
        "ix_configuration_audit_setting_created",
        "configuration_audit",
        ["setting_type", "setting_key", "created_at"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_configuration_audit_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION
                'configuration_audit is append-only; UPDATE and DELETE are prohibited';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_configuration_audit_append_only
        BEFORE UPDATE OR DELETE ON configuration_audit
        FOR EACH ROW EXECUTE FUNCTION prevent_configuration_audit_mutation()
        """
    )

    # Preserve the current known cycle for existing rows. Earlier cycles whose
    # start times were overwritten before this migration cannot be reconstructed.
    op.execute(
        """
        INSERT INTO ticket_sla_cycles (
            ticket_id, cycle_number, priority, started_at, resolved_at, closed_at,
            accumulated_pause_duration_seconds
        )
        SELECT t.id, t.reopen_count + 1, t.priority, sla.started_at,
               t.resolved_at, t.closed_at,
               sla.accumulated_pause_duration + CASE
                   WHEN sla.is_paused AND t.resolved_at IS NOT NULL AND sla.paused_at IS NOT NULL
                   THEN GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (t.resolved_at - sla.paused_at)))::bigint)
                   ELSE 0
               END
        FROM tickets AS t
        JOIN ticket_sla AS sla ON sla.ticket_id = t.id
        """
    )


def downgrade() -> None:
    # WARNING: this downgrade permanently deletes every SLA cycle and
    # configuration audit row. Back up/export them first if they must survive.
    op.execute("DROP TRIGGER trg_configuration_audit_append_only ON configuration_audit")
    op.execute("DROP FUNCTION prevent_configuration_audit_mutation()")
    op.drop_table("configuration_audit")
    op.drop_table("ticket_sla_cycles")
