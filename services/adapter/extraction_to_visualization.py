from __future__ import annotations

from dataclasses import dataclass

from contracts.common import ErrorItem, WarningItem
from contracts.extraction import DataExtractionResponse, FieldMetadata, ResultTable
from contracts.visualization import PresentationPreferences, QueryContext, VisualizationRequest
from services.adapter.aggregation_inference import infer_allowed_aggregations, infer_default_aggregation
from services.adapter.role_inference import infer_semantic_role
from services.adapter.type_mapping import infer_data_type


@dataclass
class AdapterResult:
    request: VisualizationRequest
    warnings: list[WarningItem]


class AdapterError(Exception):
    def __init__(self, errors: list[ErrorItem], warnings: list[WarningItem] | None = None):
        super().__init__(errors[0].message if errors else "Adapter failed")
        self.errors = errors
        self.warnings = warnings or []


def _columns_from_table(table: ResultTable) -> list[str]:
    if table.columns:
        return table.columns
    if table.rows:
        return list(table.rows[0].keys())
    return []


def _validate_rows(table: ResultTable, columns: list[str]) -> None:
    expected = set(columns)
    for index, row in enumerate(table.rows):
        keys = set(row.keys())
        if not expected.issubset(keys):
            missing = sorted(expected - keys)
            raise AdapterError(
                [
                    ErrorItem(
                        code="invalid_result_table",
                        message="Строка результата не содержит все заявленные колонки.",
                        source="adapter",
                        retryable=False,
                        details={"row_index": index, "missing_columns": missing},
                    )
                ]
            )


def _metadata_by_name(response: DataExtractionResponse) -> dict[str, FieldMetadata]:
    return {item.name: item for item in response.field_metadata}


def adapt_extraction_to_visualization(
    response: DataExtractionResponse,
    preferences: PresentationPreferences | None = None,
) -> AdapterResult:
    warnings = list(response.warnings)
    if response.status == "failed":
        raise AdapterError(response.errors or [
            ErrorItem(
                code="extraction_failed",
                message="Извлечение данных завершилось ошибкой.",
                source="adapter",
                retryable=True,
            )
        ], warnings)

    columns = _columns_from_table(response.result_table)
    if not columns:
        raise AdapterError(
            [
                ErrorItem(
                    code="invalid_result_table",
                    message="Контракт извлечения не содержит список колонок.",
                    source="adapter",
                    retryable=False,
                )
            ],
            warnings,
        )
    _validate_rows(response.result_table, columns)

    metadata_by_name = _metadata_by_name(response)
    normalized_metadata: list[FieldMetadata] = []
    for column in columns:
        current = metadata_by_name.get(column)
        values = [row.get(column) for row in response.result_table.rows]
        data_type = current.data_type if current and current.data_type != "unknown" else infer_data_type(column, values)
        role = current.semantic_role if current and current.semantic_role != "unknown" else infer_semantic_role(column, data_type)
        allowed = list(current.allowed_aggregations) if current and current.allowed_aggregations else infer_allowed_aggregations(role)
        default = current.default_aggregation if current and current.default_aggregation else infer_default_aggregation(role)

        if current is None:
            warnings.append(
                WarningItem(
                    code="metadata_incomplete",
                    message=f"Metadata for column '{column}' was inferred.",
                    source="adapter",
                    details={"column": column},
                )
            )
            current = FieldMetadata(name=column)
        elif current.data_type == "unknown" or current.semantic_role == "unknown" or not current.allowed_aggregations:
            warnings.append(
                WarningItem(
                    code="metadata_incomplete",
                    message=f"Incomplete metadata for column '{column}' was completed by adapter.",
                    source="adapter",
                    details={"column": column},
                )
            )

        normalized_metadata.append(
            current.model_copy(
                update={
                    "data_type": data_type,
                    "semantic_role": role,
                    "allowed_aggregations": allowed,
                    "default_aggregation": default,
                }
            )
        )

    normalized_table = response.result_table.model_copy(
        update={
            "columns": columns,
            "row_count": len(response.result_table.rows),
        }
    )

    query_context = QueryContext(
        sql=response.sql.query,
        plan=response.plan.model_dump(mode="json"),
        filters=response.plan.filters,
        group_by=response.plan.group_by,
        aggregations=response.plan.aggregations,
        order_by=response.plan.order_by,
        limit=response.plan.limit,
        assumptions=response.plan.assumptions,
    )
    request = VisualizationRequest(
        request_id=response.request_id,
        user_query=response.user_query,
        locale="ru-RU",
        timezone="Europe/Moscow",
        data_source=response.data_source,
        result_table=normalized_table,
        field_metadata=normalized_metadata,
        query_context=query_context,
        presentation_preferences=preferences or PresentationPreferences(),
    )
    return AdapterResult(request=request, warnings=warnings)

