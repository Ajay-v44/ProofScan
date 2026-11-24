from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_ignore_empty=True, hide_input_in_errors=True
    )

    deployment_environment: Literal["local", "production"] = "local"
    database_url: str
    database_pool_size: int = Field(default=5, ge=1, le=100)
    database_max_overflow: int = Field(default=5, ge=0, le=100)
    redis_url: str = "redis://127.0.0.1:6379/0"
    web_origin: str = "http://localhost:3000"
    auth_mode: Literal["local", "supabase"] = "local"
    local_auth_secret: SecretStr | None = None
    report_key_id: str = Field(min_length=1, max_length=64)
    report_private_key: SecretStr
    report_trusted_keys: dict[str, str] = Field(default_factory=dict)
    enable_simulator: bool = False
    supabase_url: str = ""
    supabase_publishable_key: SecretStr | None = None
    admin_subjects: set[UUID] = Field(default_factory=set)
    evidence_retention_days: int = Field(default=30, ge=1, le=365)
    kimi_api_key: SecretStr | None = None
    kimi_base_url: str = "https://api.moonshot.ai/v1"
    kimi_model: str = "kimi-k3"
    kimi_vision_model: str = ""
    agent_model: str = "kimi-k3"
    agent_test_model: str = "kimi-k2.6"
    agent_review_model: str = "kimi-k2.6"
    agent_vector_enabled: bool = False
    agent_embedding_cache: Path = Path("./.agent-cache")
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr | None = None
    pricing_comparables_file: Path | None = None

    @model_validator(mode="after")
    def check_configuration(self) -> "Settings":
        origin = urlsplit(self.web_origin)
        if (
            origin.scheme not in {"http", "https"}
            or origin.hostname is None
            or origin.port == 0
            or origin.username is not None
            or origin.path not in {"", "/"}
            or any(character.isspace() or character in "?#\\" for character in self.web_origin)
        ):
            raise ValueError("WEB_ORIGIN must be an HTTP or HTTPS origin")
        self.web_origin = origin._replace(path="").geturl()
        if self.deployment_environment == "production":
            if origin.scheme != "https" or self.auth_mode != "supabase" or self.enable_simulator:
                raise ValueError(
                    "Production requires an HTTPS WEB_ORIGIN, Supabase Auth and the simulator disabled"
                )
        if self.kimi_api_key:
            provider = urlsplit(self.kimi_base_url)
            if (
                provider.scheme != "https"
                or provider.hostname is None
                or provider.username is not None
                or provider.query
                or provider.fragment
            ):
                raise ValueError("KIMI_BASE_URL must be an HTTPS API URL")
        if bool(self.langfuse_public_key) != bool(self.langfuse_secret_key):
            raise ValueError("Set both Langfuse keys to enable agent tracing")
        if self.langfuse_secret_key:
            telemetry = urlsplit(self.langfuse_base_url)
            if telemetry.scheme != "https" or not telemetry.hostname or telemetry.username is not None:
                raise ValueError("LANGFUSE_BASE_URL must be a trusted HTTPS URL")
        if not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg://")
        if self.auth_mode == "local" and (
            not self.local_auth_secret or len(self.local_auth_secret.get_secret_value()) < 32
        ):
            raise ValueError("Set LOCAL_AUTH_SECRET to a random value of at least 32 characters")
        if self.auth_mode == "supabase" and (
            not self.supabase_url.startswith("https://")
            or not self.supabase_publishable_key
            or not self.supabase_publishable_key.get_secret_value()
        ):
            raise ValueError("Set HTTPS SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY")
        return self


@lru_cache
def settings() -> Settings:
    return Settings()
