from typing import Literal, Optional

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    app_env: Literal["development", "test", "staging", "production"]
    jwt_secret: SecretStr
    access_token_expire_minutes: int = 30
    demo_member_password: Optional[SecretStr] = None
    demo_agent_password: Optional[SecretStr] = None
    demo_head_password: Optional[SecretStr] = None

    @field_validator("jwt_secret")
    @classmethod
    def require_strong_jwt_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters")
        return value

    @field_validator("access_token_expire_minutes")
    @classmethod
    def require_positive_token_lifetime(cls, value: int) -> int:
        if value < 1 or value > 1440:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 1440")
        return value

    @field_validator(
        "demo_member_password",
        "demo_agent_password",
        "demo_head_password",
    )
    @classmethod
    def validate_demo_password_length(
        cls, value: Optional[SecretStr]
    ) -> Optional[SecretStr]:
        if value is not None:
            length = len(value.get_secret_value())
            if length < 12 or length > 128:
                raise ValueError("Demo passwords must contain 12 to 128 characters")
        return value

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
