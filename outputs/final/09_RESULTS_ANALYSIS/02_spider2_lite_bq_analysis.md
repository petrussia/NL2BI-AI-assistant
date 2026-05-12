# Spider2-Lite-BQ Analysis — 34.6 % BigQuery dry_run-pass FULL 205

This document analyses the Spider2-Lite-BQ FULL 205 result. The headline number is 34.6 % BigQuery `dry_run`-pass rate (\*) at Phase 24 stable (run directory `outputs/spider2_lite/runs/lite_bq_full_v25/`). The analysis covers what the number means, what the per-lane progression looked like, what the dominant failure clusters are, what Phase 30 will do about them, and how the result positions against the published Lite-BQ leaderboard.

> (\*) Spider2-Lite-BQ uses BigQuery's `client.query(..., dry_run=True)`, a plan-level acceptance check that does NOT execute the query. The reported 34.6 % is plan-acceptance, not row-set match. See [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md) for the full forensic disclosure and the Phase 28b audit plan.

Companion files: classical at [01_classical_benchmarks_spider1_bird.md](01_classical_benchmarks_spider1_bird.md); Snow at [03_spider2_snow_analysis.md](03_spider2_snow_analysis.md); DBT at [04_spider2_dbt_analysis.md](04_spider2_dbt_analysis.md); per-DB BQ at [../07_METRICS_AND_RESULTS/06_per_db_breakdown_bq.md](../07_METRICS_AND_RESULTS/06_per_db_breakdown_bq.md).

## 1. Headline number and exact wording

**Spider2-Lite-BQ FULL 205: 34.6 % BigQuery `dry_run`-pass rate (plan-level acceptance, 71 / 205, see [Appendix 07](../11_APPENDIX/07_critical_metric_caveat.md) (\*)).** This is the canonical wording. The full aggregate from `metrics.csv`:

| Counter | Value | Rate of 205 |
|---|---|---|
| n_total | 205 | 100.0 % |
| chosen_schema_valid | 119 | 58.0 % |
| parse_ok | 204 | 99.5 % |
| **execute_ok = `dry_run_ok` (BigQuery dry_run-pass)** (\*) | **71** | **34.6 %** |
| chosen_family_A | 172 | 83.9 % |
| chosen_family_B | 33 | 16.1 % |

