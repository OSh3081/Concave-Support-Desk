from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.passwords import hash_password, verify_password
from app.models import User, UserRole


SUPPORTED_LOGIN_ROLES = {
    UserRole.MEMBER,
    UserRole.SUPPORT_AGENT,
    UserRole.SUPPORT_HEAD,
}
PUBLIC_DEMO_EMAILS = {
    "member@concave.test",
    "agent@concave.test",
    "head@concave.test",
}
_DUMMY_PASSWORD_HASH = hash_password("constant-time-demo-login-check")


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    normalized_email = email.strip().casefold()
    user = db.scalar(select(User).where(User.email == normalized_email))
    password_hash = user.password_hash if user and user.password_hash else _DUMMY_PASSWORD_HASH
    password_matches = verify_password(password, password_hash)
    demo_account_disabled = (
        normalized_email in PUBLIC_DEMO_EMAILS and settings.app_env != "development"
    )

    if (
        user is None
        or not password_matches
        or not user.is_active
        or user.role not in SUPPORTED_LOGIN_ROLES
        or demo_account_disabled
    ):
        return None
    return user
