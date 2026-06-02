from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from contracts.extraction import FieldMetadata, FieldProvenance, ResultTable


YEAR_FIELD_RE = re.compile(r"(^|_)year$|^year_|^год$|_год$", re.IGNORECASE)
MONTH_FIELD_RE = re.compile(r"(^|_)month$|^month_|^месяц$|_месяц$", re.IGNORECASE)
MONTH_PERIOD_FIELD = "__period_month"
DEFAULT_INLINE_LIMIT = 100
DISTRIBUTION_INLINE_LIMIT = 1000


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


def _field_title(field: FieldMetadata) -> str:
    return field.display_name or field.name


def _tooltip_for(field: FieldMetadata) -> dict[str, Any]:
    return {
        "field": field.name,
        "type": _vega_type(field),
        "title": _field_title(field),
    }


def _inline_rows(table: ResultTable, *, limit: int = DEFAULT_INLINE_LIMIT) -> list[dict[str, Any]]:
    return table.rows[:limit]


def _x_encoding(field: FieldMetadata, table: ResultTable) -> dict[str, Any]:
    x_type = _vega_type(field)
    encoding: dict[str, Any] = {
        "field": field.name,
        "type": x_type,
        "title": _field_title(field),
    }
    if field.name == MONTH_PERIOD_FIELD:
        encoding["axis"] = {
            "format": "%Y-%m",
            "labelAngle": 0,
            "labelLimit": 80,
            "labelOverlap": "greedy",
        }
    elif x_type == "nominal":
        n_rows = len(table.rows)
        max_label_len = max(
            (len(str(r.get(field.name, ""))) for r in table.rows[:50]),
            default=0,
        )
        needs_rotation = n_rows > 5 or max_label_len > 12
        encoding["axis"] = {
            "labelAngle": -30 if needs_rotation else 0,
            "labelLimit": 160,
            "labelOverlap": "greedy",
        }
    return encoding


def _y_encoding(field: FieldMetadata, *, stack: str | None = None) -> dict[str, Any]:
    encoding: dict[str, Any] = {
        "field": field.name,
        "type": _vega_type(field),
        "title": _field_title(field),
    }
    if _should_aggregate_in_vega(field):
        encoding["aggregate"] = field.default_aggregation
    if stack is not None:
        encoding["stack"] = stack
    return encoding


def _color_encoding(field: FieldMetadata) -> dict[str, Any]:
    return {
        "field": field.name,
        "type": _vega_type(field),
        "title": _field_title(field),
    }


def chart_spec(
    *,
    chart_type: str,
    title: str,
    x_field: FieldMetadata,
    y_field: FieldMetadata | None,
    table: ResultTable,
    color_field: FieldMetadata | None = None,
) -> dict[str, Any]:
    if chart_type == "pie" and y_field is not None:
        theta = _y_encoding(y_field)
        encoding: dict[str, Any] = {
            "theta": theta,
            "color": _color_encoding(x_field),
            "tooltip": [_tooltip_for(x_field), _tooltip_for(y_field)],
        }
        return {
            "mark": {"type": "arc", "innerRadius": 52, "stroke": "#ffffff"},
            "encoding": encoding,
            "data": {"values": _inline_rows(table)},
            "title": title,
        }

    if chart_type == "histogram":
        encoding = {
            "x": {
                "field": x_field.name,
                "type": "quantitative",
                "bin": {"maxbins": 20},
                "title": _field_title(x_field),
            },
            "y": {"aggregate": "count", "type": "quantitative", "title": "Количество"},
            "tooltip": [
                {
                    "field": x_field.name,
                    "type": "quantitative",
                    "bin": {"maxbins": 20},
                    "title": _field_title(x_field),
                },
                {"aggregate": "count", "type": "quantitative", "title": "Количество"},
            ],
        }
        return {
            "mark": "bar",
            "encoding": encoding,
            "data": {"values": _inline_rows(table, limit=DISTRIBUTION_INLINE_LIMIT)},
            "title": title,
        }

    if chart_type == "boxplot":
        if y_field is None:
            y_encoding = _y_encoding(x_field)
            y_encoding.pop("aggregate", None)
            encoding = {"y": y_encoding}
        else:
            y_encoding = _y_encoding(y_field)
            y_encoding.pop("aggregate", None)
            encoding = {"x": _x_encoding(x_field, table), "y": y_encoding}
        return {
            "mark": {"type": "boxplot", "extent": "min-max"},
            "encoding": encoding,
            "data": {"values": _inline_rows(table, limit=DISTRIBUTION_INLINE_LIMIT)},
            "title": title,
        }

    if chart_type in {"line", "area", "multi_line", "bar", "stacked_bar"}:
        x_field, chart_table, tooltip_fields = _with_month_period_axis(x_field=x_field, table=table)
    else:
        chart_table = table
        tooltip_fields = []

    mark: str | dict[str, Any]
    if chart_type == "scatter":
        mark = "point"
    elif chart_type == "area":
        mark = {"type": "area", "line": True, "opacity": 0.45}
    elif chart_type == "heatmap":
        mark = "rect"
    elif chart_type in {"line", "multi_line"}:
        mark = {"type": "line", "point": True}
    else:
        mark = {"bar": "bar", "stacked_bar": "bar"}.get(chart_type, "bar")

    encoding: dict[str, Any] = {"x": _x_encoding(x_field, chart_table)}
    if chart_type == "heatmap" and y_field is not None and color_field is not None:
        color = _y_encoding(color_field)
        color["scale"] = {"scheme": "blues"}
        y_encoding = _x_encoding(y_field, chart_table)
        if "axis" in y_encoding:
            y_encoding["axis"]["labelAngle"] = 0
            y_encoding["axis"]["labelLimit"] = 120
        encoding["y"] = y_encoding
        encoding["color"] = color
        encoding["tooltip"] = [_tooltip_for(x_field), _tooltip_for(y_field), _tooltip_for(color_field)]
    elif y_field is not None:
        encoding["y"] = _y_encoding(y_field, stack="zero" if chart_type == "stacked_bar" else None)
        if chart_type == "scatter":
            encoding["y"].pop("aggregate", None)
        tooltip: list[dict[str, Any]] = [*tooltip_fields, _tooltip_for(x_field), _tooltip_for(y_field)]
        if color_field is not None:
            encoding["color"] = _color_encoding(color_field)
            tooltip.append(_tooltip_for(color_field))
        if tooltip_fields or color_field is not None or chart_type in {"scatter", "area", "stacked_bar", "multi_line"}:
            encoding["tooltip"] = tooltip
    return {
        "mark": mark,
        "encoding": encoding,
        "data": {"values": _inline_rows(chart_table)},
        "title": title,
    }


