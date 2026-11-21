from datetime import datetime, timezone
from typing import Optional, Union

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    Sequence,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import TicketCategory, TicketPriority, TicketStatus, UserRole


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


ticket_number_sequence = Sequence("ticket_number_seq", metadata=Base.metadata)


def enum_column(enum_type: type, name: str) -> SqlEnum:
    return SqlEnum(
        enum_type,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role <> 'SYSTEM' OR password_hash IS NULL", name="system_password_absent"),
        Index(
            "uq_users_single_system_role",
            "role",
            unique=True,
            postgresql_where=text("role = 'SYSTEM'::user_role"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    role: Mapped[UserRole] = mapped_column(enum_column(UserRole, "user_role"), nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now, server_default=text("now()"))

    member_tickets: Mapped[list["Ticket"]] = relationship(foreign_keys="Ticket.member_id", back_populates="member")
    assigned_tickets: Mapped[list["Ticket"]] = relationship(foreign_keys="Ticket.assigned_to_id", back_populates="assigned_to")
    replies: Mapped[list["TicketReply"]] = relationship(back_populates="sender")
    history_events: Mapped[list["TicketHistory"]] = relationship(back_populates="actor")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="recipient")
    configuration_changes: Mapped[list["ConfigurationAudit"]] = relationship(back_populates="actor")


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("reopen_count >= 0", name="reopen_count_nonnegative"),
        Index("ix_tickets_status_priority", "status", "priority"),
        Index("ix_tickets_category_status", "category", "status"),
        Index("ix_tickets_member_created", "member_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_number: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True,
        server_default=text("next_ticket_number()"),
    )
    member_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    category: Mapped[TicketCategory] = mapped_column(enum_column(TicketCategory, "ticket_category"), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[TicketPriority] = mapped_column(enum_column(TicketPriority, "ticket_priority"), nullable=False, index=True)
    status: Mapped[TicketStatus] = mapped_column(enum_column(TicketStatus, "ticket_status"), nullable=False, default=TicketStatus.OPEN, server_default=text("'OPEN'"), index=True)
    previous_status: Mapped[Optional[TicketStatus]] = mapped_column(enum_column(TicketStatus, "ticket_status"), nullable=True)
    reopen_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, server_default=text("now()"), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now, server_default=text("now()"))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    member: Mapped[User] = relationship(foreign_keys=[member_id], back_populates="member_tickets")
    assigned_to: Mapped[Optional[User]] = relationship(foreign_keys=[assigned_to_id], back_populates="assigned_tickets")
    replies: Mapped[list["TicketReply"]] = relationship(back_populates="ticket", cascade="all, delete-orphan", passive_deletes=True)
    history: Mapped[list["TicketHistory"]] = relationship(back_populates="ticket", passive_deletes="all")
    sla: Mapped[Optional["TicketSLA"]] = relationship(back_populates="ticket", cascade="all, delete-orphan", passive_deletes=True, uselist=False)
    notifications: Mapped[list["Notification"]] = relationship(back_populates="ticket", passive_deletes=True)
    sla_cycles: Mapped[list["TicketSLACycle"]] = relationship(
        back_populates="ticket", order_by="TicketSLACycle.cycle_number"
    )


class TicketReply(Base):
    __tablename__ = "ticket_replies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, server_default=text("now()"), index=True)

    ticket: Mapped[Ticket] = relationship(back_populates="replies")
    sender: Mapped[User] = relationship(back_populates="replies")


class TicketHistory(Base):
    __tablename__ = "ticket_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False, index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    old_value: Mapped[Optional[Union[dict, list]]] = mapped_column(JSONB)
    new_value: Mapped[Optional[Union[dict, list]]] = mapped_column(JSONB)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, server_default=text("now()"), index=True)

    ticket: Mapped[Ticket] = relationship(back_populates="history")
    actor: Mapped[User] = relationship(back_populates="history_events")


class CategoryPrioritySetting(Base):
    __tablename__ = "category_priority_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    category: Mapped[TicketCategory] = mapped_column(enum_column(TicketCategory, "ticket_category"), nullable=False, unique=True)
    default_priority: Mapped[TicketPriority] = mapped_column(enum_column(TicketPriority, "ticket_priority"), nullable=False)
    updated_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now, server_default=text("now()"))
    updated_by: Mapped[Optional[User]] = relationship()


