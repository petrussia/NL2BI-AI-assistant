from pathlib import Path

from scripts.evaluate_predictions import evaluate_predictions
from t2v_eval.metrics.ranking_metrics import evaluate_ranking
from t2v_eval.metrics.spec_metrics import evaluate_spec
from t2v_eval.utils.io import read_csv, write_jsonl


GOLD_BAR = {
    "mark": "bar",
    "encoding": {
        "x": {"field": "region", "type": "nominal"},
        "y": {"field": "sales", "type": "quantitative", "aggregate": "sum"},
    },
}


def test_spec_metrics_separate_chart_and_field_accuracy() -> None:
    predicted = {
        "mark": "line",
        "encoding": {
            "x": {"field": "region", "type": "nominal"},
            "y": {"field": "profit", "type": "quantitative", "aggregate": "sum"},
        },
    }

    metrics = evaluate_spec(GOLD_BAR, predicted)

    assert metrics.chart_type_accuracy == 0.0
    assert metrics.x_field_accuracy == 1.0
    assert metrics.y_field_accuracy == 0.0
    assert 0.0 < metrics.field_selection_f1 < 1.0


def test_invalid_prediction_spec_is_counted_as_failure() -> None:
    metrics = evaluate_spec(GOLD_BAR, {"encoding": {"x": {"field": "region"}}})

    assert metrics.status == "failed"
    assert metrics.vega_lite_validity == 0.0
    assert metrics.normalized_exact_match == 0.0


def test_ranking_metrics_return_none_without_candidates() -> None:
    metrics = evaluate_ranking(GOLD_BAR, [])

    assert metrics["top1_success"] is None
    assert metrics["oracle_success_at_k"] is None


def test_ranking_metrics_find_oracle_success_at_k() -> None:
    candidates = [
        {"spec": {"mark": "line", "encoding": GOLD_BAR["encoding"]}},
        {"spec": GOLD_BAR},
    ]

    metrics = evaluate_ranking(GOLD_BAR, candidates, k=2)

    assert metrics["top1_success"] == 0.0
    assert metrics["oracle_success_at_k"] == 1.0
    assert metrics["mrr"] == 0.5


def test_evaluator_writes_metric_csvs(tmp_path: Path) -> None:
    examples_path = tmp_path / "examples.jsonl"
    predictions_path = tmp_path / "predictions.jsonl"
    output_dir = tmp_path / "metrics"

    write_jsonl(
        examples_path,
        [
            {
                "example_id": "ex1",
                "query": "show sales by region",
                "table_path": "tables/ex1.csv",
                "metadata": {"fields": []},
                "gold_spec": GOLD_BAR,
            },
            {
                "example_id": "ex2",
                "query": "broken spec",
                "table_path": "tables/ex2.csv",
                "metadata": {"fields": []},
                "gold_spec": GOLD_BAR,
            },
        ],
    )
    write_jsonl(
        predictions_path,
        [
            {
                "run_id": "run_test",
                "method": "unit",
                "example_id": "ex1",
                "raw_spec": GOLD_BAR,
                "latency_ms": 10,
                "memory_peak_mb": 50,
            },
            {
                "run_id": "run_test",
                "method": "unit",
                "example_id": "ex2",
                "raw_spec": {"encoding": {"x": {"field": "region"}}},
                "latency_ms": 20,
                "memory_peak_mb": 55,
            },
        ],
    )

    result = evaluate_predictions(
        examples_path=examples_path,
        predictions_path=predictions_path,
        output_dir=output_dir,
        run_id="run_test",
    )

    per_example = read_csv(result["per_example_metrics"])
    aggregate = read_csv(result["aggregate_metrics"])[0]

    assert len(per_example) == 2
    assert aggregate["examples"] == "2"
    assert float(aggregate["vega_lite_validity"]) == 0.5
    assert (output_dir / "per_example_metrics.csv").exists()
    assert (output_dir / "aggregate_metrics.csv").exists()
