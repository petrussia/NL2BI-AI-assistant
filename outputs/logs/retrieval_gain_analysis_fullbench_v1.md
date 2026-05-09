# Retrieval gain analysis (full benchmarks v1)

_Generated: 2026-05-03 00:20 UTC._

B0 (full schema anchor) reused from v11. B1_v5 = retrieval-only direct.
B2_v5 = retrieval + benchmark evidence direct.

## Headline EX

| Bench | B0 (anchor) | B1_v5 (retrieval) | B2_v5 (retrieval+evidence) |
|---|---:|---:|---:|
| Spider dev (1034) | 72.53% | 74.85% | 74.76% |
| BIRD Mini-Dev (500) | 20.40% | 23.00% | 37.60% |

## Paired diff vs anchor (helpful = B fixes A; harmful = B breaks A)

| Bench | A | B | n | EX(A) | EX(B) | Δ pp | 95% CI pp | McNemar p | helpful | harmful | neutral |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Spider | B0 | B1_v5 | 1034 | 72.53% | 74.85% | +2.32 | [+0.39, +4.35] | 0.0237 | 64 | 40 | 930 |
| Spider | B0 | B2_v5 | 1034 | 72.53% | 74.76% | +2.22 | [+0.29, +4.16] | 0.0265 | 61 | 38 | 935 |
| Spider | B1_v5 | B2_v5 | 1034 | 74.85% | 74.76% | -0.10 | [-1.06, +0.87] | 1.0000 | 13 | 14 | 1007 |
| BIRD | B0 | B1_v5 | 500 | 20.40% | 23.00% | +2.60 | [-0.20, +5.40] | 0.0919 | 32 | 19 | 449 |
| BIRD | B0 | B2_v5 | 500 | 20.40% | 37.60% | +17.20 | [+13.00, +21.20] | 0.0000 | 105 | 19 | 376 |
| BIRD | B1_v5 | B2_v5 | 500 | 23.00% | 37.60% | +14.60 | [+10.80, +18.80] | 0.0000 | 93 | 20 | 387 |

## Verdicts

- Spider B0 → B1_v5: **B1_v5 significantly beats B0** (Δ +2.32 pp, p=0.0237) (helpful 64 / harmful 40)
- Spider B0 → B2_v5: **B2_v5 significantly beats B0** (Δ +2.22 pp, p=0.0265) (helpful 61 / harmful 38)
- Spider B1_v5 → B2_v5: no significant difference (p ≥ 0.05) (helpful 13 / harmful 14)
- BIRD B0 → B1_v5: no significant difference (p ≥ 0.05) (helpful 32 / harmful 19)
- BIRD B0 → B2_v5: **B2_v5 significantly beats B0** (Δ +17.20 pp, p=0.0000) (helpful 105 / harmful 19)
- BIRD B1_v5 → B2_v5: **B2_v5 significantly beats B1_v5** (Δ +14.60 pp, p=0.0000) (helpful 93 / harmful 20)
