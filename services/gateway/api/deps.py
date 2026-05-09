from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import Cookie, Depends, HTTPException, status

from services.artifacts.store import LocalArtifactStore
from services.gateway.auth_service import AuthService
from services.gateway.config import Settings, get_settings
from services.orchestrator.nl2chart_orchestrator import Nl2ChartOrchestrator


AUTH_COOKIE_NAME = "nl2bi_auth"


@lru_cache(maxsize=1)
def cached_settings() -> Settings:
    return get_settings()


def get_app_settings() -> Settings:
    return cached_settings()


@lru_cache(maxsize=1)
def cached_auth_service() -> AuthService:
    settings = cached_settings()
    return AuthService(settings.auth_db_path, settings.auth_jwt_secret)


def get_auth_service() -> AuthService:
    return cached_auth_service()


def get_current_user(
    token: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, Any]:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    user = auth_service.verify_token(token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    return user


def get_artifact_store(settings: Settings = Depends(get_app_settings)) -> LocalArtifactStore:
    return LocalArtifactStore(settings.artifact_dir)


def get_orchestrator(settings: Settings = Depends(get_app_settings)) -> Nl2ChartOrchestrator:
    return Nl2ChartOrchestrator(settings=settings)

