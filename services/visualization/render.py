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


def _should_aggregate_in_vega(field: FieldMetadata) -> bool:
    if not field.default_aggregation or field.default_aggregation == "none":
        return False
    if field.provenance.derived:
        return False
    if field.provenance.aggregation is not None:
        return False
    return True


def chart_spec(
    *,
    chart_type: str,
    title: str,
    x_field: FieldMetadata,
    y_field: FieldMetadata | None,
    table: ResultTable,
) -> dict[str, Any]:
    mark = {"line": "line", "bar": "bar", "scatter": "point"}.get(chart_type, "bar")
    x_type = _vega_type(x_field)
    x_encoding: dict[str, Any] = {
        "field": x_field.name,
        "type": x_type,
        "title": x_field.display_name or x_field.name,
    }
    if x_type == "nominal":
        n_rows = len(table.rows)
        max_label_len = max(
            (len(str(r.get(x_field.name, ""))) for r in table.rows[:50]),
            default=0,
        )
        needs_rotation = n_rows > 5 or max_label_len > 12
        x_encoding["axis"] = {
            "labelAngle": -30 if needs_rotation else 0,
            "labelLimit": 160,
            "labelOverlap": "greedy",
        }
    encoding: dict[str, Any] = {"x": x_encoding}
    if y_field is not None:
        y_encoding: dict[str, Any] = {
            "field": y_field.name,
            "type": _vega_type(y_field),
            "title": y_field.display_name or y_field.name,
        }
        if _should_aggregate_in_vega(y_field):
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
