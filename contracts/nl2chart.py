from __future__ import annotations

from typing import Any

from pydantic import Field

from contracts.common import ArtifactRef, ContractModel, ErrorItem, Status, WarningItem
from contracts.visualization import PresentationPreferences


class Nl2ChartRequest(ContractModel):
    user_query: str
    data_source_id: str = "demo_sales"
    locale: str = "ru-RU"
    timezone: str = "Europe/Moscow"
    presentation_preferences: PresentationPreferences = Field(default_factory=PresentationPreferences)


class Nl2ChartResponse(ContractModel):
    request_id: str
    status: Status
    message: str
    selected_view: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    warnings: list[WarningItem] = Field(default_factory=list)
    errors: list[ErrorItem] = Field(default_factory=list)
    debug: dict[str, Any] = Field(default_factory=dict)

