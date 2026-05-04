# Phase D planner-model swap analysis (full benchmarks)

_Generated: 2026-05-04 01:23 UTC._

## Headline EX

| Bench | B0 | B2_v5 | B4_v5 (Coder-7B planner) | B4_v5 (Qwen3-8B planner) | B4_v5 (Gemma-12b planner) |
|---|---:|---:|---:|---:|---:|
| Spider dev | 72.53% | 74.76% | 76.69% | — | — |
| BIRD Mini-Dev | 20.40% | 37.60% | 34.00% | 27.60% | 24.11% |

## Paired comparisons

| Bench | A | B | n | EX(A) | EX(B) | Δ pp | 95% CI pp | McNemar p | helpful | harmful |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BIRD | B4_v5 | B4_v5_planner_qwen3_8b | 500 | 34.00% | 27.60% | -6.40 | [-8.80, -4.20] | 0.0000 | 1 | 33 |
| BIRD | B4_v5 | B4_v5_planner_gemma_12b | 253 | 35.57% | 24.11% | -11.46 | [-15.81, -7.91] | 0.0000 | 0 | 29 |
| BIRD | B4_v5_planner_qwen3_8b | B4_v5_planner_gemma_12b | 253 | 27.67% | 24.11% | -3.56 | [-7.11, -0.40] | 0.0636 | 5 | 14 |
| BIRD | B2_v5 | B4_v5_planner_qwen3_8b | 500 | 37.60% | 27.60% | -10.00 | [-14.00, -6.00] | 0.0000 | 27 | 77 |
| BIRD | B2_v5 | B4_v5_planner_gemma_12b | 253 | 37.94% | 24.11% | -13.83 | [-19.76, -7.91] | 0.0000 | 17 | 52 |

## Plan validity + source breakdown by planner lane

| lane | bench | source | count | pct | EX rate | plan_valid_pct | planner_used_pct |
|---|---|---|---:|---:|---:|---:|---:|
| phase_c_default | spider_dev | C0_anchor | 986 | 95.4% | 78.90% | 2.5% | 2.5% |
| phase_c_default | spider_dev | C3_planner_compiled | 26 | 2.5% | 26.92% | 2.5% | 2.5% |
| phase_c_default | spider_dev | C1_retrieval_direct | 14 | 1.4% | 21.43% | 2.5% | 2.5% |
| phase_c_default | spider_dev | C2_retrieval_evidence | 8 | 0.8% | 62.50% | 2.5% | 2.5% |
| phase_c_default | bird_full | C0_anchor | 348 | 69.6% | 34.48% | 6.0% | 6.0% |
| phase_c_default | bird_full | C2_retrieval_evidence | 64 | 12.8% | 51.56% | 6.0% | 6.0% |
| phase_c_default | bird_full | C1_retrieval_direct | 58 | 11.6% | 18.97% | 6.0% | 6.0% |
| phase_c_default | bird_full | C3_planner_compiled | 30 | 6.0% | 20.00% | 6.0% | 6.0% |
| phase_d_qwen3_8b | bird_full | C0_anchor | 421 | 84.2% | 28.74% | 0.0% | 0.0% |
| phase_d_qwen3_8b | bird_full | C1_retrieval_direct | 51 | 10.2% | 11.76% | 0.0% | 0.0% |
| phase_d_qwen3_8b | bird_full | C2_retrieval_evidence | 28 | 5.6% | 39.29% | 0.0% | 0.0% |
| phase_d_gemma_12b | bird_full | C0_anchor | 157 | 62.1% | 33.12% | 5.1% | 5.1% |
| phase_d_gemma_12b | bird_full | ? | 49 | 19.4% | 0.00% | 5.1% | 5.1% |
| phase_d_gemma_12b | bird_full | C1_retrieval_direct | 21 | 8.3% | 9.52% | 5.1% | 5.1% |
| phase_d_gemma_12b | bird_full | C3_planner_compiled | 13 | 5.1% | 15.38% | 5.1% | 5.1% |
| phase_d_gemma_12b | bird_full | C2_retrieval_evidence | 13 | 5.1% | 38.46% | 5.1% | 5.1% |

## Verdicts

- BIRD B4_v5 → B4_v5_planner_qwen3_8b: **B4_v5_planner_qwen3_8b significantly worse than B4_v5** (Δ -6.40 pp, p=0.0000) (helpful 1 / harmful 33)
- BIRD B4_v5 → B4_v5_planner_gemma_12b: **B4_v5_planner_gemma_12b significantly worse than B4_v5** (Δ -11.46 pp, p=0.0000) (helpful 0 / harmful 29)
- BIRD B4_v5_planner_qwen3_8b → B4_v5_planner_gemma_12b: no significant difference (p=0.0636) (helpful 5 / harmful 14)
- BIRD B2_v5 → B4_v5_planner_qwen3_8b: **B4_v5_planner_qwen3_8b significantly worse than B2_v5** (Δ -10.00 pp, p=0.0000) (helpful 27 / harmful 77)
- BIRD B2_v5 → B4_v5_planner_gemma_12b: **B4_v5_planner_gemma_12b significantly worse than B2_v5** (Δ -13.83 pp, p=0.0000) (helpful 17 / harmful 52)
