# Phase A readiness (Phase B/C/D deferred)

_Generated: 2026-05-03 00:20 UTC._

## What is closed

- Phase A retrieval ablation: B0 (v11) vs B1_v5 vs B2_v5, Qwen2.5-Coder-7B, full Spider dev (1034) + full BIRD Mini-Dev (500).

## What is NOT closed (deferred to next sessions)

- Phase B: planner_v2 + sql_compiler_v2 + b3_v5 (gated planner+compiler) — code not yet written.
- Phase C: candidate_generator_v2 + verifier_ranker_v2 + repair_v2 + b4_v5 (full controller); model scaling across Gemma-3-12b / Qwen-Coder-32B/30B / SQLCoder.
- Phase D: planner-model swap (Qwen3-8B vs Gemma-3-12b as planner/verifier).
- Spider2-Lite v2: Phase A skipped Spider2-Lite (no execution engine; structural-only B0/B3_v4 closed in v11).
- BIRD official R-VES + Soft-F1: still blocked by official CLI drift.
- Premium retrieval lane R2 (Qwen3-Embedding + Qwen3-Reranker): not yet implemented; FAST lane (BM25 + char n-gram) is what Phase A used.

## Cells in this readout

| Cell | N | source | EX | 95% CI |
|---|---:|---|---:|---:|
| b0_qwen2p5_coder_7b_spider_dev_full | 1034 | v11_anchor | 72.53% | [69.7, 75.2] |
| b1v5_qwen2p5_coder_7b_spider_dev_full | 1034 | phase_a | 74.85% | [72.1, 77.4] |
| b2v5_qwen2p5_coder_7b_spider_dev_full | 1034 | phase_a | 74.76% | [72.0, 77.3] |
| b0_qwen2p5_coder_7b_bird_full | 500 | v11_anchor | 20.40% | [17.1, 24.2] |
| b1v5_qwen2p5_coder_7b_bird_full | 500 | phase_a | 23.00% | [19.5, 26.9] |
| b2v5_qwen2p5_coder_7b_bird_full | 500 | phase_a | 37.60% | [33.5, 41.9] |
