"""Rule-based post-query Text-to-Visualization baseline."""

from __future__ import annotations

import re
from time import perf_counter
from dataclasses import dataclass
from typing import Any

import pandas as pd

from t2v_eval.data.schema import FieldMetadata, T2VExample, T2VPrediction
from t2v_eval.normalization.vega_lite import normalize_spec

try:
    import psutil
except ModuleNotFoundError:  # pragma: no cover - dependency is in requirements.
    psutil = None  # type: ignore[assignment]


METHOD_NAME = "B0_rule_based"

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_AGGREGATE_MEASURE_PREFIXES = ("count(", "sum(", "avg(", "mean(", "min(", "max(")


@dataclass(slots=True)
class Candidate:
    raw_spec: dict[str, Any]
    score: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_spec": self.raw_spec,
            "normalized_spec": normalize_spec(self.raw_spec),
            "score": round(self.score, 6),
            "reason": self.reason,
        }


def predict(example: T2VExample, *, run_id: str, top_k: int = 5) -> T2VPrediction:
    start = perf_counter()
    start_memory = _memory_mb()
    try:
        candidates = generate_candidates(example, top_k=top_k)
        latency_ms = _elapsed_ms(start)
        memory_peak_mb = max(value for value in (start_memory, _memory_mb()) if value is not None) if start_memory is not None else _memory_mb()
        if not candidates:
            return T2VPrediction.failed(
                run_id=run_id,
                method=METHOD_NAME,
                example_id=example.example_id,
                error="no compatible rule-based candidate",
                latency_ms=latency_ms,
            )
        best = candidates[0]
        return T2VPrediction(
            run_id=run_id,
            method=METHOD_NAME,
            example_id=example.example_id,
            status="ok",
            raw_spec=best.raw_spec,
            normalized_spec=normalize_spec(best.raw_spec),
            candidates=[candidate.to_dict() for candidate in candidates],
            latency_ms=latency_ms,
            memory_peak_mb=memory_peak_mb,
        )
    except Exception as exc:  # pragma: no cover - safety path for batch runs.
        return T2VPrediction.failed(
            run_id=run_id,
            method=METHOD_NAME,
            example_id=example.example_id,
            error=str(exc),
            latency_ms=_elapsed_ms(start),
        )


