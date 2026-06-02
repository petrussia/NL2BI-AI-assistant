from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from contracts.common import ContractModel, ErrorItem, Status, WarningItem
from contracts.extraction import DataSourceInfo, FieldMetadata, ResultTable


ChartType = Literal[
    "bar",
    "line",
    "scatter",
    "pie",
    "area",
    "histogram",
    "stacked_bar",
    "multi_line",
    "heatmap",
    "boxplot",
    "table",
    "unknown",
]

PreferredChartType = Literal[
    "bar",
    "line",
    "scatter",
    "pie",
    "area",
    "histogram",
    "stacked_bar",
    "multi_line",
    "heatmap",
    "boxplot",
    "table",
]


class PresentationPreferences(ContractModel):
    preferred_output: Literal["auto", "chart", "table"] = "auto"
    preferred_chart_type: PreferredChartType | None = None
    style_template: str | None = None
    max_candidates: int = 3
    render: bool = True
    technical_mode: bool = False


class QueryContext(ContractModel):
    sql: str | None = None
    plan: dict[str, Any] = Field(default_factory=dict)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    aggregations: list[dict[str, Any]] = Field(default_factory=list)
    order_by: list[dict[str, Any]] = Field(default_factory=list)
    limit: int | None = None
    assumptions: list[str] = Field(default_factory=list)


class VisualizationRequest(ContractModel):
    request_id: str
    user_query: str
    locale: str = "ru-RU"
    timezone: str = "Europe/Moscow"
    data_source: DataSourceInfo
    result_table: ResultTable
    field_metadata: list[FieldMetadata] = Field(default_factory=list)
    query_context: QueryContext = Field(default_factory=QueryContext)
    presentation_preferences: PresentationPreferences = Field(default_factory=PresentationPreferences)


class RenderedArtifacts(ContractModel):
    png_uri: str | None = None
    svg_uri: str | None = None
    html_uri: str | None = None


class SelectedView(ContractModel):
    type: Literal["chart", "table"]
    chart_type: ChartType = "unknown"
    title: str
    spec: dict[str, Any] = Field(default_factory=dict)
    normalized_spec: dict[str, Any] = Field(default_factory=dict)
    rendered_artifacts: RenderedArtifacts = Field(default_factory=RenderedArtifacts)


class VisualizationCandidate(ContractModel):
    chart_type: ChartType
    score: float
    reason: str
    fields: list[str] = Field(default_factory=list)
    spec: dict[str, Any] = Field(default_factory=dict)


class VisualizationExplanation(ContractModel):
    intent: str | None = None
    used_fields: list[str] = Field(default_factory=list)
    used_aggregations: list[str] = Field(default_factory=list)
    reason: str = ""


class VisualizationQuality(ContractModel):
    confidence: float | None = None
    validation_passed: bool = True
    warnings: list[str] = Field(default_factory=list)


class VisualizationPerformance(ContractModel):
    latency_ms: int | None = None
    model: str = "local_cpu_rules"
    mode: Literal["fast", "fallback"] = "fast"


class VisualizationResponse(ContractModel):
    request_id: str
    status: Status
    selected_view: SelectedView
    candidates: list[VisualizationCandidate] = Field(default_factory=list)
    table_view: dict[str, Any] = Field(default_factory=dict)
    explanation: VisualizationExplanation = Field(default_factory=VisualizationExplanation)
    quality: VisualizationQuality = Field(default_factory=VisualizationQuality)
    performance: VisualizationPerformance = Field(default_factory=VisualizationPerformance)
    errors: list[ErrorItem] = Field(default_factory=list)
    warnings: list[WarningItem] = Field(default_factory=list)
