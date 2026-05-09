# Master matrix v16 — through Phase D planner-model swap

B0 from v11. B2_v5 Phase A. B4_v5 Phase C (planner=Coder-7B, single-model setup).
Phase D = B4_v5 with Qwen3-8B or Gemma-3-12b-it as the planner LLM (synth=Coder-7B unchanged).

| Baseline | Bench | N | EX | 95% CI | Exec | Plan valid | Avg LM calls | Lat p50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| B0 | spider_dev | 1034 | 72.53% | [69.7, 75.2] | 94.87% | 0.00% | 1.00 | 829 |
| B2_v5 | spider_dev | 1034 | 74.76% | [72.0, 77.3] | 94.97% | 0.00% | 1.00 | 1504 |
| B4_v5 | spider_dev | 1034 | 76.69% | [74.0, 79.2] | 98.36% | 2.51% | 4.83 | 8203 |
| B0 | bird_full | 500 | 20.40% | [17.1, 24.2] | 79.80% | 0.00% | 1.00 | 1948 |
| B2_v5 | bird_full | 500 | 37.60% | [33.5, 41.9] | 84.20% | 0.00% | 1.00 | 3675 |
| B4_v5 | bird_full | 500 | 34.00% | [30.0, 38.3] | 98.40% | 6.00% | 4.90 | 14019 |
| B4_v5_planner_qwen3_8b | spider_dev | 0 | — | — | — | — | 0.00 | 0 |
| B4_v5_planner_qwen3_8b | bird_full | 500 | 27.60% | [23.9, 31.7] | 93.80% | 0.00% | 4.92 | 31647 |
| B4_v5_planner_gemma_12b | spider_dev | 0 | — | — | — | — | 0.00 | 0 |
| B4_v5_planner_gemma_12b | bird_full | 253 | 24.11% | [19.3, 29.7] | 76.28% | 5.14% | 4.19 | 30624 |
