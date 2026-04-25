"""Metrics for normalized Vega-Lite-like specification comparison."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from t2v_eval.normalization.vega_lite import (
    aggregate_tokens,
    encoding_tokens,
    normalize_spec,
)


@dataclass(slots=True)
class SpecMetricResult:
    chart_type_accuracy: float
    x_field_accuracy: float
    y_field_accuracy: float
    field_selection_precision: float
    field_selection_recall: float
    field_selection_f1: float
    encoding_accuracy: float
    aggregation_accuracy: float
    transform_accuracy: float
    normalized_exact_match: float
    vega_lite_validity: float
    status: str = "ok"
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_spec(
    gold_spec: dict[str, Any] | None,
    predicted_spec: dict[str, Any] | None,
) -> SpecMetricResult:
    gold = normalize_spec(gold_spec)
    predicted = normalize_spec(predicted_spec)

    if not predicted["valid"]:
        return SpecMetricResult(
            chart_type_accuracy=0.0,
            x_field_accuracy=0.0,
            y_field_accuracy=0.0,
            field_selection_precision=0.0,
            field_selection_recall=0.0,
            field_selection_f1=0.0,
            encoding_accuracy=0.0,
            aggregation_accuracy=0.0,
            transform_accuracy=0.0,
            normalized_exact_match=0.0,
            vega_lite_validity=0.0,
            status="failed",
            error=predicted.get("error"),
        )

    return SpecMetricResult(
        chart_type_accuracy=_same(gold.get("chart_type"), predicted.get("chart_type")),
        x_field_accuracy=_field_accuracy(gold, predicted, "x"),
        y_field_accuracy=_field_accuracy(gold, predicted, "y"),
        field_selection_precision=_precision(
            set(predicted.get("fields") or []),
            set(gold.get("fields") or []),
        ),
        field_selection_recall=_recall(
            set(predicted.get("fields") or []),
            set(gold.get("fields") or []),
        ),
        field_selection_f1=_f1(
            set(predicted.get("fields") or []),
            set(gold.get("fields") or []),
        ),
        encoding_accuracy=_set_accuracy(encoding_tokens(predicted), encoding_tokens(gold)),
        aggregation_accuracy=_set_accuracy(aggregate_tokens(predicted), aggregate_tokens(gold)),
        transform_accuracy=_same(gold.get("transform"), predicted.get("transform")),
        normalized_exact_match=_same(
            gold.get("canonical_json"),
            predicted.get("canonical_json"),
        ),
        vega_lite_validity=1.0,
    )


def aggregate_spec_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    metric_names = [
        "chart_type_accuracy",
        "x_field_accuracy",
        "y_field_accuracy",
        "field_selection_precision",
        "field_selection_recall",
        "field_selection_f1",
        "encoding_accuracy",
        "aggregation_accuracy",
        "transform_accuracy",
        "normalized_exact_match",
        "vega_lite_validity",
    ]
    if not rows:
        return {name: 0.0 for name in metric_names}

    aggregates: dict[str, float] = {}
    for name in metric_names:
        values = [
            float(row[name])
            for row in rows
            if row.get(name) is not None and row.get(name) != ""
        ]
        aggregates[name] = sum(values) / len(values) if values else 0.0
    return aggregates


def _same(left: Any, right: Any) -> float:
    return 1.0 if left == right else 0.0


def _field_accuracy(gold: dict[str, Any], predicted: dict[str, Any], channel: str) -> float:
    gold_field = _channel_field(gold, channel)
    predicted_field = _channel_field(predicted, channel)
    if gold_field is None:
        return 1.0 if predicted_field is None else 0.0
    return 1.0 if gold_field == predicted_field else 0.0


def _channel_field(normalized: dict[str, Any], channel: str) -> str | None:
    value = (normalized.get("encoding") or {}).get(channel)
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict) and value.get("field"):
        return str(value["field"])
    return None


def _precision(predicted: set[str], gold: set[str]) -> float:
    if not predicted:
        return 1.0 if not gold else 0.0
    return len(predicted & gold) / len(predicted)


def _recall(predicted: set[str], gold: set[str]) -> float:
    if not gold:
        return 1.0 if not predicted else 0.0
    return len(predicted & gold) / len(gold)


def _f1(predicted: set[str], gold: set[str]) -> float:
    precision = _precision(predicted, gold)
    recall = _recall(predicted, gold)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _set_accuracy(predicted: set[Any], gold: set[Any]) -> float:
    if not gold:
        return 1.0 if not predicted else 0.0
    return len(predicted & gold) / len(gold)
