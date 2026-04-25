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
from typing import Any

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


@dataclass(slots=True)
class LLMVegaLiteConfig:
    model_id: str = DEFAULT_MODEL_ID
    max_new_tokens: int = 1024
    temperature: float = 0.0
    top_p: float = 1.0
    seed: int = 42
    sample_rows: int = DEFAULT_SAMPLE_ROWS
    quantization: str | None = "4bit"
    torch_dtype: str = "auto"
    device_map: str = "auto"
    trust_remote_code: bool = True

    def __post_init__(self) -> None:
        if "qwen2.5" in self.model_id.lower():
            raise ValueError("Stage 6 must not use Qwen2.5 models.")
        if self.max_new_tokens <= 0:
            raise ValueError("max_new_tokens must be positive.")
        if self.sample_rows < 0:
            raise ValueError("sample_rows must be non-negative.")

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
            raw_output = self.generate(prompt)
            return prediction_from_text(
                example,
                raw_output,
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

    def generate(self, prompt: str) -> str:
        import torch

        assert self.model is not None
        assert self.tokenizer is not None

        if hasattr(self.tokenizer, "apply_chat_template"):
            text = self.tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                tokenize=False,
                add_generation_prompt=True,
            )
        else:
            text = prompt

        inputs = self.tokenizer(text, return_tensors="pt")
        inputs = {key: value.to(self.model.device) for key, value in inputs.items()}
        do_sample = self.config.temperature > 0
        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=self.config.max_new_tokens,
                do_sample=do_sample,
                temperature=self.config.temperature if do_sample else None,
                top_p=self.config.top_p if do_sample else None,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        generated = output_ids[0][inputs["input_ids"].shape[-1] :]
        return self.tokenizer.decode(generated, skip_special_tokens=True).strip()


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
        "Return only one valid JSON object for a Vega-Lite chart spec. "
        "Do not use markdown, comments, explanations, or code fences.\n\n"
        f"User query:\n{example.query}\n\n"
        f"Allowed chart mark types:\n{', '.join(allowed_chart_types)}\n\n"
        "Schema metadata as JSON:\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        f"First {len(preview)} table rows as JSON:\n"
        f"{json.dumps(preview, ensure_ascii=False, indent=2)}\n\n"
        "Requirements:\n"
        "- Use only fields from the schema.\n"
        "- Choose Vega-Lite encoding types compatible with field dtypes.\n"
        "- Prefer simple specs with mark and encoding.\n"
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
    try:
        spec = extract_json_object(raw_output)
    except ValueError as exc:
        return {"valid": False, "error": str(exc), "spec": None, "repair_status": "parse_failed"}

    repaired, repair_notes = repair_lite(spec, example)
    normalized = normalize_spec(repaired)
    if not normalized["valid"]:
        return {
            "valid": False,
            "error": normalized.get("error", "invalid_spec"),
            "spec": repaired,
            "repair_status": ",".join(repair_notes) or "unrepaired_invalid",
        }
    return {
        "valid": True,
        "error": None,
        "spec": repaired,
        "normalized_spec": normalized,
        "repair_status": ",".join(repair_notes) or "no_repair_needed",
    }


def extract_json_object(raw_output: str) -> dict[str, Any]:
    text = strip_markdown_fences(raw_output).strip()
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


def _channel_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _vega_type(field: FieldMetadata) -> str:
    dtype = field.dtype.lower()
    name = field.name.lower()
    if field.role == "time" or "date" in name or "time" in name or "year" in name:
        return "temporal"
    if field.role == "measure" or any(token in dtype for token in ("int", "float", "double", "decimal", "number")):
        return "quantitative"
    return "nominal"


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
