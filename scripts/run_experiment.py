"""Run post-query Text-to-Visualization baseline experiments."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.evaluate_predictions import evaluate_predictions
from scripts.render_charts import render_predictions
from t2v_eval.baselines.constraint_ranker import METHOD_NAME as B1_METHOD_NAME
from t2v_eval.baselines.constraint_ranker import predict as predict_b1
from t2v_eval.baselines.nl4dv_adapter import METHOD_NAME as B2_METHOD_NAME
from t2v_eval.baselines.nl4dv_adapter import predict as predict_b2
from t2v_eval.baselines.rule_based import METHOD_NAME as B0_METHOD_NAME
from t2v_eval.baselines.rule_based import predict as predict_b0
from t2v_eval.data.schema import T2VExample, T2VPrediction
from t2v_eval.utils.io import read_jsonl, write_json, write_jsonl
from t2v_eval.utils.reproducibility import pip_freeze, runtime_info, set_seed


Predictor = Callable[[T2VExample], T2VPrediction]

CANONICAL_DRIVE_ROOT = Path("/content/drive/MyDrive/diploma/petr_text_to_visualization_part")


def run_experiment(
    *,
    examples_path: Path,
    method: str,
    drive_root: Path,
    run_id: str | None = None,
    sample_size: int | None = None,
    seed: int = 42,
    top_k: int = 5,
    evaluate: bool = True,
    render_limit: int = 0,
) -> dict[str, object]:
    set_seed(seed)
    run_id = run_id or f"stage4_{time.strftime('%Y%m%d_%H%M%S')}"
    run_dir = drive_root / "runs" / run_id
    predictions_dir = run_dir / "predictions"
    metrics_dir = run_dir / "metrics"
    rendered_dir = run_dir / "rendered"
    predictions_dir.mkdir(parents=True, exist_ok=True)

    all_examples = [T2VExample.from_dict(row) for row in read_jsonl(examples_path)]
    examples = all_examples[:sample_size] if sample_size else all_examples
    examples_used_path = run_dir / "examples_used.jsonl"
    write_jsonl(examples_used_path, [example.to_dict() for example in examples])
    methods = [B0_METHOD_NAME, B1_METHOD_NAME] if method == "all" else [method]

    summary: dict[str, object] = {
        "run_id": run_id,
        "examples_path": str(examples_path),
        "examples_used": str(examples_used_path),
        "drive_root": str(drive_root),
        "sample_size": len(examples),
        "methods": {},
    }

    runtime = runtime_info(REPO_ROOT)
    write_json(run_dir / "runtime_info.json", runtime)
    (run_dir / "pip_freeze.txt").write_text(pip_freeze() + "\n", encoding="utf-8")

    for method_name in methods:
        predictor = _predictor(method_name, run_id=run_id, top_k=top_k)
        rows = [predictor(example).to_dict() for example in examples]
        predictions_path = predictions_dir / f"{method_name}.jsonl"
        write_jsonl(predictions_path, rows)

        method_summary: dict[str, object] = {
            "predictions": str(predictions_path),
            "count": len(rows),
            "failures": sum(1 for row in rows if row.get("status") != "ok"),
        }
        if evaluate:
            eval_result = evaluate_predictions(
                examples_path=examples_used_path,
                predictions_path=predictions_path,
                output_dir=metrics_dir / method_name,
                run_id=run_id,
                top_k=top_k,
            )
            method_summary["metrics"] = eval_result
        if render_limit > 0:
            render_result = render_predictions(
                examples_path=examples_used_path,
                predictions_path=predictions_path,
                output_dir=rendered_dir / method_name,
                limit=render_limit,
            )
            method_summary["rendered"] = render_result

        summary["methods"][method_name] = method_summary  # type: ignore[index]

    write_json(run_dir / "experiment_summary.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", required=True)
    parser.add_argument(
        "--method",
        choices=[B0_METHOD_NAME, B1_METHOD_NAME, B2_METHOD_NAME, "all"],
        required=True,
    )
    parser.add_argument("--drive-root", default=str(CANONICAL_DRIVE_ROOT))
    parser.add_argument("--run-id")
    parser.add_argument("--sample-size", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--no-evaluate", action="store_true")
    parser.add_argument("--render-limit", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_experiment(
        examples_path=Path(args.examples),
        method=args.method,
        drive_root=Path(args.drive_root),
        run_id=args.run_id,
        sample_size=args.sample_size,
        seed=args.seed,
        top_k=args.top_k,
        evaluate=not args.no_evaluate,
        render_limit=args.render_limit,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"run_id={result['run_id']}")
    return 0


def _predictor(method: str, *, run_id: str, top_k: int) -> Predictor:
    if method == B0_METHOD_NAME:
        return lambda example: predict_b0(example, run_id=run_id, top_k=top_k)
    if method == B1_METHOD_NAME:
        return lambda example: predict_b1(example, run_id=run_id, top_k=top_k)
    if method == B2_METHOD_NAME:
        return lambda example: predict_b2(example, run_id=run_id, top_k=top_k)
    raise ValueError(f"Unknown method: {method}")


if __name__ == "__main__":
    raise SystemExit(main())
