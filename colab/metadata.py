from __future__ import annotations

import re
from typing import Any

from contracts.extraction import (
    Aggregation,
    DataType,
    FieldMetadata,
    FieldProvenance,
    SemanticRole,
)
from colab.schema_loader import DatabaseSchema


_NUMBER_TYPES = {"int", "integer", "real", "numeric", "decimal", "float", "double", "number"}
_DATETIME_TYPES = {"datetime", "timestamp"}
_DATE_TYPES = {"date"}
_BOOLEAN_TYPES = {"boolean", "bool"}

_AGG_ALIAS_RE = re.compile(
    r"\b(sum|avg|min|max|count|count_distinct)\s*\(\s*([^)]+)\)\s+as\s+([a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)
_AGG_NAKED_RE = re.compile(
    r"\b(sum|avg|min|max|count)\s*\(\s*([^)]+)\)",
    re.IGNORECASE,
)


def _normalize_sql_type(sql_type: str) -> str:
    if not sql_type:
        return ""
    return sql_type.strip().lower().split("(")[0]


def _data_type_from_sql(sql_type: str) -> DataType:
    norm = _normalize_sql_type(sql_type)
    if not norm:
        return "unknown"
    if norm in _DATETIME_TYPES:
        return "datetime"
    if norm in _DATE_TYPES:
        return "date"
    if norm in _BOOLEAN_TYPES:
        return "boolean"
    if any(norm.startswith(t) for t in _NUMBER_TYPES):
        return "number"
    if "char" in norm or "text" in norm or norm == "varchar":
        return "string"
    return "unknown"


def _data_type_from_values(values: list[Any]) -> DataType:
    samples = [v for v in values if v is not None]
    if not samples:
        return "unknown"
    if all(isinstance(v, bool) for v in samples):
        return "boolean"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in samples):
        return "number"
    if all(isinstance(v, str) for v in samples):
        if all(re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", v) for v in samples):
            return "date"
        if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}", v[:16]) for v in samples):
            return "datetime"
        return "string"
    return "unknown"


def _looks_time(name: str) -> bool:
    n = name.lower()
    return any(
        n == k or n.endswith(f"_{k}") or n.startswith(f"{k}_") or k in n
        for k in ("date", "time", "month", "year", "day", "week", "quarter")
    )


def _looks_id(name: str) -> bool:
    n = name.lower()
    return n == "id" or n.endswith("_id") or n.startswith("id_")


def _periodicity(name: str) -> str | None:
    n = name.lower()
    for p in ("day", "week", "month", "quarter", "year"):
        if p in n:
            return p
    return None


def _aggs_for_data_type(dt: DataType) -> tuple[list[Aggregation], Aggregation | None]:
    if dt == "number":
        return ["sum", "avg", "min", "max", "count"], "sum"
    if dt in ("date", "datetime"):
        return ["min", "max", "count"], "none"
    return ["count"], "none"


def _parse_aggregation_aliases(sql: str) -> dict[str, dict[str, str]]:
    """Returns alias -> {func, expression}."""
    found: dict[str, dict[str, str]] = {}
    for match in _AGG_ALIAS_RE.finditer(sql):
        func, expr, alias = match.group(1).lower(), match.group(2).strip(), match.group(3)
        found[alias] = {"func": func, "expression": expr}
    return found


def _parse_aggregation_no_alias(sql: str) -> dict[str, dict[str, str]]:
    """When the column name itself is the aggregate (no alias)."""
    found: dict[str, dict[str, str]] = {}
    for match in _AGG_NAKED_RE.finditer(sql):
        func, expr = match.group(1).lower(), match.group(2).strip()
        col = expr.split(".")[-1].strip().strip('"')
        found.setdefault(col, {"func": func, "expression": match.group(0)})
    return found