def generate_candidates(example: T2VExample, *, top_k: int = 5) -> list[Candidate]:
    fields = load_fields(example)
    if not fields:
        return []
    intent = detect_intent(example.query)
    linked = rank_fields(example.query, fields)

    time_fields = _fields_by_kind(linked, {"time"})
    numeric_fields = _fields_by_kind(linked, {"measure", "numeric"})
    categorical_fields = _fields_by_kind(linked, {"dimension", "categorical", "id"})

    candidates: list[Candidate] = []

    if intent == "table":
        field = linked[0] if linked else fields[0]
        candidates.append(Candidate(_text_spec(field), 1.0, "table/detail intent"))

    if intent in {"trend", "dashboard"} and time_fields and numeric_fields:
        candidates.append(
            Candidate(
                _line_spec(time_fields[0], numeric_fields[0]),
                0.95,
                "time + numeric -> line",
            )
        )

    if intent == "correlation" and len(numeric_fields) >= 2:
        candidates.append(
            Candidate(
                _scatter_spec(numeric_fields[0], numeric_fields[1]),
                0.95,
                "two numeric fields -> scatter",
            )
        )

    if intent == "distribution" and numeric_fields:
        candidates.append(
            Candidate(
                _histogram_spec(numeric_fields[0]),
                0.95,
                "one numeric distribution -> binned bar",
            )
        )

    if intent == "top" and categorical_fields and numeric_fields:
        candidates.append(
            Candidate(
                _bar_spec(categorical_fields[0], numeric_fields[0], sort="-y"),
                0.95,
                "top/ranking -> sorted bar",
            )
        )

    if categorical_fields and numeric_fields:
        candidates.append(
            Candidate(
                _bar_spec(categorical_fields[0], numeric_fields[0]),
                0.8,
                "categorical + numeric -> bar",
            )
        )

    if time_fields and numeric_fields:
        candidates.append(
            Candidate(
                _line_spec(time_fields[0], numeric_fields[0]),
                0.75,
                "fallback time + numeric -> line",
            )
        )

    if len(numeric_fields) >= 2:
        candidates.append(
            Candidate(
                _scatter_spec(numeric_fields[0], numeric_fields[1]),
                0.7,
                "fallback two numeric -> scatter",
            )
        )

    if numeric_fields:
        candidates.append(
            Candidate(
                _histogram_spec(numeric_fields[0]),
                0.55,
                "fallback numeric distribution",
            )
        )

    if not candidates and linked:
        candidates.append(Candidate(_text_spec(linked[0]), 0.25, "last resort text"))

    unique: list[Candidate] = []
    seen: set[str] = set()
    for candidate in sorted(candidates, key=lambda item: item.score, reverse=True):
        key = normalize_spec(candidate.raw_spec)["canonical_json"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique[:top_k]


def detect_intent(query: str) -> str:
    text = query.lower()
    if any(word in text for word in ("dashboard", "overview", "summary panel")):
        return "dashboard"
    if any(word in text for word in ("table", "list", "detail", "records", "rows")):
        return "table"
    if any(word in text for word in ("top", "highest", "lowest", "rank", "ranking", "best", "worst")):
        return "top"
    if any(word in text for word in ("correlation", "relationship", "scatter", "versus", " vs ")):
        return "correlation"
    if any(word in text for word in ("distribution", "histogram", "spread", "frequency")):
        return "distribution"
    if any(word in text for word in ("trend", "over time", "timeline", "year", "month", "date")):
        return "trend"
    if any(word in text for word in ("compare", "comparison", "by ", "across", "versus")):
        return "comparison"
    return "comparison"


def rank_fields(query: str, fields: list[FieldMetadata]) -> list[FieldMetadata]:
    query_tokens = _tokens(query)

    def score(field: FieldMetadata) -> tuple[float, str]:
        haystack = " ".join(
            part
            for part in [field.name, field.description or "", field.unit or ""]
            if part
        )
        field_tokens = _tokens(haystack)
        overlap = len(query_tokens & field_tokens)
        exact = 1.0 if field.name.lower() in query.lower() else 0.0
        role_prior = {"time": 0.2, "measure": 0.15, "dimension": 0.1, "id": 0.05}.get(
            field.role,
            0.0,
        )
        return (exact * 2.0 + overlap + role_prior, field.name)

    return sorted(fields, key=score, reverse=True)


def load_fields(example: T2VExample) -> list[FieldMetadata]:
    fields = example.fields
    if fields:
        return fields
    try:
        df = pd.read_csv(example.table, nrows=50)
    except Exception:
        return []
    inferred: list[FieldMetadata] = []
    for column in df.columns:
        dtype = str(df[column].dtype)
        role = "unknown"
        if pd.api.types.is_datetime64_any_dtype(df[column]) or "date" in column.lower():
            role = "time"
        elif pd.api.types.is_numeric_dtype(df[column]):
            role = "measure"
        else:
            role = "dimension"
        inferred.append(
            FieldMetadata(
                name=str(column),
                dtype=dtype,
                role=role,
                allowed_aggregations=["sum", "mean", "min", "max", "count"]
                if role == "measure"
                else ["count"],
            )
        )
    return inferred


def _bar_spec(category: FieldMetadata, measure: FieldMetadata, *, sort: str | None = None) -> dict[str, Any]:
    x: dict[str, Any] = {"field": category.name, "type": _vega_type(category)}
    if sort:
        x["sort"] = sort
    return {
        "mark": "bar",
        "encoding": {
            "x": x,
            "y": {
                "field": measure.name,
                "type": "quantitative",
                "aggregate": _default_aggregate(measure),
            },
        },
    }


def _line_spec(time_field: FieldMetadata, measure: FieldMetadata) -> dict[str, Any]:
    return {
        "mark": "line",
        "encoding": {
            "x": {"field": time_field.name, "type": "temporal"},
            "y": {
                "field": measure.name,
                "type": "quantitative",
                "aggregate": _default_aggregate(measure),
            },
        },
    }


def _scatter_spec(x_measure: FieldMetadata, y_measure: FieldMetadata) -> dict[str, Any]:
    return {
        "mark": "point",
        "encoding": {
            "x": {"field": x_measure.name, "type": "quantitative"},
            "y": {"field": y_measure.name, "type": "quantitative"},
        },
    }


def _histogram_spec(measure: FieldMetadata) -> dict[str, Any]:
    return {
        "mark": "bar",
        "encoding": {
            "x": {"field": measure.name, "type": "quantitative", "bin": True},
            "y": {"aggregate": "count", "type": "quantitative"},
        },
    }


def _text_spec(field: FieldMetadata) -> dict[str, Any]:
    return {
        "mark": "text",
        "encoding": {
            "text": {"field": field.name, "type": _vega_type(field)},
        },
    }


def _fields_by_kind(fields: list[FieldMetadata], kinds: set[str]) -> list[FieldMetadata]:
    return [field for field in fields if _kind(field) in kinds or field.role in kinds]


def _kind(field: FieldMetadata) -> str:
    dtype = field.dtype.lower()
    name = field.name.lower()
    if _is_aggregate_measure(field):
        return "numeric"
    if field.role == "time" or "date" in name or "time" in name or "year" in name:
        return "time"
    if field.role == "measure" or any(token in dtype for token in ("int", "float", "double", "decimal", "number")):
        return "numeric"
    if field.role in {"dimension", "id"}:
        return field.role
    return "categorical"


def _is_aggregate_measure(field: FieldMetadata) -> bool:
    dtype = field.dtype.lower()
    name = field.name.strip().lower()
    return name.startswith(_AGGREGATE_MEASURE_PREFIXES) and any(
        token in dtype for token in ("int", "float", "double", "decimal", "number")
    )


def _vega_type(field: FieldMetadata) -> str:
    kind = _kind(field)
    if kind == "time":
        return "temporal"
    if kind == "numeric":
        return "quantitative"
    return "nominal"


def _default_aggregate(field: FieldMetadata) -> str:
    allowed = set(field.allowed_aggregations or [])
    for aggregate in ("sum", "mean", "count"):
        if aggregate in allowed:
            return aggregate
    return "sum" if not allowed else sorted(allowed)[0]


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text)}


def _elapsed_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000, 3)


def _memory_mb() -> float | None:
    if psutil is None:
        return None
    return round(psutil.Process().memory_info().rss / (1024 * 1024), 3)
