"""Run Stage 8 large LLM baselines through the strict JSON validator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_llm_experiment import run_llm_experiment
from scripts.run_llm_rerank_experiment import run_llm_rerank_experiment
from t2v_eval.baselines.llm_vegalite import gpu_runtime_info
from t2v_eval.utils.io import write_json


CANONICAL_DRIVE_ROOT = Path("/content/drive/MyDrive/diploma/petr_text_to_visualization_part")
CANONICAL_EXAMPLES = (
    CANONICAL_DRIVE_ROOT
    / "datasets"
    / "processed"
    / "nvbench_postquery"
    / "examples_sample200.jsonl"
)
DEFAULT_CONFIG = REPO_ROOT / "configs" / "stage8_large_llm_models.json"


def load_stage8_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        config = json.load(file)
    if not isinstance(config.get("models"), dict) or not config["models"]:
        raise ValueError("Stage 8 config must contain a non-empty `models` object.")
    return config


def stage8_model_keys(path: Path = DEFAULT_CONFIG) -> list[str]:
    return sorted(load_stage8_config(path)["models"])


def run_stage8_model(
    *,
    config_path: Path = DEFAULT_CONFIG,
    model_key: str,
    examples_path: Path = CANONICAL_EXAMPLES,
    drive_root: Path = CANONICAL_DRIVE_ROOT,
    run_id: str | None = None,
    sample_size: int | None = None,
    render_limit: int | None = None,
    mode: str | None = None,
    evaluate: bool = True,
    allow_low_vram: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    stage_config = load_stage8_config(config_path)
    models = stage_config["models"]
    if model_key not in models:
        raise ValueError(
            f"Unknown Stage 8 model key `{model_key}`. Available: {', '.join(sorted(models))}."
        )

    model_config = dict(models[model_key])
    effective_mode = mode or str(model_config.get("mode") or "single")
    effective_sample_size = (
        sample_size if sample_size is not None else int(stage_config.get("default_sample_size") or 20)
    )
    effective_render_limit = (
        render_limit if render_limit is not None else int(stage_config.get("default_render_limit") or 0)
    )
    effective_run_id = run_id or str(model_config["run_id"])
    gpu_info = gpu_runtime_info()
    _check_vram(model_key, model_config, gpu_info, allow_low_vram=allow_low_vram)

    common_kwargs = {
        "examples_path": examples_path,
        "drive_root": drive_root,
        "run_id": effective_run_id,
        "sample_size": effective_sample_size,
        "model_id": str(model_config["model_id"]),
        "quantization": model_config.get("quantization"),
        "max_new_tokens": int(model_config.get("max_new_tokens", 384)),
        "seed": int(model_config.get("seed", 42)),
        "sample_rows": int(model_config.get("sample_rows", 5)),
        "torch_dtype": str(model_config.get("torch_dtype", "auto")),
        "device_map": str(model_config.get("device_map", "auto")),
        "model_loader": str(model_config.get("model_loader", "causal_lm")),
        "attn_implementation": model_config.get("attn_implementation"),
        "bnb_4bit_compute_dtype": str(model_config.get("bnb_4bit_compute_dtype", "float16")),
        "assistant_model_id": model_config.get("assistant_model_id"),
        "assistant_quantization": model_config.get("assistant_quantization"),
        "assistant_model_loader": str(model_config.get("assistant_model_loader", "causal_lm")),
        "method_name": str(model_config["method_name"]),
        "evaluate": evaluate,
        "render_limit": effective_render_limit,
    }
    planned = {
        "stage": stage_config.get("stage"),
        "model_key": model_key,
        "mode": effective_mode,
        "model_config": model_config,
        "run_kwargs": _stringify_paths(common_kwargs),
        "gpu_runtime_before": gpu_info,
        "dry_run": dry_run,
    }
    if dry_run:
        return planned

    if effective_mode == "single":
        result = run_llm_experiment(
            **common_kwargs,
            temperature=float(model_config.get("temperature", 0.0)),
            top_p=float(model_config.get("top_p", 1.0)),
        )
    elif effective_mode == "rerank":
        result = run_llm_rerank_experiment(
            **common_kwargs,
            top_p=float(model_config.get("top_p", 0.9)),
            candidate_count=int(model_config.get("candidate_count", 3)),
            candidate_temperatures=tuple(
                float(value) for value in model_config.get("candidate_temperatures", [0.0, 0.2, 0.3])
            ),
        )
    else:
        raise ValueError("Stage 8 mode must be `single` or `rerank`.")

    summary = {
        **planned,
        "dry_run": False,
        "result": result,
    }
    write_json(drive_root / "runs" / result["run_id"] / "stage8_model_summary.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--model-key")
    parser.add_argument("--examples", default=str(CANONICAL_EXAMPLES))
    parser.add_argument("--drive-root", default=str(CANONICAL_DRIVE_ROOT))
    parser.add_argument("--run-id")
    parser.add_argument("--sample-size", type=int)
    parser.add_argument("--render-limit", type=int)
    parser.add_argument("--mode", choices=["single", "rerank"])
    parser.add_argument("--allow-low-vram", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-evaluate", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = Path(args.config)
    if args.list_models:
        config = load_stage8_config(config_path)
        rows = [
            {
                "key": key,
                "label": value.get("label"),
                "model_id": value.get("model_id"),
                "quantization": value.get("quantization"),
                "min_vram_gb": value.get("min_vram_gb"),
                "recommended_colab_gpu": value.get("recommended_colab_gpu"),
            }
            for key, value in sorted(config["models"].items())
        ]
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not args.model_key:
        raise SystemExit("--model-key is required unless --list-models is used.")

    result = run_stage8_model(
        config_path=config_path,
        model_key=args.model_key,
        examples_path=Path(args.examples),
        drive_root=Path(args.drive_root),
        run_id=args.run_id,
        sample_size=args.sample_size,
        render_limit=args.render_limit,
        mode=args.mode,
        evaluate=not args.no_evaluate,
        allow_low_vram=args.allow_low_vram,
        dry_run=args.dry_run,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"run_id={result.get('result', {}).get('run_id') or result['run_kwargs']['run_id']}")
    return 0


def _check_vram(
    model_key: str,
    model_config: dict[str, Any],
    gpu_info: dict[str, Any],
    *,
    allow_low_vram: bool,
) -> None:
    min_vram_gb = model_config.get("min_vram_gb")
    if not min_vram_gb or not gpu_info.get("cuda_available"):
        return
    available_gb = float(gpu_info.get("vram_total_mb") or 0.0) / 1024.0
    if available_gb + 0.25 >= float(min_vram_gb):
        return
    message = (
        f"Stage 8 model `{model_key}` needs about {min_vram_gb}GB VRAM, "
        f"but current GPU has {available_gb:.1f}GB. Recommended: "
        f"{model_config.get('recommended_colab_gpu') or 'use a larger GPU'}."
    )
    if allow_low_vram:
        print(f"WARNING: {message}")
        return
    raise RuntimeError(message + " Pass --allow-low-vram only if you intentionally want to risk OOM.")


def _stringify_paths(values: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values.items():
        result[key] = str(value) if isinstance(value, Path) else value
    return result


if __name__ == "__main__":
    raise SystemExit(main())
