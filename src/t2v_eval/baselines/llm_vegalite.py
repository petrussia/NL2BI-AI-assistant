"""Local LLM baseline for Vega-Lite JSON generation.

This module intentionally avoids closed APIs. It provides prompt construction,
JSON extraction, repair-lite validation, and a thin Hugging Face Transformers
runtime wrapper for Colab execution.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from time import perf_counter
from typing import Any, Protocol

import pandas as pd

from t2v_eval.data.schema import FieldMetadata, T2VExample, T2VPrediction
from t2v_eval.normalization.vega_lite import normalize_spec

try:
    import psutil
except ModuleNotFoundError:  # pragma: no cover - dependency is in requirements.
    psutil = None  # type: ignore[assignment]


METHOD_NAME = "B3_local_llm_qwen3_8b"
DEFAULT_MODEL_ID = "Qwen/Qwen3-8B"
ALLOWED_CHART_TYPES = ("bar", "line", "point", "area", "tick", "text")
DEFAULT_SAMPLE_ROWS = 5
DEFAULT_MAX_NEW_TOKENS = 384
DEFAULT_MAX_VALIDATION_RETRIES = 3
MAX_RETRY_OUTPUT_CHARS = 1600
_AGGREGATE_MEASURE_PREFIXES = ("count(", "sum(", "avg(", "mean(", "min(", "max(")


class ChatTemplateTokenizer(Protocol):
    def apply_chat_template(self, *args: Any, **kwargs: Any) -> str: ...


@dataclass(slots=True)
class LLMVegaLiteConfig:
    model_id: str = DEFAULT_MODEL_ID
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS
    temperature: float = 0.0
    top_p: float = 1.0
    seed: int = 42
    sample_rows: int = DEFAULT_SAMPLE_ROWS
    quantization: str | None = "4bit"
    torch_dtype: str = "auto"
    device_map: str = "auto"
    trust_remote_code: bool = True
    enable_thinking: bool = False
    stop_after_json: bool = True
    max_validation_retries: int = DEFAULT_MAX_VALIDATION_RETRIES

    def __post_init__(self) -> None:
        if "qwen2.5" in self.model_id.lower():
            raise ValueError("Stage 6 must not use Qwen2.5 models.")
        if self.max_new_tokens <= 0:
            raise ValueError("max_new_tokens must be positive.")
        if self.sample_rows < 0:
            raise ValueError("sample_rows must be non-negative.")
        if self.max_validation_retries < 0:
            raise ValueError("max_validation_retries must be non-negative.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LLMVegaLitePredictor:
    """A loaded local Transformers model used for batch prediction."""

    def __init__(self, config: LLMVegaLiteConfig) -> None:
        self.config = config
        self.tokenizer: Any | None = None
        self.model: Any | None = None

    def load(self) -> "LLMVegaLitePredictor":
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ModuleNotFoundError as exc:  # pragma: no cover - Colab path.
            raise RuntimeError(
                "transformers and torch are required for Stage 6 local LLM runs."
            ) from exc

        model_kwargs: dict[str, Any] = {
            "device_map": self.config.device_map,
            "trust_remote_code": self.config.trust_remote_code,
        }
        if self.config.torch_dtype != "auto":
            model_kwargs["torch_dtype"] = getattr(torch, self.config.torch_dtype)
        else:
            model_kwargs["torch_dtype"] = "auto"

        if self.config.quantization == "4bit":
            try:
                from transformers import BitsAndBytesConfig

                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                )
            except Exception as exc:  # pragma: no cover - Colab path.
                raise RuntimeError("4-bit quantization requires bitsandbytes.") from exc

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_id,
            trust_remote_code=self.config.trust_remote_code,
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            self.config.model_id,
            **model_kwargs,
        )
        self.model.eval()
        return self

    def predict(self, example: T2VExample, *, run_id: str) -> T2VPrediction:
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("LLMVegaLitePredictor.load() must be called first.")

        start = perf_counter()
        start_memory = _memory_mb()
        prompt = build_prompt(example, sample_rows=self.config.sample_rows)
        try:
            generation = self.generate_validated(
                prompt,
                example,
            )
            return prediction_from_validated_generation(
                example=example,
                generation=generation,
                run_id=run_id,
                method=METHOD_NAME,
                latency_ms=_elapsed_ms(start),
                memory_peak_mb=_max_memory(start_memory),
            )
        except Exception as exc:  # pragma: no cover - safety path for batch runs.
            return T2VPrediction.failed(
                run_id=run_id,
                method=METHOD_NAME,
                example_id=example.example_id,
                error=str(exc),
                latency_ms=_elapsed_ms(start),
            )

    def generate(
        self,
        prompt: str,
        *,
        temperature: float | None = None,
        top_p: float | None = None,
        max_new_tokens: int | None = None,
    ) -> str:
        import torch

        assert self.model is not None
        assert self.tokenizer is not None

        text = format_prompt_for_model(
            self.tokenizer,
            prompt,
            enable_thinking=self.config.enable_thinking,
        )

        inputs = self.tokenizer(text, return_tensors="pt")
        inputs = {key: value.to(self.model.device) for key, value in inputs.items()}
        generation_temperature = self.config.temperature if temperature is None else temperature
        generation_top_p = self.config.top_p if top_p is None else top_p
        generation_max_new_tokens = (
            self.config.max_new_tokens if max_new_tokens is None else max_new_tokens
        )
        do_sample = generation_temperature > 0
        eos_token_id = self.tokenizer.eos_token_id
        pad_token_id = self.tokenizer.pad_token_id or eos_token_id
        generation_kwargs: dict[str, Any] = {
            **inputs,
            "max_new_tokens": generation_max_new_tokens,
            "do_sample": do_sample,
            "pad_token_id": pad_token_id,
            "eos_token_id": eos_token_id,
            "use_cache": True,
        }
        if do_sample:
            generation_kwargs["temperature"] = generation_temperature
            generation_kwargs["top_p"] = generation_top_p
        if self.config.stop_after_json:
            from transformers import StoppingCriteriaList

            generation_kwargs["stopping_criteria"] = StoppingCriteriaList(
                [_StopOnValidJson(self.tokenizer, inputs["input_ids"].shape[-1])]
            )

        with torch.no_grad():
            output_ids = self.model.generate(**generation_kwargs)
        generated = output_ids[0][inputs["input_ids"].shape[-1] :]
        return strip_thinking_blocks(
            self.tokenizer.decode(generated, skip_special_tokens=True)
        ).strip()

    def generate_validated(
        self,
        prompt: str,
        example: T2VExample,
        *,
        temperature: float | None = None,
        top_p: float | None = None,
        max_new_tokens: int | None = None,
        max_retries: int | None = None,
    ) -> dict[str, Any]:
        """Generate JSON, validate it strictly, and retry with validator feedback."""

        retry_limit = self.config.max_validation_retries if max_retries is None else max_retries
        current_prompt = prompt
        attempts: list[dict[str, Any]] = []
        raw_output = ""
        validation: dict[str, Any] = {
            "valid": False,
            "error": "not_generated",
            "feedback": "The model did not return any output.",
        }

        for attempt_index in range(retry_limit + 1):
            raw_output = self.generate(
                current_prompt,
                temperature=temperature,
                top_p=top_p,
                max_new_tokens=max_new_tokens,
            )
            validation = validate_generated_spec(
                raw_output,
                example,
                strict_json=True,
                allow_repair=False,
            )
            attempts.append(_validation_attempt(attempt_index, raw_output, validation))
            if validation["valid"]:
                return {
                    "valid": True,
                    "raw_output": raw_output,
                    "validation": validation,
                    "attempts": attempts,
                }
            if attempt_index < retry_limit:
                current_prompt = build_retry_prompt(
                    prompt,
                    raw_output=raw_output,
                    validation=validation,
                    retry_number=attempt_index + 1,
                    max_retries=retry_limit,
                )

        return {
            "valid": False,
            "raw_output": raw_output,
            "validation": validation,
            "attempts": attempts,
        }


def format_prompt_for_model(
    tokenizer: Any,
    prompt: str,
    *,
    enable_thinking: bool = False,
) -> str:
    system_prompt = (
        "You are a deterministic Text-to-Visualization compiler. "
        "Return only one compact Vega-Lite JSON object. /no_think"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt + "\n/no_think"},
    ]
    if hasattr(tokenizer, "apply_chat_template"):
        try:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=enable_thinking,
            )
        except TypeError:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
    return f"{system_prompt}\n\n{prompt}\n/no_think\n"


def build_prompt(
    example: T2VExample,
    *,
    sample_rows: int = DEFAULT_SAMPLE_ROWS,
    allowed_chart_types: tuple[str, ...] = ALLOWED_CHART_TYPES,
) -> str:
    schema = compact_schema(example.fields)
    preview = table_preview(example, sample_rows=sample_rows)
    return (
        "You are a local Text-to-Visualization model. "
        "Return only one minimal valid JSON object for a Vega-Lite chart spec. "
        "Do not use markdown, comments, explanations, code fences, or reasoning. "
        "Do not output <think> blocks.\n\n"
        f"User query:\n{example.query}\n\n"
        f"Allowed chart mark types:\n{', '.join(allowed_chart_types)}\n\n"
        "Schema metadata as JSON:\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        f"First {len(preview)} table rows as JSON:\n"
        f"{json.dumps(preview, ensure_ascii=False, indent=2)}\n\n"
        "Requirements:\n"
        "- Use only fields from the schema.\n"
        "- Choose Vega-Lite encoding types compatible with field dtypes.\n"
        "- Prefer simple compact specs with only mark and encoding.\n"
        "- Use aggregate only when it is allowed by field metadata.\n"
        "- Return JSON only, starting with { and ending with }.\n"
    )


def compact_schema(fields: list[FieldMetadata]) -> list[dict[str, Any]]:
    return [
        {
            "name": field.name,
            "dtype": field.dtype,
            "role": field.role,
            "description": field.description,
            "unit": field.unit,
            "allowed_aggregations": field.allowed_aggregations,
        }
        for field in fields
    ]


def table_preview(example: T2VExample, *, sample_rows: int = DEFAULT_SAMPLE_ROWS) -> list[dict[str, Any]]:
    if sample_rows <= 0:
        return []
    try:
        table = pd.read_csv(example.table, nrows=sample_rows)
    except Exception:
        return []
    return json.loads(table.to_json(orient="records", force_ascii=False))


def prediction_from_validated_generation(
    *,
    example: T2VExample,
    generation: dict[str, Any],
    run_id: str,
    method: str = METHOD_NAME,
    latency_ms: float | None = None,
    memory_peak_mb: float | None = None,
) -> T2VPrediction:
    attempts = list(generation.get("attempts") or [])
    raw_output = str(generation.get("raw_output") or "")
    validation = generation.get("validation") or {}
    if not generation.get("valid"):
        return T2VPrediction(
            run_id=run_id,
            method=method,
            example_id=example.example_id,
            status="failed",
            raw_output=raw_output,
            candidates=[{"validation_attempts": attempts}],
            latency_ms=latency_ms,
            memory_peak_mb=memory_peak_mb,
            error=str(validation.get("error") or "validated_generation_failed"),
        )

    spec = validation["spec"]
    normalized = validation["normalized_spec"]
    candidate = {
        "raw_spec": spec,
        "normalized_spec": normalized,
        "score": 1.0,
        "reason": validation.get("repair_status") or "strict_json_validated",
        "validation_attempts": attempts,
    }
    return T2VPrediction(
        run_id=run_id,
        method=method,
        example_id=example.example_id,
        status="ok",
        raw_output=raw_output,
        raw_spec=spec,
        normalized_spec=normalized,
        candidates=[candidate],
        latency_ms=latency_ms,
        memory_peak_mb=memory_peak_mb,
    )


def prediction_from_text(
    example: T2VExample,
    raw_output: str,
    *,
    run_id: str,
    method: str = METHOD_NAME,
    latency_ms: float | None = None,
    memory_peak_mb: float | None = None,
) -> T2VPrediction:
    extraction = extract_and_repair_spec(raw_output, example)
    if not extraction["valid"]:
        return T2VPrediction.failed(
            run_id=run_id,
            method=method,
            example_id=example.example_id,
            raw_output=raw_output,
            error=extraction["error"],
            latency_ms=latency_ms,
        )

    spec = extraction["spec"]
    normalized = normalize_spec(spec)
    candidate = {
        "raw_spec": spec,
        "normalized_spec": normalized,
        "score": 1.0,
        "reason": extraction["repair_status"],
    }
    return T2VPrediction(
        run_id=run_id,
        method=method,
        example_id=example.example_id,
        status="ok",
        raw_output=raw_output,
        raw_spec=spec,
        normalized_spec=normalized,
        candidates=[candidate],
        latency_ms=latency_ms,
        memory_peak_mb=memory_peak_mb,
    )


def extract_and_repair_spec(raw_output: str, example: T2VExample) -> dict[str, Any]:
    return validate_generated_spec(
        raw_output,
        example,
        strict_json=False,
        allow_repair=True,
    )


def validate_generated_spec(
    raw_output: str,
    example: T2VExample,
    *,
    allowed_chart_types: tuple[str, ...] = ALLOWED_CHART_TYPES,
    strict_json: bool = True,
    allow_repair: bool = False,
) -> dict[str, Any]:
    """Validate generated output as JSON and as a constrained Vega-Lite spec."""

    parse_result = parse_json_object(raw_output, strict_json=strict_json)
    if not parse_result["valid"]:
        return parse_result

    spec = parse_result["spec"]
    repair_notes: list[str] = []
    if allow_repair:
        spec, repair_notes = repair_lite(spec, example)

    strict_schema_error = None if allow_repair else _strict_schema_error(spec)
    if strict_schema_error is not None:
        return _invalid_validation(
            strict_schema_error["error"],
            strict_schema_error["feedback"],
            spec=spec,
            repair_status="strict_schema_failed",
        )

    normalized = normalize_spec(spec)
    if not normalized["valid"]:
        error = str(normalized.get("error", "invalid_spec"))
        return _invalid_validation(
            error,
            _normalization_feedback(error),
            spec=spec,
            normalized_spec=normalized,
            repair_status=",".join(repair_notes) or "unrepaired_invalid",
        )

    chart_type = str(normalized.get("chart_type") or "").lower()
    allowed = {mark.lower() for mark in allowed_chart_types}
    if chart_type not in allowed:
        return _invalid_validation(
            f"unsupported_mark_type:{chart_type or 'missing'}",
            (
                f"Use one of the allowed mark values: {', '.join(allowed_chart_types)}. "
                "Do not use arc or pie."
            ),
            spec=spec,
            normalized_spec=normalized,
            repair_status=",".join(repair_notes) or "unsupported_mark_type",
        )

    contract_error = _spec_contract_error(normalized, example)
    if contract_error is not None:
        return _invalid_validation(
            contract_error["error"],
            contract_error["feedback"],
            spec=spec,
            normalized_spec=normalized,
            repair_status=",".join(repair_notes) or "contract_validation_failed",
        )

    return {
        "valid": True,
        "error": None,
        "feedback": None,
        "spec": spec,
        "normalized_spec": normalized,
        "repair_status": ",".join(repair_notes) or "strict_json_validated",
    }


def parse_json_object(raw_output: str, *, strict_json: bool) -> dict[str, Any]:
    if not strict_json:
        try:
            return {"valid": True, "error": None, "feedback": None, "spec": extract_json_object(raw_output)}
        except ValueError as exc:
            return _invalid_validation("parse_failed", str(exc), repair_status="parse_failed")

    text = strip_thinking_blocks(raw_output).strip()
    if not text:
        return _invalid_validation(
            "empty_output",
            "Return exactly one JSON object. The response is empty.",
            repair_status="parse_failed",
        )

    decoder = json.JSONDecoder()
    try:
        value, end = decoder.raw_decode(text)
    except json.JSONDecodeError as exc:
        return _invalid_validation(
            f"invalid_json:line_{exc.lineno}:column_{exc.colno}:{exc.msg}",
            (
                f"JSON syntax error at line {exc.lineno}, column {exc.colno}: {exc.msg}. "
                "Return exactly one JSON object that starts with { and ends with }. "
                "Use double quotes for all keys and strings, and do not use markdown fences or explanations."
            ),
            repair_status="parse_failed",
        )

    trailing = text[end:]
    if trailing.strip():
        offset = end + len(trailing) - len(trailing.lstrip())
        line, column = _line_column(text, offset)
        return _invalid_validation(
            f"invalid_json_extra_text:line_{line}:column_{column}",
            (
                f"Extra text starts after the JSON object at line {line}, column {column}. "
                "Remove all text before or after the JSON. Return only one JSON object."
            ),
            spec=value if isinstance(value, dict) else None,
            repair_status="parse_failed",
        )

    if not isinstance(value, dict):
        return _invalid_validation(
            f"json_root_not_object:{type(value).__name__}",
            "The JSON root must be an object like {\"mark\":\"bar\",\"encoding\":{...}}, not an array or scalar.",
            repair_status="parse_failed",
        )
    return {"valid": True, "error": None, "feedback": None, "spec": value}


def build_retry_prompt(
    original_prompt: str,
    *,
    raw_output: str,
    validation: dict[str, Any],
    retry_number: int,
    max_retries: int,
) -> str:
    return (
        f"{original_prompt}\n\n"
        f"Your previous answer failed validation. Retry {retry_number} of {max_retries}.\n"
        f"Validator error:\n{validation.get('error')}\n\n"
        f"How to fix it:\n{validation.get('feedback')}\n\n"
        "Previous invalid answer:\n"
        f"{_truncate(raw_output, MAX_RETRY_OUTPUT_CHARS)}\n\n"
        "Return the corrected answer now. Output only one JSON object, no markdown, no explanations."
    )


def _strict_schema_error(spec: dict[str, Any]) -> dict[str, str] | None:
    if "mark" not in spec:
        if "chart_type" in spec or "chartType" in spec:
            return {
                "error": "missing_mark:used_chart_type",
                "feedback": "Use top-level key `mark`, not `chart_type` or `chartType`.",
            }
        return {
            "error": "missing_mark",
            "feedback": "Add a top-level `mark` key with an allowed value such as `bar`, `line`, or `point`.",
        }
    if "encoding" not in spec:
        top_level_channels = sorted(set(spec) & {"x", "y", "color", "tooltip", "text"})
        if top_level_channels:
            return {
                "error": f"missing_encoding:top_level_channels:{','.join(top_level_channels)}",
                "feedback": "Put channel definitions inside `encoding`, for example `{\"encoding\":{\"x\":{...},\"y\":{...}}}`.",
            }
        return {
            "error": "missing_encoding",
            "feedback": "Add a top-level `encoding` object with the chart channels.",
        }
    if not isinstance(spec.get("encoding"), dict):
        return {
            "error": f"encoding_not_object:{type(spec.get('encoding')).__name__}",
            "feedback": "`encoding` must be a JSON object, not a list or string.",
        }
    return None


def _spec_contract_error(normalized: dict[str, Any], example: T2VExample) -> dict[str, str] | None:
    encoding = normalized.get("encoding") or {}
    if not encoding:
        return {
            "error": "empty_encoding",
            "feedback": "Add at least one useful encoding channel using fields from the schema.",
        }

    fields_by_name = {field.name: field for field in example.fields}
    valid_fields = ", ".join(fields_by_name) or "no fields available"
    for channel, channel_value in encoding.items():
        for item in _channel_items(channel_value):
            field_name = item.get("field")
            field = fields_by_name.get(str(field_name)) if field_name else None
            path = f"encoding.{channel}.field"
            if field_name and field is None:
                return {
                    "error": f"unknown_field:{path}:{field_name}",
                    "feedback": f"At `{path}`, use only fields from the schema. Valid fields: {valid_fields}.",
                }
            declared_type = item.get("type")
            if field is not None and declared_type and not _type_compatible(field, declared_type):
                return {
                    "error": f"incompatible_type:encoding.{channel}.type:{field.name}:{declared_type}",
                    "feedback": (
                        f"`encoding.{channel}.type` is incompatible with field `{field.name}`. "
                        f"Use `{_vega_type(field)}` for this field."
                    ),
                }
            aggregate = item.get("aggregate")
            if aggregate and not _aggregate_allowed(field, str(aggregate)):
                return {
                    "error": f"disallowed_aggregate:encoding.{channel}.aggregate:{aggregate}",
                    "feedback": (
                        f"Aggregate `{aggregate}` is not allowed for this field. "
                        "Use one of the field's allowed aggregations or `count` when appropriate."
                    ),
                }
    return None


def _invalid_validation(
    error: str,
    feedback: str,
    *,
    spec: dict[str, Any] | None = None,
    normalized_spec: dict[str, Any] | None = None,
    repair_status: str = "validation_failed",
) -> dict[str, Any]:
    return {
        "valid": False,
        "error": error,
        "feedback": feedback,
        "spec": spec,
        "normalized_spec": normalized_spec,
        "repair_status": repair_status,
    }


def _validation_attempt(
    attempt_index: int,
    raw_output: str,
    validation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "attempt": attempt_index + 1,
        "valid": bool(validation.get("valid")),
        "error": validation.get("error"),
        "feedback": validation.get("feedback"),
        "raw_output_excerpt": _truncate(raw_output, MAX_RETRY_OUTPUT_CHARS),
    }


def _normalization_feedback(error: str) -> str:
    if error == "missing_mark":
        return "Add top-level `mark`, for example `\"mark\":\"bar\"`."
    if error == "encoding_not_object":
        return "Make `encoding` a JSON object with channels such as `x` and `y`."
    return "Return a valid compact Vega-Lite JSON object with top-level `mark` and `encoding`."


def _line_column(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    line_start = text.rfind("\n", 0, offset)
    column = offset + 1 if line_start < 0 else offset - line_start
    return line, column


def _truncate(value: str, max_chars: int) -> str:
    text = value.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...<truncated>"


def _type_compatible(field: FieldMetadata, vega_type: Any) -> bool:
    normalized_type = str(vega_type).lower()
    expected = _vega_type(field)
    if expected == "temporal":
        return normalized_type in {"temporal", "ordinal", "nominal"}
    if expected == "quantitative":
        return normalized_type in {"quantitative", "ordinal"}
    return normalized_type in {"nominal", "ordinal"}


def _aggregate_allowed(field: FieldMetadata | None, aggregate: str) -> bool:
    aggregate = aggregate.lower()
    if aggregate == "count":
        return True
    if field is None:
        return False
    allowed = {item.lower() for item in field.allowed_aggregations}
    if allowed:
        return aggregate in allowed
    return field.role == "measure"


def extract_json_object(raw_output: str) -> dict[str, Any]:
    text = strip_markdown_fences(strip_thinking_blocks(raw_output)).strip()
    first_object = _first_json_object_from_first_brace(text)
    if first_object is not None:
        return first_object
    for start in [match.start() for match in re.finditer(r"\{", text)]:
        candidate = _first_balanced_object(text[start:])
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("No valid JSON object found in model output.")


def strip_markdown_fences(raw_output: str) -> str:
    text = raw_output.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def strip_thinking_blocks(raw_output: str) -> str:
    text = raw_output.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"</?think>", "", text, flags=re.IGNORECASE)
    return text.strip()


def repair_lite(spec: dict[str, Any], example: T2VExample) -> tuple[dict[str, Any], list[str]]:
    repaired = dict(spec)
    notes: list[str] = []
    if "mark" not in repaired and "chart_type" in repaired:
        repaired["mark"] = repaired.pop("chart_type")
        notes.append("chart_type_to_mark")
    if "mark" in repaired and isinstance(repaired["mark"], dict) and "type" not in repaired["mark"]:
        mark_value = repaired["mark"].get("mark")
        if mark_value:
            repaired["mark"] = {"type": mark_value}
            notes.append("mark_mark_to_type")
    if "encoding" not in repaired:
        encoding = {
            key: repaired.pop(key)
            for key in ("x", "y", "color", "tooltip", "text")
            if isinstance(repaired.get(key), dict)
        }
        if encoding:
            repaired["encoding"] = encoding
            notes.append("top_level_channels_to_encoding")

    field_types = {field.name: _vega_type(field) for field in example.fields}
    encoding = repaired.get("encoding")
    if isinstance(encoding, dict):
        for channel_value in encoding.values():
            for item in _channel_items(channel_value):
                field = item.get("field")
                if field and "type" not in item and field in field_types:
                    item["type"] = field_types[str(field)]
                    notes.append("filled_missing_type")

    return repaired, notes


def gpu_runtime_info() -> dict[str, Any]:
    info: dict[str, Any] = {"cuda_available": False}
    try:
        import torch
    except ModuleNotFoundError:
        info["error"] = "torch_not_installed"
        return info

    info["cuda_available"] = bool(torch.cuda.is_available())
    if not torch.cuda.is_available():
        return info
    device = torch.cuda.current_device()
    properties = torch.cuda.get_device_properties(device)
    info.update(
        {
            "device_index": device,
            "device_name": torch.cuda.get_device_name(device),
            "vram_total_mb": round(properties.total_memory / (1024 * 1024), 2),
            "memory_allocated_mb": round(torch.cuda.memory_allocated(device) / (1024 * 1024), 2),
            "memory_reserved_mb": round(torch.cuda.memory_reserved(device) / (1024 * 1024), 2),
            "max_memory_allocated_mb": round(torch.cuda.max_memory_allocated(device) / (1024 * 1024), 2),
        }
    )
    return info


def _first_balanced_object(text: str) -> str | None:
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[: index + 1]
    return None


class _StopOnValidJson:
    def __init__(self, tokenizer: Any, prompt_tokens: int) -> None:
        self.tokenizer = tokenizer
        self.prompt_tokens = prompt_tokens

    def __call__(self, input_ids: Any, scores: Any, **kwargs: Any) -> bool:
        generated_ids = input_ids[0][self.prompt_tokens :]
        if len(generated_ids) == 0:
            return False
        text = strip_thinking_blocks(
            self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        )
        return _first_json_object_from_first_brace(text) is not None


def _first_json_object_from_first_brace(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    if start < 0:
        return None
    candidate = _first_balanced_object(text[start:])
    if not candidate:
        return None
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _channel_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _vega_type(field: FieldMetadata) -> str:
    dtype = field.dtype.lower()
    name = field.name.lower()
    if _is_aggregate_measure(field):
        return "quantitative"
    if field.role == "time" or "date" in name or "time" in name or "year" in name:
        return "temporal"
    if field.role == "measure" or any(token in dtype for token in ("int", "float", "double", "decimal", "number")):
        return "quantitative"
    return "nominal"


def _is_aggregate_measure(field: FieldMetadata) -> bool:
    dtype = field.dtype.lower()
    name = field.name.strip().lower()
    return name.startswith(_AGGREGATE_MEASURE_PREFIXES) and any(
        token in dtype for token in ("int", "float", "double", "decimal", "number")
    )


def _elapsed_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000, 3)


def _memory_mb() -> float | None:
    if psutil is None:
        return None
    return round(psutil.Process().memory_info().rss / (1024 * 1024), 3)


def _max_memory(start_memory: float | None) -> float | None:
    current = _memory_mb()
    values = [value for value in (start_memory, current) if value is not None]
    return max(values) if values else None
