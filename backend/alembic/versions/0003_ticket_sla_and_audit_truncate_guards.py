"""Enforce ticket SLA presence and protect audit rows from TRUNCATE.

Revision ID: 0003_ticket_sla_audit_guards
Revises: 0002_sla_cycles_config_audit
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_ticket_sla_audit_guards"
down_revision = "0002_sla_cycles_config_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    missing_ids = op.get_bind().execute(
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
        sample_ids = ", ".join(str(ticket_id) for ticket_id in missing_ids)
        raise RuntimeError(
            "Cannot upgrade to 0003: existing tickets have no ticket_sla rows "
            f"(sample ticket IDs: {sample_ids}). Restore truthful SLA state before retrying; "
            "the migration will not invent timestamps or durations."
        )

    # Deferred checks permit the ticket and its SLA to be inserted in either
    # order within one transaction, while rejecting a missing SLA at commit.
    op.execute(
        """
        CREATE FUNCTION enforce_ticket_sla_presence() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            checked_ticket_id bigint;
        BEGIN
            IF TG_TABLE_NAME = 'tickets' THEN
                checked_ticket_id := NEW.id;
            ELSE
                checked_ticket_id := OLD.ticket_id;
            END IF;

            IF EXISTS (SELECT 1 FROM tickets WHERE id = checked_ticket_id)
               AND NOT EXISTS (
                   SELECT 1 FROM ticket_sla WHERE ticket_id = checked_ticket_id
               ) THEN
                RAISE EXCEPTION
                    'ticket % must have a ticket_sla row at transaction end',
                    checked_ticket_id
                    USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_tickets_require_sla
        AFTER INSERT ON tickets
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_ticket_sla_presence()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_ticket_sla_delete_requires_parent_sla
        AFTER DELETE ON ticket_sla
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_ticket_sla_presence()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_ticket_sla_update_requires_parent_sla
        AFTER UPDATE ON ticket_sla
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_ticket_sla_presence()
        """
    )
    op.execute(
        """
        CREATE FUNCTION prevent_ticket_sla_truncate() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION
                'ticket_sla cannot be truncated while tickets may depend on SLA state';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_ticket_sla_no_truncate
        BEFORE TRUNCATE ON ticket_sla
        FOR EACH STATEMENT EXECUTE FUNCTION prevent_ticket_sla_truncate()
        """
    )
    op.execute(
        """
        CREATE FUNCTION prevent_configuration_audit_truncate() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION
                'configuration_audit is append-only; TRUNCATE is prohibited';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_configuration_audit_no_truncate
        BEFORE TRUNCATE ON configuration_audit
        FOR EACH STATEMENT EXECUTE FUNCTION prevent_configuration_audit_truncate()
        """
    )


def downgrade() -> None:
    # This downgrade removes integrity protections but deletes no application
    # data: tickets may again commit without SLA rows, and audit rows can again
    # be truncated. Re-upgrading restores the guards after validating existing
    # ticket/SLA consistency.
    op.execute("DROP TRIGGER trg_configuration_audit_no_truncate ON configuration_audit")
    op.execute("DROP FUNCTION prevent_configuration_audit_truncate()")
    op.execute("DROP TRIGGER trg_ticket_sla_no_truncate ON ticket_sla")
    op.execute("DROP FUNCTION prevent_ticket_sla_truncate()")
    op.execute("DROP TRIGGER trg_ticket_sla_update_requires_parent_sla ON ticket_sla")
    op.execute("DROP TRIGGER trg_ticket_sla_delete_requires_parent_sla ON ticket_sla")
    op.execute("DROP TRIGGER trg_tickets_require_sla ON tickets")
    op.execute("DROP FUNCTION enforce_ticket_sla_presence()")
