from typing import Any, Dict

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings


def make_settings(**overrides: Any) -> Settings:
    values: Dict[str, Any] = {
        "postgres_host": "localhost",
        "postgres_port": 5432,
        "postgres_db": "isolated_test_db",
        "postgres_user": "test_user",
        "postgres_password": "test_password",
        "app_env": "development",
        "jwt_secret": SecretStr("local-testing-secret-that-is-at-least-thirty-two-characters"),
    }
    values.update(overrides)
    return Settings(_env_file=None, _env_prefix="STAGEC_CONFIG_TEST_", **values)


def test_access_token_lifetime_defaults_to_30_minutes():
    assert make_settings().access_token_expire_minutes == 30


def test_valid_custom_access_token_lifetime_is_accepted():
    assert make_settings(access_token_expire_minutes=720).access_token_expire_minutes == 720


@pytest.mark.parametrize("minutes", [0, -1, 1441])
def test_invalid_access_token_lifetimes_are_rejected(minutes):
    with pytest.raises(ValidationError, match="between 1 and 1440"):
        make_settings(access_token_expire_minutes=minutes)


def test_missing_app_env_is_rejected():
    values = {
        "postgres_host": "localhost",
        "postgres_port": 5432,
        "postgres_db": "isolated_test_db",
        "postgres_user": "test_user",
        "postgres_password": "test_password",
        "jwt_secret": SecretStr("local-testing-secret-that-is-at-least-thirty-two-characters"),
    }
    with pytest.raises(ValidationError, match="app_env"):
        Settings(_env_file=None, _env_prefix="STAGEC_CONFIG_TEST_", **values)


def test_invalid_app_env_is_rejected():
    with pytest.raises(ValidationError, match="app_env"):
        make_settings(app_env="preview")


@pytest.mark.parametrize("length", [12, 128])
def test_demo_password_length_boundaries_are_accepted(length):
    config = make_settings(demo_member_password=SecretStr("x" * length))
    assert len(config.demo_member_password.get_secret_value()) == length


@pytest.mark.parametrize("length", [11, 129])
def test_demo_passwords_outside_allowed_range_are_rejected(length):
    with pytest.raises(ValidationError, match="12 to 128 characters"):
        make_settings(demo_member_password=SecretStr("x" * length))
