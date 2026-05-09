# Controller analysis (Phase C b4_v5 = candidate pool + verifier + bounded repair)

_Generated: 2026-05-03 13:16 UTC._

## Headline EX

| Bench | B0 | B1_v5 | B2_v5 | B3_v5 | **B4_v5** |
|---|---:|---:|---:|---:|---:|
| Spider dev | 72.53% | 74.85% | 74.76% | 56.96% | **76.69%** |
| BIRD Mini-Dev | 20.40% | 23.00% | 37.60% | 23.80% | **34.00%** |

## Paired stats (key questions)

| Bench | A | B | n | EX(A) | EX(B) | Δ pp | 95% CI pp | McNemar p | helpful | harmful |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Spider | B0 | B4_v5 | 1034 | 72.53% | 76.69% | +4.16 | [+2.22, +6.19] | 0.0001 | 77 | 34 |
| Spider | B2_v5 | B4_v5 | 1034 | 74.76% | 76.69% | +1.93 | [+0.77, +3.09] | 0.0012 | 28 | 8 |
| Spider | B3_v5 | B4_v5 | 1034 | 56.96% | 76.69% | +19.73 | [+17.02, +22.34] | 0.0000 | 222 | 18 |
| BIRD | B0 | B4_v5 | 500 | 20.40% | 34.00% | +13.60 | [+10.20, +17.00] | 0.0000 | 74 | 6 |
| BIRD | B2_v5 | B4_v5 | 500 | 37.60% | 34.00% | -3.60 | [-7.20, -0.20] | 0.0630 | 33 | 51 |
| BIRD | B3_v5 | B4_v5 | 500 | 23.80% | 34.00% | +10.20 | [+6.40, +13.60] | 0.0000 | 71 | 20 |

## Controller-source breakdown (B4_v5 final pick distribution)

### Spider dev
| source | count | pct | EX | EX rate |
|---|---:|---:|---:|---:|
| C0_anchor | 986 | 95.4% | 778 | 78.90% |
| C3_planner_compiled | 26 | 2.5% | 7 | 26.92% |
| C1_retrieval_direct | 14 | 1.4% | 3 | 21.43% |
| C2_retrieval_evidence | 8 | 0.8% | 5 | 62.50% |

### BIRD Mini-Dev
| source | count | pct | EX | EX rate |
|---|---:|---:|---:|---:|
| C0_anchor | 348 | 69.6% | 120 | 34.48% |
| C2_retrieval_evidence | 64 | 12.8% | 33 | 51.56% |
| C1_retrieval_direct | 58 | 11.6% | 11 | 18.97% |
| C3_planner_compiled | 30 | 6.0% | 6 | 20.00% |

## Verifier + repair impact

| Bench | N | total EX | repair n | repair EX | repair EX rate | no-repair n | no-repair EX rate | fallback-to-anchor n | fallback EX |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| spider_dev | 1034 | 793 | 22 | 4 | 18.18% | 1012 | 77.96% | 986 | 778 |
| bird_full | 500 | 170 | 9 | 0 | 0.00% | 491 | 34.62% | 348 | 120 |

## Verdicts

- Spider B0 → B4_v5: **B4_v5 significantly beats B0** (Δ +4.16 pp, p=0.0001) (helpful 77 / harmful 34)
- Spider B2_v5 → B4_v5: **B4_v5 significantly beats B2_v5** (Δ +1.93 pp, p=0.0012) (helpful 28 / harmful 8)
- Spider B3_v5 → B4_v5: **B4_v5 significantly beats B3_v5** (Δ +19.73 pp, p=0.0000) (helpful 222 / harmful 18)
- BIRD B0 → B4_v5: **B4_v5 significantly beats B0** (Δ +13.60 pp, p=0.0000) (helpful 74 / harmful 6)
- BIRD B2_v5 → B4_v5: no significant difference (p=0.0630) (helpful 33 / harmful 51)
- BIRD B3_v5 → B4_v5: **B4_v5 significantly beats B3_v5** (Δ +10.20 pp, p=0.0000) (helpful 71 / harmful 20)
