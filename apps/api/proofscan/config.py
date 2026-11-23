from functools import lru_cache
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_ignore_empty=True, hide_input_in_errors=True
    )

    database_url: str
    redis_url: str = "redis://127.0.0.1:6379/0"
    web_origin: str = "http://localhost:3000"
    auth_mode: Literal["local", "supabase"] = "local"
    local_auth_secret: SecretStr | None = None
    report_key_id: str
    report_private_key: SecretStr
    report_trusted_keys: dict[str, str] = {}
    enable_simulator: bool = False
    supabase_url: str = ""
    supabase_publishable_key: SecretStr | None = None
    admin_subjects: set[UUID] = set()
    evidence_retention_days: int = 30
    kimi_api_key: SecretStr | None = None
    kimi_base_url: str = "https://api.moonshot.ai/v1"
    kimi_model: str = ""
    kimi_vision_model: str = ""
    pricing_comparables_file: Path | None = None

    @model_validator(mode="after")
    def check_configuration(self) -> "Settings":
        if not 1 <= self.evidence_retention_days <= 365:
            raise ValueError("EVIDENCE_RETENTION_DAYS must be between 1 and 365")
        if self.kimi_api_key and (not self.kimi_model or not self.kimi_base_url.startswith("https://")):
            raise ValueError("Set KIMI_MODEL and an HTTPS KIMI_BASE_URL with KIMI_API_KEY")
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
