from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from contracts.nl2chart import Nl2ChartRequest, Nl2ChartResponse
from services.artifacts.store import LocalArtifactStore
from services.gateway.api.deps import get_artifact_store, get_orchestrator
from services.orchestrator.nl2chart_orchestrator import Nl2ChartOrchestrator

router = APIRouter(prefix="/api/nl2chart", tags=["nl2chart"])


@router.post("", response_model=Nl2ChartResponse)
def nl2chart(
    body: Nl2ChartRequest,
    orchestrator: Nl2ChartOrchestrator = Depends(get_orchestrator),
) -> Nl2ChartResponse:
    return orchestrator.run(body)


@router.get("/{request_id}")
def get_nl2chart_response(
    request_id: str,
    store: LocalArtifactStore = Depends(get_artifact_store),
) -> dict[str, object]:
    payload = store.read(f"{request_id}-response")
    if payload is None:
        raise HTTPException(status_code=404, detail="Response not found.")
    return payload

