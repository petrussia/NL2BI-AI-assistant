from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Status = Literal["success", "partial_success", "failed"]
ErrorSource = Literal[
    "server",
    "colab",
    "extraction",
    "adapter",
    "visualization",
    "frontend",
    "unknown",
]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ErrorItem(ContractModel):
    code: str
    message: str
    source: ErrorSource = "unknown"
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class WarningItem(ContractModel):
    code: str
    message: str
    source: ErrorSource = "unknown"
    details: dict[str, Any] = Field(default_factory=dict)


class ArtifactRef(ContractModel):
    artifact_id: str
    artifact_type: Literal[
        "table",
        "chart_spec",
        "chart_image",
        "warning",
        "error",
        "debug_sql",
        "response",
    ]
    title: str
    uri: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

