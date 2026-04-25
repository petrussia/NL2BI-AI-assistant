"""Constraint and ranking baseline for post-query Text-to-Visualization."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from t2v_eval.baselines.rule_based import (
    Candidate,
    _bar_spec,
    _default_aggregate,
    _fields_by_kind,
    _histogram_spec,
    _kind,
    _line_spec,
    _scatter_spec,
    _text_spec,
    detect_intent,
    load_fields,
    rank_fields,
)
from t2v_eval.data.schema import FieldMetadata, T2VExample, T2VPrediction
from t2v_eval.normalization.vega_lite import normalize_spec

try:
    import psutil
except ModuleNotFoundError:  # pragma: no cover - dependency is in requirements.
    psutil = None  # type: ignore[assignment]


METHOD_NAME = "B1_constraint_ranker"


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
                error="no candidate passed hard constraints",
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
    ranked_fields = rank_fields(example.query, fields)
    time_fields = _fields_by_kind(ranked_fields, {"time"})
    numeric_fields = _fields_by_kind(ranked_fields, {"measure", "numeric"})
    categorical_fields = _fields_by_kind(ranked_fields, {"dimension", "categorical", "id"})

    generated: list[Candidate] = []
    for category in categorical_fields[:4]:
        for measure in numeric_fields[:4]:
            generated.append(Candidate(_bar_spec(category, measure), 0.0, "generated categorical + numeric"))
            generated.append(Candidate(_bar_spec(category, measure, sort="-y"), 0.0, "generated sorted categorical + numeric"))
    for time_field in time_fields[:3]:
        for measure in numeric_fields[:4]:
            generated.append(Candidate(_line_spec(time_field, measure), 0.0, "generated time + numeric"))
    for index, x_measure in enumerate(numeric_fields[:4]):
        for y_measure in numeric_fields[index + 1 : 5]:
            generated.append(Candidate(_scatter_spec(x_measure, y_measure), 0.0, "generated numeric + numeric"))
    for measure in numeric_fields[:4]:
        generated.append(Candidate(_histogram_spec(measure), 0.0, "generated numeric distribution"))
    if intent == "table":
        for field in ranked_fields[:4]:
            generated.append(Candidate(_text_spec(field), 0.0, "generated table/detail text fallback"))

    constrained = [
        Candidate(candidate.raw_spec, _score(candidate.raw_spec, ranked_fields, intent), candidate.reason)
        for candidate in generated
        if passes_hard_constraints(candidate.raw_spec, fields)
    ]

    unique: list[Candidate] = []
    seen: set[str] = set()
    for candidate in sorted(constrained, key=lambda item: item.score, reverse=True):
        key = normalize_spec(candidate.raw_spec)["canonical_json"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique[:top_k]


def passes_hard_constraints(spec: dict[str, Any], fields: list[FieldMetadata]) -> bool:
    fields_by_name = {field.name: field for field in fields}
    normalized = normalize_spec(spec)
    if not normalized["valid"]:
        return False
    encoding = normalized["encoding"]
    for channel, channel_value in encoding.items():
        items = channel_value if isinstance(channel_value, list) else [channel_value]
        for item in items:
            if not isinstance(item, dict):
                return False
            field_name = item.get("field")
            if not field_name:
                continue
            field = fields_by_name.get(str(field_name))
            if field is None:
                return False
            declared_type = item.get("type")
            if declared_type == "temporal" and _kind(field) != "time":
                return False
            if declared_type == "quantitative" and _kind(field) != "numeric":
                return False
            aggregate = item.get("aggregate")
            if aggregate and not _aggregation_allowed(field, str(aggregate)):
                return False
            if channel in {"x", "y"} and declared_type == "temporal" and _kind(field) != "time":
                return False
    return True


def _score(spec: dict[str, Any], ranked_fields: list[FieldMetadata], intent: str) -> float:
    normalized = normalize_spec(spec)
    score = 0.0
    chart = normalized.get("chart_type")
    fields = normalized.get("fields") or []
    field_rank = {field.name: index for index, field in enumerate(ranked_fields)}

    if intent == "trend" and chart == "line":
        score += 3.0
    elif intent == "correlation" and chart == "point":
        score += 3.0
    elif intent == "distribution" and _has_bin(normalized):
        score += 3.0
    elif intent == "top" and chart == "bar" and _has_sort(normalized):
        score += 3.0
    elif intent == "table" and chart == "text":
        score += 3.0
    elif intent in {"comparison", "dashboard"} and chart == "bar":
        score += 2.0

    for field in fields:
        score += max(0.0, 1.5 - field_rank.get(field, len(ranked_fields)) * 0.15)

    score += _simplicity_bonus(normalized)
    score -= 0.05 * len(fields)
    return score


def _aggregation_allowed(field: FieldMetadata, aggregate: str) -> bool:
    if aggregate == "count":
        return True
    if _kind(field) != "numeric":
        return False
    allowed = set(field.allowed_aggregations or [])
    return not allowed or aggregate in allowed or _default_aggregate(field) == aggregate


def _has_bin(normalized: dict[str, Any]) -> bool:
    for channel_value in normalized.get("encoding", {}).values():
        items = channel_value if isinstance(channel_value, list) else [channel_value]
        if any(isinstance(item, dict) and item.get("bin") for item in items):
            return True
    return False


def _has_sort(normalized: dict[str, Any]) -> bool:
    for channel_value in normalized.get("encoding", {}).values():
        items = channel_value if isinstance(channel_value, list) else [channel_value]
        if any(isinstance(item, dict) and item.get("sort") for item in items):
            return True
    return False


def _simplicity_bonus(normalized: dict[str, Any]) -> float:
    channels = len(normalized.get("encoding", {}))
    if channels <= 2:
        return 0.6
    if channels <= 3:
        return 0.3
    return 0.0


def _elapsed_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000, 3)


def _memory_mb() -> float | None:
    if psutil is None:
        return None
    return round(psutil.Process().memory_info().rss / (1024 * 1024), 3)
