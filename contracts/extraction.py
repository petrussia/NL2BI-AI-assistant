from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from contracts.common import ContractModel, ErrorItem, Status, WarningItem


Dialect = Literal["sqlite", "postgresql", "clickhouse", "trino", "unknown"]
DataType = Literal["number", "string", "date", "datetime", "boolean", "unknown"]
SemanticRole = Literal["measure", "dimension", "time", "id", "text", "unknown"]
Aggregation = Literal["sum", "avg", "count", "min", "max", "none"]


class DataSourceRequest(ContractModel):
    id: str
    dialect: Dialect = "unknown"
    connection_ref: str | None = None
    schema_version: str | None = None


class DataSourceInfo(ContractModel):
    id: str
    name: str | None = None
    dialect: Dialect = "unknown"
    schema_version: str | None = None


class ExtractionConstraints(ContractModel):
    read_only: bool = True
    timeout_ms: int = 8000
    row_limit: int = 1000
    allow_llm_repair: bool = True


class PresentationHint(ContractModel):
    preferred_output: Literal["auto", "chart", "table"] = "auto"
    requested_fields: list[str] = Field(default_factory=list)
    requested_metrics: list[str] = Field(default_factory=list)


class DataExtractionRequest(ContractModel):
    request_id: str
    user_query: str
    locale: str = "ru-RU"
    timezone: str = "Europe/Moscow"
    data_source: DataSourceRequest
    constraints: ExtractionConstraints = Field(default_factory=ExtractionConstraints)
    presentation_hint: PresentationHint = Field(default_factory=PresentationHint)


class ExtractionPlan(ContractModel):
    raw: dict[str, Any] = Field(default_factory=dict)
    validated: bool = True
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


class SqlInfo(ContractModel):
    query: str | None = None
    dialect: Dialect = "unknown"
    validated: bool = True
    read_only: bool = True


class ResultTable(ContractModel):
    format: Literal["records"] = "records"
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    uri: str | None = None
    row_count: int = 0
    truncated: bool = False


class FieldProvenance(ContractModel):
    expression: str | None = None
    aggregation: str | None = None
    derived: bool = False


class FieldMetadata(ContractModel):
    name: str
    source_table: str | None = None
    source_column: str | None = None
    display_name: str | None = None
    description: str | None = None
    sql_type: str | None = None
    data_type: DataType = "unknown"
    semantic_role: SemanticRole = "unknown"
    unit: str | None = None
    periodicity: Literal["day", "week", "month", "quarter", "year"] | None = None
    allowed_aggregations: list[Aggregation] = Field(default_factory=list)
    default_aggregation: Aggregation | None = None
    nullable: bool | None = None
    examples: list[Any] = Field(default_factory=list)
    provenance: FieldProvenance = Field(default_factory=FieldProvenance)


class ExecutionInfo(ContractModel):
    latency_ms: int | None = None
    row_limit: int = 1000
    timeout_ms: int = 8000
    executable: bool = True


class QualityInfo(ContractModel):
    confidence: float | None = None
    warnings: list[str] = Field(default_factory=list)


class DataExtractionResponse(ContractModel):
    request_id: str
    status: Status
    user_query: str
    normalized_query: str | None = None
    data_source: DataSourceInfo
    plan: ExtractionPlan = Field(default_factory=ExtractionPlan)
    sql: SqlInfo = Field(default_factory=SqlInfo)
    result_table: ResultTable = Field(default_factory=ResultTable)
    field_metadata: list[FieldMetadata] = Field(default_factory=list)
    execution: ExecutionInfo = Field(default_factory=ExecutionInfo)
    quality: QualityInfo = Field(default_factory=QualityInfo)
    errors: list[ErrorItem] = Field(default_factory=list)
    warnings: list[WarningItem] = Field(default_factory=list)

