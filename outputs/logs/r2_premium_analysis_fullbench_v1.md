# R2 (Premium retrieval + reranker) analysis

_Generated: 2026-05-03 18:44 UTC._

## Headline EX

| Bench | B0 | B1_v5 | B2_v5 | B3_v5 | B4_v5 | **B5_v6 (R2)** |
|---|---:|---:|---:|---:|---:|---:|
| Spider dev | 72.53% | 74.85% | 74.76% | 56.96% | 76.69% | **76.60%** |
| BIRD Mini-Dev | 20.40% | 23.00% | 37.60% | 23.80% | 34.00% | **31.20%** |

## Key paired comparisons

| Bench | A | B | n | EX(A) | EX(B) | Δ pp | 95% CI pp | McNemar p | helpful | harmful |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Spider | B0 | B5_v6 | 1034 | 72.53% | 76.60% | +4.06 | [+2.13, +6.00] | 0.0001 | 76 | 34 |
| Spider | B2_v5 | B5_v6 | 1034 | 74.76% | 76.60% | +1.84 | [+0.68, +3.00] | 0.0019 | 27 | 8 |
| Spider | B4_v5 | B5_v6 | 1034 | 76.69% | 76.60% | -0.10 | [-0.29, +0.00] | 1.0000 | 0 | 1 |
| BIRD | B0 | B5_v6 | 500 | 20.40% | 31.20% | +10.80 | [+8.00, +13.60] | 0.0000 | 60 | 6 |
| BIRD | B2_v5 | B5_v6 | 500 | 37.60% | 31.20% | -6.40 | [-10.20, -2.60] | 0.0014 | 32 | 64 |
| BIRD | B4_v5 | B5_v6 | 500 | 34.00% | 31.20% | -2.80 | [-4.40, -1.40] | 0.0005 | 1 | 15 |

## Controller source breakdown (B5_v6 with R2)

### Spider dev
| source | count | pct | EX | EX rate |
|---|---:|---:|---:|---:|
| C0_anchor | 986 | 95.4% | 778 | 78.90% |
| C3_planner_compiled | 26 | 2.5% | 7 | 26.92% |
| C1_retrieval_direct | 15 | 1.5% | 3 | 20.00% |
| C2_retrieval_evidence | 7 | 0.7% | 4 | 57.14% |

### BIRD Mini-Dev
| source | count | pct | EX | EX rate |
|---|---:|---:|---:|---:|
| C0_anchor | 374 | 74.8% | 120 | 32.09% |
| C1_retrieval_direct | 60 | 12.0% | 12 | 20.00% |
| C2_retrieval_evidence | 41 | 8.2% | 19 | 46.34% |
| C3_planner_compiled | 25 | 5.0% | 5 | 20.00% |

## Reranker confidence buckets (top candidate score)

| bench | bucket | range | n | EX | EX rate |
|---|---|---|---:|---:|---:|
| spider_dev | low | [0.00, 0.50) | 0 | 0 | 0.00% |
| spider_dev | mid | [0.50, 0.80) | 1 | 1 | 100.00% |
| spider_dev | high | [0.80, 0.95) | 9 | 4 | 44.44% |
| spider_dev | very_high | [0.95, 1.01) | 1024 | 787 | 76.86% |
| bird_full | low | [0.00, 0.50) | 3 | 0 | 0.00% |
| bird_full | mid | [0.50, 0.80) | 5 | 1 | 20.00% |
| bird_full | high | [0.80, 0.95) | 8 | 0 | 0.00% |
| bird_full | very_high | [0.95, 1.01) | 484 | 155 | 32.02% |

## Verdicts

- Spider B0 → B5_v6: **B5_v6 significantly beats B0** (Δ +4.06 pp, p=0.0001) (helpful 76 / harmful 34)
- Spider B2_v5 → B5_v6: **B5_v6 significantly beats B2_v5** (Δ +1.84 pp, p=0.0019) (helpful 27 / harmful 8)
- Spider B4_v5 → B5_v6: no significant difference (p=1.0000) (helpful 0 / harmful 1)
- BIRD B0 → B5_v6: **B5_v6 significantly beats B0** (Δ +10.80 pp, p=0.0000) (helpful 60 / harmful 6)
- BIRD B2_v5 → B5_v6: **B5_v6 significantly worse than B2_v5** (Δ -6.40 pp, p=0.0014) (helpful 32 / harmful 64)
- BIRD B4_v5 → B5_v6: **B5_v6 significantly worse than B4_v5** (Δ -2.80 pp, p=0.0005) (helpful 1 / harmful 15)
