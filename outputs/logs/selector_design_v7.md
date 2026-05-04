# Selector design v7 (LLM-as-judge over heuristic verifier)

_Generated: 2026-05-04 07:03 UTC._

Architecture: B4_v5 controller (Phase C) augmented with a calibrated
LLM-as-judge selector (Coder-7B as judge, single-model setup).

## Calibration triggers

- benchmark profile: bird (loose: margin<0.10, conf>=0.65, anchor override OK)
- benchmark profile: spider (safe: margin<0.04, conf>=0.75, anchor override OK)
- requires C2_retrieval_evidence executable in candidate set
- requires non-empty evidence text or db-level evidence store
- requires consensus_top_count < n_candidates (not all agree)

## Headline EX

| Bench | B0 | B2_v5 | B4_v5 | B5_v6 | **B6_v7** |
|---|---:|---:|---:|---:|---:|
| Spider dev (1034) | 72.53% | 74.76% | 76.69% | 76.60% | **76.79%** |
| BIRD Mini-Dev (500) | 20.40% | 37.60% | 34.00% | 31.20% | **38.80%** |

## Paired stats vs prior best

| Bench | A | B | n | EX(A) | EX(B) | Δ pp | 95% CI pp | McNemar p | helpful | harmful |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Spider | B0 | B6_v7 | 1034 | 72.53% | 76.79% | +4.26 | [+2.13, +6.29] | 0.0001 | 80 | 36 |
| Spider | B2_v5 | B6_v7 | 1034 | 74.76% | 76.79% | +2.03 | [+0.68, +3.29] | 0.0025 | 33 | 12 |
| Spider | B4_v5 | B6_v7 | 1034 | 76.69% | 76.79% | +0.10 | [-0.77, +0.87] | 1.0000 | 9 | 8 |
| Spider | B5_v6 | B6_v7 | 1034 | 76.60% | 76.79% | +0.19 | [-0.68, +0.97] | 0.8145 | 10 | 8 |
| BIRD | B0 | B6_v7 | 500 | 20.40% | 38.80% | +18.40 | [+14.60, +22.20] | 0.0000 | 98 | 6 |
| BIRD | B2_v5 | B6_v7 | 500 | 37.60% | 38.80% | +1.20 | [-1.60, +4.00] | 0.4966 | 30 | 24 |
| BIRD | B4_v5 | B6_v7 | 500 | 34.00% | 38.80% | +4.80 | [+2.40, +7.40] | 0.0004 | 34 | 10 |
| BIRD | B5_v6 | B6_v7 | 500 | 31.20% | 38.80% | +7.60 | [+4.80, +10.60] | 0.0000 | 47 | 9 |

## Verdicts

- Spider B0 → B6_v7: **B6_v7 significantly beats B0** (Δ +4.26 pp, p=0.0001) (helpful 80 / harmful 36)
- Spider B2_v5 → B6_v7: **B6_v7 significantly beats B2_v5** (Δ +2.03 pp, p=0.0025) (helpful 33 / harmful 12)
- Spider B4_v5 → B6_v7: no significant difference (p=1.0000) (helpful 9 / harmful 8)
- Spider B5_v6 → B6_v7: no significant difference (p=0.8145) (helpful 10 / harmful 8)
- BIRD B0 → B6_v7: **B6_v7 significantly beats B0** (Δ +18.40 pp, p=0.0000) (helpful 98 / harmful 6)
- BIRD B2_v5 → B6_v7: no significant difference (p=0.4966) (helpful 30 / harmful 24)
- BIRD B4_v5 → B6_v7: **B6_v7 significantly beats B4_v5** (Δ +4.80 pp, p=0.0004) (helpful 34 / harmful 10)
- BIRD B5_v6 → B6_v7: **B6_v7 significantly beats B5_v6** (Δ +7.60 pp, p=0.0000) (helpful 47 / harmful 9)
