"""Application configuration, loaded from environment / .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Gmail / OAuth
    gmail_credentials_file: str = "credentials.json"
    gmail_token_file: str = "token.json"

    # Storage
    database_url: str = "sqlite:///./data/phishguard.db"

    # Poller
    poll_interval_seconds: int = 120
    poll_max_results: int = 25
    initial_lookback_days: int = 3

    # Scoring thresholds (0-100)
    suspicious_threshold: int = 50
    junk_threshold: int = 25

    # Labels
    label_suspicious: str = "PhishGuard/Suspicious"
    label_junk: str = "PhishGuard/Junk"

    # Gmail OAuth scope: read messages + modify labels (no delete/send).
    gmail_scopes: tuple[str, ...] = (
        "https://www.googleapis.com/auth/gmail.modify",
    )


settings = Settings()
