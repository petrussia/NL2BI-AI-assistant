from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from services.artifacts.store import LocalArtifactStore
from services.gateway.api.deps import get_artifact_store

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


@router.get("/{artifact_id}")
def get_artifact(artifact_id: str, store: LocalArtifactStore = Depends(get_artifact_store)) -> dict[str, object]:
    payload = store.read(artifact_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return payload

