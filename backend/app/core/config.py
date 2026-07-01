from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ — anchor for the default DB path so it's correct regardless of the caller's cwd
# (systemd, cron, Docker, and ad-hoc scripts in database/seed/ all invoke this from different places).
BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = f"sqlite+aiosqlite:///{BACKEND_DIR / 'data' / 'monitoring.db'}"


class Settings(BaseSettings):
    """Infra-level configuration, loaded once at process start (see ARCHITECTURE.md §10).

    Runtime-tunable settings (poll interval, thresholds, display names) live in the
    Configuration table instead, and can change without a restart.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Industrial Server Room Monitoring"
    environment: str = "development"

    database_url: str = DEFAULT_DATABASE_URL
    sql_echo: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
