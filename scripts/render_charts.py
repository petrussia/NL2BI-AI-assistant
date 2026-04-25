"""Render predicted Vega-Lite specs for manual inspection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from t2v_eval.data.schema import T2VExample, T2VPrediction
from t2v_eval.utils.io import read_jsonl


def render_predictions(
    *,
    examples_path: Path,
    predictions_path: Path,
    output_dir: Path,
    limit: int = 20,
) -> dict[str, Any]:
    examples = {row["example_id"]: T2VExample.from_dict(row) for row in read_jsonl(examples_path)}
    predictions = [T2VPrediction.from_dict(row) for row in read_jsonl(predictions_path)]
    output_dir.mkdir(parents=True, exist_ok=True)

    rendered = 0
    failures: list[dict[str, str]] = []
    for prediction in predictions:
        if rendered >= limit:
            break
        if prediction.status != "ok" or not prediction.raw_spec:
            continue
        example = examples.get(prediction.example_id)
        if example is None:
            failures.append({"example_id": prediction.example_id, "error": "missing example"})
            continue
        try:
            target = output_dir / f"{prediction.example_id}.png"
            render_single(example, prediction.raw_spec, target)
            rendered += 1
        except Exception as exc:  # pragma: no cover - renderer depends on optional backend.
            failures.append({"example_id": prediction.example_id, "error": str(exc)})

    failures_path = output_dir / "render_failures.json"
    failures_path.write_text(json.dumps(failures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "rendered": rendered,
        "failed": len(failures),
        "output_dir": str(output_dir),
        "failures": str(failures_path),
    }


def render_single(example: T2VExample, spec: dict[str, Any], target: Path) -> None:
    import vl_convert as vlc

    table = pd.read_csv(example.table)
    spec_with_data = dict(spec)
    spec_with_data["data"] = {"values": table.head(500).to_dict(orient="records")}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(vlc.vegalite_to_png(spec_with_data))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = render_predictions(
        examples_path=Path(args.examples),
        predictions_path=Path(args.predictions),
        output_dir=Path(args.output_dir),
        limit=args.limit,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"rendered={result['rendered']} output_dir={result['output_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
