from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CategoryPrioritySetting,
    ConfigurationAudit,
    ReopenSetting,
    TATSetting,
    TicketCategory,
    TicketPriority,
    User,
    UserRole,
)
from app.schemas.tickets import SettingsResponse


def _not_configured() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Ticket settings are not fully configured",
    )


def _require_head(actor: User) -> None:
    if actor.role is not UserRole.SUPPORT_HEAD:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Support Head role required",
        )


def _audit(
    db: Session,
    actor: User,
    setting_type: str,
    setting_key: str,
    old_value: dict,
    new_value: dict,
) -> None:
    db.add(
        ConfigurationAudit(
            actor_id=actor.id,
            setting_type=setting_type,
            setting_key=setting_key,
            old_value=old_value,
            new_value=new_value,
        )
    )


def read_settings(db: Session, actor: User) -> SettingsResponse:
    _require_head(actor)
    categories = db.scalars(select(CategoryPrioritySetting)).all()
    tats = db.scalars(select(TATSetting)).all()
    reopen = db.scalar(select(ReopenSetting).where(ReopenSetting.id == 1))
    category_map = {row.category: row.default_priority for row in categories}
    tat_map = {row.priority: row.resolution_hours for row in tats}
    if set(category_map) != set(TicketCategory) or set(tat_map) != set(TicketPriority) or reopen is None:
        raise _not_configured()
    return SettingsResponse(
        category_priorities=category_map,
        tat_hours=tat_map,
        reopen_window_days=reopen.reopen_window_days,
        max_reopens=reopen.max_reopens,
    )


def update_category_priority(
    db: Session, actor: User, category: TicketCategory, priority: TicketPriority
) -> SettingsResponse:
    _require_head(actor)
    row = db.scalar(
        select(CategoryPrioritySetting)
        .where(CategoryPrioritySetting.category == category)
        .with_for_update()
    )
    if row is None:
        raise _not_configured()
    old_priority = row.default_priority
    if old_priority is not priority:
        _audit(
            db,
            actor,
            "CATEGORY_PRIORITY",
            category.value,
            {"default_priority": old_priority.value},
            {"default_priority": priority.value},
        )
    row.default_priority = priority
    row.updated_by_id = actor.id
    db.flush()
    return read_settings(db, actor)


def update_tat(db: Session, actor: User, priority: TicketPriority, hours: int) -> SettingsResponse:
    _require_head(actor)
    row = db.scalar(
        select(TATSetting).where(TATSetting.priority == priority).with_for_update()
    )
    if row is None:
        raise _not_configured()
    old_hours = row.resolution_hours
    if old_hours != hours:
        _audit(
            db,
            actor,
            "TAT",
            priority.value,
            {"resolution_hours": old_hours},
            {"resolution_hours": hours},
        )
    row.resolution_hours = hours
    row.updated_by_id = actor.id
    db.flush()
    return read_settings(db, actor)


def update_reopen_settings(
    db: Session, actor: User, days: int, max_reopens: int
) -> SettingsResponse:
    _require_head(actor)
    row = db.scalar(
        select(ReopenSetting).where(ReopenSetting.id == 1).with_for_update()
    )
    if row is None:
        raise _not_configured()
    old_value = {
        "reopen_window_days": row.reopen_window_days,
        "max_reopens": row.max_reopens,
    }
    new_value = {"reopen_window_days": days, "max_reopens": max_reopens}
    if old_value != new_value:
        _audit(db, actor, "REOPEN", "GLOBAL", old_value, new_value)
    row.reopen_window_days = days
    row.max_reopens = max_reopens
    row.updated_by_id = actor.id
    db.flush()
    return read_settings(db, actor)
