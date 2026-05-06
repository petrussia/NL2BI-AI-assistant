"""Run the Stage 6 local LLM Vega-Lite baseline."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.evaluate_predictions import evaluate_predictions
from scripts.render_charts import render_predictions
from t2v_eval.baselines.llm_vegalite import (
    DEFAULT_MODEL_ID,
    DEFAULT_MAX_NEW_TOKENS,
    METHOD_NAME,
    LLMVegaLiteConfig,
    LLMVegaLitePredictor,
    gpu_runtime_info,
)
from t2v_eval.data.schema import T2VExample
from t2v_eval.utils.io import read_jsonl, write_json, write_jsonl
from t2v_eval.utils.reproducibility import pip_freeze, runtime_info, set_seed


CANONICAL_DRIVE_ROOT = Path("/content/drive/MyDrive/diploma/petr_text_to_visualization_part")


def run_llm_experiment(
    *,
    examples_path: Path,
    drive_root: Path,
    run_id: str | None = None,
    sample_size: int | None = None,
    model_id: str = DEFAULT_MODEL_ID,
    quantization: str | None = "4bit",
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    temperature: float = 0.0,
    top_p: float = 1.0,
    seed: int = 42,
    sample_rows: int = 5,
    torch_dtype: str = "auto",
    device_map: str = "auto",
    model_loader: str = "causal_lm",
    attn_implementation: str | None = None,
    bnb_4bit_compute_dtype: str = "float16",
    assistant_model_id: str | None = None,
    assistant_quantization: str | None = None,
    assistant_model_loader: str = "causal_lm",
    enable_thinking: bool = False,
    stop_after_json: bool = True,
    method_name: str = METHOD_NAME,
    evaluate: bool = True,
    render_limit: int = 0,
) -> dict[str, Any]:
    set_seed(seed)
    run_id = run_id or f"stage6_qwen3_8b_{time.strftime('%Y%m%d_%H%M%S')}"
    run_dir = drive_root / "runs" / run_id
    predictions_dir = run_dir / "predictions"
    metrics_dir = run_dir / "metrics"
    rendered_dir = run_dir / "rendered"
    predictions_dir.mkdir(parents=True, exist_ok=True)

    all_examples = [T2VExample.from_dict(row) for row in read_jsonl(examples_path)]
    examples = all_examples[:sample_size] if sample_size else all_examples
    examples_used_path = run_dir / "examples_used.jsonl"
    write_jsonl(examples_used_path, [example.to_dict() for example in examples])

    config = LLMVegaLiteConfig(
        model_id=model_id,
        quantization=quantization,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
        seed=seed,
        sample_rows=sample_rows,
        enable_thinking=enable_thinking,
        stop_after_json=stop_after_json,
        torch_dtype=torch_dtype,
        device_map=device_map,
        model_loader=model_loader,
        attn_implementation=attn_implementation,
        bnb_4bit_compute_dtype=bnb_4bit_compute_dtype,
        assistant_model_id=assistant_model_id,
        assistant_quantization=assistant_quantization,
        assistant_model_loader=assistant_model_loader,
        method_name=method_name,
    )
    method_name = config.method_name
    runtime = runtime_info(REPO_ROOT)
    write_json(run_dir / "runtime_info.json", runtime)
    write_json(run_dir / "llm_config.json", config.to_dict())
    write_json(run_dir / "gpu_runtime_before.json", gpu_runtime_info())
    (run_dir / "pip_freeze.txt").write_text(pip_freeze() + "\n", encoding="utf-8")

    predictor = LLMVegaLitePredictor(config).load()
    rows = [predictor.predict(example, run_id=run_id).to_dict() for example in examples]
    predictions_path = predictions_dir / f"{method_name}.jsonl"
    write_jsonl(predictions_path, rows)
    write_json(run_dir / "gpu_runtime_after.json", gpu_runtime_info())

    method_summary: dict[str, Any] = {
        "predictions": str(predictions_path),
        "count": len(rows),
        "failures": sum(1 for row in rows if row.get("status") != "ok"),
    }
    if evaluate:
        method_summary["metrics"] = evaluate_predictions(
            examples_path=examples_used_path,
            predictions_path=predictions_path,
            output_dir=metrics_dir / method_name,
            run_id=run_id,
            top_k=1,
        )
    if render_limit > 0:
        method_summary["rendered"] = render_predictions(
            examples_path=examples_used_path,
            predictions_path=predictions_path,
            output_dir=rendered_dir / method_name,
            limit=render_limit,
        )

    summary: dict[str, Any] = {
        "run_id": run_id,
        "examples_path": str(examples_path),
        "examples_used": str(examples_used_path),
        "drive_root": str(drive_root),
        "sample_size": len(examples),
        "method": method_name,
        "llm_config": config.to_dict(),
        "methods": {method_name: method_summary},
    }
    write_json(run_dir / "experiment_summary.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", required=True)
    parser.add_argument("--drive-root", default=str(CANONICAL_DRIVE_ROOT))
    parser.add_argument("--run-id")
    parser.add_argument("--sample-size", type=int)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--quantization", default="4bit", choices=["4bit", "prequantized", "none"])
    parser.add_argument("--max-new-tokens", type=int, default=DEFAULT_MAX_NEW_TOKENS)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sample-rows", type=int, default=5)
    parser.add_argument("--torch-dtype", default="auto")
    parser.add_argument("--device-map", default="auto")
    parser.add_argument("--model-loader", default="causal_lm")
    parser.add_argument("--attn-implementation")
    parser.add_argument("--bnb-4bit-compute-dtype", default="float16")
    parser.add_argument("--assistant-model-id")
    parser.add_argument("--assistant-quantization", default="none", choices=["4bit", "prequantized", "none"])
    parser.add_argument("--assistant-model-loader", default="causal_lm")
    parser.add_argument("--method-name", default=METHOD_NAME)
    parser.add_argument("--enable-thinking", action="store_true")
    parser.add_argument("--no-stop-after-json", action="store_true")
    parser.add_argument("--no-evaluate", action="store_true")
    parser.add_argument("--render-limit", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_llm_experiment(
        examples_path=Path(args.examples),
        drive_root=Path(args.drive_root),
        run_id=args.run_id,
        sample_size=args.sample_size,
        model_id=args.model_id,
        quantization=None if args.quantization == "none" else args.quantization,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
        seed=args.seed,
        sample_rows=args.sample_rows,
        torch_dtype=args.torch_dtype,
        device_map=args.device_map,
        model_loader=args.model_loader,
        attn_implementation=args.attn_implementation,
        bnb_4bit_compute_dtype=args.bnb_4bit_compute_dtype,
        assistant_model_id=args.assistant_model_id,
        assistant_quantization=None if args.assistant_quantization == "none" else args.assistant_quantization,
        assistant_model_loader=args.assistant_model_loader,
        enable_thinking=args.enable_thinking,
        stop_after_json=not args.no_stop_after_json,
        method_name=args.method_name,
        evaluate=not args.no_evaluate,
        render_limit=args.render_limit,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"run_id={result['run_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
