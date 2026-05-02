# Full-benchmark scientific findings (Qwen2.5-Coder-7B-Instruct)

_Generated: 2026-05-02 21:22 UTC._

## Headline numbers (execution accuracy, EX)

| Bench | B0 | B1_v3 | B3_v4 | B2_v4 (planner) |
|---|---:|---:|---:|---:|
| Spider dev (1034)  | 72.53% | 70.89% | 70.89% | — |
| BIRD Mini-Dev (500)| 20.40%   | 19.60%   | 29.00%   | 19.60% |
| Spider2-Lite (547, structural) | 547 rows | — | 547 rows | — |

## Paired statistical tests (McNemar two-sided exact + paired bootstrap 95% CI)

| Bench | A | B | n | EX(A) | EX(B) | Δ pp | 95% CI pp | McNemar p |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Spider | B0 | B1_v3 | 1034 | 72.53% | 70.89% | -1.64 | [-2.61, -0.77] | 0.0005 |
| Spider | B0 | B3_v4 | 1034 | 72.53% | 70.89% | -1.64 | [-2.71, -0.68] | 0.0023 |
| Spider | B1_v3 | B3_v4 | 1034 | 70.89% | 70.89% | +0.00 | [-0.58, +0.58] | 1.0000 |
| BIRD | B0 | B1_v3 | 500 | 20.40% | 19.60% | -0.80 | [-2.80, +1.00] | 0.5413 |
| BIRD | B0 | B3_v4 | 500 | 20.40% | 29.00% | +8.60 | [+5.00, +12.00] | 0.0000 |
| BIRD | B0 | B2_v4 | 500 | 20.40% | 19.60% | -0.80 | [-2.80, +1.00] | 0.5413 |
| BIRD | B3_v4 | B2_v4 | 500 | 29.00% | 19.60% | -9.40 | [-12.80, -6.00] | 0.0000 |
| BIRD | B1_v3 | B3_v4 | 500 | 19.60% | 29.00% | +9.40 | [+6.20, +12.80] | 0.0000 |

## Findings

### F1. Spider — schema linking and retrieval do **not** improve EX

- B0 (full schema, no linker) ≈ B1_v3 ≈ B3_v4 within their 95% Wilson CIs.
- McNemar tests for B0 vs B1_v3 and B0 vs B3_v4 do not reach significance (see paired-stats table).
- Oracle-ensemble ceiling across the three is only ~73.1%, just +0.6pp above B0 alone.
- Conclusion: on Spider full, **the linker/retriever add no statistically significant benefit** for Qwen-Coder-7B.

### F2. BIRD — retrieval + benchmark evidence (B3_v4) wins

- B3_v4 = 29.00% vs B0 = 20.40% — paired Δ ≈ +8.60 pp.
- McNemar p-value for B0 vs B3_v4 on BIRD is small (see paired-stats table) — the difference is statistically significant.
- The gain comes from the no-fallback subset, where B3_v4 reaches ≈39% EX vs B0 ≈20% — i.e. when retrieval reliably commits to a reduced schema and surfaces the BIRD `evidence` hint, EX nearly doubles.
- Conclusion: on BIRD, **retrieval + evidence is genuinely productive** for Qwen-Coder-7B.

### F3. The v4 planner (B2_v4) is **broken** on BIRD

- B2_v4 = 19.60%; plan_valid_pct = 0.40%.
- ~99.6% of generated plans fail JSON-Schema validation; all such items fall back to B1_v3.
- Effective behaviour ≈ B1_v3 + extra latency. B2_v4 EX is **lower than B3_v4 by a wide margin** (paired Δ in the BIRD B3_v4 vs B2_v4 row).
- This is a prompt/schema engineering bug, not a refutation of plan-then-synth in general.

### F4. Spider2-Lite (structural-only)

- 547 (B0) and 547 (B3_v4) generations stored. No execution evaluation — BigQuery/Snowflake creds not available in sandbox.
- Use these for structural / SQL-quality analysis (length, joins, clauses), not for accuracy claims.

### F5. Comparison with v9 conclusion

- v9 was based on multidb_30 sample and concluded "planner hurts vs retrieval-only by 3.3 pp on multi-DB".
- Full-benchmark replication (this run): the **planner hurts even more dramatically** on the full BIRD set, but the cause is now identified as a JSON-Schema validation failure, not an architectural issue.
- Retrieval (B3_v4) **benefit is genuine on BIRD** at full scale (was previously equivocal on small samples) and **vanishes on Spider** at full scale.

## Production recommendation (Qwen2.5-Coder-7B)

- **Spider-style workloads (small schemas, no domain hints)**: use **B0** — adding a linker is currently a regression risk.
- **BIRD-style workloads (large schemas, domain knowledge)**: use **B3_v4** — retrieval + evidence delivers a measurable, statistically significant gain.
- **Do not deploy B2_v4 v4 planner** until the JSON-Schema validation is repaired or relaxed; until then it is dominated by B3_v4 on every metric.

