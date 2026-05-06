from pathlib import Path

import pytest

from scripts.run_stage8_large_llm import load_stage8_config, run_stage8_model, stage8_model_keys
from t2v_eval.baselines.llm_vegalite import LLMVegaLiteConfig
from t2v_eval.baselines.llm_validator_reranker import LLMRerankerConfig


def test_stage8_config_contains_requested_model_family() -> None:
    config = load_stage8_config()
    models = config["models"]

    assert set(stage8_model_keys()) == {
        "gemma4_26b_a4b_it_mtp",
        "gemma4_e2b_it",
        "qwen36_35b_a3b",
        "qwen3_coder_next_awq4",
    }
    assert models["qwen36_35b_a3b"]["requested_model_id"] == "Qwen/Qwen3.6-35B-A3B"
    assert models["qwen36_35b_a3b"]["model_id"] == "bombman/Qwen3.6-35B-A3B-4bit-Native"
    assert models["qwen36_35b_a3b"]["quantization"] == "prequantized"
    assert models["qwen3_coder_next_awq4"]["requested_model_id"] == "Qwen/Qwen3-Coder-Next"
    assert models["qwen3_coder_next_awq4"]["quantization"] == "prequantized"
    assert models["gemma4_e2b_it"]["model_id"] == "google/gemma-4-E2B-it"
    assert models["gemma4_26b_a4b_it_mtp"]["assistant_model_id"] == (
        "google/gemma-4-26B-A4B-it-assistant"
    )


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

    with pytest.raises(RuntimeError, match="needs about 24GB VRAM"):
        run_stage8_model(
            model_key="qwen36_35b_a3b",
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
        model_id="Qwen/Qwen3.6-35B-A3B",
        method_name="B5_stage8_qwen36_35b_a3b",
        quantization="prequantized",
    )

    assert config.method_name == "B5_stage8_gemma4_e2b_it"
    assert config.model_loader == "processor_causal_lm"
    assert rerank.to_llm_config().method_name == "B5_stage8_qwen36_35b_a3b"
    assert rerank.to_dict()["quantization"] == "prequantized"
