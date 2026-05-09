# Planner harm analysis (Phase B b3_v5 vs anchor and Phase A best)

_Generated: 2026-05-03 06:48 UTC._

## Headline EX

| Bench | B0 anchor | B1_v5 retr | B2_v5 retr+ev | B3_v5 planner+compiler |
|---|---:|---:|---:|---:|
| Spider dev (1034) | 72.53% | 74.85% | 74.76% | 56.96% |
| BIRD Mini-Dev (500) | 20.40% | 23.00% | 37.60% | 23.80% |

## Paired comparisons

| Bench | A | B | n | EX(A) | EX(B) | Δ pp | 95% CI pp | McNemar p | helpful | harmful | neutral |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Spider | B0 | B3_v5 | 1034 | 72.53% | 56.96% | -15.57 | [-18.38, -12.77] | 0.0000 | 43 | 204 | 787 |
| Spider | B1_v5 | B3_v5 | 1034 | 74.85% | 56.96% | -17.89 | [-20.79, -15.09] | 0.0000 | 29 | 214 | 791 |
| Spider | B2_v5 | B3_v5 | 1034 | 74.76% | 56.96% | -17.79 | [-20.50, -14.89] | 0.0000 | 30 | 214 | 790 |
| BIRD | B0 | B3_v5 | 500 | 20.40% | 23.80% | +3.40 | [+0.00, +7.20] | 0.0784 | 50 | 33 | 417 |
| BIRD | B1_v5 | B3_v5 | 500 | 23.00% | 23.80% | +0.80 | [-2.60, +4.20] | 0.7343 | 41 | 37 | 422 |
| BIRD | B2_v5 | B3_v5 | 500 | 37.60% | 23.80% | -13.80 | [-18.20, -9.40] | 0.0000 | 29 | 98 | 373 |

## Selected-candidate breakdown (Phase B b3_v5)

### spider
| source | count | pct |
|---|---:|---:|
| planner_compiled | 799 | 77.3% |
| b0_anchor_plan_invalid | 129 | 12.5% |
| b0_anchor_easy | 103 | 10.0% |
| planner_skeleton_synth | 3 | 0.3% |

### bird
| source | count | pct |
|---|---:|---:|
| planner_compiled | 373 | 74.6% |
| b0_anchor_plan_invalid | 83 | 16.6% |
| b0_anchor_easy | 34 | 6.8% |
| planner_skeleton_synth | 10 | 2.0% |

## Compiler family success (Phase B b3_v5, both benchmarks combined)

| family | total | EX | EX rate |
|---|---:|---:|---:|
| aggregate | 601 | 259 | 43.09% |
| filter | 600 | 257 | 42.83% |
| join | 576 | 155 | 26.91% |
| anchor_only | 349 | 221 | 63.32% |
| group_by | 227 | 54 | 23.79% |
| top_k | 207 | 46 | 22.22% |
| simple | 77 | 44 | 57.14% |
| having | 65 | 3 | 4.62% |
| distinct | 51 | 11 | 21.57% |
| nested | 12 | 5 | 41.67% |
| window | 1 | 0 | 0.00% |

## Verdicts

- Spider B0 → B3_v5: **B3_v5 significantly worse than B0** (Δ -15.57 pp, p=0.0000) (helpful 43 / harmful 204)
- Spider B1_v5 → B3_v5: **B3_v5 significantly worse than B1_v5** (Δ -17.89 pp, p=0.0000) (helpful 29 / harmful 214)
- Spider B2_v5 → B3_v5: **B3_v5 significantly worse than B2_v5** (Δ -17.79 pp, p=0.0000) (helpful 30 / harmful 214)
- BIRD B0 → B3_v5: no significant difference (p=0.0784) (helpful 50 / harmful 33)
- BIRD B1_v5 → B3_v5: no significant difference (p=0.7343) (helpful 41 / harmful 37)
- BIRD B2_v5 → B3_v5: **B3_v5 significantly worse than B2_v5** (Δ -13.80 pp, p=0.0000) (helpful 29 / harmful 98)
