from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.extraction_client.colab_client import ColabExtractionClient
from services.gateway.api.deps import get_app_settings, get_auth_service
from services.gateway.api.routers.auth import get_current_user
from services.gateway.auth_service import AuthService
from services.gateway.config import Settings

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _client(settings: Settings) -> ColabExtractionClient:
    if settings.extraction_mode != "colab":
        raise HTTPException(status_code=503, detail="Colab extraction mode is not active.")
    return ColabExtractionClient(
        settings.text_to_sql_service_url,
        settings.text_to_sql_timeout_seconds,
        settings.text_to_sql_auth_token,
    )


@router.get("/models")
def list_models(
    settings: Settings = Depends(get_app_settings),
    current_user=Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),  # noqa: ARG001 — keep the auth dep
) -> dict[str, object]:
    """Proxy of GET /models on the Colab service.

    Authenticated users can list supported model ids; switching is also
    permitted (see /load_model). This is intentionally not gated by a separate
    admin role — the diploma MVP has a single role 'analyst' and the demo
    benefits from showing live model-switch capability to reviewers. Tighten
    via current_user.role before merging to a multi-tenant prod.
    """
    ok, payload = _client(settings).list_models()
    if not ok:
        raise HTTPException(status_code=502, detail=payload)
    return payload


class LoadModelRequest(BaseModel):
    model_id: str | None = None


@router.post("/load_model")
def load_model(
    body: LoadModelRequest,
    settings: Settings = Depends(get_app_settings),
    current_user=Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),  # noqa: ARG001
) -> dict[str, object]:
    """Proxy of POST /reload_model. Slow — UI must show a spinner.

    Forwards the optional model_id. Returns whatever Colab reports — including
    load_error when the requested model failed to load (then the next /extract
    will return model_not_loaded until the operator picks something else).
    """
    ok, payload = _client(settings).load_model(body.model_id)
    if not ok:
        raise HTTPException(status_code=502, detail=payload)
    return payload
