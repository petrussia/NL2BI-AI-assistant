"""FastAPI Colab Text-to-SQL service.

Run from Colab notebook (or locally) with:

    uvicorn colab.text_to_sql_colab_server:app --host 0.0.0.0 --port 8000

In Colab, the bundled notebook (text_to_sql_colab_server.ipynb) handles
Drive mount, ngrok tunnel, and uvicorn startup.

Mock-model mode for HTTP smoke tests:

    COLAB_MOCK_MODEL=true uvicorn colab.text_to_sql_colab_server:app
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from contracts.common import ErrorItem  # noqa: E402
from contracts.extraction import (  # noqa: E402
    DataExtractionRequest,
    DataExtractionResponse,
    DataSourceInfo,
    ExecutionInfo,
    QualityInfo,
    SqlInfo,
)
from colab.config import ColabServerConfig, load_data_sources, resolve_sqlite_path  # noqa: E402
from colab.errors import SAFE_USER_MESSAGES, ExtractionErrorCode  # noqa: E402
from colab.extract_pipeline import run_extraction  # noqa: E402
from colab.gpu import gpu_info  # noqa: E402
from colab.model import TextToSqlModel  # noqa: E402

logger = logging.getLogger("colab.text_to_sql")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


_config = ColabServerConfig.from_env()
_model = TextToSqlModel(_config)
app = FastAPI(title="NL2BI Colab Text-to-SQL Service", version="0.1.0")


@app.on_event("startup")
def _on_startup() -> None:
    try:
        _config.artifacts_dir.mkdir(parents=True, exist_ok=True)
        _config.log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("could not create artifacts/log dirs: %s", exc)
    state = _model.load()
    logger.info(
        "model load: loaded=%s mock=%s id=%s err=%s",
        state.loaded,
        state.mock,
        state.model_id,
        state.load_error,
    )


def _health_payload() -> dict[str, object]:
    info = gpu_info()
    sqlite_root_exists = _config.spider_db_root.exists()
    return {
        "status": "ok",
        "model_loaded": _model.is_ready(),
        "model_id": _model.state.model_id or _config.model_id,
        "mock_model": _model.state.mock,
        "device": info["device"],
        "gpu_name": info["gpu_name"],
        "vram_total_gb": info["vram_total_gb"],
        "vram_free_gb": info["vram_free_gb"],
        "demo_db_ready": sqlite_root_exists,
        "server_role": _config.server_role,
    }


@app.get("/health")
def health() -> dict[str, object]:
    return _health_payload()


@app.get("/admin/bridge_url")
def admin_bridge_url() -> dict[str, object]:
    """Return the agent bridge URL recorded by colab.agent_bridge.start_bridge.

    Lets the agent fetch the (rotating) bridge URL through the stable FastAPI
    URL — i.e. with one known endpoint the agent can find both /extract (here)
    and /exec (the bridge), without the human re-pasting URLs after restarts.
    """
    marker_path = Path(
        os.environ.get(
            "COLAB_BRIDGE_URL_MARKER",
            "/content/drive/MyDrive/nl2bi_colab/.bridge_url",
        )
    )
    if not marker_path.exists():
        return {"bridge_url": None, "marker_path": str(marker_path), "exists": False}
    text = marker_path.read_text(encoding="utf-8").strip() or None
    return {"bridge_url": text, "marker_path": str(marker_path), "exists": True}


@app.get("/debug/datasources")
def debug_datasources() -> dict[str, object]:
    """Diagnose schema_not_found errors: list each id and whether its file exists."""
    sources = load_data_sources(_config)
    items: list[dict[str, object]] = []
    for ds_id in sorted(set(list(sources.keys()) + [_config.default_data_source_id])):
        path = resolve_sqlite_path(_config, ds_id)
        items.append({
            "data_source_id": ds_id,
            "resolved_path": str(path) if path else None,
            "exists": bool(path and path.exists()),
        })
    spider_root = _config.spider_db_root
    spider_root_exists = spider_root.exists()
    sample_db_dirs: list[str] = []
    if spider_root_exists:
        try:
            sample_db_dirs = sorted(p.name for p in spider_root.iterdir() if p.is_dir())[:30]
        except OSError:
            sample_db_dirs = []
    return {
        "data_sources_path": str(_config.data_sources_path),
        "data_sources_path_exists": _config.data_sources_path.exists(),
        "data_sources_loaded_keys": sorted(sources.keys()),
        "default_data_source_id": _config.default_data_source_id,
        "spider_db_root": str(spider_root),
        "spider_db_root_exists": spider_root_exists,
        "spider_db_root_first_dirs": sample_db_dirs,
        "data_source_resolutions": items,
    }


@app.post("/extract", response_model=DataExtractionResponse, response_model_exclude_none=False)
def extract(body: DataExtractionRequest) -> DataExtractionResponse:
    try:
        return run_extraction(body, _config, _model)
    except Exception as exc:  # noqa: BLE001
        logger.exception("extract failed: %s", exc)
        return DataExtractionResponse(
            request_id=body.request_id,
            status="failed",
            user_query=body.user_query,
            data_source=DataSourceInfo(
                id=body.data_source.id,
                dialect=body.data_source.dialect,
                schema_version=body.data_source.schema_version,
            ),
            sql=SqlInfo(query=None, dialect="sqlite", validated=False, read_only=True),
            execution=ExecutionInfo(
                latency_ms=None,
                row_limit=body.constraints.row_limit,
                timeout_ms=body.constraints.timeout_ms,
                executable=False,
            ),
            quality=QualityInfo(),
            errors=[
                ErrorItem(
                    code=ExtractionErrorCode.SQL_EXECUTION_FAILED.value,
                    message=SAFE_USER_MESSAGES[ExtractionErrorCode.SQL_EXECUTION_FAILED],
                    source="colab",
                    retryable=True,
                    details={"error_type": type(exc).__name__},
                )
            ],
        )


@app.post("/reload_model")
def reload_model() -> JSONResponse:
    _model._tokenizer = None  # type: ignore[attr-defined]
    _model._model = None  # type: ignore[attr-defined]
    _model.state = type(_model.state)(
        loaded=False,
        model_id=_config.model_id,
        mock=_config.mock_model,
        quantization=None,
    )
    new_state = _model.load()
    return JSONResponse(
        {
            "status": "ok" if new_state.loaded else "failed",
            "model_loaded": new_state.loaded,
            "model_id": new_state.model_id,
            "mock_model": new_state.mock,
            "load_error": new_state.load_error,
            "load_latency_ms": new_state.load_latency_ms,
        }
    )
