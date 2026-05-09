from __future__ import annotations

from typing import Any

from contracts.extraction import FieldMetadata, ResultTable


def _vega_type(field: FieldMetadata) -> str:
    if field.data_type in {"date", "datetime"}:
        return "temporal"
    if field.data_type == "number":
        return "quantitative"
    if field.data_type == "boolean":
        return "nominal"
    return "nominal"


def chart_spec(
    *,
    chart_type: str,
    title: str,
    x_field: FieldMetadata,
    y_field: FieldMetadata | None,
    table: ResultTable,
) -> dict[str, Any]:
    mark = {"line": "line", "bar": "bar", "scatter": "point"}.get(chart_type, "bar")
    encoding: dict[str, Any] = {
        "x": {
            "field": x_field.name,
            "type": _vega_type(x_field),
            "title": x_field.display_name or x_field.name,
        }
    }
    if y_field is not None:
        y_encoding: dict[str, Any] = {
            "field": y_field.name,
            "type": _vega_type(y_field),
            "title": y_field.display_name or y_field.name,
        }
        if y_field.default_aggregation and y_field.default_aggregation != "none":
            y_encoding["aggregate"] = y_field.default_aggregation
        encoding["y"] = y_encoding
    return {
        "mark": mark,
        "encoding": encoding,
        "data": {"values": table.rows[:100]},
        "title": title,
    }


def table_spec(title: str, table: ResultTable) -> dict[str, Any]:
    return {
        "type": "table",
        "title": title,
        "columns": table.columns,
        "rows": table.rows[:100],
        "row_count": table.row_count,
        "truncated": table.truncated or table.row_count > 100,
    }

