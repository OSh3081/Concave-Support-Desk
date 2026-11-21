from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_roles
from app.models import TicketCategory, TicketPriority, User, UserRole
from app.schemas.tickets import (
    CategoryPriorityUpdate,
    DashboardResponse,
    ReopenSettingsUpdate,
    SettingsResponse,
    TATUpdate,
)
from app.services import ticket_settings, tickets


router = APIRouter(prefix="/support", tags=["support"])
support_roles = Depends(require_roles(UserRole.SUPPORT_AGENT, UserRole.SUPPORT_HEAD))
head_role = Depends(require_roles(UserRole.SUPPORT_HEAD))


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    _support: User = support_roles,
) -> DashboardResponse:
    return tickets.dashboard(db, _support)


@router.get("/settings", response_model=SettingsResponse)
def get_ticket_settings(
    db: Session = Depends(get_db),
    _head: User = head_role,
) -> SettingsResponse:
    return ticket_settings.read_settings(db, _head)


@router.patch("/settings/categories/{category}", response_model=SettingsResponse)
def set_category_priority(
    category: TicketCategory,
    request: CategoryPriorityUpdate,
    db: Session = Depends(get_db),
    head: User = head_role,
) -> SettingsResponse:
    result = ticket_settings.update_category_priority(db, head, category, request.default_priority)
    db.commit()
    return result


@router.patch("/settings/tat/{priority}", response_model=SettingsResponse)
def set_tat(
    priority: TicketPriority,
    request: TATUpdate,
    db: Session = Depends(get_db),
    head: User = head_role,
) -> SettingsResponse:
    result = ticket_settings.update_tat(db, head, priority, request.resolution_hours)
    db.commit()
    return result


@router.patch("/settings/reopen", response_model=SettingsResponse)
def set_reopen_settings(
    request: ReopenSettingsUpdate,
    db: Session = Depends(get_db),
    head: User = head_role,
) -> SettingsResponse:
    result = ticket_settings.update_reopen_settings(
        db, head, request.reopen_window_days, request.max_reopens
    )
    db.commit()
    return result
