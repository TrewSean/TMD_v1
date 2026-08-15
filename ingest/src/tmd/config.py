"""Runtime settings. Everything comes from environment variables (or a local .env).

Never hard-code secrets. In GitHub Actions these are repository secrets;
locally they live in ingest/.env which is git-ignored.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Postgres connection string (Supabase "Transaction pooler" URI recommended for jobs).
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    # Alpaca market data (free plan is fine).
    alpaca_key: str | None = Field(default=None, alias="ALPACA_API_KEY")
    alpaca_secret: str | None = Field(default=None, alias="ALPACA_API_SECRET")
    alpaca_feed: str = Field(default="iex", alias="ALPACA_FEED")  # "iex" free, "sip" paid

    # Polite HTTP identity for public data sites.
    http_user_agent: str = Field(
        default="TMD-Markets/0.1 (personal markets dashboard; contact via GitHub TrewSean/TMD_v1)",
        alias="TMD_USER_AGENT",
    )
    http_timeout_s: float = Field(default=30.0, alias="TMD_HTTP_TIMEOUT")

    # If true, run() prints observations instead of writing to the DB.
    dry_run: bool = Field(default=False, alias="TMD_DRY_RUN")


settings = Settings()
