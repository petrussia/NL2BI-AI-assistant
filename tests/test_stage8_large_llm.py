from pathlib import Path

import pytest

from scripts.run_stage8_large_llm import load_stage8_config, run_stage8_model, stage8_model_keys
from t2v_eval.baselines.llm_vegalite import LLMVegaLiteConfig
from t2v_eval.baselines.llm_vegalite import _device_map_arg
from t2v_eval.baselines.llm_validator_reranker import LLMRerankerConfig


def test_stage8_config_contains_requested_model_family() -> None:
    config = load_stage8_config()
    models = config["models"]

    assert set(stage8_model_keys()) == {
        "gemma3_12b_it",
        "gemma4_e2b_it",
        "mistral_small_31_24b_bnb4",
        "mistral_small_32_24b_bnb4",
        "qwen3_14b",
    }
    assert models["qwen3_14b"]["model_id"] == "Qwen/Qwen3-14B"
    assert models["qwen3_14b"]["quantization"] == "4bit"
    assert models["qwen3_14b"]["device_map"] == "single_gpu"
    assert models["gemma3_12b_it"]["model_id"] == "google/gemma-3-12b-it"
    assert models["gemma3_12b_it"]["model_loader"] == "gemma3_conditional_generation"
    assert models["gemma4_e2b_it"]["model_id"] == "google/gemma-4-E2B-it"
    assert models["mistral_small_31_24b_bnb4"]["model_id"] == (
        "unsloth/Mistral-Small-3.1-24B-Instruct-2503-bnb-4bit"
    )
    assert models["mistral_small_31_24b_bnb4"]["model_loader"] == (
        "mistral3_conditional_generation"
    )
    assert models["mistral_small_32_24b_bnb4"]["model_id"] == (
        "unsloth/Mistral-Small-3.2-24B-Instruct-2506-bnb-4bit"
    )
    assert models["mistral_small_32_24b_bnb4"]["quantization"] == "prequantized"


def test_stage8_dry_run_builds_validator_run_without_loading_model(tmp_path: Path) -> None:
    result = run_stage8_model(
        model_key="gemma4_e2b_it",
        examples_path=tmp_path / "examples.jsonl",
        drive_root=tmp_path,
        sample_size=3,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["mode"] == "single"
    assert result["run_kwargs"]["sample_size"] == 3
    assert result["run_kwargs"]["method_name"] == "B5_stage8_gemma4_e2b_it"
    assert result["run_kwargs"]["quantization"] == "4bit"
    assert result["run_kwargs"]["model_loader"] == "processor_causal_lm"


def test_stage8_low_vram_guard_can_fail_before_model_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import run_stage8_large_llm

    monkeypatch.setattr(
        run_stage8_large_llm,
        "gpu_runtime_info",
        lambda: {"cuda_available": True, "vram_total_mb": 16 * 1024},
    )

    with pytest.raises(RuntimeError, match="needs about 28GB VRAM"):
        run_stage8_model(
            model_key="mistral_small_31_24b_bnb4",
            examples_path=tmp_path / "examples.jsonl",
            drive_root=tmp_path,
            dry_run=True,
        )


def test_llm_configs_support_stage8_method_and_loaders() -> None:
    config = LLMVegaLiteConfig(
        model_id="google/gemma-4-E2B-it",
        method_name="B5_stage8_gemma4_e2b_it",
        model_loader="processor_causal_lm",
    )
    rerank = LLMRerankerConfig(
        model_id="Qwen/Qwen3-14B",
        method_name="B5_stage8_qwen3_14b",
        quantization="prequantized",
    )

    assert config.method_name == "B5_stage8_gemma4_e2b_it"
    assert config.model_loader == "processor_causal_lm"
    assert rerank.to_llm_config().method_name == "B5_stage8_qwen3_14b"
    assert rerank.to_dict()["quantization"] == "prequantized"


def test_stage8_configs_accept_new_processor_model_loaders() -> None:
    gemma = LLMVegaLiteConfig(
        model_id="google/gemma-3-12b-it",
        model_loader="gemma3_conditional_generation",
    )
    mistral = LLMVegaLiteConfig(
        model_id="unsloth/Mistral-Small-3.2-24B-Instruct-2506-bnb-4bit",
        model_loader="mistral3_conditional_generation",
        quantization="prequantized",
    )

    assert gemma.model_loader == "gemma3_conditional_generation"
    assert mistral.model_loader == "mistral3_conditional_generation"


def test_single_gpu_device_map_expands_to_accelerate_mapping() -> None:
    assert _device_map_arg("single_gpu") == {"": 0}
    assert _device_map_arg("cuda:0") == {"": 0}
    assert _device_map_arg("auto") == "auto"
