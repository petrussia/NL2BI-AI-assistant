"""Stage 7 LLM multi-candidate validator/reranker baseline."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from time import perf_counter
from typing import Any

from t2v_eval.baselines.llm_vegalite import (
    DEFAULT_MAX_NEW_TOKENS,
    DEFAULT_MAX_VALIDATION_RETRIES,
    DEFAULT_MODEL_ID,
    LLMVegaLiteConfig,
    LLMVegaLitePredictor,
    build_prompt,
    extract_and_repair_spec,
)
from t2v_eval.data.schema import FieldMetadata, T2VExample, T2VPrediction
from t2v_eval.normalization.vega_lite import normalize_spec

try:
    import psutil
except ModuleNotFoundError:  # pragma: no cover - dependency is in requirements.
    psutil = None  # type: ignore[assignment]


METHOD_NAME = "B4_llm_validator_reranker"
DEFAULT_CANDIDATE_COUNT = 3
DEFAULT_CANDIDATE_TEMPERATURES = (0.0, 0.2, 0.3)
PROMPT_VARIANTS = (
    "Use the most direct chart that satisfies the user query.",
    "Prefer a compact chart with the strongest x/y field mapping.",
    "Check whether aggregation or color is needed, but avoid extra encodings.",
)


@dataclass(slots=True)
class LLMRerankerConfig:
    model_id: str = DEFAULT_MODEL_ID
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS
    top_p: float = 0.9
    seed: int = 42
    sample_rows: int = 5
    quantization: str | None = "4bit"
    candidate_count: int = DEFAULT_CANDIDATE_COUNT
    candidate_temperatures: tuple[float, ...] = DEFAULT_CANDIDATE_TEMPERATURES
    torch_dtype: str = "auto"
    device_map: str = "auto"
    model_loader: str = "causal_lm"
    trust_remote_code: bool = True
    low_cpu_mem_usage: bool = True
    attn_implementation: str | None = None
    bnb_4bit_compute_dtype: str = "float16"
    assistant_model_id: str | None = None
    assistant_quantization: str | None = None
    assistant_model_loader: str = "causal_lm"
    enable_thinking: bool = False
    stop_after_json: bool = True
    max_validation_retries: int = DEFAULT_MAX_VALIDATION_RETRIES
    method_name: str = METHOD_NAME

    def __post_init__(self) -> None:
        if "qwen2.5" in self.model_id.lower():
            raise ValueError("Stage 7 must not use Qwen2.5 models.")
        if self.candidate_count <= 0:
            raise ValueError("candidate_count must be positive.")
        if self.max_new_tokens <= 0:
            raise ValueError("max_new_tokens must be positive.")
        if not self.candidate_temperatures:
            raise ValueError("candidate_temperatures must not be empty.")
        if self.max_validation_retries < 0:
            raise ValueError("max_validation_retries must be non-negative.")

    def to_llm_config(self) -> LLMVegaLiteConfig:
        return LLMVegaLiteConfig(
            model_id=self.model_id,
            max_new_tokens=self.max_new_tokens,
            temperature=self.candidate_temperatures[0],
            top_p=self.top_p,
            seed=self.seed,
            sample_rows=self.sample_rows,
            quantization=self.quantization,
            torch_dtype=self.torch_dtype,
            device_map=self.device_map,
            model_loader=self.model_loader,
            trust_remote_code=self.trust_remote_code,
            low_cpu_mem_usage=self.low_cpu_mem_usage,
            attn_implementation=self.attn_implementation,
            bnb_4bit_compute_dtype=self.bnb_4bit_compute_dtype,
            assistant_model_id=self.assistant_model_id,
            assistant_quantization=self.assistant_quantization,
            assistant_model_loader=self.assistant_model_loader,
            enable_thinking=self.enable_thinking,
            stop_after_json=self.stop_after_json,
            max_validation_retries=self.max_validation_retries,
            method_name=self.method_name,
        )

    def temperature_for(self, index: int) -> float:
        return self.candidate_temperatures[index % len(self.candidate_temperatures)]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["candidate_temperatures"] = list(self.candidate_temperatures)
        return data


class LLMValidatorRerankerPredictor:
    """Generate k candidates, validate them against input data, and rerank."""

    def __init__(self, config: LLMRerankerConfig) -> None:
        self.config = config
        self.llm = LLMVegaLitePredictor(config.to_llm_config())

    def load(self) -> "LLMValidatorRerankerPredictor":
        self.llm.load()
        return self

    def predict(self, example: T2VExample, *, run_id: str) -> T2VPrediction:
        start = perf_counter()
        start_memory = _memory_mb()
        candidates: list[dict[str, Any]] = []
        raw_outputs: list[str] = []

        for index in range(self.config.candidate_count):
            prompt = build_candidate_prompt(
                example,
                sample_rows=self.config.sample_rows,
                variant=PROMPT_VARIANTS[index % len(PROMPT_VARIANTS)],
            )
            try:
                generation = self.llm.generate_validated(
                    prompt,
                    example,
                    temperature=self.config.temperature_for(index),
                    top_p=self.config.top_p,
                    max_new_tokens=self.config.max_new_tokens,
                )
            except Exception as exc:  # pragma: no cover - Colab runtime safety.
                raw_output = ""
                candidates.append(
                    _failed_candidate(index, f"generation_failed: {exc}")
                )
                raw_outputs.append(raw_output)
                continue

            raw_output = str(generation.get("raw_output") or "")
            raw_outputs.append(raw_output)
            if not generation.get("valid"):
                candidate = _failed_candidate(
                    index,
                    str((generation.get("validation") or {}).get("error") or "validation_failed"),
                    raw_output=raw_output,
                )
                candidate["validation_attempts"] = generation.get("attempts") or []
                candidates.append(candidate)
                continue

            candidate = score_candidate(raw_output, example, candidate_index=index)
            candidate["validation_attempts"] = generation.get("attempts") or []
            candidates.append(candidate)

        ranked = sorted(
            candidates,
            key=lambda candidate: (
                float(candidate.get("score") or 0.0),
                bool(candidate.get("normalized_spec", {}).get("valid")),
            ),
            reverse=True,
        )
        for rank, candidate in enumerate(ranked, start=1):
            candidate["rank"] = rank

        winner = ranked[0] if ranked else _failed_candidate(0, "no_candidates")
        latency_ms = _elapsed_ms(start)
        memory_peak_mb = _max_memory(start_memory)
        raw_output = "\n\n---CANDIDATE---\n\n".join(raw_outputs)
        if not winner.get("raw_spec") or not winner.get("normalized_spec", {}).get("valid"):
            return T2VPrediction(
                run_id=run_id,
                method=self.config.method_name,
                example_id=example.example_id,
                status="failed",
                raw_output=raw_output,
                candidates=ranked,
                latency_ms=latency_ms,
                memory_peak_mb=memory_peak_mb,
                error=str(winner.get("error") or "no_valid_candidate"),
            )

        return T2VPrediction(
            run_id=run_id,
            method=self.config.method_name,
            example_id=example.example_id,
            status="ok",
            raw_output=raw_output,
            raw_spec=winner["raw_spec"],
            normalized_spec=winner["normalized_spec"],
            candidates=ranked,
            latency_ms=latency_ms,
            memory_peak_mb=memory_peak_mb,
        )


def build_candidate_prompt(
    example: T2VExample,
    *,
    sample_rows: int,
    variant: str,
) -> str:
    return (
        build_prompt(example, sample_rows=sample_rows)
        + "\nCandidate variant instruction:\n"
        + variant
        + "\nReturn one JSON object only.\n"
    )


def score_candidate(raw_output: str, example: T2VExample, *, candidate_index: int) -> dict[str, Any]:
    extraction = extract_and_repair_spec(raw_output, example)
    if not extraction["valid"]:
        return _failed_candidate(candidate_index, str(extraction["error"]), raw_output=raw_output)

    spec = extraction["spec"]
    normalized = normalize_spec(spec)
    legality = validate_spec_legality(spec, normalized, example)
    score = (
        3.0 * float(normalized["valid"])
        + 2.0 * legality["field_legality"]
        + 1.5 * legality["dtype_compatibility"]
        + 1.5 * legality["aggregation_legality"]
        + 1.0 * legality["parsimony"]
    ) / 9.0

    return {
        "candidate_index": candidate_index,
        "raw_output": raw_output,
        "raw_spec": spec,
        "normalized_spec": normalized,
        "score": round(score, 6),
        "reason": extraction["repair_status"],
        "validator": legality,
    }


def validate_spec_legality(
    spec: dict[str, Any],
    normalized: dict[str, Any],
    example: T2VExample,
) -> dict[str, Any]:
    fields = {field.name: field for field in example.fields}
    used_fields = [str(field) for field in normalized.get("fields") or []]
    illegal_fields = sorted(field for field in used_fields if field not in fields)
    dtype_checks = _dtype_checks(normalized, fields)
    aggregation_checks = _aggregation_checks(normalized, fields)
    parsimony = _parsimony_score(spec, normalized)
    return {
        "json_validity": 1.0,
        "vega_lite_validity": 1.0 if normalized.get("valid") else 0.0,
        "field_legality": 1.0 if not illegal_fields else 0.0,
        "illegal_fields": illegal_fields,
        "dtype_compatibility": _mean(dtype_checks),
        "dtype_checks": dtype_checks,
        "aggregation_legality": _mean(aggregation_checks),
        "aggregation_checks": aggregation_checks,
        "parsimony": parsimony,
    }


def _dtype_checks(normalized: dict[str, Any], fields: dict[str, FieldMetadata]) -> list[float]:
    checks: list[float] = []
    for channel_value in (normalized.get("encoding") or {}).values():
        for item in _channel_items(channel_value):
            field_name = item.get("field")
            if not field_name:
                continue
            field = fields.get(str(field_name))
            if field is None:
                checks.append(0.0)
                continue
            checks.append(1.0 if _type_compatible(field, item.get("type")) else 0.0)
    return checks or [1.0]


def _aggregation_checks(normalized: dict[str, Any], fields: dict[str, FieldMetadata]) -> list[float]:
    checks: list[float] = []
    for channel_value in (normalized.get("encoding") or {}).values():
        for item in _channel_items(channel_value):
            aggregate = item.get("aggregate")
            if not aggregate:
                continue
            field = fields.get(str(item.get("field") or ""))
            checks.append(1.0 if _aggregate_allowed(field, str(aggregate)) else 0.0)
    return checks or [1.0]


def _parsimony_score(spec: dict[str, Any], normalized: dict[str, Any]) -> float:
    encoding_count = sum(
        1 for _channel, value in (normalized.get("encoding") or {}).items() if value
    )
    transform_count = len(normalized.get("transform") or [])
    top_level_penalty = max(0, len(set(spec) - {"mark", "encoding", "transform", "title"}))
    penalty = max(0, encoding_count - 3) + transform_count + top_level_penalty
    return max(0.0, 1.0 - 0.15 * penalty)


def _type_compatible(field: FieldMetadata, vega_type: Any) -> bool:
    if not vega_type:
        return True
    normalized_type = str(vega_type).lower()
    role = field.role
    dtype = field.dtype.lower()
    if _is_aggregate_measure(field):
        return normalized_type in {"quantitative", "ordinal"}
    if role == "time" or "date" in dtype or "time" in dtype:
        return normalized_type in {"temporal", "ordinal", "nominal"}
    if role == "measure" or any(token in dtype for token in ("int", "float", "double", "decimal", "number")):
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


def _is_aggregate_measure(field: FieldMetadata) -> bool:
    dtype = field.dtype.lower()
    name = field.name.strip().lower()
    return name.startswith(("count(", "sum(", "avg(", "mean(", "min(", "max(")) and any(
        token in dtype for token in ("int", "float", "double", "decimal", "number")
    )


def _channel_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _failed_candidate(
    candidate_index: int,
    error: str,
    *,
    raw_output: str | None = None,
) -> dict[str, Any]:
    return {
        "candidate_index": candidate_index,
        "raw_output": raw_output,
        "raw_spec": None,
        "normalized_spec": {"valid": False, "error": error},
        "score": 0.0,
        "reason": "failed",
        "error": error,
        "validator": {
            "json_validity": 0.0,
            "vega_lite_validity": 0.0,
            "field_legality": 0.0,
            "dtype_compatibility": 0.0,
            "aggregation_legality": 0.0,
            "parsimony": 0.0,
        },
    }


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
