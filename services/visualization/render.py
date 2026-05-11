from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from contracts.extraction import FieldMetadata, FieldProvenance, ResultTable


YEAR_FIELD_RE = re.compile(r"(^|_)year$|^year_|^год$|_год$", re.IGNORECASE)
MONTH_FIELD_RE = re.compile(r"(^|_)month$|^month_|^месяц$|_месяц$", re.IGNORECASE)
MONTH_PERIOD_FIELD = "__period_month"


def _is_year_field(name: str) -> bool:
    return bool(YEAR_FIELD_RE.search(name))


def _is_month_field(name: str) -> bool:
    return bool(MONTH_FIELD_RE.search(name))


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
    return None


def _field_by_name(columns: list[str], predicate: Callable[[str], bool]) -> str | None:
    for column in columns:
        if predicate(column):
            return column
    return None


def _with_month_period_axis(
    *,
    x_field: FieldMetadata,
    table: ResultTable,
) -> tuple[FieldMetadata, ResultTable, list[dict[str, Any]]]:
    """Turn YEAR + MONTH result columns into a single temporal chart axis."""
    columns = table.columns or (list(table.rows[0].keys()) if table.rows else [])
    year_col = _field_by_name(columns, _is_year_field)
    month_col = _field_by_name(columns, _is_month_field)
    if not year_col or not month_col:
        return x_field, table, []
    if x_field.name not in {year_col, month_col}:
        return x_field, table, []

    rows: list[dict[str, Any]] = []
    for row in table.rows:
        year = _coerce_int(row.get(year_col))
        month = _coerce_int(row.get(month_col))
        if year is None or month is None or not 1 <= month <= 12:
            return x_field, table, []
        enriched = dict(row)
        enriched[MONTH_PERIOD_FIELD] = f"{year:04d}-{month:02d}-01"
        rows.append(enriched)

    period_field = FieldMetadata(
        name=MONTH_PERIOD_FIELD,
        display_name="Месяц",
        data_type="date",
        semantic_role="time",
        periodicity="month",
        allowed_aggregations=["none"],
        default_aggregation="none",
        provenance=FieldProvenance(
            expression=f"{year_col}, {month_col}",
            aggregation=None,
            derived=True,
        ),
    )
    chart_table = table.model_copy(update={"rows": rows})
    tooltips = [
        {"field": year_col, "type": "ordinal", "title": "Год"},
        {"field": month_col, "type": "ordinal", "title": "Месяц"},
    ]
    return period_field, chart_table, tooltips


def _vega_type(field: FieldMetadata) -> str:
    if field.data_type in {"date", "datetime"}:
        return "temporal"
    if field.semantic_role == "time" and field.data_type == "number":
        return "ordinal"
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
    x_field, chart_table, tooltip_fields = _with_month_period_axis(x_field=x_field, table=table)
    mark = {"line": "line", "bar": "bar", "scatter": "point"}.get(chart_type, "bar")
    x_type = _vega_type(x_field)
    x_encoding: dict[str, Any] = {
        "field": x_field.name,
        "type": x_type,
        "title": x_field.display_name or x_field.name,
    }
    if x_field.name == MONTH_PERIOD_FIELD:
        x_encoding["axis"] = {
            "format": "%Y-%m",
            "labelAngle": 0,
            "labelLimit": 80,
            "labelOverlap": "greedy",
        }
    if x_type == "nominal":
        n_rows = len(chart_table.rows)
        max_label_len = max(
            (len(str(r.get(x_field.name, ""))) for r in chart_table.rows[:50]),
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
        if tooltip_fields:
            encoding["tooltip"] = [
                *tooltip_fields,
                {
                    "field": y_field.name,
                    "type": _vega_type(y_field),
                    "title": y_field.display_name or y_field.name,
                },
            ]
    return {
        "mark": mark,
        "encoding": encoding,
        "data": {"values": chart_table.rows[:100]},
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
