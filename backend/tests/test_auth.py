from datetime import timedelta
from typing import Optional

import jwt
import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_db, get_current_user, require_roles
from app.core.config import settings
from app.core.passwords import hash_password, verify_password
from app.core.tokens import ALGORITHM, create_access_token
from app.db.session import engine
from app.db import seed as seed_module
from app.main import app
from app.models import User, UserRole


_authorization_test_router = APIRouter()


@_authorization_test_router.get("/_test/support-head")
def support_head_test_endpoint(
    user: User = Depends(require_roles(UserRole.SUPPORT_HEAD)),
) -> dict[str, str]:
    return {"role": user.role.value}


app.include_router(_authorization_test_router, prefix="/api")


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def make_user(
    db: Session,
    role: UserRole,
    email: str,
    password: str = "LocalTestPassword!2026",
    active: bool = True,
) -> User:
    user = User(
        name=f"Test {role.value}",
        email=email,
        role=role,
        is_active=active,
        password_hash=None if role is UserRole.SYSTEM else hash_password(password),
    )
    db.add(user)
    db.flush()
    return user


def token_for(user: User, expires_delta: Optional[timedelta] = None) -> str:
    token, _ = create_access_token(user.id, user.role, expires_delta=expires_delta)
    return token


@pytest.mark.parametrize(
    ("role", "email"),
    [
        (UserRole.MEMBER, "member-auth@example.test"),
        (UserRole.SUPPORT_AGENT, "agent-auth@example.test"),
        (UserRole.SUPPORT_HEAD, "head-auth@example.test"),
    ],
)
def test_login_for_supported_roles_and_me(client, db_session, role, email):
    user = make_user(db_session, role, email)
    assert user.password_hash != "LocalTestPassword!2026"
    assert verify_password("LocalTestPassword!2026", user.password_hash)

    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "LocalTestPassword!2026"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["expires_in"] == settings.access_token_expire_minutes * 60
    assert payload["expires_at"]
    assert payload["user"]["role"] == role.value
    assert "password_hash" not in payload["user"]

    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json() == {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": role.value,
    }


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("known-auth@example.test", "wrong-password"),
        ("unknown-auth@example.test", "LocalTestPassword!2026"),
    ],
)
def test_invalid_login_is_rejected_without_account_details(client, db_session, email, password):
    if email.startswith("known"):
        make_user(db_session, UserRole.MEMBER, email)
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_inactive_user_cannot_login(client, db_session):
    make_user(db_session, UserRole.MEMBER, "inactive-auth@example.test", active=False)
    response = client.post(
        "/api/auth/login",
        json={"email": "inactive-auth@example.test", "password": "LocalTestPassword!2026"},
    )
    assert response.status_code == 401


def test_system_cannot_login_or_use_a_signed_bearer_token(client, db_session):
    system_user = db_session.scalar(
        select(User).where(User.email == "system@concave.internal")
    )
    if system_user is None:
        system_user = make_user(db_session, UserRole.SYSTEM, "system@concave.internal")
    assert system_user.password_hash is None
    login_response = client.post(
        "/api/auth/login",
        json={"email": system_user.email, "password": "LocalTestPassword!2026"},
    )
    assert login_response.status_code == 401

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token_for(system_user)}"},
    )
    assert response.status_code == 401


def test_missing_invalid_and_malformed_tokens_are_rejected(client, db_session):
    user = make_user(db_session, UserRole.MEMBER, "token-auth@example.test")
    assert client.get("/api/auth/me").status_code == 401
    assert client.get(
        "/api/auth/me", headers={"Authorization": "Bearer malformed-token"}
    ).status_code == 401
    wrong_key_token = jwt.encode(
        {"sub": str(user.id), "role": user.role.value, "iat": 1, "exp": 4102444800},
        "incorrect-signing-key-for-test-that-is-long-enough",
        algorithm=ALGORITHM,
    )
    assert client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {wrong_key_token}"}
    ).status_code == 401


def test_expired_token_is_rejected(client, db_session):
    user = make_user(db_session, UserRole.MEMBER, "expired-auth@example.test")
    expired = token_for(user, expires_delta=timedelta(seconds=-1))
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_deactivated_user_cannot_use_previously_issued_token(client, db_session):
    user = make_user(db_session, UserRole.MEMBER, "deactivate-auth@example.test")
    token = token_for(user)
    user.is_active = False
    db_session.flush()

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_role_change_in_database_updates_existing_token_permissions(client, db_session):
    user = make_user(db_session, UserRole.SUPPORT_HEAD, "role-change-auth@example.test")
    token = token_for(user)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/_test/support-head", headers=headers).status_code == 200

    user.role = UserRole.MEMBER
    db_session.flush()
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] == UserRole.MEMBER.value
    assert client.get("/api/_test/support-head", headers=headers).status_code == 403


