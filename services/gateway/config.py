from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _path_env(name: str, default: str) -> Path:
    raw = os.getenv(name, default).strip() or default
    path = Path(raw)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


@dataclass(frozen=True)
class Settings:
    app_env: str
    extraction_mode: str
    text_to_sql_service_url: str
    text_to_sql_timeout_seconds: float
    visualization_mode: str
    artifact_storage: str
    artifact_dir: Path
    demo_data_dir: Path
    auth_db_path: Path
    auth_jwt_secret: str
    debug_sql_visible: bool

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_env=os.getenv("APP_ENV", "development").strip() or "development",
            extraction_mode=os.getenv("EXTRACTION_MODE", "mock").strip().lower() or "mock",
            text_to_sql_service_url=os.getenv("TEXT_TO_SQL_SERVICE_URL", "").strip(),
            text_to_sql_timeout_seconds=float(os.getenv("TEXT_TO_SQL_TIMEOUT_SECONDS", "60") or "60"),
            visualization_mode=os.getenv("VISUALIZATION_MODE", "local_cpu").strip().lower() or "local_cpu",
            artifact_storage=os.getenv("ARTIFACT_STORAGE", "local").strip().lower() or "local",
            artifact_dir=_path_env("ARTIFACT_DIR", "./artifacts"),
            demo_data_dir=_path_env("DEMO_DATA_DIR", "./demo_data"),
            auth_db_path=_path_env("AUTH_DB_PATH", "./data/auth.db"),
            auth_jwt_secret=os.getenv("AUTH_JWT_SECRET", "dev-only-change-me").strip()
            or "dev-only-change-me",
            debug_sql_visible=_bool_env("DEBUG_SQL_VISIBLE", False),
        )


def get_settings() -> Settings:
    return Settings.from_env()

