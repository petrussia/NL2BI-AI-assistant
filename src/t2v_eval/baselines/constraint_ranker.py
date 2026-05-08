"""Constraint and ranking baseline for post-query Text-to-Visualization."""

from __future__ import annotations

from copy import deepcopy
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
    _vega_type,
    detect_chart_hint,
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
    chart_hint = detect_chart_hint(example.query)
    ranked_fields = rank_fields(example.query, fields)
    time_fields = _fields_by_kind(ranked_fields, {"time"})
    numeric_fields = _fields_by_kind(ranked_fields, {"measure", "numeric"})
    categorical_fields = _fields_by_kind(ranked_fields, {"dimension", "categorical", "id"})
    color_fields = _color_fields(example.query, categorical_fields)

    generated: list[Candidate] = []
    for category in categorical_fields[:4]:
        for measure in numeric_fields[:4]:
            _append_candidate_variants(
                generated,
                _bar_spec(category, measure),
                "generated categorical + numeric",
                color_fields,
            )
            _append_candidate_variants(
                generated,
                _bar_spec(category, measure, sort="-y"),
                "generated sorted categorical + numeric",
                color_fields,
            )
    if chart_hint == "bar" or intent in {"comparison", "dashboard", "top"}:
        for time_field in time_fields[:3]:
            for measure in numeric_fields[:4]:
                _append_candidate_variants(
                    generated,
                    _bar_spec(time_field, measure),
                    "generated temporal + numeric bar",
                    color_fields,
                )
                _append_candidate_variants(
                    generated,
                    _bar_spec(time_field, measure, sort="-x"),
                    "generated sorted temporal + numeric bar",
                    color_fields,
                )
    for time_field in time_fields[:3]:
        for measure in numeric_fields[:4]:
            _append_candidate_variants(
                generated,
                _line_spec(time_field, measure),
                "generated time + numeric",
                color_fields,
            )
    for index, x_measure in enumerate(numeric_fields[:4]):
        for y_measure in numeric_fields[index + 1 : 5]:
            _append_candidate_variants(
                generated,
                _scatter_spec(x_measure, y_measure),
                "generated numeric + numeric",
                color_fields,
            )
    if intent == "distribution" or chart_hint == "histogram":
        for measure in numeric_fields[:4]:
            generated.append(Candidate(_histogram_spec(measure), 0.0, "generated numeric distribution"))
    if intent == "table" and not generated:
        for field in ranked_fields[:4]:
            generated.append(Candidate(_text_spec(field), 0.0, "generated table/detail text fallback"))

    constrained = [
        Candidate(
            candidate.raw_spec,
            _score(
                candidate.raw_spec,
                ranked_fields,
                intent,
                chart_hint=chart_hint,
                query=example.query,
            ),
            candidate.reason,
        )
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


def _append_candidate_variants(
    generated: list[Candidate],
    spec: dict[str, Any],
    reason: str,
    color_fields: list[FieldMetadata],
) -> None:
    generated.append(Candidate(spec, 0.0, reason))
    spec_fields = _spec_fields(spec)
    for color_field in color_fields[:2]:
        if color_field.name in spec_fields:
            continue
        generated.append(
            Candidate(
                _with_color(spec, color_field),
                0.0,
                f"{reason} + color",
            )
        )


def _color_fields(query: str, categorical_fields: list[FieldMetadata]) -> list[FieldMetadata]:
    text = query.lower()
    has_signal = any(
        word in text
        for word in ("colored by", "different", "for each", "group", "grouped", "stacked")
    )
    classify_fields = [
        field for field in categorical_fields if field.name.lower() == "classify"
    ]
    if not has_signal and not classify_fields:
        return []
    remaining = [field for field in categorical_fields if field not in classify_fields]
    return classify_fields + remaining


def _with_color(spec: dict[str, Any], color_field: FieldMetadata) -> dict[str, Any]:
    colored = deepcopy(spec)
    encoding = dict(colored.get("encoding") or {})
    encoding["color"] = {"field": color_field.name, "type": _vega_type(color_field)}
    colored["encoding"] = encoding
    return colored


def _spec_fields(spec: dict[str, Any]) -> set[str]:
    fields: set[str] = set()
    for channel_value in (spec.get("encoding") or {}).values():
        items = channel_value if isinstance(channel_value, list) else [channel_value]
        for item in items:
            if isinstance(item, dict) and item.get("field"):
                fields.add(str(item["field"]))
    return fields


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


def _score(
    spec: dict[str, Any],
    ranked_fields: list[FieldMetadata],
    intent: str,
    *,
    chart_hint: str | None = None,
    query: str = "",
) -> float:
    normalized = normalize_spec(spec)
    score = 0.0
    chart = normalized.get("chart_type")
    fields = normalized.get("fields") or []
    field_rank = {field.name: index for index, field in enumerate(ranked_fields)}
    has_bin = _has_bin(normalized)
    expected_chart = "bar" if chart_hint == "histogram" else chart_hint

    if expected_chart:
        if chart == expected_chart:
            score += 4.0
        else:
            score -= 4.0

    if intent == "trend" and chart == "line":
        score += 3.0
    elif intent == "correlation" and chart == "point":
        score += 3.0
    elif intent == "distribution" and has_bin:
        score += 3.0
    elif intent == "top" and chart == "bar" and _has_sort(normalized):
        score += 3.0
    elif intent == "table" and chart == "text":
        score += 3.0
    elif intent in {"comparison", "dashboard"} and chart == "bar":
        score += 2.0

    for field in fields:
        score += max(0.0, 1.5 - field_rank.get(field, len(ranked_fields)) * 0.15)

    if "color" in (normalized.get("encoding") or {}):
        score += 0.8
    if has_bin and chart_hint != "histogram" and not _has_histogram_signal(query):
        score -= 2.0
    if chart == "text" and chart_hint in {"bar", "line", "point", "histogram"}:
        score -= 5.0

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


def _has_histogram_signal(query: str) -> bool:
    text = query.lower()
    return any(word in text for word in ("frequency", "histogram", "spread"))


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
