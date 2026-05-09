# Llama-3.1-8B-Instruct — RESOLVED

**Resolved at:** 2026-04-30T12:01:54.471460+00:00
**Original blocker:** HF_TOKEN missing in runtime → gated repo inaccessible.
**Resolution:** user attached HF_TOKEN via Colab Secrets / runtime env var.

## Outcome
- Gated repo access: **OK** (sha resolved, no 401/403).
- Model loaded in 4-bit nf4 bnb on NVIDIA L4 (≈ 5.4 GB VRAM).
- B0 smoke10 EX = **0.8000 (8/10)**
- B1 smoke10 EX = **0.9000 (9/10)**

## Artefacts
- `outputs/predictions/b0_llama_3p1_8b_instruct_smoke10_predictions.jsonl`
- `outputs/metrics/b0_llama_3p1_8b_instruct_smoke10_metrics.csv`
- `outputs/predictions/b1_llama_3p1_8b_instruct_smoke10_predictions.jsonl`
- `outputs/metrics/b1_llama_3p1_8b_instruct_smoke10_metrics.csv`
- `outputs/logs/llama_runtime_attempt.md`
- `outputs/logs/llama_bg_task_log.txt`

## Status
Mandatory model from the proposal — **evaluated**. Model block now: 3 of 4
mandatory models with empirical EX numbers (Qwen-Coder, Qwen-Instruct, Llama).
DeepSeek remains environmentally blocked (transformers version mismatch in
trust_remote_code modeling file).
