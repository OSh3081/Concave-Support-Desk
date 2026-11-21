from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel, Field, ConfigDict

from app.models.enums import TicketCategory, TicketPriority, TicketStatus, UserRole


class TicketCreate(BaseModel):
    category: TicketCategory
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)


class ReplyCreate(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    is_internal: bool = False
    request_information: bool = False


class AssignmentUpdate(BaseModel):
    assigned_to_id: Optional[int] = None


class StatusUpdate(BaseModel):
    status: TicketStatus
    reason: Optional[str] = Field(default=None, max_length=1000)


class PriorityUpdate(BaseModel):
    priority: TicketPriority
    reason: str = Field(min_length=1, max_length=1000)


class ReopenRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class UserSummary(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole


class ReplyResponse(BaseModel):
    id: int
    sender: UserSummary
    message: str
    is_internal: bool
    created_at: datetime


class HistoryResponse(BaseModel):
    id: int
    actor: UserSummary
    action: str
    old_value: Optional[Union[dict, list]]
    new_value: Optional[Union[dict, list]]
    reason: Optional[str]
    created_at: datetime


class TicketSummary(BaseModel):
    id: int
    ticket_number: str
    category: TicketCategory
    subject: str
    priority: TicketPriority
    status: TicketStatus
    assigned_to: Optional[UserSummary]
    created_at: datetime
    updated_at: datetime
    due_at: datetime
    is_overdue: bool


class TicketDetail(TicketSummary):
    member: UserSummary
    description: str
    reopen_count: int
    resolved_at: Optional[datetime]
    closed_at: Optional[datetime]
    is_sla_paused: bool
    replies: list[ReplyResponse]
    history: list[HistoryResponse]


class TicketList(BaseModel):
    items: list[TicketSummary]
    page: int
    page_size: int
    total: int


class SupportTicketDetail(TicketDetail):
    pass


class DashboardResponse(BaseModel):
    open_ticket_count: int
    overdue_unresolved_count: int
    escalated_ticket_count: int
    tickets_resolved_today: int
    average_resolution_hours: Optional[float]
    tickets_by_category: dict[str, int]


class SettingsResponse(BaseModel):
    category_priorities: dict[TicketCategory, TicketPriority]
    tat_hours: dict[TicketPriority, int]
    reopen_window_days: int
    max_reopens: int


class CategoryPriorityUpdate(BaseModel):
    default_priority: TicketPriority


class TATUpdate(BaseModel):
    resolution_hours: int = Field(gt=0)


class ReopenSettingsUpdate(BaseModel):
    reopen_window_days: int = Field(ge=0)
    max_reopens: int = Field(ge=0)
