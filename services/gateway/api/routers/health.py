from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict[str, object]:
    return {"status": "ok", "service": "nl2bi-gateway"}


@router.get("/api/ready")
def ready() -> dict[str, object]:
    return {"status": "ready", "server_runtime": True, "gpu_in_backend": False}

