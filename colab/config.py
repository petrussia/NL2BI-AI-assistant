from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


def _envbool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _read_file_secret(*candidates: Path) -> str | None:
    """Return the first non-empty text from the given paths (utf-8 stripped)."""
    for path in candidates:
        try:
            if path.exists():
                text = path.read_text(encoding="utf-8").strip()
                if text:
                    return text
        except OSError:
            continue
    return None


@dataclass(frozen=True)
class ColabServerConfig:
    model_id: str
    mock_model: bool
    quantization: str
    max_new_tokens: int
    spider_db_root: Path
    data_sources_path: Path
    default_data_source_id: str
    artifacts_dir: Path
    log_dir: Path
    server_role: str
    # Auth + feature flags
    api_token: str | None
    require_auth: bool
    debug_endpoints: bool
    bridge_enabled: bool

    @classmethod
    def from_env(cls) -> "ColabServerConfig":
        repo_root = Path(__file__).resolve().parent.parent
        repo_default_sources = repo_root / "demo_data" / "data_sources.json"
        env_sources = os.environ.get("COLAB_DATA_SOURCES_PATH")
        if env_sources and Path(env_sources).exists():
            data_sources_path = Path(env_sources)
        else:
            data_sources_path = repo_default_sources

        default_artifacts = Path("/content/drive/MyDrive/nl2bi_colab/artifacts")
        default_logs = Path("/content/drive/MyDrive/nl2bi_colab/logs")
        artifacts_dir = Path(os.environ.get("COLAB_ARTIFACTS_DIR", str(default_artifacts)))
        log_dir = Path(os.environ.get("COLAB_LOG_DIR", str(default_logs)))

        # API token: env > Drive fallback files. Drive fallback exists because
        # the claude.ai Drive MCP can only write at MyDrive root.
        api_token = os.environ.get("COLAB_API_TOKEN") or _read_file_secret(
            Path("/content/drive/MyDrive/nl2bi_colab/.colab_api_token"),
            Path("/content/drive/MyDrive/.colab_api_token"),
        )

        return cls(
            model_id=os.environ.get("COLAB_MODEL_ID", "Qwen/Qwen2.5-Coder-7B-Instruct"),
            mock_model=_envbool("COLAB_MOCK_MODEL", False),
            quantization=os.environ.get("COLAB_QUANTIZATION", "4bit"),
            max_new_tokens=int(os.environ.get("COLAB_MAX_NEW_TOKENS", "512")),
            spider_db_root=Path(
                os.environ.get(
                    "COLAB_SPIDER_DB_ROOT",
                    "/content/drive/MyDrive/diploma_plan_sql/data/spider/database",
                )
            ),
            data_sources_path=data_sources_path,
            default_data_source_id=os.environ.get(
                "COLAB_DEFAULT_DATA_SOURCE_ID", "demo_concert_singer"
            ),
            artifacts_dir=artifacts_dir,
            log_dir=log_dir,
            server_role="colab-runtime",
            api_token=api_token,
            # Secure-by-default: if COLAB_REQUIRE_AUTH is unset, /extract and
            # /reload_model still require a Bearer token. Operators must
            # explicitly opt out with COLAB_REQUIRE_AUTH=false (don't).
            require_auth=_envbool("COLAB_REQUIRE_AUTH", True),
            debug_endpoints=_envbool("COLAB_DEBUG_ENDPOINTS", False),
            bridge_enabled=_envbool("COLAB_BRIDGE_ENABLED", False),
        )


def load_data_sources(config: ColabServerConfig) -> dict[str, dict[str, str]]:
    """Map of data_source.id -> {db_name, sqlite_path, name?, schema_version?}.

    Keys starting with `_` are treated as comments/documentation (e.g. `_doc`)
    and excluded from the returned map.
    """
    if not config.data_sources_path.exists():
        return {}
    try:
        raw = json.loads(config.data_sources_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def resolve_sqlite_path(
    config: ColabServerConfig,
    data_source_id: str,
) -> Path | None:
    """Legacy SQLite-only resolver kept for backward compatibility.

    New callers should use resolve_data_source() which returns a full
    DataSourceSpec (engine, dsn, etc). This function returns None for
    non-sqlite engines.
    """
    spec = resolve_data_source(config, data_source_id)
    if spec is None or spec.engine != "sqlite":
        return None
    return spec.path


def resolve_data_source(
    config: ColabServerConfig,
    data_source_id: str,
):
    """Build a DataSourceSpec for the given id, supporting multi-engine.

    Returns None if the source isn't known and there's no matching sqlite
    file in the spider_db_root fallback.

    Per-entry shape in data_sources.json (new, optional fields):
      {
        "db_name": "concert_singer",
        "name": "Spider concert_singer",
        "engine": "sqlite" | "duckdb" | "postgres",
        "path": "/optional/abs/path",
        "dsn": "postgresql://...",
        "schema_version": "..."
      }
    Backward-compat: entries without "engine" are treated as sqlite, and
    resolution falls back to spider_db_root/<db_name>/<db_name>.sqlite.
    """
    # Lazy import to avoid circular ref at module load.
    from colab.db_engine import DataSourceSpec

    sources = load_data_sources(config)
    entry = sources.get(data_source_id)
    if entry is None:
        # Fallback: try Spider directory layout.
        candidate = config.spider_db_root / data_source_id / f"{data_source_id}.sqlite"
        if candidate.exists():
            return DataSourceSpec(
                id=data_source_id,
                engine="sqlite",
                path=candidate,
                name=data_source_id,
                db_name=data_source_id,
            )
        return None

    engine = (entry.get("engine") or "sqlite").lower()
    name = entry.get("name")
    db_name = entry.get("db_name", data_source_id)
    schema_version = entry.get("schema_version")

    if engine == "sqlite":
        explicit = entry.get("path") or entry.get("sqlite_path")
        if explicit:
            path = Path(explicit)
        else:
            path = config.spider_db_root / db_name / f"{db_name}.sqlite"
        return DataSourceSpec(
            id=data_source_id,
            engine="sqlite",
            path=path,
            name=name,
            db_name=db_name,
            schema_version=schema_version,
        )
    if engine == "duckdb":
        explicit = entry.get("path")
        if not explicit:
            return None
        return DataSourceSpec(
            id=data_source_id,
            engine="duckdb",
            path=Path(explicit),
            name=name,
            db_name=db_name,
            schema_version=schema_version,
        )
    if engine == "postgres":
        dsn = entry.get("dsn")
        if not dsn:
            return None
        pg_schemas = tuple(entry.get("pg_schemas") or ("public",))
        return DataSourceSpec(
            id=data_source_id,
            engine="postgres",
            dsn=dsn,
            name=name,
            db_name=db_name,
            schema_version=schema_version,
            pg_schemas=pg_schemas,
        )
    # Unknown engine — surface as missing.
    return None
