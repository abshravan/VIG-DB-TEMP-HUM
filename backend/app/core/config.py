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

    # PLC communication (ARCHITECTURE.md §3.1, §4.1) — switching s7<->modbus is this one value,
    # never a code change, since both PLCClient implementations share the same interface.
    plc_protocol: Literal["s7", "modbus"] = "s7"
    plc_address: str = "192.168.1.10"
    plc_rack: int = 0
    plc_slot: int = 1
    plc_s7_port: int = 102
    plc_modbus_port: int = 502
    tag_map_path: str = DEFAULT_TAG_MAP_PATH


@lru_cache
def get_settings() -> Settings:
    return Settings()
