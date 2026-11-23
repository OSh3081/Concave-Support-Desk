from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, require_roles
from app.models import TicketCategory, TicketPriority, TicketStatus, User, UserRole
from app.schemas.tickets import (
    AssignmentUpdate,
    PriorityUpdate,
    ReplyCreate,
    ReopenRequest,
    StatusUpdate,
    TicketCreate,
    TicketDetail,
    TicketList,
    UserSummary,
)
from app.services import tickets as service


router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketDetail, status_code=status.HTTP_201_CREATED)
def create_member_ticket(
    request: TicketCreate,
    db: Session = Depends(get_db),
    member: User = Depends(require_roles(UserRole.MEMBER)),
) -> TicketDetail:
    response = service.create_ticket(db, member, request.category, request.subject, request.description)
    db.commit()
    return response


@router.get("", response_model=TicketList)
def get_member_tickets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    member: User = Depends(require_roles(UserRole.MEMBER)),
) -> TicketList:
    return service.list_member_tickets(db, member, page, page_size)


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TicketDetail:
    return service.read_ticket(db, ticket_id, current_user)


@router.post("/{ticket_id}/replies", response_model=TicketDetail)
def reply_to_ticket(
    ticket_id: int,
    request: ReplyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TicketDetail:
    response = service.add_reply(
        db,
        ticket_id,
        current_user,
        request.message,
        is_internal=request.is_internal,
        request_information=request.request_information,
    )
    db.commit()
    return response


@router.post("/{ticket_id}/confirm-resolution", response_model=TicketDetail)
def confirm_ticket_resolution(
    ticket_id: int,
    db: Session = Depends(get_db),
    member: User = Depends(require_roles(UserRole.MEMBER)),
) -> TicketDetail:
    response = service.confirm_resolution(db, ticket_id, member)
    db.commit()
    return response


@router.post("/{ticket_id}/reopen", response_model=TicketDetail)
def reopen_ticket(
    ticket_id: int,
    request: ReopenRequest,
    db: Session = Depends(get_db),
    member: User = Depends(require_roles(UserRole.MEMBER)),
) -> TicketDetail:
    response = service.reopen_ticket(db, ticket_id, member, request.reason)
    db.commit()
    return response


support_router = APIRouter(prefix="/support", tags=["support tickets"])
support_user = Depends(require_roles(UserRole.SUPPORT_AGENT, UserRole.SUPPORT_HEAD))


@support_router.get("/tickets", response_model=TicketList)
def get_support_queue(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    ticket_status: Optional[TicketStatus] = Query(default=None, alias="status"),
    category: Optional[TicketCategory] = None,
    priority: Optional[TicketPriority] = None,
    overdue: Optional[bool] = None,
    search: Optional[str] = Query(default=None, min_length=1, max_length=100),
    db: Session = Depends(get_db),
    _support: User = support_user,
) -> TicketList:
    return service.list_support_tickets(
        db, _support, page, page_size, ticket_status, category, priority, overdue, search
    )


@support_router.get("/agents", response_model=list[UserSummary])
def get_assignable_agents(
    db: Session = Depends(get_db),
    _support: User = support_user,
) -> list[UserSummary]:
    return service.list_assignable_agents(db)


@support_router.get("/tickets/{ticket_id}", response_model=TicketDetail)
def get_support_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    _support: User = support_user,
) -> TicketDetail:
    return service.read_ticket(db, ticket_id, _support)


@support_router.post("/tickets/{ticket_id}/assign", response_model=TicketDetail)
def assign_support_ticket(
    ticket_id: int,
    request: AssignmentUpdate,
    db: Session = Depends(get_db),
    _support: User = support_user,
) -> TicketDetail:
    response = service.assign_ticket(db, ticket_id, _support, request.assigned_to_id)
    db.commit()
    return response


@support_router.patch("/tickets/{ticket_id}/status", response_model=TicketDetail)
def change_ticket_status(
    ticket_id: int,
    request: StatusUpdate,
    db: Session = Depends(get_db),
    _support: User = support_user,
) -> TicketDetail:
    response = service.update_status(db, ticket_id, _support, request.status, request.reason)
    db.commit()
    return response


@support_router.patch("/tickets/{ticket_id}/priority", response_model=TicketDetail)
def change_ticket_priority(
    ticket_id: int,
    request: PriorityUpdate,
    db: Session = Depends(get_db),
    _support: User = support_user,
) -> TicketDetail:
    response = service.change_priority(
        db, ticket_id, _support, request.priority, request.reason
    )
    db.commit()
    return response