class TATSetting(Base):
    __tablename__ = "tat_settings"
    __table_args__ = (CheckConstraint("resolution_hours > 0", name="resolution_hours_positive"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    priority: Mapped[TicketPriority] = mapped_column(enum_column(TicketPriority, "ticket_priority"), nullable=False, unique=True)
    resolution_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now, server_default=text("now()"))
    updated_by: Mapped[Optional[User]] = relationship()


class TicketSLA(Base):
    __tablename__ = "ticket_sla"
    __table_args__ = (
        CheckConstraint("accumulated_pause_duration >= 0", name="pause_duration_nonnegative"),
        CheckConstraint(
            "(is_paused AND paused_at IS NOT NULL) OR (NOT is_paused AND paused_at IS NULL)",
            name="pause_state_consistent",
        ),
        CheckConstraint("due_at >= started_at", name="deadline_not_before_start"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, unique=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    is_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    accumulated_pause_duration: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Accumulated paused duration in whole seconds.",
    )
    breached_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    escalated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_calculated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    ticket: Mapped[Ticket] = relationship(back_populates="sla")


class TicketSLACycle(Base):
    __tablename__ = "ticket_sla_cycles"
    __table_args__ = (
        UniqueConstraint("ticket_id", "cycle_number", name="uq_ticket_sla_cycles_ticket_cycle"),
        CheckConstraint("cycle_number > 0", name="cycle_number_positive"),
        CheckConstraint(
            "accumulated_pause_duration_seconds >= 0",
            name="cycle_pause_duration_nonnegative",
        ),
        CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= started_at",
            name="cycle_resolution_not_before_start",
        ),
        CheckConstraint(
            "resolved_at IS NULL OR accumulated_pause_duration_seconds <= "
            "EXTRACT(EPOCH FROM (resolved_at - started_at))",
            name="cycle_pause_not_longer_than_elapsed",
        ),
        CheckConstraint(
            "closed_at IS NULL OR resolved_at IS NOT NULL",
            name="cycle_close_requires_resolution",
        ),
        CheckConstraint(
            "closed_at IS NULL OR closed_at >= resolved_at",
            name="cycle_close_not_before_resolution",
        ),
        Index(
            "uq_ticket_sla_cycles_one_active",
            "ticket_id",
            unique=True,
            postgresql_where=text("resolved_at IS NULL"),
        ),
        Index("ix_ticket_sla_cycles_resolved_at", "resolved_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[TicketPriority] = mapped_column(
        enum_column(TicketPriority, "ticket_priority"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    accumulated_pause_duration_seconds: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Accumulated paused duration for this SLA cycle in whole seconds.",
    )

    ticket: Mapped[Ticket] = relationship(back_populates="sla_cycles")


class ConfigurationAudit(Base):
    __tablename__ = "configuration_audit"
    __table_args__ = (
        CheckConstraint(
            "setting_type IN ('CATEGORY_PRIORITY', 'TAT', 'REOPEN')",
            name="configuration_setting_type_valid",
        ),
        Index("ix_configuration_audit_actor_created", "actor_id", "created_at"),
        Index("ix_configuration_audit_setting_created", "setting_type", "setting_key", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    setting_type: Mapped[str] = mapped_column(String(40), nullable=False)
    setting_key: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    new_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=text("now()")
    )

    actor: Mapped[User] = relationship(back_populates="configuration_changes")


class ReopenSetting(Base):
    __tablename__ = "reopen_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton_id"),
        CheckConstraint("reopen_window_days >= 0", name="reopen_window_nonnegative"),
        CheckConstraint("max_reopens >= 0", name="max_reopens_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reopen_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    max_reopens: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now, server_default=text("now()"))
    updated_by: Mapped[Optional[User]] = relationship()


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ticket_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, server_default=text("now()"), index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    recipient: Mapped[User] = relationship(back_populates="notifications")
    ticket: Mapped[Optional[Ticket]] = relationship(back_populates="notifications")
