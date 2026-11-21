"""Idempotently create the development demo accounts and baseline settings.

Run from ``backend/`` with the configured database available:
``python -m app.db.seed``.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.core.passwords import hash_password
from app.db.session import SessionLocal
from app.models import (
    CategoryPrioritySetting,
    ReopenSetting,
    TATSetting,
    TicketCategory,
    TicketPriority,
    User,
    UserRole,
)


DEMO_USERS = (
    {"name": "Demo Member", "email": "member@concave.test", "role": UserRole.MEMBER},
    {"name": "Demo Support Agent", "email": "agent@concave.test", "role": UserRole.SUPPORT_AGENT},
    {"name": "Demo Support Head", "email": "head@concave.test", "role": UserRole.SUPPORT_HEAD},
    {"name": "System", "email": "system@concave.internal", "role": UserRole.SYSTEM},
)

CATEGORY_DEFAULTS = {
    TicketCategory.PAYMENT: TicketPriority.HIGH,
    TicketCategory.PROFILE_CHANGE: TicketPriority.MEDIUM,
    TicketCategory.SURVEY_ISSUE: TicketPriority.HIGH,
    TicketCategory.ELIGIBILITY: TicketPriority.MEDIUM,
    TicketCategory.OTHER: TicketPriority.LOW,
}
TAT_HOURS = {
    TicketPriority.HIGH: 4,
    TicketPriority.MEDIUM: 24,
    TicketPriority.LOW: 48,
}
DEMO_PASSWORD_SETTING_NAMES = {
    "member@concave.test": "demo_member_password",
    "agent@concave.test": "demo_agent_password",
    "head@concave.test": "demo_head_password",
}


def seed_database(include_demo_accounts: bool = True) -> None:
    """Insert baseline data; public demo users are restricted to development."""
    if include_demo_accounts and settings.app_env != "development":
        raise RuntimeError(
            "Public demo accounts may only be seeded when APP_ENV=development. "
            "For production, call seed_database(include_demo_accounts=False) to seed "
            "SYSTEM and default settings, then provision real users separately."
        )

    with SessionLocal.begin() as session:
        expected_users = DEMO_USERS if include_demo_accounts else (DEMO_USERS[-1],)
        session.execute(
            insert(User).values(list(expected_users)).on_conflict_do_nothing(index_elements=[User.email])
        )
        seeded_users = {}
        for expected in expected_users:
            user = session.scalar(select(User).where(User.email == expected["email"]))
            if user is None or user.name != expected["name"] or user.role is not expected["role"]:
                raise RuntimeError(
                    "A seeded demo account conflicts with its required name or role"
                )
            seeded_users[user.email] = user

        system_user = seeded_users["system@concave.internal"]
        if system_user.is_active is not True or system_user.password_hash is not None:
            raise RuntimeError(
                "Existing system@concave.internal user must be active and passwordless"
            )
        system_user_id = system_user.id

        if include_demo_accounts:
            for email, user in seeded_users.items():
                if user.role is UserRole.SYSTEM or user.password_hash is not None:
                    continue
                setting_name = DEMO_PASSWORD_SETTING_NAMES[email]
                configured_password = getattr(settings, setting_name)
                if configured_password is None:
                    raise RuntimeError(
                        "Set the local DEMO_MEMBER_PASSWORD, DEMO_AGENT_PASSWORD, and "
                        "DEMO_HEAD_PASSWORD values before seeding demo accounts"
                    )
                password = configured_password.get_secret_value()
                if len(password) < 12 or len(password) > 128:
                    raise RuntimeError(
                        "Demo passwords must contain 12 to 128 characters"
                    )
                user.password_hash = hash_password(password)

        categories = [
            {"category": category, "default_priority": priority, "updated_by_id": system_user_id}
            for category, priority in CATEGORY_DEFAULTS.items()
        ]
        session.execute(
            insert(CategoryPrioritySetting).values(categories).on_conflict_do_nothing(
                index_elements=[CategoryPrioritySetting.category]
            )
        )
        tat_rows = [
            {"priority": priority, "resolution_hours": hours, "updated_by_id": system_user_id}
            for priority, hours in TAT_HOURS.items()
        ]
        session.execute(
            insert(TATSetting).values(tat_rows).on_conflict_do_nothing(
                index_elements=[TATSetting.priority]
            )
        )
        session.execute(
            insert(ReopenSetting)
            .values(id=1, reopen_window_days=7, max_reopens=3, updated_by_id=system_user_id)
            .on_conflict_do_nothing(index_elements=[ReopenSetting.id])
        )


if __name__ == "__main__":
    seed_database()
    print("Demo users and default settings are present.")
