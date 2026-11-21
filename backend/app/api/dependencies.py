from typing import Callable, Generator, Optional, Set

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tokens import decode_access_token, invalid_credentials
from app.db.session import SessionLocal
from app.models import User, UserRole


bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise invalid_credentials()

    claims = decode_access_token(credentials.credentials)
    try:
        user_id = int(claims["sub"])
        UserRole(claims["role"])
    except (KeyError, TypeError, ValueError) as exc:
        raise invalid_credentials() from exc

    user = db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active or user.role is UserRole.SYSTEM:
        raise invalid_credentials()
    # Effective permissions always come from the current database role, not the
    # potentially stale role claim embedded in an otherwise valid token.
    return user


def require_roles(*allowed_roles: UserRole) -> Callable:
    allowed: Set[UserRole] = set(allowed_roles)
    if UserRole.SYSTEM in allowed:
        raise ValueError("SYSTEM cannot be granted normal endpoint access")

    def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_dependency
