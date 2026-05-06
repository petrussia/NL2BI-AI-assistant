from pathlib import Path

import pytest

from t2v_eval.baselines.llm_vegalite import (
    DEFAULT_MODEL_ID,
    DEFAULT_MAX_NEW_TOKENS,
    LLMVegaLiteConfig,
    LLMVegaLitePredictor,
    build_prompt,
    extract_json_object,
    format_prompt_for_model,
    prediction_from_text,
    repair_lite,
    strip_markdown_fences,
    strip_thinking_blocks,
    validate_generated_spec,
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
    assert config.max_new_tokens == DEFAULT_MAX_NEW_TOKENS
    assert config.enable_thinking is False
    assert config.stop_after_json is True
    assert config.max_validation_retries == 3
    with pytest.raises(ValueError, match="Qwen2.5"):
        LLMVegaLiteConfig(model_id="Qwen/Qwen2.5-7B")


def test_prompt_contains_required_inputs(tmp_path: Path) -> None:
    prompt = build_prompt(_example(tmp_path), sample_rows=1)

    assert "Show sales by month" in prompt
    assert "Schema metadata as JSON" in prompt
    assert "First 1 table rows as JSON" in prompt
    assert "Allowed chart mark types" in prompt
    assert "bar, line, point, area, tick, text" in prompt
    assert "arc" not in prompt
    assert "pie" not in prompt
    assert "Return only one minimal valid JSON object" in prompt
    assert "Do not use markdown" in prompt
    assert "Do not output <think> blocks" in prompt
    assert "month" in prompt
    assert "sales" in prompt


def test_format_prompt_disables_qwen3_thinking() -> None:
    class FakeTokenizer:
        def __init__(self) -> None:
            self.kwargs = {}

        def apply_chat_template(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            self.kwargs = kwargs
            return str(messages)

    tokenizer = FakeTokenizer()
    formatted = format_prompt_for_model(tokenizer, "Return JSON")

    assert tokenizer.kwargs["enable_thinking"] is False
    assert tokenizer.kwargs["add_generation_prompt"] is True
    assert "/no_think" in formatted


def test_extract_json_object_removes_markdown_and_prefix() -> None:
    raw = 'Here is the chart:\n```json\n{"mark":"bar","encoding":{}}\n```'

    assert strip_markdown_fences("```json\n{}\n```") == "{}"
    assert extract_json_object(raw) == {"mark": "bar", "encoding": {}}


def test_strip_thinking_blocks_before_json_extraction() -> None:
    raw = "<think>long reasoning</think>\n{\"mark\":\"point\",\"encoding\":{}}"

    assert strip_thinking_blocks(raw) == '{"mark":"point","encoding":{}}'
    assert extract_json_object(raw) == {"mark": "point", "encoding": {}}


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


@pytest.mark.parametrize("mark", ["arc", "pie"])
def test_prediction_rejects_unsupported_pie_marks(tmp_path: Path, mark: str) -> None:
    raw = """
    {
      "mark": "%s",
      "encoding": {
        "theta": {"field": "sales", "type": "quantitative"},
        "color": {"field": "region", "type": "nominal"}
      }
    }
    """ % mark

    prediction = prediction_from_text(_example(tmp_path), raw, run_id="unit")

    assert prediction.status == "failed"
    assert prediction.error == f"unsupported_mark_type:{mark}"


def test_strict_validator_reports_json_location_and_fix(tmp_path: Path) -> None:
    raw = '{"mark":"bar" "encoding":{"x":{"field":"month","type":"temporal"}}}'

    validation = validate_generated_spec(raw, _example(tmp_path), strict_json=True)

    assert validation["valid"] is False
    assert validation["error"].startswith("invalid_json:line_1:column_15")
    assert "line 1, column 15" in validation["feedback"]
    assert "Return exactly one JSON object" in validation["feedback"]


def test_strict_validator_rejects_unknown_schema_field(tmp_path: Path) -> None:
    raw = '{"mark":"line","encoding":{"x":{"field":"missing","type":"temporal"},"y":{"field":"sales","type":"quantitative"}}}'

    validation = validate_generated_spec(raw, _example(tmp_path), strict_json=True)

    assert validation["valid"] is False
    assert validation["error"] == "unknown_field:encoding.x.field:missing"
    assert "Valid fields: month, region, sales" in validation["feedback"]


def test_generate_validated_retries_with_validator_feedback(tmp_path: Path) -> None:
    example = _example(tmp_path)
    predictor = _FakePredictor(
        [
            '{"mark":"line","encoding":{"x":{"field":"missing","type":"temporal"},"y":{"field":"sales","type":"quantitative"}}}',
            '{"mark":"line","encoding":{"x":{"field":"month","type":"temporal"},"y":{"field":"sales","type":"quantitative"}}}',
        ]
    )

    generation = predictor.generate_validated("BASE PROMPT", example)

    assert generation["valid"] is True
    assert len(generation["attempts"]) == 2
    assert "unknown_field:encoding.x.field:missing" in predictor.prompts[1]
    assert "Valid fields: month, region, sales" in predictor.prompts[1]


def test_generate_validated_stops_after_three_retries(tmp_path: Path) -> None:
    example = _example(tmp_path)
    predictor = _FakePredictor(['{"mark":"arc","encoding":{}}'] * 10)

    generation = predictor.generate_validated("BASE PROMPT", example)

    assert generation["valid"] is False
    assert len(generation["attempts"]) == 4
    assert len(predictor.prompts) == 4
    assert generation["validation"]["error"] == "unsupported_mark_type:arc"


class _FakePredictor(LLMVegaLitePredictor):
    def __init__(self, outputs: list[str]) -> None:
        super().__init__(LLMVegaLiteConfig())
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    def generate(self, prompt: str, **_kwargs) -> str:  # type: ignore[no-untyped-def]
        self.prompts.append(prompt)
        if not self.outputs:
            raise AssertionError("No fake outputs left.")
        return self.outputs.pop(0)
