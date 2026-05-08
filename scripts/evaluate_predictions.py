"""Evaluate post-query Text-to-Visualization predictions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from t2v_eval.data.schema import T2VExample, T2VPrediction
from t2v_eval.metrics.ranking_metrics import evaluate_ranking
from t2v_eval.metrics.spec_metrics import aggregate_spec_metrics, evaluate_spec
from t2v_eval.metrics.system_metrics import summarize_system_metrics
from t2v_eval.normalization.vega_lite import normalize_spec
from t2v_eval.utils.io import read_jsonl, write_csv, write_json


def evaluate_predictions(
    *,
    examples_path: Path,
    predictions_path: Path,
    output_dir: Path,
    run_id: str | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    examples = [T2VExample.from_dict(row) for row in read_jsonl(examples_path)]
    predictions = [_prediction_from_dict(row) for row in read_jsonl(predictions_path)]
    predictions_by_id = {prediction.example_id: prediction for prediction in predictions}

    output_dir.mkdir(parents=True, exist_ok=True)
    per_example_rows: list[dict[str, Any]] = []

    for example in examples:
        prediction = predictions_by_id.get(example.example_id)
        if prediction is None:
            prediction = T2VPrediction.failed(
                run_id=run_id or "missing_prediction",
                method="missing",
                example_id=example.example_id,
                error="missing prediction",
            )

        gold_spec = example.gold_spec_normalized or example.gold_spec
        predicted_spec = (
            prediction.normalized_spec
            or prediction.raw_spec
            or _first_candidate_spec(prediction.candidates)
        )

        if prediction.status != "ok":
            predicted_spec = None

        spec_metrics = evaluate_spec(gold_spec, predicted_spec).to_dict()
        ranking_metrics = evaluate_ranking(gold_spec, prediction.candidates, k=top_k)
        normalized_prediction = normalize_spec(predicted_spec)

        per_example_rows.append(
            {
                "example_id": example.example_id,
                "run_id": prediction.run_id,
                "method": prediction.method,
                "prediction_status": prediction.status,
                "prediction_error": prediction.error or spec_metrics.get("error") or "",
                "predicted_valid": normalized_prediction["valid"],
                "latency_ms": prediction.latency_ms,
                "memory_peak_mb": prediction.memory_peak_mb,
                **spec_metrics,
                **ranking_metrics,
            }
        )

    aggregate = {
        "examples": len(examples),
        "predictions": len(predictions),
        **aggregate_spec_metrics(per_example_rows),
        **_aggregate_ranking_metrics(per_example_rows),
        **summarize_system_metrics([prediction.to_dict() for prediction in predictions]),
    }

    per_example_path = output_dir / "per_example_metrics.csv"
    aggregate_path = output_dir / "aggregate_metrics.csv"
    summary_path = output_dir / "evaluation_summary.json"
    write_csv(per_example_path, per_example_rows)
    write_csv(aggregate_path, [aggregate])
    write_json(summary_path, aggregate)

    return {
        "status": "ok",
        "examples": len(examples),
        "predictions": len(predictions),
        "per_example_metrics": str(per_example_path),
        "aggregate_metrics": str(aggregate_path),
        "summary": str(summary_path),
        "aggregate": aggregate,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", "--gold-jsonl", dest="examples", required=True)
    parser.add_argument("--predictions", "--predictions-jsonl", dest="predictions", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = evaluate_predictions(
        examples_path=Path(args.examples),
        predictions_path=Path(args.predictions),
        output_dir=Path(args.output_dir),
        run_id=args.run_id,
        top_k=args.top_k,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"aggregate_metrics={result['aggregate_metrics']}")
        print(f"per_example_metrics={result['per_example_metrics']}")
    return 0


def _prediction_from_dict(data: dict[str, Any]) -> T2VPrediction:
    row = dict(data)
    row.setdefault("run_id", "unknown_run")
    row.setdefault("method", "unknown_method")
    row.setdefault("example_id", row.get("id") or row.get("example") or "")
    if not row["example_id"]:
        raise ValueError(f"Prediction row is missing example_id: {data}")
    return T2VPrediction.from_dict(row)


def _first_candidate_spec(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    candidate = candidates[0]
    return (
        candidate.get("normalized_spec")
        or candidate.get("raw_spec")
        or candidate.get("spec")
        or candidate
    )


def _aggregate_ranking_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    names = ["top1_success", "oracle_success_at_k", "precision_at_k", "mrr"]
    aggregates: dict[str, float] = {}
    for name in names:
        values = [
            float(row[name])
            for row in rows
            if row.get(name) is not None and row.get(name) != ""
        ]
        aggregates[name] = sum(values) / len(values) if values else 0.0
    return aggregates


if __name__ == "__main__":
    raise SystemExit(main())