def precomputed_boxplot_spec(
    *,
    title: str,
    category_field: FieldMetadata,
    q1_field: FieldMetadata,
    median_field: FieldMetadata,
    q3_field: FieldMetadata,
    table: ResultTable,
    min_field: FieldMetadata | None = None,
    max_field: FieldMetadata | None = None,
) -> dict[str, Any]:
    """Render a boxplot from SQL-precomputed quartile columns.

    Vega-Lite's native boxplot mark expects raw values. Text-to-SQL models
    sometimes return one row per group with q1/median/q3 already calculated;
    this layered spec keeps that result visually faithful instead of falling
    back to a misleading bar chart over q1.
    """
    tooltip = [
        _tooltip_for(category_field),
        _tooltip_for(q1_field),
        _tooltip_for(median_field),
        _tooltip_for(q3_field),
    ]
    if min_field is not None:
        tooltip.append(_tooltip_for(min_field))
    if max_field is not None:
        tooltip.append(_tooltip_for(max_field))

    x_encoding = _x_encoding(category_field, table)
    box_layer: dict[str, Any] = {
        "mark": {"type": "bar", "size": 34, "color": "#2563eb", "opacity": 0.82},
        "encoding": {
            "x": x_encoding,
            "y": {"field": q1_field.name, "type": "quantitative", "title": _field_title(median_field)},
            "y2": {"field": q3_field.name},
            "tooltip": tooltip,
        },
    }
    median_layer: dict[str, Any] = {
        "mark": {"type": "tick", "size": 42, "thickness": 2, "color": "#111827"},
        "encoding": {
            "x": x_encoding,
            "y": {"field": median_field.name, "type": "quantitative", "title": _field_title(median_field)},
            "tooltip": tooltip,
        },
    }
    layers: list[dict[str, Any]] = []
    if min_field is not None and max_field is not None:
        layers.append(
            {
                "mark": {"type": "rule", "color": "#1f2937", "strokeWidth": 1.4},
                "encoding": {
                    "x": x_encoding,
                    "y": {"field": min_field.name, "type": "quantitative", "title": _field_title(median_field)},
                    "y2": {"field": max_field.name},
                    "tooltip": tooltip,
                },
            }
        )
    layers.extend([box_layer, median_layer])
    return {
        "layer": layers,
        "data": {"values": _inline_rows(table)},
        "title": title,
        "resolve": {"scale": {"y": "shared"}},
    }


def multi_measure_line_spec(
    *,
    title: str,
    x_field: FieldMetadata,
    measure_fields: list[FieldMetadata],
    table: ResultTable,
) -> dict[str, Any]:
    x_field, chart_table, tooltip_fields = _with_month_period_axis(x_field=x_field, table=table)
    folded_fields = [field.name for field in measure_fields[:6]]
    return {
        "mark": "line",
        "encoding": {
            "x": _x_encoding(x_field, chart_table),
            "y": {"field": "value", "type": "quantitative", "title": "Значение"},
            "color": {"field": "series", "type": "nominal", "title": "Показатель"},
            "tooltip": [
                *tooltip_fields,
                _tooltip_for(x_field),
                {"field": "series", "type": "nominal", "title": "Показатель"},
                {"field": "value", "type": "quantitative", "title": "Значение"},
            ],
        },
        "transform": [{"fold": folded_fields, "as": ["series", "value"]}],
        "data": {"values": _inline_rows(chart_table)},
        "title": title,
    }


def table_spec(title: str, table: ResultTable) -> dict[str, Any]:
    return {
        "type": "table",
        "title": title,
        "columns": table.columns,
        "rows": _inline_rows(table),
        "row_count": table.row_count,
        "truncated": table.truncated or table.row_count > 100,
    }
