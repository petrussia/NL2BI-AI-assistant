# BIRD discrimination gap closure memo v7

_Generated: 2026-05-04 07:03 UTC._

## The named gap

Phase R2 conclusion (frozen): on BIRD, B2_v5 standalone (37.60%) outperformed
B4_v5 controller (34.00%) and B5_v6 + reranker (31.20%). The verifier could
not distinguish C0_anchor from C2_retrieval_evidence on close-call items;
non-harm tie-break biased toward C0_anchor and discarded productive C2 picks.

## Phase 6 result

| Bench | B2_v5 (was best) | B6_v7 | Δ |
|---|---:|---:|---:|
| BIRD Mini-Dev (500) | 37.60% | 38.80% | +1.20 pp |

## Selector confusion C0 vs C2 (BIRD only)

| heuristic top → final top | count | EX | EX rate | override |
|---|---:|---:|---:|---:|
| C0_anchor → C0_anchor | 229 | 109 | 47.60% | False |
| C0_anchor → C1_retrieval_direct | 18 | 2 | 11.11% | True |
| C0_anchor → C2_retrieval_evidence | 113 | 45 | 39.82% | True |
| C0_anchor → C3_planner_compiled | 12 | 3 | 25.00% | True |
| C1_retrieval_direct → C0_anchor | 2 | 0 | 0.00% | True |
| C1_retrieval_direct → C1_retrieval_direct | 27 | 4 | 14.81% | False |
| C1_retrieval_direct → C2_retrieval_evidence | 24 | 8 | 33.33% | True |
| C1_retrieval_direct → C3_planner_compiled | 7 | 3 | 42.86% | True |
| C2_retrieval_evidence → C0_anchor | 1 | 0 | 0.00% | True |
| C2_retrieval_evidence → C2_retrieval_evidence | 32 | 16 | 50.00% | False |
| C2_retrieval_evidence → C3_planner_compiled | 8 | 0 | 0.00% | True |
| C3_planner_compiled → C0_anchor | 2 | 0 | 0.00% | True |
| C3_planner_compiled → C1_retrieval_direct | 2 | 0 | 0.00% | True |
| C3_planner_compiled → C2_retrieval_evidence | 1 | 0 | 0.00% | True |
| C3_planner_compiled → C3_planner_compiled | 22 | 4 | 18.18% | False |

## Source breakdown (B6_v7 BIRD final picks)

| source | count | pct | EX | EX rate |
|---|---:|---:|---:|---:|
| C0_anchor | 234 | 46.8% | 109 | 46.58% |
| C2_retrieval_evidence | 170 | 34.0% | 69 | 40.59% |
| C3_planner_compiled | 49 | 9.8% | 10 | 20.41% |
| C1_retrieval_direct | 47 | 9.4% | 6 | 12.77% |

## Helpful / harmful via judge override (vs B4_v5 anchor)

- helpful (B6 right, B4 wrong): 34
- harmful (B6 wrong, B4 right): 10
- neutral: 456
- net: +24
- of which produced via judge override: helpful 34, harmful 10, neutral 146

## Judge confidence calibration (BIRD only)

| bucket | range | n | EX | EX rate | overrode | override rate |
|---|---|---:|---:|---:|---:|---:|
| low | [0.00, 0.50) | 0 | 0 | 0.00% | 0 | 0.0% |
| mid | [0.50, 0.65) | 0 | 0 | 0.00% | 0 | 0.0% |
| high | [0.65, 0.80) | 0 | 0 | 0.00% | 0 | 0.0% |
| very_high | [0.80, 1.01) | 326 | 110 | 33.74% | 190 | 58.3% |
