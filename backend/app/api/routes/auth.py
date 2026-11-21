from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.core.config import settings
from app.core.tokens import create_access_token
from app.models import User
from app.schemas.auth import LoginRequest, LoginResponse, UserProfile
from app.services.auth import authenticate_user


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=LoginResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = authenticate_user(
        db,
        credentials.email,
        credentials.password.get_secret_value(),
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, expires_at = create_access_token(user.id, user.role)
    return LoginResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
        expires_at=expires_at,
        user=UserProfile(id=user.id, name=user.name, email=user.email, role=user.role),
    )


@router.get("/me", response_model=UserProfile)
def read_current_user(current_user: User = Depends(get_current_user)) -> UserProfile:
    return UserProfile(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
    )
