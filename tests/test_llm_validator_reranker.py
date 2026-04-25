from pathlib import Path

import pytest

from t2v_eval.baselines.llm_validator_reranker import (
    LLMRerankerConfig,
    METHOD_NAME,
    score_candidate,
    validate_spec_legality,
)
from t2v_eval.data.schema import FieldMetadata, T2VExample
from t2v_eval.metrics.ranking_metrics import evaluate_ranking
from t2v_eval.normalization.vega_lite import normalize_spec


def _example(tmp_path: Path) -> T2VExample:
    table = tmp_path / "table.csv"
    table.write_text(
        "month,region,sales\n"
        "2024-01,North,100\n"
        "2024-02,South,160\n",
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
    ]
    gold = {
        "mark": "line",
        "encoding": {
            "x": {"field": "month", "type": "temporal"},
            "y": {"field": "sales", "type": "quantitative", "aggregate": "sum"},
        },
    }
    return T2VExample(
        example_id="ex1",
        query="Show sales by month",
        table_path=str(table),
        metadata={"fields": fields},
        gold_spec=gold,
    )


def test_reranker_config_uses_b4_and_rejects_qwen25() -> None:
    config = LLMRerankerConfig()

    assert METHOD_NAME == "B4_llm_validator_reranker"
    assert config.candidate_count == 3
    assert config.candidate_temperatures == (0.0, 0.2, 0.3)
    with pytest.raises(ValueError, match="Qwen2.5"):
        LLMRerankerConfig(model_id="Qwen/Qwen2.5-7B")


def test_validator_rejects_illegal_fields_without_gold(tmp_path: Path) -> None:
    example = _example(tmp_path)
    spec = {
        "mark": "bar",
        "encoding": {
            "x": {"field": "missing", "type": "nominal"},
            "y": {"field": "sales", "type": "quantitative", "aggregate": "sum"},
        },
    }

    legality = validate_spec_legality(spec, normalize_spec(spec), example)

    assert legality["field_legality"] == 0.0
    assert legality["illegal_fields"] == ["missing"]
    assert legality["aggregation_legality"] == 1.0


def test_score_candidate_prefers_valid_legal_spec(tmp_path: Path) -> None:
    example = _example(tmp_path)
    valid = '{"mark":"line","encoding":{"x":{"field":"month","type":"temporal"},"y":{"field":"sales","type":"quantitative","aggregate":"sum"}}}'
    illegal = '{"mark":"bar","encoding":{"x":{"field":"missing","type":"nominal"},"y":{"field":"sales","type":"quantitative","aggregate":"sum"}}}'

    valid_candidate = score_candidate(valid, example, candidate_index=0)
    illegal_candidate = score_candidate(illegal, example, candidate_index=1)

    assert valid_candidate["score"] > illegal_candidate["score"]
    assert valid_candidate["normalized_spec"]["valid"] is True
    assert illegal_candidate["validator"]["field_legality"] == 0.0


def test_oracle_at_3_counts_later_exact_match(tmp_path: Path) -> None:
    example = _example(tmp_path)
    gold = example.gold_spec
    wrong = {
        "raw_spec": {
            "mark": "bar",
            "encoding": {
                "x": {"field": "region", "type": "nominal"},
                "y": {"field": "sales", "type": "quantitative", "aggregate": "sum"},
            },
        },
        "score": 1.0,
    }
    exact = {
        "raw_spec": gold,
        "score": 0.9,
    }

    metrics = evaluate_ranking(gold, [wrong, exact], k=3)

    assert metrics["top1_success"] == 0.0
    assert metrics["oracle_success_at_k"] == 1.0
    assert metrics["mrr"] == 0.5
