"""Configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Literal


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "gpt-proxy"
    app_env: Literal["development", "production"] = "development"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_workers: int = 1

    # OpenAI
    openai_api_base_url: str = "https://api.openai.com/v1"
    openai_api_keys: list[str] = []
    openai_key_rotation_strategy: Literal["round-robin", "least-used", "random"] = "round-robin"

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60
    rate_limit_tokens_per_minute: int = 90000

    # Caching
    cache_enabled: bool = False
    cache_backend: Literal["memory", "redis"] = "memory"
    cache_ttl_seconds: int = 3600
    redis_url: str = "redis://localhost:6379"

    # Database
    database_url: str = "sqlite+aiosqlite:///./gpt_proxy.db"

    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"

    # Cost Tracking
    cost_tracking_enabled: bool = True

    # Browser Auth (代理设置)
    browser_proxy: str = ""  # 例如: "http://127.0.0.1:7890"
    browser_profile_dir: str = "./browser_profile"

    # HTTP Client
    http_timeout: float = 30.0
    http_connect_timeout: float = 10.0

    # ChatGPT API settings
    conversation_only: bool = False  # Skip sentinel verification (may trigger rate limits)
    pow_difficulty: int = 3  # Minimum POW difficulty to solve (lower = harder)
    arkose_token_url: str = ""  # Arkose token service URL (required for free accounts)

    @field_validator("openai_api_keys", mode="before")
    @classmethod
    def parse_keys(cls, v: str | list[str]) -> list[str]:
        """Parse comma-separated API keys from environment."""
        if isinstance(v, str):
            return [k.strip() for k in v.split(",") if k.strip()]
        return v


settings = Settings()
