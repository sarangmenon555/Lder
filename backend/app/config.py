import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), extra="ignore")

    database_url: str = "sqlite:///./lder.db"
    secret_key: str = "change-me"
    admin_password: str = "change-me"
    token_ttl_hours: int = 72
    encryption_key: str = ""
    cors_origins: str = "http://localhost:3000"
    public_base_url: str = Field(default_factory=lambda: os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:8000"))
    frontend_base_url: str = "http://localhost:3000"
    cron_secret: str = ""
    guardrail_secret: str = ""
    enable_scheduler: bool = True
    tick_interval_minutes: int = Field(default=1, ge=1, le=60)

    otari_base_url: str = "https://api.otari.ai/api/v1"
    otari_api_key: str = ""
    otari_user_prefix: str = "lder-elder-"
    otari_timeout_seconds: int = Field(default=45, ge=5, le=120)

    classifier_model: str = "lder-classifier"
    classifier_fallback_models: str = ""
    classifier_reasoning_effort: str = ""
    summary_model: str = "lder-summary"
    summary_fallback_models: str = ""
    assistant_model: str = "lder-assistant"
    assistant_fallback_models: str = ""

    stt_base_url: str = ""
    stt_api_key: str = ""
    stt_model: str = "whisper-large-v3"
    stt_language: str = "ml"
    stt_prompt: str = "സുഖമാണ്. മരുന്ന് കഴിച്ചു. വേദന. വീണു. ശ്വാസം മുട്ടൽ."
    confidence_threshold: float = 0.55

    mcp_public_url: str = ""
    mcp_token_ttl_seconds: int = Field(default=600, ge=60, le=3600)

    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_api_version: str = "v21.0"
    whatsapp_template_name: str = "hello_world"
    whatsapp_template_language: str = "en_US"

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    email_api_url: str = ""
    email_api_key: str = ""
    email_from: str = ""

    retry_delays_minutes: str = "15,30"
    final_wait_minutes: int = 30
    escalation_delay_minutes: int = 20
    slot_grace_minutes: int = 60
    summary_weekday: int = 6
    summary_hour_utc: int = 12

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        if url.startswith("postgres://"):
            return "postgresql+psycopg2://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            return "postgresql+psycopg2://" + url[len("postgresql://"):]
        return url

    @property
    def retry_delays(self) -> list[int]:
        return [int(x) for x in self.retry_delays_minutes.split(",") if x.strip()]

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def static_dir(self) -> Path:
        return BASE_DIR / "static"

    @property
    def prompt_dir(self) -> Path:
        return BASE_DIR / "static" / "prompts"

    @property
    def stt_url(self) -> str:
        return (self.stt_base_url or self.otari_base_url).rstrip("/")

    @property
    def stt_key(self) -> str:
        return self.stt_api_key or self.otari_api_key

    def model_chain(self, primary: str, fallbacks: str) -> list[str]:
        chain = [primary.strip()] if primary.strip() else []
        for item in fallbacks.split(","):
            item = item.strip()
            if item and item not in chain:
                chain.append(item)
        return chain


@lru_cache
def get_settings() -> Settings:
    return Settings()