def infer_field_metadata(
    columns: list[str],
    column_sql_types: dict[str, str],
    sample_rows: list[dict[str, Any]],
    sql: str,
    schema: DatabaseSchema | None,
) -> tuple[list[FieldMetadata], list[str]]:
    """Build FieldMetadata for each result column. Returns (items, warnings)."""
    warnings: list[str] = []
    alias_map = _parse_aggregation_aliases(sql)
    naked_map = _parse_aggregation_no_alias(sql)
    column_lookup = schema.column_lookup() if schema else {}

    out: list[FieldMetadata] = []
    for col in columns:
        sql_type = column_sql_types.get(col) or ""
        sample_values = [r.get(col) for r in sample_rows[:5] if r.get(col) is not None]
        data_type = _data_type_from_sql(sql_type)
        if data_type == "unknown":
            data_type = _data_type_from_values(sample_values)

        provenance_expr: str | None = None
        provenance_agg: str | None = None
        derived = False
        source_table: str | None = None
        source_column: str | None = None
        agg_hit = alias_map.get(col) or naked_map.get(col.lower())
        if agg_hit:
            provenance_expr = agg_hit["expression"]
            provenance_agg = agg_hit["func"]
            derived = True
            inner = agg_hit["expression"].split(".")[-1].strip().strip('"').lower()
            inner = re.sub(r"[^a-z0-9_]", "", inner)
            if inner in column_lookup:
                source_table, source_col_obj = column_lookup[inner]
                source_column = source_col_obj.name
        else:
            base_lookup = column_lookup.get(col.lower())
            if base_lookup is not None:
                source_table, source_col_obj = base_lookup
                source_column = source_col_obj.name
                if not sql_type:
                    sql_type = source_col_obj.sql_type
                    if data_type == "unknown":
                        data_type = _data_type_from_sql(sql_type)

        is_aggregate_numeric = derived and provenance_agg in {"sum", "avg", "count", "min", "max"}
        if is_aggregate_numeric and data_type == "unknown":
            data_type = "number"

        if data_type == "datetime" or data_type == "date" or _looks_time(col):
            role: SemanticRole = "time"
            if data_type == "unknown":
                data_type = "date"
        elif _looks_id(col) and not is_aggregate_numeric:
            role = "id"
        elif is_aggregate_numeric or data_type == "number":
            role = "measure"
        elif data_type == "string":
            role = "dimension"
        elif data_type == "boolean":
            role = "dimension"
        else:
            role = "unknown"

        allowed_aggs, default_agg = _aggs_for_data_type(data_type)
        if role == "id":
            allowed_aggs = ["count"]
            default_agg = "count"
        if role == "time":
            allowed_aggs = ["min", "max", "count"]
            default_agg = "none"
        if role == "dimension":
            allowed_aggs = ["count"]
            default_agg = "count"

        # Already-aggregated columns must not be aggregated again downstream.
        # Visualizer / chart adapter reads default_aggregation and would
        # double-count if it saw 'sum' / 'count' on a SUM(...) / COUNT(*)
        # alias. provenance.aggregation still carries the actual SQL function
        # for traceability.
        if derived and provenance_agg is not None:
            allowed_aggs = ["none"]
            default_agg = "none"

        examples: list[Any] = []
        for v in sample_values[:3]:
            try:
                if isinstance(v, (int, float, str, bool)) or v is None:
                    examples.append(v)
                else:
                    examples.append(str(v))
            except Exception:
                continue

        meta = FieldMetadata(
            name=col,
            source_table=source_table,
            source_column=source_column,
            display_name=None,
            description=None,
            sql_type=sql_type or None,
            data_type=data_type,
            semantic_role=role,
            unit=None,
            periodicity=_periodicity(col) if role == "time" else None,  # type: ignore[arg-type]
            allowed_aggregations=allowed_aggs,
            default_aggregation=default_agg,
            nullable=None,
            examples=examples,
            provenance=FieldProvenance(
                expression=provenance_expr,
                aggregation=provenance_agg,
                derived=derived,
            ),
        )
        out.append(meta)

    if any(m.data_type == "unknown" for m in out):
        warnings.append("metadata_incomplete")
    return out, warnings
