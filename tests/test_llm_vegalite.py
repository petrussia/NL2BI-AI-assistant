from pathlib import Path

import pytest

from t2v_eval.baselines.llm_vegalite import (
    DEFAULT_MODEL_ID,
    LLMVegaLiteConfig,
    build_prompt,
    extract_json_object,
    prediction_from_text,
    repair_lite,
    strip_markdown_fences,
)
from t2v_eval.data.schema import FieldMetadata, T2VExample


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
    return T2VExample(
        example_id="ex1",
        query="Show sales by month",
        table_path=str(table),
        metadata={"fields": fields},
        gold_spec={
            "mark": "line",
            "encoding": {
                "x": {"field": "month", "type": "temporal"},
                "y": {"field": "sales", "type": "quantitative", "aggregate": "sum"},
            },
        },
    )


def test_config_uses_qwen3_and_rejects_qwen25() -> None:
    config = LLMVegaLiteConfig()

    assert config.model_id == DEFAULT_MODEL_ID
    assert "Qwen3" in config.model_id
    with pytest.raises(ValueError, match="Qwen2.5"):
        LLMVegaLiteConfig(model_id="Qwen/Qwen2.5-7B")


def test_prompt_contains_required_inputs(tmp_path: Path) -> None:
    prompt = build_prompt(_example(tmp_path), sample_rows=1)

    assert "Show sales by month" in prompt
    assert "Schema metadata as JSON" in prompt
    assert "First 1 table rows as JSON" in prompt
    assert "Allowed chart mark types" in prompt
    assert "Return only one valid JSON object" in prompt
    assert "Do not use markdown" in prompt
    assert "month" in prompt
    assert "sales" in prompt


def test_extract_json_object_removes_markdown_and_prefix() -> None:
    raw = 'Here is the chart:\n```json\n{"mark":"bar","encoding":{}}\n```'

    assert strip_markdown_fences("```json\n{}\n```") == "{}"
    assert extract_json_object(raw) == {"mark": "bar", "encoding": {}}


def test_repair_lite_fills_mark_and_encoding_type(tmp_path: Path) -> None:
    example = _example(tmp_path)
    spec = {
        "chart_type": "line",
        "encoding": {
            "x": {"field": "month"},
            "y": {"field": "sales", "aggregate": "sum"},
        },
    }

    repaired, notes = repair_lite(spec, example)

    assert repaired["mark"] == "line"
    assert repaired["encoding"]["x"]["type"] == "temporal"
    assert repaired["encoding"]["y"]["type"] == "quantitative"
    assert "chart_type_to_mark" in notes


def test_prediction_from_text_returns_common_prediction_shape(tmp_path: Path) -> None:
    raw = """
    ```json
    {
      "mark": "line",
      "encoding": {
        "x": {"field": "month", "type": "temporal"},
        "y": {"field": "sales", "type": "quantitative", "aggregate": "sum"}
      }
    }
    ```
    """

    prediction = prediction_from_text(_example(tmp_path), raw, run_id="unit")

    assert prediction.status == "ok"
    assert prediction.raw_spec
    assert prediction.normalized_spec
    assert prediction.candidates
    assert prediction.raw_output == raw
