"""NL4DV/partial-tool adapter for existing-tool baseline experiments.

NL4DV is treated as an optional external tool. The default Stage 5 method is a
partial-fit fallback recommender because the current dependency plan for NL4DV
is too invasive for the project environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import pandas as pd

from t2v_eval.baselines.rule_based import (
    Candidate,
    _bar_spec,
    _fields_by_kind,
    _histogram_spec,
    _kind,
    _line_spec,
    _scatter_spec,
    _text_spec,
    load_fields,
    rank_fields,
)
from t2v_eval.data.schema import FieldMetadata, T2VExample, T2VPrediction
from t2v_eval.normalization.vega_lite import is_vega_lite_like, normalize_spec

try:
    import psutil
except ModuleNotFoundError:  # pragma: no cover - dependency is in requirements.
    psutil = None  # type: ignore[assignment]


METHOD_NAME = "B2_partial_recommender"
NL4DV_METHOD_NAME = "B2_nl4dv"


@dataclass(slots=True)
class FieldProfile:
    field: FieldMetadata
    cardinality: int | None = None
    non_null_ratio: float | None = None


def predict(example: T2VExample, *, run_id: str, top_k: int = 5) -> T2VPrediction:
    """Predict with the partial table-only recommender fallback."""

    start = perf_counter()
    start_memory = _memory_mb()
    try:
        candidates = generate_partial_candidates(example, top_k=top_k)
        latency_ms = _elapsed_ms(start)
        memory_peak_mb = _max_memory(start_memory)
        if not candidates:
            return T2VPrediction.failed(
                run_id=run_id,
                method=METHOD_NAME,
                example_id=example.example_id,
                error="no partial recommender candidate",
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


def predict_nl4dv(example: T2VExample, *, run_id: str, top_k: int = 5) -> T2VPrediction:
    """Best-effort NL4DV call, used only when NL4DV is explicitly available."""

    start = perf_counter()
    try:
        from nl4dv import NL4DV  # type: ignore[import-not-found]

        tool = NL4DV(data_url=str(example.table))
        output = tool.analyze_query(example.query)
        candidates = convert_nl4dv_output(output, top_k=top_k)
        if not candidates:
            return T2VPrediction.failed(
                run_id=run_id,
                method=NL4DV_METHOD_NAME,
                example_id=example.example_id,
                error="NL4DV returned no Vega-Lite-like candidates",
                latency_ms=_elapsed_ms(start),
            )
        best = candidates[0]
        return T2VPrediction(
            run_id=run_id,
            method=NL4DV_METHOD_NAME,
            example_id=example.example_id,
            status="ok",
            raw_spec=best.raw_spec,
            normalized_spec=normalize_spec(best.raw_spec),
            candidates=[candidate.to_dict() for candidate in candidates],
            latency_ms=_elapsed_ms(start),
            memory_peak_mb=_memory_mb(),
        )
    except Exception as exc:
        return T2VPrediction.failed(
            run_id=run_id,
            method=NL4DV_METHOD_NAME,
            example_id=example.example_id,
            error=str(exc),
            latency_ms=_elapsed_ms(start),
        )


def generate_partial_candidates(example: T2VExample, *, top_k: int = 5) -> list[Candidate]:
    """Generate table-profile recommendations and rank by query field mentions.

    Chart type recommendations come from schema/table profiles. The NL query is
    used only to prioritize fields and candidates, which makes this a partial
    fit rather than a full NL-to-Vis tool.
    """

    fields = load_fields(example)
    if not fields:
        return []

    profiles = profile_fields(example, fields)
    ranked_fields = rank_fields(example.query, fields)
    rank_by_name = {field.name: index for index, field in enumerate(ranked_fields)}

    time_fields = _fields_by_kind(fields, {"time"})
    numeric_fields = _fields_by_kind(fields, {"measure", "numeric"})
    categorical_fields = _fields_by_kind(fields, {"dimension", "categorical", "id"})

    generated: list[Candidate] = []
    for time_field in time_fields[:3]:
        for measure in numeric_fields[:5]:
            generated.append(
                Candidate(
                    _line_spec(time_field, measure),
                    _score_fields([time_field, measure], rank_by_name, profiles) + 0.5,
                    "table-profile time + numeric recommendation",
                )
            )

    for category in categorical_fields[:5]:
        for measure in numeric_fields[:5]:
            sort = "-y" if _low_cardinality(category, profiles) else None
            generated.append(
                Candidate(
                    _bar_spec(category, measure, sort=sort),
                    _score_fields([category, measure], rank_by_name, profiles) + 0.4,
                    "table-profile categorical + numeric recommendation",
                )
            )

    for index, x_measure in enumerate(numeric_fields[:5]):
        for y_measure in numeric_fields[index + 1 : 6]:
            generated.append(
                Candidate(
                    _scatter_spec(x_measure, y_measure),
                    _score_fields([x_measure, y_measure], rank_by_name, profiles) + 0.25,
                    "table-profile numeric pair recommendation",
                )
            )

    for measure in numeric_fields[:5]:
        generated.append(
            Candidate(
                _histogram_spec(measure),
                _score_fields([measure], rank_by_name, profiles) + 0.2,
                "table-profile numeric distribution recommendation",
            )
        )

    if not generated and ranked_fields:
        generated.append(
            Candidate(
                _text_spec(ranked_fields[0]),
                0.1,
                "table-profile text fallback",
            )
        )

    unique: list[Candidate] = []
    seen: set[str] = set()
    for candidate in sorted(generated, key=lambda item: item.score, reverse=True):
        normalized = normalize_spec(candidate.raw_spec)
        if not normalized["valid"]:
            continue
        key = normalized["canonical_json"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique[:top_k]


def convert_nl4dv_output(output: Any, *, top_k: int = 5) -> list[Candidate]:
    """Convert common NL4DV output shapes to Vega-Lite-like candidates."""

    specs: list[dict[str, Any]] = []
    for item in _walk_possible_specs(output):
        if is_vega_lite_like(item):
            specs.append(item)

    candidates: list[Candidate] = []
    seen: set[str] = set()
    for index, spec in enumerate(specs):
        key = normalize_spec(spec)["canonical_json"]
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            Candidate(
                raw_spec=spec,
                score=max(0.0, 1.0 - index * 0.05),
                reason="converted NL4DV Vega-Lite-like output",
            )
        )
    return candidates[:top_k]


def profile_fields(example: T2VExample, fields: list[FieldMetadata]) -> dict[str, FieldProfile]:
    profiles = {field.name: FieldProfile(field=field) for field in fields}
    try:
        table = pd.read_csv(example.table, nrows=500)
    except Exception:
        return profiles

    for field in fields:
        if field.name not in table.columns:
            continue
        column = table[field.name]
        profiles[field.name] = FieldProfile(
            field=field,
            cardinality=int(column.nunique(dropna=True)),
            non_null_ratio=float(column.notna().mean()) if len(column) else None,
        )
    return profiles


def _walk_possible_specs(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key in ("vlSpec", "vl_spec", "vegaLite", "vegalite", "spec"):
            item = value.get(key)
            if isinstance(item, dict):
                found.append(item)
        if is_vega_lite_like(value):
            found.append(value)
        for item in value.values():
            found.extend(_walk_possible_specs(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_walk_possible_specs(item))
    return found


def _score_fields(
    fields: list[FieldMetadata],
    rank_by_name: dict[str, int],
    profiles: dict[str, FieldProfile],
) -> float:
    score = 0.0
    for field in fields:
        rank = rank_by_name.get(field.name, len(rank_by_name))
        score += max(0.0, 2.0 - rank * 0.2)
        profile = profiles.get(field.name)
        if profile and profile.non_null_ratio is not None:
            score += min(profile.non_null_ratio, 1.0) * 0.1
    score -= 0.05 * max(0, len(fields) - 2)
    return score


def _low_cardinality(
    field: FieldMetadata,
    profiles: dict[str, FieldProfile],
    *,
    threshold: int = 30,
) -> bool:
    if _kind(field) in {"time", "numeric"}:
        return False
    profile = profiles.get(field.name)
    return profile is None or profile.cardinality is None or profile.cardinality <= threshold


def _elapsed_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000, 3)


def _memory_mb() -> float | None:
    if psutil is None:
        return None
    return round(psutil.Process().memory_info().rss / (1024 * 1024), 3)


def _max_memory(start_memory: float | None) -> float | None:
    current = _memory_mb()
    values = [value for value in (start_memory, current) if value is not None]
    return max(values) if values else None