The 34.6 % dry_run-pass rate is the Lite-BQ headline. It is higher than the Spider2-Snow 23.76 % EXPLAIN-pass rate for two reasons: (a) Lite-BQ tasks use public BigQuery datasets with stable, well-documented schemas (simpler than Snow's private warehouse data); (b) the v24 BQ engine-compat rewrites catch a class of Snowflake-flavoured emissions that would otherwise fail dry_run. The 99.5 % parse_ok rate confirms that the planner's SQL is syntactically well-formed at near-ceiling on this lane.

## 2. Per-lane progression (Phase 15 → Phase 25)

The Lite-BQ progression is documented in [../07_METRICS_AND_RESULTS/03_progression_by_benchmark.md](../07_METRICS_AND_RESULTS/03_progression_by_benchmark.md) §3. Highlights:

| Phase | dry_run-pass | Headline change |
|---|---|---|
| 15 (v15 first BQ attempt) | 0 % | First submission, baseline 0 % |
| 17 (v17 model-swap pilot) | 10 % | Model family confirmed (Qwen-Coder > generic 30B) |
| 18 (v18 schema-first pivot) | 30 % | Closed-set planner + live catalog probing |
| 19 (v19 repair sprint) | 30 % | Seven validator-feedback patches |
| 20 (STAGE A1 identifier canon) | 30 % | plan_validation 42 → 54 %, chosen_schema_valid unchanged |
| 21 (STAGE A1 converge) | 30 % | Metric-label fix + UNNEST alias trust |
| 22 (STAGE A1+A2+A3) | 30 % | Family C explicit join hints added; rarely chosen |
| 24 (orchestration fix + A4) | 30 % pilot 50 | Sequential runner; A4 BQ rewrites |
| **25 (v25 stable FULL 205)** | **34.6 %** | **Final FULL run on canonical stack** |

The progression's defining characteristic is the *plateau at 30 % from Phase 18 through Phase 24*, followed by a 4.6-pp lift from Phase 22-pilot-50 to Phase 25-FULL-205. The plateau is the dossier's most informative *negative result*: every architectural intervention from Phase 19 to Phase 24 (validator-feedback patches, identifier canonicalisation, all-columns pack, join-hint Family C, A4 dialect rewrites) produced only single-digit pilot-scale movements that did not compound. The Phase 22 audit (`outputs/logs/phase19_pack_thinness_audit.md`) predicted +20 pp from STAGE A3 and observed +4 pp. This gap is the empirical evidence for Claim 5 (layered fixes can mask each other's contributions; cross-component interaction matters).

The Phase 25 lift from 30 % to 34.6 % at FULL is driven by the v24 engine-compat rewrites operating at scale: the rewrites' impact on small pilot 50 samples is in the noise (1–2 tasks), but at 205 tasks the absolute count rises to a measurable 9–10 tasks.

## 3. Failure cluster analysis

The Lite-BQ failure-class distribution at Phase 22 pilot 50 (representative of the FULL 205 distribution, see [06_failure_analysis_remaining.md](06_failure_analysis_remaining.md) §3 for the full table):

| failure class | share of failures | mechanism |
|---|---|---|
| unrecog_name_join_missing | ≈ 36 % | JOIN predicate column exists but is in the wrong table for the chosen join graph |
| AND_int_date | ≈ 21 % | integer-typed column combined with date-typed comparison; BigQuery type-check rejects |
| types_mismatch | ≈ 21 % | STRING vs BYTES, or TIMESTAMP vs DATE without explicit cast |
| nested_agg | ≈ 14 % | nested aggregate in SELECT without proper GROUP BY materialisation |
| ARRAY_CONTAINS | ≈ 7 % | Snowflake-flavoured `ARRAY_CONTAINS` left in BQ emission |

The dominant cluster is **unrecog_name_join_missing (36 %)**: the planner picks tables but the join predicate is wrong because the candidate-selector's Family B (two-table join) does not see the right join key. This is the target of Phase 30 F2 (JOIN-graph expansion).

The second tier is **dialect-rewrite issues (AND_int_date + types_mismatch + ARRAY_CONTAINS = 49 % of failures)**: BigQuery is stricter about type coercion than Snowflake, and our emitter produces SQL in a Snowflake-flavoured idiom. The Phase 30 F4 BQ post-processor (an AST-aware rewriter analogous to the F4 wrap on Snow) targets this cluster.

The residual **nested_agg (14 %)** is harder: it requires the planner to decompose a query like "average of the maximum per group" into a sub-aggregation pattern. The closed-set planner does not currently emit this; a hypothetical Phase 32 multi-shot synthesis would be the natural target.

## 4. Family distribution diagnostic

The FULL 205 chosen-family split:

| family | count | share |
|---|---|---|
| Family A (one-table candidate) | 172 | 83.9 % |
| Family B (two-table join candidate) | 33 | 16.1 % |

This split is essentially unchanged from the Phase 22 pilot pattern, confirming that the v22 → v24 stack saturated the lane on the current planner+pack design. The Phase 22 audit's prediction of "+20 pp via Family B uptake" was contingent on Family B being selected more often; instead, the candidate selector's joint-plausibility scoring continued to prefer Family A on most tasks. Family C (explicit join hints, added at Phase 22 to give the planner an alternative path to two-table joins) was almost never the highest-scoring candidate.

The Phase 30 F2 intervention targets exactly this gap: by surfacing more join candidates from the live catalog's PK/FK metadata, Family B's score should rise relative to Family A on join-heavy questions. The audit projects Family B selection growing to 30–40 % of tasks; combined with correct join predicates from F2, this is the projected source of the +6 to +10 pp dry_run-pass lift.

## 5. Position relative to published systems

The cross-metric situation applies to Lite-BQ same as to Snow. The dossier uses the canonical band-placement wording.

| System | Metric | Value | Class |
|---|---|---|---|
| AutoLink + DeepSeek-R1 (closed) | row-match | 52.28 % | closed competitor |
| **Ours (Phase 24 stable)** | **dry_run-pass (\*)** | **34.6 %** | open ≤30 B |
| LinkAlign + DeepSeek-R1 (closed) | row-match | 33.09 % | closed competitor |
| Spider-Agent + Qwen3-Coder | row-match | ≈ 27–32 % | open ≤30 B baseline |

**Canonical band-placement wording**: *"Our plan-acceptance rate on Spider2-Lite-BQ is in the same band as the open-weight Spider-Agent baselines, pending row-match audit."*

A back-of-envelope row-match projection from the failure-class distribution: of the 71 dry_run-pass tasks, the ones likely to also row-match are those where the failure cluster does not produce silent-row-mismatch (cluster's `nested_agg` and `types_mismatch` are likely to row-mismatch even when passing dry_run). Projecting 60–75 % conversion: row-match band 20–28 %. **Not publishable** — this is design-time projection, not measurement; the Phase 28b audit will produce the real number.

## 6. Phase 30 plan — projected impact

**Phase 30 F2 (JOIN-graph expansion, 2 weeks).** Surface PK/FK relationships from BigQuery `INFORMATION_SCHEMA.KEY_COLUMN_USAGE` and equivalent metadata into the schema pack; produce Family B candidates with correct join predicates; let the candidate selector rank these higher than the current Family A defaults on join-heavy questions. Projected impact: +6 to +10 pp dry_run-pass, lifting 34.6 % to **40–44 %**.

**Phase 30 F4 BQ post-processor (1 week).** AST-aware rewrites for `AND_int_date`, `types_mismatch`, and `ARRAY_CONTAINS`. Analogous in spirit to F4 on Snow but with BigQuery-specific rules. Projected impact: +3 to +5 pp on top of F2, lifting to **43–49 %**.

**Cumulative Phase 30 projection**: 34.6 % → 43–49 % dry_run-pass on Spider2-Lite-BQ FULL 205, corresponding (at projected 60–75 % conversion) to row-match in the 26–37 % range. If the audit conversion ratio is high, this would put the system at the open-weight Spider-Agent + Qwen3-Coder ceiling on Lite-BQ.

The Phase 30 work is post-defence and is documented in [../06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md](../06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md) §3.

## 7. What this analysis establishes

This document establishes:

* The Spider2-Lite-BQ FULL 205 headline number is 34.6 % BigQuery dry_run-pass (\*), traceable to a single canonical run at Phase 25.
* The lane plateaued at 30 % from Phase 18 to Phase 22 despite multiple architectural interventions, illustrating the *layered-fix-masking* phenomenon (Claim 5) and the value of architectural-progression negative-result documentation.
* The dominant failure cluster is `unrecog_name_join_missing` (36 % of failures), specifically targeted by the Phase 30 F2 JOIN-graph expansion.
* The Family distribution (A 83.9 % / B 16.1 %) confirms that the architecture is currently conservative on join inference; Phase 30 targets exactly this.
* The cross-metric situation on Lite-BQ is identical to Snow: 34.6 % is plan-acceptance, not row-match; row-match is bounded above by 34.6 %; the audit is Phase 28b.

This document does **not** establish:

* The row-match rate on Lite-BQ. Phase 28b audit produces this.
* The per-DB breakdown on Lite-BQ (the v25 runner did not persist `task_db` in predictions; the per-DB analysis is deferred to the audit, see [../07_METRICS_AND_RESULTS/06_per_db_breakdown_bq.md](../07_METRICS_AND_RESULTS/06_per_db_breakdown_bq.md)).
* The Phase 30 projected impact quantitatively. The +6 to +10 pp from F2 and +3 to +5 pp from F4 are design-time projections from the failure-class distribution, not measurements.
* A direct leaderboard ranking on Lite-BQ. The canonical band-placement wording is "in the same band as the open-weight Spider-Agent baselines, pending row-match audit."

The defendable Lite-BQ position at thesis defence: **34.6 % BigQuery dry_run-pass rate (\*) on Spider2-Lite-BQ FULL 205, mid-band open-weight ≤30 B pending row-match audit; the dominant residual failure cluster (`unrecog_name_join_missing`, 36 % of failures) is named and targeted by the post-defence Phase 30 F2 intervention with a projected +6–10 pp lift.**
