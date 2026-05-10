# NL2BI MVP Contracts

## 1. Shared envelope

```python
from typing import Any, Literal
from pydantic import BaseModel, Field

Status = Literal["success", "partial_success", "failed"]
ErrorCode = Literal[
    "schema_not_found",
    "ambiguous_query",
    "plan_invalid",
    "sql_generation_failed",
    "sql_validation_failed",
    "sql_execution_failed",
    "timeout",
    "empty_result",
    "row_limit_exceeded",
    "permission_denied",
    "metadata_incomplete",
    "visualization_failed",
    "render_failed",
    "invalid_request",
    "internal_error",
]

class ErrorItem(BaseModel):
    code: ErrorCode
    message: str
    source: Literal["gateway", "extract", "adapter", "visualize", "renderer", "frontend"]
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)

class WarningItem(BaseModel):
    code: str
    message: str
    source: Literal["gateway", "extract", "adapter", "visualize", "renderer"] = "adapter"
    details: dict[str, Any] = Field(default_factory=dict)
```

## 2. DataExtractionRequest

Запрос от общего backend к upstream-модулю Дениса.

```python
class UserContext(BaseModel):
    user_id: str | None = None
    permissions: list[str] = Field(default_factory=list)
    organization_id: str | None = None

class DataSourceRequest(BaseModel):
    id: str
    dialect: Literal["postgresql", "sqlite", "clickhouse", "trino", "unknown"] = "unknown"
    connection_ref: str | None = None
    schema_version: str | None = None

class ExtractionConstraints(BaseModel):
    read_only: bool = True
    timeout_ms: int = 8000
    row_limit: int = 1000
    max_joins: int | None = None
    allow_llm_repair: bool = True

class PresentationHint(BaseModel):
    preferred_output: Literal["chart", "table", "auto"] = "auto"
    requested_fields: list[str] = Field(default_factory=list)
    requested_metrics: list[str] = Field(default_factory=list)

class DataExtractionRequest(BaseModel):
    request_id: str
    user_query: str
    locale: str = "ru-RU"
    timezone: str = "Europe/Moscow"
    user_context: UserContext = Field(default_factory=UserContext)
    data_source: DataSourceRequest
    constraints: ExtractionConstraints = Field(default_factory=ExtractionConstraints)
    presentation_hint: PresentationHint = Field(default_factory=PresentationHint)
```

## 3. DataExtractionResponse

Ответ upstream-модуля Дениса. Это целевой `AnalyticsPayload v2`, совместимый с текущим `AnalyticsPayload v1` через adapter.

```python
class DataSourceResponse(BaseModel):
    id: str
    name: str | None = None
    dialect: Literal["postgresql", "sqlite", "clickhouse", "trino", "unknown"] = "unknown"
    schema_version: str | None = None

class SqlInfo(BaseModel):
    query: str | None = None
    dialect: str = "unknown"
    validated: bool = False
    read_only: bool = True

class ResultColumn(BaseModel):
    name: str
    data_type: Literal["number", "string", "date", "datetime", "boolean", "unknown"] = "unknown"
    sql_type: str | None = None

class ResultTable(BaseModel):
    format: Literal["records", "csv_uri", "arrow_uri"] = "records"
    columns: list[str]
    rows: list[dict[str, Any]] = Field(default_factory=list)
    uri: str | None = None
    row_count: int = 0
    truncated: bool = False

class PlanInfo(BaseModel):
    raw: dict[str, Any] = Field(default_factory=dict)
    validated: bool = False
    intent: str | None = None
    tables: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    aggregations: list[dict[str, Any]] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    order_by: list[dict[str, Any]] = Field(default_factory=list)
    limit: int | None = None
    joins: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

class Provenance(BaseModel):
    expression: str | None = None
    aggregation: str | None = None
    derived: bool = False

class FieldMetadata(BaseModel):
    name: str
    source_table: str | None = None
    source_column: str | None = None
    display_name: str | None = None
    description: str | None = None
    sql_type: str | None = None
    data_type: Literal["number", "string", "date", "datetime", "boolean", "unknown"] = "unknown"
    semantic_role: Literal["measure", "dimension", "time", "id", "text", "unknown"] = "unknown"
    unit: str | None = None
    periodicity: Literal["day", "week", "month", "quarter", "year"] | None = None
    allowed_aggregations: list[Literal["sum", "avg", "count", "min", "max", "none"]] = Field(default_factory=list)
    default_aggregation: Literal["sum", "avg", "count", "min", "max", "none"] | None = None
    nullable: bool | None = None
    examples: list[Any] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)

class ExecutionInfo(BaseModel):
    latency_ms: int | None = None
    row_limit: int | None = None
    timeout_ms: int | None = None
    executable: bool | None = None

class QualityInfo(BaseModel):
    confidence: float | None = None
    warnings: list[WarningItem] = Field(default_factory=list)

class DataExtractionResponse(BaseModel):
    request_id: str
    status: Status
    user_query: str
    normalized_query: str | None = None
    data_source: DataSourceResponse
    plan: PlanInfo = Field(default_factory=PlanInfo)
    sql: SqlInfo = Field(default_factory=SqlInfo)
    result_table: ResultTable
    field_metadata: list[FieldMetadata] = Field(default_factory=list)
    execution: ExecutionInfo = Field(default_factory=ExecutionInfo)
    quality: QualityInfo = Field(default_factory=QualityInfo)
    errors: list[ErrorItem] = Field(default_factory=list)
```

