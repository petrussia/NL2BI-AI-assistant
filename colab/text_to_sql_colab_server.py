"""FastAPI Colab Text-to-SQL service.

Run from Colab notebook (or locally) with:

    uvicorn colab.text_to_sql_colab_server:app --host 0.0.0.0 --port 8000

In Colab, the bundled notebook (text_to_sql_colab_server.ipynb) handles
Drive mount, ngrok tunnel, and uvicorn startup.

Mock-model mode for HTTP smoke tests:

    COLAB_MOCK_MODEL=true uvicorn colab.text_to_sql_colab_server:app

Auth / feature flags (read by colab.config.ColabServerConfig.from_env):

    COLAB_API_TOKEN          shared secret for Bearer auth on /extract,
                             /reload_model, and gated endpoints. Resolved
                             from env or Drive-fallback files.
    COLAB_REQUIRE_AUTH       default TRUE — secure-by-default. /extract and
                             /reload_model require Authorization: Bearer
                             <COLAB_API_TOKEN>. Set to 'false' only with
                             explicit intent (private experiment).
    COLAB_DEBUG_ENDPOINTS    default FALSE — /debug/datasources is hidden
                             (404). When 'true', it is exposed but still
                             auth-gated.
    COLAB_BRIDGE_ENABLED     default FALSE — /admin/bridge_url is hidden
                             (404). When 'true', it is exposed but still
                             auth-gated.

Auth never logs the token (only the response status).
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

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
from colab.config import ColabServerConfig, load_data_sources, resolve_data_source, resolve_sqlite_path  # noqa: E402
from colab.errors import SAFE_USER_MESSAGES, ExtractionErrorCode  # noqa: E402
from colab.extract_pipeline import run_extraction  # noqa: E402
from colab.gpu import gpu_info  # noqa: E402
from colab.model import TextToSqlModel  # noqa: E402

logger = logging.getLogger("colab.text_to_sql")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


_config = ColabServerConfig.from_env()
_model = TextToSqlModel(_config)

# Optional planner — loaded when COLAB_PLANNER_MODEL_ID is set. Lives in
# a separate slot so the emitter (Qwen2.5-Coder-7B) and the planner
# (Qwen3-Coder-30B or any larger HF model) coexist in GPU VRAM. Use the
# `_PlannerConfig` shim so we don't pollute the main config.
class _PlannerConfig:
    def __init__(self, src: ColabServerConfig, model_id: str, quantization: str = "bf16"):
        self.model_id = model_id
        self.quantization = quantization
        self.max_new_tokens = max(512, src.max_new_tokens)
        self.mock_model = False


_planner_model_id = os.environ.get("COLAB_PLANNER_MODEL_ID", "").strip()
_planner: TextToSqlModel | None = None
if _planner_model_id:
    _planner_cfg = _PlannerConfig(
        _config,
        _planner_model_id,
        quantization=os.environ.get("COLAB_PLANNER_QUANTIZATION", "bf16"),
    )
    _planner = TextToSqlModel(_planner_cfg)  # shares interface; load() called by background task

app = FastAPI(title="NL2BI Colab Text-to-SQL Service", version="0.2.0")


def _validate_bearer(authorization: str | None) -> None:
    """Raise 401 if the Authorization header doesn't carry the configured token.

    Does NOT log the token — only the failure reason.
    """
    if not _config.api_token:
        raise HTTPException(status_code=503, detail="server has no api_token configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing or invalid Authorization header")
    token = authorization[len("Bearer "):].strip()
    if not token or token != _config.api_token:
        raise HTTPException(status_code=401, detail="invalid bearer token")


def require_api_auth(authorization: str | None = Header(None)) -> None:
    """Bearer auth dependency for /extract + /reload_model.

    No-op only when an operator has explicitly set COLAB_REQUIRE_AUTH=false.
    The default in colab.config.ColabServerConfig.from_env is True, so a
    missing env var keeps the endpoints locked.
    """
    if not _config.require_auth:
        return
    _validate_bearer(authorization)


def require_debug_enabled(authorization: str | None = Header(None)) -> None:
    """Gate /debug/* — must be explicitly enabled, and the call must auth.

    When disabled the endpoint pretends not to exist (404) so probes don't
    leak its presence.
    """
    if not _config.debug_endpoints:
        raise HTTPException(status_code=404, detail="Not Found")
    _validate_bearer(authorization)


def require_bridge_enabled(authorization: str | None = Header(None)) -> None:
    """Gate /admin/* — same shape as require_debug_enabled."""
    if not _config.bridge_enabled:
        raise HTTPException(status_code=404, detail="Not Found")
    _validate_bearer(authorization)


@app.on_event("startup")
def _on_startup() -> None:
    try:
        _config.artifacts_dir.mkdir(parents=True, exist_ok=True)
        _config.log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("could not create artifacts/log dirs: %s", exc)
    state = _model.load()
    logger.info(
        "emitter load: loaded=%s mock=%s id=%s err=%s",
        state.loaded,
        state.mock,
        state.model_id,
        state.load_error,
    )
    # Optional planner (Qwen3-Coder-30B BF16 or similar). Load in a
    # background thread so the emitter is usable while the planner spools
    # up — first load of a 30B model can take 5-10 min on a fresh kernel.
    if _planner is not None:
        def _bg_planner_load():
            try:
                logger.info("planner load starting: %s", _planner_model_id)
                ps = _planner.load(model_id_override=_planner_model_id)
                logger.info(
                    "planner load: loaded=%s id=%s err=%s",
                    ps.loaded, ps.model_id, ps.load_error,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("planner load failed: %s", exc)
        import threading
        threading.Thread(target=_bg_planner_load, daemon=True, name="planner-loader").start()
    # Never log token values; only whether each is configured.
    logger.info(
        "auth flags: require_auth=%s api_token_set=%s debug_endpoints=%s bridge_enabled=%s",
        _config.require_auth,
        bool(_config.api_token),
        _config.debug_endpoints,
        _config.bridge_enabled,
    )


def _health_payload() -> dict[str, object]:
    info = gpu_info()
    return {
        "status": "ok",
        "model_loaded": _model.is_ready(),
        "model_id": _model.state.model_id or _config.model_id,
        "mock_model": _model.state.mock,
        "planner_enabled": _planner is not None,
        "planner_loaded": (_planner.is_ready() if _planner is not None else False),
        "planner_id": (_planner.state.model_id if _planner is not None else None),
        "device": info["device"],
        "gpu_name": info["gpu_name"],
        "vram_total_gb": info["vram_total_gb"],
        "vram_free_gb": info["vram_free_gb"],
        "demo_db_ready": _config.spider_db_root.exists(),
        "server_role": _config.server_role,
        "auth": {
            "require_auth": _config.require_auth,
            "api_token_set": bool(_config.api_token),
            "debug_endpoints": _config.debug_endpoints,
            "bridge_enabled": _config.bridge_enabled,
        },
    }


@app.get("/health")
def health() -> dict[str, object]:
    return _health_payload()


@app.get("/debug/datasources", dependencies=[Depends(require_debug_enabled)])
def debug_datasources() -> dict[str, object]:
    """Diagnose schema_not_found errors: list each id and whether its file exists."""
    sources = load_data_sources(_config)
    items: list[dict[str, object]] = []
    for ds_id in sorted(set(list(sources.keys()) + [_config.default_data_source_id])):
        spec = resolve_data_source(_config, ds_id)
        entry: dict[str, object] = {"data_source_id": ds_id}
        if spec is None:
            entry["resolved"] = None
            entry["engine"] = None
            entry["exists"] = False
        else:
            entry["engine"] = spec.engine
            entry["name"] = spec.name
            if spec.engine in ("sqlite", "duckdb"):
                entry["resolved_path"] = str(spec.path) if spec.path else None
                entry["exists"] = bool(spec.path and spec.path.exists())
            elif spec.engine == "postgres":
                # Don't log full DSN (might contain password). Just signal presence.
                entry["dsn_set"] = bool(spec.dsn)
                entry["pg_schemas"] = list(spec.pg_schemas)
                entry["exists"] = bool(spec.dsn)
        items.append(entry)
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


@app.get("/admin/bridge_url", dependencies=[Depends(require_bridge_enabled)])
def admin_bridge_url() -> dict[str, object]:
    """Return the agent bridge URL recorded by colab.agent_bridge.start_bridge.

    Auth-gated. The returned URL itself is a credential; the gate prevents
    casual discovery of the bridge from anyone who can reach /admin/*.
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


@app.post(
    "/extract",
    response_model=DataExtractionResponse,
    response_model_exclude_none=False,
    dependencies=[Depends(require_api_auth)],
)
def extract(body: DataExtractionRequest) -> DataExtractionResponse:
    try:
        return run_extraction(body, _config, _model, planner=_planner)
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


# --- Curated catalog of HF models known to fit Colab L4 (22 GB VRAM, 4-bit) ---
SUPPORTED_MODELS: list[dict[str, object]] = [
    {
        "id": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "label": "Qwen2.5-Coder 7B (Instruct, 4-bit)",
        "approx_vram_gb": 6,
        "family": "Qwen",
        "default": True,
    },
    {
        "id": "Qwen/Qwen2.5-Coder-14B-Instruct",
        "label": "Qwen2.5-Coder 14B (Instruct, 4-bit)",
        "approx_vram_gb": 10,
        "family": "Qwen",
        "default": False,
    },
    {
        "id": "deepseek-ai/deepseek-coder-6.7b-instruct",
        "label": "DeepSeek-Coder 6.7B (Instruct, 4-bit)",
        "approx_vram_gb": 6,
        "family": "DeepSeek",
        "default": False,
    },
    {
        "id": "meta-llama/Meta-Llama-3.1-8B-Instruct",
        "label": "Llama 3.1 8B (Instruct, 4-bit) — gated, may fail",
        "approx_vram_gb": 7,
        "family": "Llama",
        "default": False,
    },
]


@app.get("/models")
def list_models() -> dict[str, object]:
    """Curated catalog of HF model ids the operator can switch to.

    No auth so the frontend can populate the picker even when the user isn't
    authenticated to the gateway — the actual load operation is auth-gated.
    """
    current = _model.state.model_id or _config.model_id
    return {
        "current": current,
        "loaded": _model.is_ready(),
        "load_error": _model.state.load_error,
        "models": SUPPORTED_MODELS,
    }


class ReloadModelRequest(BaseModel):
    model_id: str | None = None


@app.post("/reload_model", dependencies=[Depends(require_api_auth)])
def reload_model(body: ReloadModelRequest | None = None) -> JSONResponse:
    requested = (body.model_id if body else None) or _config.model_id
    # Drop the current model first to free VRAM, then load the requested one.
    _model.unload()
    new_state = _model.load(model_id_override=requested)
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
