from __future__ import annotations

from fastapi import APIRouter, Depends

from services.extraction_client.colab_client import ColabExtractionClient
from services.gateway.api.deps import get_app_settings
from services.gateway.config import Settings

router = APIRouter(tags=["runtime"])


@router.get("/api/runtime")
def runtime(settings: Settings = Depends(get_app_settings)) -> dict[str, object]:
    payload: dict[str, object] = {
        "server_runtime": True,
        "gpu_in_backend": False,
        "extraction_mode": settings.extraction_mode,
        "visualization_mode": settings.visualization_mode,
        "artifact_storage": settings.artifact_storage,
        "colab_service_url_configured": bool(settings.text_to_sql_service_url),
        "server_allows_llm_imports": False,
        "debug_sql_visible": settings.debug_sql_visible,
    }
    if settings.extraction_mode == "colab":
        client = ColabExtractionClient(
            settings.text_to_sql_service_url,
            settings.text_to_sql_timeout_seconds,
        )
        available, health = client.health()
        payload["colab_available"] = available
        if available:
            payload["colab_health"] = health
        else:
            payload.update(health)
    return payload
