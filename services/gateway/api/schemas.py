from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    username: str
    role: str = "analyst"


class MessageResponse(BaseModel):
    message: str


class CreateChatRequest(BaseModel):
    title: str | None = None


class ChatSessionResponse(BaseModel):
    session_id: str
    title: str
    created_at: int
    updated_at: int
    settings: dict[str, Any] = Field(default_factory=dict)


class ChatSessionListResponse(BaseModel):
    sessions: list[ChatSessionResponse]


class ChatMessageResponse(BaseModel):
    message_id: str
    session_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    created_at: int


class ChatMessageListResponse(BaseModel):
    messages: list[ChatMessageResponse]


class SendMessageRequest(BaseModel):
    content: str
    data_source_id: str = "demo_concert_singer"
    preferred_output: Literal["auto", "chart", "table"] = "auto"
    response_style: Literal["business", "technical"] = "business"


class SendMessageResponse(BaseModel):
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
