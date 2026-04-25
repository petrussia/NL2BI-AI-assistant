import csv
from pathlib import Path

from scripts.run_experiment import run_experiment
from t2v_eval.baselines.nl4dv_adapter import (
    METHOD_NAME,
    convert_nl4dv_output,
    generate_partial_candidates,
    predict,
)
from t2v_eval.data.schema import FieldMetadata, T2VExample
from t2v_eval.utils.io import read_jsonl, write_jsonl


def _example(tmp_path: Path, query: str = "Show sales by region") -> T2VExample:
    table = tmp_path / "table.csv"
    table.write_text(
        "month,region,sales,profit\n"
        "2024-01,North,100,20\n"
        "2024-02,South,160,28\n"
        "2024-03,West,120,35\n",
        encoding="utf-8",
    )
    fields = [
        FieldMetadata(name="month", dtype="date", role="time").to_dict(),
        FieldMetadata(name="region", dtype="string", role="dimension").to_dict(),
        FieldMetadata(
            name="sales",
            dtype="float",
            role="measure",
            allowed_aggregations=["sum", "mean"],
        ).to_dict(),
        FieldMetadata(
            name="profit",
            dtype="float",
            role="measure",
            allowed_aggregations=["sum", "mean"],
        ).to_dict(),
    ]
    return T2VExample(
        example_id="ex1",
        query=query,
        table_path=str(table),
        metadata={"fields": fields},
        gold_spec={
            "mark": "bar",
            "encoding": {
                "x": {"field": "region", "type": "nominal"},
                "y": {"field": "sales", "type": "quantitative", "aggregate": "sum"},
            },
        },
    )


def test_partial_recommender_returns_candidates(tmp_path: Path) -> None:
    example = _example(tmp_path)

    prediction = predict(example, run_id="unit", top_k=3)

    assert prediction.method == METHOD_NAME
    assert prediction.status == "ok"
    assert prediction.raw_spec
    assert prediction.normalized_spec
    assert prediction.candidates
    assert prediction.latency_ms is not None


def test_partial_recommender_uses_query_for_field_ranking(tmp_path: Path) -> None:
    example = _example(tmp_path, "Show profit by month")

    candidates = generate_partial_candidates(example, top_k=3)

    assert candidates
    fields = candidates[0].to_dict()["normalized_spec"]["fields"]
    assert "profit" in fields
    assert "month" in fields


def test_convert_nl4dv_output_handles_common_spec_shapes() -> None:
    output = {
        "visList": [
            {
                "vlSpec": {
                    "mark": "bar",
                    "encoding": {
                        "x": {"field": "region", "type": "nominal"},
                        "y": {"field": "sales", "type": "quantitative"},
                    },
                }
            }
        ]
    }

    candidates = convert_nl4dv_output(output)

    assert len(candidates) == 1
    assert candidates[0].raw_spec["mark"] == "bar"


def test_run_experiment_supports_b2_partial_recommender(tmp_path: Path) -> None:
    examples_path = tmp_path / "examples.jsonl"
    drive_root = tmp_path / "drive"
    rows = []
    for index in range(4):
        row = _example(tmp_path, "Show sales by region").to_dict()
        row["example_id"] = f"ex{index}"
        rows.append(row)
    write_jsonl(examples_path, rows)

    result = run_experiment(
        examples_path=examples_path,
        method=METHOD_NAME,
        drive_root=drive_root,
        run_id="unit_stage5",
        sample_size=3,
        render_limit=0,
    )

    run_root = drive_root / "runs" / "unit_stage5"
    predictions = run_root / "predictions" / f"{METHOD_NAME}.jsonl"
    metrics = run_root / "metrics" / METHOD_NAME / "aggregate_metrics.csv"

    assert result["run_id"] == "unit_stage5"
    assert predictions.exists()
    assert len(read_jsonl(predictions)) == 3
    with metrics.open(newline="", encoding="utf-8") as file:
        row = next(csv.DictReader(file))
    assert row["examples"] == "3"
    assert row["predictions"] == "3"
