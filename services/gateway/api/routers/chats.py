from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from contracts.nl2chart import Nl2ChartRequest
from contracts.visualization import PresentationPreferences
from services.gateway.api.deps import get_auth_service, get_current_user, get_orchestrator
from services.gateway.api.schemas import (
    ChatMessageListResponse,
    ChatMessageResponse,
    ChatSessionListResponse,
    ChatSessionResponse,
    CreateChatRequest,
    MessageResponse,
    SendMessageRequest,
    SendMessageResponse,
    UpdateChatRequest,
)
from services.gateway.auth_service import AuthService
from services.orchestrator.nl2chart_orchestrator import Nl2ChartOrchestrator

router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.get("", response_model=ChatSessionListResponse)
def list_chats(
    current_user=Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> ChatSessionListResponse:
    return ChatSessionListResponse(
        sessions=[ChatSessionResponse(**item) for item in auth_service.list_sessions(current_user["username"])]
    )


@router.post("", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_chat(
    body: CreateChatRequest,
    current_user=Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> ChatSessionResponse:
    return ChatSessionResponse(**auth_service.create_session(current_user["username"], body.title))


@router.patch("/{session_id}", response_model=ChatSessionResponse)
def update_chat(
    session_id: str,
    body: UpdateChatRequest,
    current_user=Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> ChatSessionResponse:
    """Persist user-edited fields on a chat session. Today: title only."""
    if body.title is None:
        raise HTTPException(status_code=400, detail="Nothing to update.")
    try:
        updated = auth_service.update_chat_title(current_user["username"], session_id, body.title)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Chat session not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ChatSessionResponse(**updated)


@router.delete("/{session_id}", response_model=MessageResponse)
def delete_chat(
    session_id: str,
    current_user=Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    try:
        auth_service.delete_chat(current_user["username"], session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Chat session not found.") from exc
    return MessageResponse(message="deleted")


@router.get("/{session_id}/messages", response_model=ChatMessageListResponse)
def list_messages(
    session_id: str,
    current_user=Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> ChatMessageListResponse:
    try:
        messages = auth_service.list_messages(current_user["username"], session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Chat session not found.") from exc
    return ChatMessageListResponse(messages=[ChatMessageResponse(**item) for item in messages])


@router.post("/{session_id}/messages", response_model=SendMessageResponse)
def send_message(
    session_id: str,
    body: SendMessageRequest,
    current_user=Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    orchestrator: Nl2ChartOrchestrator = Depends(get_orchestrator),
) -> SendMessageResponse:
    # Persist the request settings on the user message metadata so that the
    # frontend's "Regenerate" can replay the original data_source + output
    # mode + response style, instead of using the (possibly-changed) current
    # global toggles. Also lets us show a per-message "Источник: …" badge
    # so old answers stay correctly attributed when the user later switches
    # the source dropdown.
    request_settings = {
        "data_source_id": body.data_source_id,
        "preferred_output": body.preferred_output,
        "response_style": body.response_style,
    }
    try:
        user_message = auth_service.add_message(
            username=current_user["username"],
            session_id=session_id,
            role="user",
            content=body.content,
            metadata={"request_settings": request_settings},
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Chat session not found.") from exc

    result = orchestrator.run(
        Nl2ChartRequest(
            user_query=body.content,
            data_source_id=body.data_source_id,
            presentation_preferences=PresentationPreferences(
                preferred_output=body.preferred_output,
                technical_mode=body.response_style == "technical",
            ),
        )
    )
    artifacts = [artifact.model_dump(mode="json") for artifact in result.artifacts]
    if result.warnings:
        artifacts.extend(
            {
                "artifact_id": f"{result.request_id}-warning-{idx}",
                "artifact_type": "warning",
                "title": warning.code,
                "uri": None,
                "payload": warning.model_dump(mode="json"),
                "metadata": {"request_id": result.request_id},
            }
            for idx, warning in enumerate(result.warnings)
        )
    if result.errors:
        artifacts.extend(
            {
                "artifact_id": f"{result.request_id}-error-{idx}",
                "artifact_type": "error",
                "title": error.code,
                "uri": None,
                "payload": error.model_dump(mode="json"),
                "metadata": {"request_id": result.request_id},
            }
            for idx, error in enumerate(result.errors)
        )

    assistant_message = auth_service.add_message(
        username=current_user["username"],
        session_id=session_id,
        role="assistant",
        content=result.message,
        metadata={
            "request_id": result.request_id,
            "status": result.status,
            "selected_view": result.selected_view,
            "debug": result.debug,
            # Mirror the user request settings so the UI can show a per-answer
            # "Источник: …" badge directly from message.metadata without
            # needing to chase the previous user message in the array.
            "request_settings": request_settings,
        },
        artifacts=artifacts,
    )
    return SendMessageResponse(
        user_message=ChatMessageResponse(**user_message),
        assistant_message=ChatMessageResponse(**assistant_message),
    )

