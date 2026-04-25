import csv
from pathlib import Path

from scripts.run_experiment import run_experiment
from t2v_eval.baselines.constraint_ranker import generate_candidates as generate_b1
from t2v_eval.baselines.constraint_ranker import passes_hard_constraints
from t2v_eval.baselines.rule_based import generate_candidates as generate_b0
from t2v_eval.baselines.rule_based import predict as predict_b0
from t2v_eval.data.schema import FieldMetadata, T2VExample
from t2v_eval.utils.io import read_jsonl, write_jsonl


def _example(query: str = "Show sales by month") -> T2VExample:
    fields = [
        FieldMetadata(name="month", dtype="date", role="time").to_dict(),
        FieldMetadata(
            name="region",
            dtype="string",
            role="dimension",
            allowed_aggregations=["count"],
        ).to_dict(),
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
        table_path="tables/ex1.csv",
        metadata={"fields": fields},
        gold_spec={
            "mark": "line",
            "encoding": {
                "x": {"field": "month", "type": "temporal"},
                "y": {"field": "sales", "type": "quantitative", "aggregate": "sum"},
            },
        },
    )


def test_b0_rule_based_returns_prediction_with_candidates() -> None:
    prediction = predict_b0(_example(), run_id="unit", top_k=3)

    assert prediction.status == "ok"
    assert prediction.raw_spec
    assert prediction.normalized_spec
    assert prediction.candidates
    assert prediction.latency_ms is not None


def test_b0_and_b1_are_different_for_top_query() -> None:
    example = _example("Show top regions by sales")

    b0 = generate_b0(example, top_k=3)
    b1 = generate_b1(example, top_k=3)

    assert b0
    assert b1
    assert [candidate.to_dict()["score"] for candidate in b1] != [
        candidate.to_dict()["score"] for candidate in b0
    ]
    assert b1[0].raw_spec["encoding"]["x"].get("sort") == "-y"


def test_b1_rejects_temporal_axis_for_non_temporal_field() -> None:
    example = _example()
    fields = example.fields
    bad_spec = {
        "mark": "line",
        "encoding": {
            "x": {"field": "region", "type": "temporal"},
            "y": {"field": "sales", "type": "quantitative", "aggregate": "sum"},
        },
    }

    assert passes_hard_constraints(bad_spec, fields) is False


def test_run_experiment_writes_predictions_and_metrics(tmp_path: Path) -> None:
    examples_path = tmp_path / "examples.jsonl"
    drive_root = tmp_path / "drive"
    rows = []
    for index in range(5):
        example = _example("Show sales by month").to_dict()
        example["example_id"] = f"ex{index}"
        rows.append(example)
    write_jsonl(examples_path, rows)

    result = run_experiment(
        examples_path=examples_path,
        method="all",
        drive_root=drive_root,
        run_id="unit_stage4",
        sample_size=3,
        render_limit=0,
    )

    run_root = drive_root / "runs" / "unit_stage4"
    b0_predictions = run_root / "predictions" / "B0_rule_based.jsonl"
    b1_predictions = run_root / "predictions" / "B1_constraint_ranker.jsonl"
    b0_metrics = run_root / "metrics" / "B0_rule_based" / "aggregate_metrics.csv"

    assert result["run_id"] == "unit_stage4"
    assert len(read_jsonl(run_root / "examples_used.jsonl")) == 3
    assert b0_predictions.exists()
    assert b1_predictions.exists()
    assert len(read_jsonl(b0_predictions)) == 3
    assert len(read_jsonl(b1_predictions)) == 3
    with b0_metrics.open(newline="", encoding="utf-8") as file:
        b0_row = next(csv.DictReader(file))
    assert b0_row["examples"] == "3"
    assert b0_metrics.exists()
    assert (run_root / "metrics" / "B1_constraint_ranker" / "aggregate_metrics.csv").exists()
