from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ — anchor for default paths so they're correct regardless of the caller's cwd
# (systemd, cron, Docker, and ad-hoc scripts in database/seed/ all invoke this from different places).
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
DEFAULT_DATABASE_URL = f"sqlite+aiosqlite:///{BACKEND_DIR / 'data' / 'monitoring.db'}"
DEFAULT_TAG_MAP_PATH = str(REPO_ROOT / "config" / "plc_tags.yaml")


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

    # PLC communication (ARCHITECTURE.md §3.1, §4.1) — switching s7<->modbus<->simulated is
    # this one value, never a code change, since all three PLCClient implementations share
    # the same interface. "simulated" needs no PLC hardware/network at all — useful for
    # local development, demos, and dashboard testing before the real PLC is reachable.
    plc_protocol: Literal["s7", "modbus", "simulated"] = "s7"
    plc_address: str = "192.168.1.10"
    plc_rack: int = 0
    plc_slot: int = 1
    plc_s7_port: int = 102
    plc_modbus_port: int = 502
    tag_map_path: str = DEFAULT_TAG_MAP_PATH
    # Only used when plc_protocol == "simulated". A fixed seed makes the simulated readings
    # reproducible run-to-run; leave unset for different random drift each run.
    plc_sim_seed: int | None = None

    # JWT auth (ARCHITECTURE.md §3.6, §15). The default secret is only for first-run local
    # dev — every real deployment must set JWT_SECRET_KEY in .env to a random value.
    jwt_secret_key: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # How old a sensor's latest reading may be before /live reports it as stale.
    live_stale_threshold_seconds: int = 30

    cors_allow_origins: list[str] = ["http://localhost:5173"]

    # Background workers (ARCHITECTURE.md §9, §12).
    raw_retention_days: int = 90
    retention_run_at: str = "02:00"  # UTC, "HH:MM"
    backup_run_at: str = "03:00"  # UTC, "HH:MM"
    # Empty string disables Atlas sync entirely — it's an optional enhancement, never a
    # dependency for core operation (ARCHITECTURE.md §12).
    atlas_connection_string: str = ""
    atlas_database_name: str = "server_room_monitor"
    atlas_sync_interval_seconds: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
