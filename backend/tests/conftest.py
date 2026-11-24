"""Test startup safety and shared database fixtures.

This file is loaded before pytest imports test modules. Keep the guard above
all application imports so a misconfigured run cannot initialize the app's
global SQLAlchemy engine with development settings.
"""

import os

import pytest


_EXPECTED_DATABASE = "concave_support_desk_test"
_EXPECTED_HOST = "127.0.0.1"
_EXPECTED_PORT = "55432"
_DEVELOPMENT_USER = "concave_dev"
_REQUIRED_ENV = (
    "APP_ENV",
    "POSTGRES_DB",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "JWT_SECRET",
)


def _validate_test_database_environment() -> None:
    """Validate explicit shell environment without loading any dotenv file."""
    errors = []
    values = {}
    for name in _REQUIRED_ENV:
        matches = [(key, value) for key, value in os.environ.items() if key.upper() == name]
        if len(matches) != 1:
            errors.append(
                f"{name} must be supplied exactly once in the process environment; "
                "pytest does not load .env files."
            )
            continue
        key, value = matches[0]
        if key != name:
            errors.append(f"Use the canonical uppercase variable name {name} (found {key}).")
        if not value.strip():
            errors.append(f"{name} must not be empty.")
        values[name] = value.strip()

    alternate_url_names = {"DATABASE_URL", "SQLALCHEMY_DATABASE_URI"}
    for key, value in os.environ.items():
        if key.upper() in alternate_url_names and value.strip():
            errors.append(
                f"{key} is also set; remove alternate database URLs because the app uses POSTGRES_* settings."
            )

    if values.get("APP_ENV") != "test":
        errors.append("APP_ENV must equal 'test'.")
    if values.get("POSTGRES_DB") != _EXPECTED_DATABASE:
        errors.append(f"POSTGRES_DB must equal '{_EXPECTED_DATABASE}'.")
    if values.get("POSTGRES_HOST") != _EXPECTED_HOST:
        errors.append(f"POSTGRES_HOST must equal '{_EXPECTED_HOST}' for the dedicated test service.")
    if values.get("POSTGRES_PORT") != _EXPECTED_PORT:
        errors.append(f"POSTGRES_PORT must equal '{_EXPECTED_PORT}' for the dedicated test service.")
    if values.get("POSTGRES_USER", "").casefold() == _DEVELOPMENT_USER.casefold():
        errors.append("POSTGRES_USER must be different from the development database user.")
    if len(values.get("JWT_SECRET", "")) < 32:
        errors.append("JWT_SECRET must contain at least 32 characters.")

    if errors:
        detail = "\n  - ".join(errors)
        pytest.exit(
            "Unsafe pytest database configuration.\n  - "
            + detail
            + "\nLoad the dedicated test env file into the shell before running pytest; "
            "the development .env file is deliberately not used by this guard.",
            returncode=4,
        )


_validate_test_database_environment()

# Import the application only after the environment has passed the guard.
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.db.session import engine
from app.main import app


@pytest.fixture
def db_session():
    """Use a savepoint-backed session inside a per-test outer transaction."""
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
        try:
            session.close()
        finally:
            try:
                transaction.rollback()
            finally:
                connection.close()


@pytest.fixture
def client(db_session):
    """Override FastAPI's DB dependency for the duration of a test."""
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