def test_member_cannot_access_support_head_dependency(client, db_session):
    member = make_user(db_session, UserRole.MEMBER, "member-forbidden@example.test")
    response = client.get(
        "/api/_test/support-head",
        headers={"Authorization": f"Bearer {token_for(member)}"},
    )
    assert response.status_code == 403


def test_development_seed_hashes_demo_passwords_and_is_idempotent(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(
        seed_module,
        "settings",
        settings.model_copy(update={"app_env": "development"}),
    )
    from app.services import auth as auth_service

    monkeypatch.setattr(
        auth_service,
        "settings",
        settings.model_copy(update={"app_env": "development"}),
    )
    isolated_factory = sessionmaker(
        bind=db_session.connection(),
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    monkeypatch.setattr(seed_module, "SessionLocal", isolated_factory)

    seed_module.seed_database()
    sample_accounts = [
        ("member@concave.test", "MemberDemoOnly!2026", UserRole.MEMBER),
        ("agent@concave.test", "AgentDemoOnly!2026", UserRole.SUPPORT_AGENT),
        ("head@concave.test", "HeadDemoOnly!2026", UserRole.SUPPORT_HEAD),
    ]
    first_hashes = {}
    for email, password, role in sample_accounts:
        user = db_session.scalar(select(User).where(User.email == email))
        assert user is not None
        assert user.role is role
        assert user.password_hash is not None
        assert user.password_hash != password
        assert verify_password(password, user.password_hash)
        first_hashes[email] = user.password_hash

        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200
        assert response.json()["user"]["role"] == role.value

    system = db_session.scalar(select(User).where(User.email == "system@concave.internal"))
    assert system is not None
    assert system.password_hash is None

    seed_module.seed_database()
    assert db_session.scalar(select(func.count()).select_from(User)) == 4
    for email, password, _ in sample_accounts:
        user = db_session.scalar(select(User).where(User.email == email))
        assert user.password_hash == first_hashes[email]
        assert client.post(
            "/api/auth/login", json={"email": email, "password": password}
        ).status_code == 200


def test_production_seed_refuses_public_demo_accounts(monkeypatch):
    production_settings = settings.model_copy(update={"app_env": "production"})
    monkeypatch.setattr(seed_module, "settings", production_settings)
    with pytest.raises(RuntimeError, match="APP_ENV=development"):
        seed_module.seed_database()


def test_production_can_seed_system_and_defaults_without_demo_users(
    db_session, monkeypatch
):
    production_settings = settings.model_copy(update={"app_env": "production"})
    monkeypatch.setattr(seed_module, "settings", production_settings)
    monkeypatch.setattr(
        seed_module,
        "SessionLocal",
        sessionmaker(
            bind=db_session.connection(),
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ),
    )

    seed_module.seed_database(include_demo_accounts=False)
    emails = set(db_session.scalars(select(User.email)).all())
    assert emails == {"system@concave.internal"}


def test_seed_requires_configured_demo_passwords(db_session, monkeypatch):
    incomplete_settings = settings.model_copy(
        update={"app_env": "development", "demo_member_password": None}
    )
    monkeypatch.setattr(seed_module, "settings", incomplete_settings)
    monkeypatch.setattr(
        seed_module,
        "SessionLocal",
        sessionmaker(
            bind=db_session.connection(),
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ),
    )

    with pytest.raises(RuntimeError, match="DEMO_MEMBER_PASSWORD"):
        seed_module.seed_database()
    assert db_session.scalar(select(func.count()).select_from(User)) == 0


def test_existing_demo_account_cannot_login_outside_development(
    client, db_session, monkeypatch
):
    email = "member@concave.test"
    make_user(db_session, UserRole.MEMBER, email, password="MemberDemoOnly!2026")
    from app.services import auth as auth_service

    monkeypatch.setattr(
        auth_service,
        "settings",
        settings.model_copy(update={"app_env": "production"}),
    )
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "MemberDemoOnly!2026"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "claims",
    [
        {"role": "MEMBER", "iat": 1, "exp": 4102444800},
        {"sub": "1", "role": "MEMBER", "iat": 1},
        {"sub": "1", "role": "MEMBER", "exp": 4102444800},
        {"sub": "1", "iat": 1, "exp": 4102444800},
        {"sub": "1", "role": "NOT_A_ROLE", "iat": 1, "exp": 4102444800},
    ],
)
def test_tokens_with_missing_or_unsupported_claims_are_rejected(client, claims):
    bad_token = jwt.encode(
        claims,
        settings.jwt_secret.get_secret_value(),
        algorithm=ALGORITHM,
    )
    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {bad_token}"}
    )
    assert response.status_code == 401


def test_token_signed_with_unsupported_algorithm_is_rejected(client):
    unsupported_token = jwt.encode(
        {"sub": "1", "role": "MEMBER", "iat": 1, "exp": 4102444800},
        "unsupported-algorithm-test-key-with-more-than-48-bytes",
        algorithm="HS384",
    )
    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {unsupported_token}"}
    )
    assert response.status_code == 401
