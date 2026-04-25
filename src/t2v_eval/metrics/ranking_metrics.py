"""Ranking metrics for prediction candidates."""

from __future__ import annotations

from typing import Any

from t2v_eval.metrics.spec_metrics import evaluate_spec
from t2v_eval.normalization.vega_lite import normalize_spec


def evaluate_ranking(
    gold_spec: dict[str, Any] | None,
    candidates: list[dict[str, Any]] | None,
    *,
    k: int = 5,
) -> dict[str, float | None]:
    ranked = candidates or []
    if not ranked:
        return {
            "top1_success": None,
            "oracle_success_at_k": None,
            "precision_at_k": None,
            "mrr": None,
        }

    limited = ranked[:k]
    successes = [_candidate_success(gold_spec, candidate) for candidate in limited]
    top1_success = 1.0 if successes and successes[0] else 0.0
    oracle_success_at_k = 1.0 if any(successes) else 0.0
    precision_at_k = sum(1 for value in successes if value) / len(limited)

    mrr: float = 0.0
    for index, success in enumerate(successes, start=1):
        if success:
            mrr = 1.0 / index
            break

    return {
        "top1_success": top1_success,
        "oracle_success_at_k": oracle_success_at_k,
        "precision_at_k": precision_at_k,
        "mrr": mrr,
    }


def _candidate_success(
    gold_spec: dict[str, Any] | None,
    candidate: dict[str, Any],
) -> bool:
    spec = (
        candidate.get("normalized_spec")
        or candidate.get("raw_spec")
        or candidate.get("spec")
        or candidate
    )
    normalized = normalize_spec(spec)
    if not normalized["valid"]:
        return False
    metrics = evaluate_spec(gold_spec, spec)
    return bool(metrics.normalized_exact_match)