## 4. VisualizationRequest

Запрос от adapter/common backend к downstream-модулю Петра.

```python
class VisualizationDataSource(BaseModel):
    id: str
    name: str | None = None
    dialect: Literal["postgresql", "sqlite", "clickhouse", "trino", "unknown"] = "unknown"
    schema_version: str | None = None

class QueryContext(BaseModel):
    sql: str | None = None
    plan: dict[str, Any] | None = None
    filters: list[dict[str, Any]] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    aggregations: list[dict[str, Any]] = Field(default_factory=list)
    order_by: list[dict[str, Any]] = Field(default_factory=list)
    limit: int | None = None
    assumptions: list[str] = Field(default_factory=list)

class PresentationPreferences(BaseModel):
    preferred_output: Literal["chart", "table", "auto"] = "auto"
    preferred_chart_type: str | None = None
    style_template: str | None = None
    max_candidates: int = 3
    render: bool = True
    mode: Literal["fast", "quality", "fallback"] = "fast"

class VisualizationRequest(BaseModel):
    request_id: str
    user_query: str
    locale: str = "ru-RU"
    timezone: str = "Europe/Moscow"
    data_source: VisualizationDataSource
    result_table: ResultTable
    field_metadata: list[FieldMetadata]
    query_context: QueryContext = Field(default_factory=QueryContext)
    presentation_preferences: PresentationPreferences = Field(default_factory=PresentationPreferences)
```

## 5. VisualizationResponse

Ответ downstream-модуля Петра.

```python
class RenderedArtifacts(BaseModel):
    png_uri: str | None = None
    svg_uri: str | None = None
    html_uri: str | None = None
    spec_uri: str | None = None

class SelectedView(BaseModel):
    type: Literal["chart", "table"]
    chart_type: Literal["bar", "line", "scatter", "pie", "area", "histogram", "table", "unknown"] = "unknown"
    title: str = ""
    spec: dict[str, Any] = Field(default_factory=dict)
    normalized_spec: dict[str, Any] = Field(default_factory=dict)
    rendered_artifacts: RenderedArtifacts = Field(default_factory=RenderedArtifacts)

class CandidateView(BaseModel):
    type: Literal["chart", "table"]
    chart_type: str = "unknown"
    score: float | None = None
    reason: str = ""
    spec: dict[str, Any] = Field(default_factory=dict)

class TableView(BaseModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False

class Explanation(BaseModel):
    intent: str | None = None
    used_fields: list[str] = Field(default_factory=list)
    used_aggregations: list[dict[str, Any]] = Field(default_factory=list)
    reason: str = ""

class VisualizationQuality(BaseModel):
    confidence: float | None = None
    validation_passed: bool = False
    warnings: list[WarningItem] = Field(default_factory=list)

class VisualizationPerformance(BaseModel):
    latency_ms: int | None = None
    model: str | None = None
    mode: Literal["fast", "quality", "fallback"] = "fast"

class VisualizationResponse(BaseModel):
    request_id: str
    status: Status
    selected_view: SelectedView | None = None
    candidates: list[CandidateView] = Field(default_factory=list)
    table_view: TableView = Field(default_factory=TableView)
    explanation: Explanation = Field(default_factory=Explanation)
    quality: VisualizationQuality = Field(default_factory=VisualizationQuality)
    performance: VisualizationPerformance = Field(default_factory=VisualizationPerformance)
    errors: list[ErrorItem] = Field(default_factory=list)
```

## 6. Nl2ChartRequest / Nl2ChartResponse

Внешний endpoint общего backend для сайта/чата.

```python
class Nl2ChartRequest(BaseModel):
    request_id: str | None = None
    user_query: str
    data_source: DataSourceRequest | None = None
    locale: str = "ru-RU"
    timezone: str = "Europe/Moscow"
    constraints: ExtractionConstraints = Field(default_factory=ExtractionConstraints)
    presentation_preferences: PresentationPreferences = Field(default_factory=PresentationPreferences)

class Nl2ChartResponse(BaseModel):
    request_id: str
    status: Status
    assistant_message: str
    extraction: DataExtractionResponse | None = None
    visualization: VisualizationResponse | None = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[WarningItem] = Field(default_factory=list)
    errors: list[ErrorItem] = Field(default_factory=list)
```

## 7. Adapter rules

### data_type inference

| Input signal | Output |
|---|---|
| SQL numeric / pandas numeric / all values numeric | `number` |
| SQL date / ISO date strings / name contains date/day/month/year | `date` или `datetime` |
| boolean SQL / true-false values | `boolean` |
| text/categorical/mixed | `string` |
| ambiguous | `unknown` + warning |

### semantic_role inference

| Signal | Role |
|---|---|
| Date/datetime type or time-grain in plan | `time` |
| Numeric aggregated expression or metric-like name | `measure` |
| Low-cardinality string/category | `dimension` |
| id-like name: `id`, `_id`, UUID-like values | `id` |
| Long free-text strings | `text` |
| No confident signal | `unknown` |

### aggregation inference

| Field | allowed_aggregations | default_aggregation |
|---|---|---|
| measure, raw numeric | `sum, avg, min, max, count` | `sum` or `avg` by name/plan |
| measure, already aggregated | `none` | `none` |
| dimension | `count` | `count` |
| time | `count` or `none` | `none` |
| id/text | `count` or `none` | `none` |
