# Evidence semantics design v7

_Generated: 2026-05-04 20:02 UTC._

Architecture: B6_v7 controller (Phase 6 LLM-as-judge selector) + extended
evidence layer per `evidence_semantics_v7`.

## Evidence layers
- gold: BIRD per-item snippet (was the only source in B6_v7).
- schema: table/column comments + FK summary (from IR).
- value-hints: bounded SQLite probes (DISTINCT LIMIT 10 / MIN-MAX).
- generated_aliases: rule-based camelCase/snake_case → English mapping.

## Per-db precompute
Value hints and schema evidence are computed once per db_id (~5s for 11 BIRD dbs)
and reused across all 500 questions. Per-item cost is just rendering + ranking.

## Headline ablation (FULL BIRD 500)

| Cell | EX | 95% CI | evidence chars avg |
|---|---:|---:|---:|
| B6_v7 | 38.80% | [34.6, 43.1] | 0 |
| B7d_rich | 39.20% | [35.0, 43.5] | 546 |
| B7c_profiles_only | 33.20% | [29.2, 37.4] | 528 |
| B7e_none | 33.20% | [29.2, 37.4] | 0 |

## Paired stats

| Bench | A | B | n | EX(A) | EX(B) | Δ pp | 95% CI pp | McNemar p | helpful | harmful |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BIRD | B6_v7 | B7d_rich | 500 | 38.80% | 39.20% | +0.40 | [-1.60, +2.40] | 0.8555 | 16 | 14 |
| BIRD | B7d_rich | B7c_profiles_only | 500 | 39.20% | 33.20% | -6.00 | [-8.60, -3.40] | 0.0000 | 10 | 40 |
| BIRD | B7d_rich | B7e_none | 500 | 39.20% | 33.20% | -6.00 | [-8.60, -3.20] | 0.0000 | 10 | 40 |
| BIRD | B7c_profiles_only | B7e_none | 500 | 33.20% | 33.20% | +0.00 | [-2.00, +2.00] | 1.0000 | 13 | 13 |
| BIRD | B6_v7 | B7c_profiles_only | 500 | 38.80% | 33.20% | -5.60 | [-8.60, -3.00] | 0.0001 | 12 | 40 |
| BIRD | B6_v7 | B7e_none | 500 | 38.80% | 33.20% | -5.60 | [-8.00, -3.40] | 0.0000 | 4 | 32 |
| BIRD | B2_v5 | B7d_rich | 500 | 37.60% | 39.20% | +1.60 | [-1.60, +4.80] | 0.3961 | 38 | 30 |

## Verdicts

- BIRD B6_v7 → B7d_rich: no significant difference (p=0.8555) (helpful 16 / harmful 14)
- BIRD B7d_rich → B7c_profiles_only: **B7c_profiles_only significantly worse than B7d_rich** (Δ -6.00 pp, p=0.0000) (helpful 10 / harmful 40)
- BIRD B7d_rich → B7e_none: **B7e_none significantly worse than B7d_rich** (Δ -6.00 pp, p=0.0000) (helpful 10 / harmful 40)
- BIRD B7c_profiles_only → B7e_none: no significant difference (p=1.0000) (helpful 13 / harmful 13)
- BIRD B6_v7 → B7c_profiles_only: **B7c_profiles_only significantly worse than B6_v7** (Δ -5.60 pp, p=0.0001) (helpful 12 / harmful 40)
- BIRD B6_v7 → B7e_none: **B7e_none significantly worse than B6_v7** (Δ -5.60 pp, p=0.0000) (helpful 4 / harmful 32)
- BIRD B2_v5 → B7d_rich: no significant difference (p=0.3961) (helpful 38 / harmful 30)
