"""JWT issuance and validation, isolated from API route handlers."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import jwt
from fastapi import HTTPException, status
from jwt.exceptions import InvalidTokenError

from app.core.config import settings
from app.models.enums import UserRole


ALGORITHM = "HS256"


def create_access_token(
    user_id: int,
    role: UserRole,
    expires_delta: Optional[timedelta] = None,
) -> Tuple[str, datetime]:
    # JWT NumericDate claims have second precision; align the response expiry
    # timestamp with the exact instant PyJWT will encode and validate.
    now = datetime.now(timezone.utc).replace(microsecond=0)
    expires_at = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM)
    return token, expires_at


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],
            options={"require": ["exp", "iat", "sub", "role"]},
        )
    except InvalidTokenError as exc:
        raise invalid_credentials() from exc


def invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
