from __future__ import annotations

from contracts.common import ErrorItem
from contracts.visualization import VisualizationRequest


def validate_visualization_request(request: VisualizationRequest) -> list[ErrorItem]:
    errors: list[ErrorItem] = []
    columns = set(request.result_table.columns)
    if not columns:
        errors.append(
            ErrorItem(
                code="invalid_result_table",
                message="Нет колонок для визуализации.",
                source="visualization",
                retryable=False,
            )
        )
    for item in request.field_metadata:
        if item.name not in columns:
            errors.append(
                ErrorItem(
                    code="invalid_field_metadata",
                    message="Metadata ссылается на отсутствующую колонку.",
                    source="visualization",
                    retryable=False,
                    details={"field": item.name},
                )
            )
    return errors

