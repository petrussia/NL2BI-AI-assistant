from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status

from services.gateway.api.deps import AUTH_COOKIE_NAME, get_auth_service, get_current_user
from services.gateway.api.schemas import LoginRequest, MessageResponse, RegisterRequest, UserResponse
from services.gateway.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=12 * 3600,
        path="/",
        httponly=True,
        samesite="lax",
        secure=False,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    try:
        result = auth_service.register(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _set_cookie(response, result["token"])
    return UserResponse(username=result["username"], role=result["role"])


@router.post("/login", response_model=UserResponse)
def login(
    body: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    try:
        result = auth_service.authenticate(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    _set_cookie(response, result["token"])
    return UserResponse(username=result["username"], role=result["role"])


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response) -> MessageResponse:
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return MessageResponse(message="Logged out.")


@router.get("/me")
def me(
    token: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, object]:
    if not token:
        return {"authenticated": False}
    current_user = auth_service.verify_token(token)
    if current_user is None:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "username": current_user["username"],
        "role": current_user["role"],
    }
