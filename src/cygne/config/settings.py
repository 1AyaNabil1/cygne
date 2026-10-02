"""Typed application settings, loaded from the environment.

All configuration enters the system here. Nothing else reads ``os.environ``
directly, which keeps configuration testable and the rest of the code free of
environment assumptions.
"""

from __future__ import annotations

from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings sourced from environment variables / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─── LLM provider ───
    llm_provider: str = Field(default="qwen", alias="CYGNE_LLM_PROVIDER")
    qwen_api_key: str = Field(default="", alias="QWEN_API_KEY")
    qwen_base_url: str = Field(
        default="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        alias="QWEN_BASE_URL",
    )
    # Any OpenAI-compatible endpoint, with CYGNE_LLM_PROVIDER=openai-compatible
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    main_model: str = Field(default="qwen-max", alias="CYGNE_MAIN_MODEL")
    summary_model: str = Field(default="qwen-plus", alias="CYGNE_SUMMARY_MODEL")

    # ─── Telegram ───
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_operator_chat_id: str = Field(default="", alias="TELEGRAM_OPERATOR_CHAT_ID")

    # ─── Google Calendar (optional; falls back to internal scheduling if unset) ───
    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", alias="GOOGLE_CLIENT_SECRET")
    google_refresh_token: str = Field(default="", alias="GOOGLE_REFRESH_TOKEN")
    google_calendar_id: str = Field(default="primary", alias="GOOGLE_CALENDAR_ID")

    # ─── Email (optional; branded invite is skipped if unset) ───
    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=465, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    agency_name: str = Field(default="Cygne Marketing", alias="CYGNE_AGENCY_NAME")
    meeting_organizer_email: str = Field(default="", alias="CYGNE_ORGANIZER_EMAIL")

    # ─── Dashboard (shows prospects' contact details, so it needs a password) ───
    dashboard_user: str = Field(default="operator", alias="CYGNE_DASHBOARD_USER")
    dashboard_password: str = Field(default="", alias="CYGNE_DASHBOARD_PASSWORD")

    # ─── Database ───
    database_url: str = Field(
        default="postgresql+asyncpg://cygne:cygne@localhost:5432/cygne",
        alias="DATABASE_URL",
    )

    # ─── App ───
    env: str = Field(default="development", alias="CYGNE_ENV")
    log_level: str = Field(default="INFO", alias="CYGNE_LOG_LEVEL")
    summary_threshold: int = Field(default=50, alias="SUMMARY_THRESHOLD")
    # The agency's smallest monthly engagement; budgets are scored against it
    min_monthly_budget: float = Field(default=1000, alias="CYGNE_MIN_MONTHLY_BUDGET")
    timezone: str = Field(default="UTC", alias="CYGNE_TIMEZONE")

    @property
    def tzinfo(self) -> ZoneInfo:
        """The business timezone used for scheduling and slot display."""
        return ZoneInfo(self.timezone)

    @property
    def calendar_enabled(self) -> bool:
        """True when Google Calendar credentials are fully configured."""
        return bool(
            self.google_client_id and self.google_client_secret and self.google_refresh_token
        )

    @property
    def email_enabled(self) -> bool:
        """True when SMTP credentials are configured."""
        return bool(self.smtp_user and self.smtp_password)

    def provider_kwargs(self) -> dict[str, str]:
        """Return the keyword arguments for building the configured LLM provider."""
        if self.llm_provider == "qwen":
            return {"api_key": self.qwen_api_key, "base_url": self.qwen_base_url}
        if self.llm_provider == "openai-compatible":
            return {"api_key": self.llm_api_key, "base_url": self.llm_base_url}
        raise ValueError(f"Unsupported LLM provider: {self.llm_provider!r}")


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()
