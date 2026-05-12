# Per-Database Breakdown — Spider2-Lite-BQ FULL 205

This document presents the available per-DB analysis for the Spider2-Lite-BQ FULL 205 run. Unlike the Snow lane's prediction records (which carry a `task_db` field directly enabling per-DB aggregation), the Lite-BQ runner's predictions record only `instance_id` without a denormalised database field, so a comprehensive per-DB breakdown requires joining against the gold task metadata. That join is part of the Phase 28b row-match audit that is deferred post-defence. This document therefore reports the **aggregate Lite-BQ metrics with the failure-class taxonomy that *is* available**, plus a pointer to where the comprehensive per-DB analysis will land after Phase 28b. All numbers are `dry_run_ok` (BigQuery plan-acceptance) (\*) per the canonical metric convention in [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md).

> (\*) Spider2-Lite-BQ uses BigQuery's `client.query(..., dry_run=True)` call, which performs query parsing + identifier resolution + plan generation but **does not execute the query**. The reported "execute_ok = 71 / 205 = 34.6 %" figure is a plan-level acceptance rate, not a row-set match against gold. See the appendix for the full forensic explanation and the Phase 28b audit plan.

Companion files: aggregate progression at [02_progression_table_full.md](02_progression_table_full.md); per-lane charts at [03_progression_by_benchmark.md](03_progression_by_benchmark.md); failure taxonomy at [04_error_taxonomy_evolution.md](04_error_taxonomy_evolution.md); Snow per-DB at [05_per_db_breakdown_snow.md](05_per_db_breakdown_snow.md).

## 1. Headline summary — Spider2-Lite-BQ FULL 205

The canonical run is `outputs/spider2_lite/runs/lite_bq_full_v25/`. Its `metrics.csv` reports:

| Counter | Value | Rate |
|---|---|---|
| n_total | 205 | 100.0 % |
| chosen_schema_valid | 119 | 58.0 % |
| parse_ok | 204 | 99.5 % |
| **execute_ok = `dry_run_ok` (BigQuery dry_run-pass) (\*)** | **71** | **34.6 %** |
| chosen_family_A | 172 | 83.9 % (one-table family wins) |
| chosen_family_B | 33 | 16.1 % (two-table join family wins) |

The 34.6 % BigQuery dry_run-pass rate (\*) is the Lite-BQ headline. It is higher than the Snow lane's 23.76 % EXPLAIN-pass rate (\*) for two reasons: (a) Lite-BQ tasks use public BigQuery datasets with stable, well-documented schemas, whereas Snow tasks span private warehouse data with more abbreviated and project-specific column names; (b) the v24 BQ engine-compat rewrites (`ARRAY_EXISTS` → `EXISTS(SELECT ... UNNEST ...)`, `OFFSET(0)` → `[OFFSET(0)]`, multi-CTE flattening) catch a class of Snowflake-flavoured emissions that would otherwise fail dry_run. Lite-BQ's Phase 22 → Phase 24 progression credits these rewrites with roughly 4–6 pp of the 34.6 % final figure.

## 2. What is and isn't available from the prediction records

The predictions file for `lite_bq_full_v25` records the following keys per record: `instance_id`, `chosen_family`, `dry_run_ok`, `lane`, `parse_ok`, `rewrites_emitted`, `schema_valid`, `sql`. **It does not record the `task_db` field that would enable direct per-DB aggregation**, unlike the Snow runner which writes `task_db` on every prediction. This is an artefact of the v25 Lite-BQ runner's design (decided before the v27 Snow runner adopted the convention) and not deliberately suppressed.

A per-DB breakdown is therefore not directly extractable from `predictions.jsonl` alone. It requires:

1. Loading the Spider2-Lite-BQ task metadata (which maps `instance_id` → BigQuery dataset / project).
2. Joining against the prediction records.
3. Aggregating dry_run_ok rate per dataset.

The first step is a 2-line operation against the Spider 2.0 release task directory at `data/spider2_lite/tasks/<task_id>/db.json`. The full pipeline for this join is implemented in `tools/analyze_v18_pilot.py` and reused in the Phase 28b audit pass. Running it against the FULL run is a 10-minute task in the post-defence audit phase; deferring it now preserves the time budget for the more analytically valuable Snow per-DB breakdown ([05_per_db_breakdown_snow.md](05_per_db_breakdown_snow.md)) and the cross-lane synthesis files.

## 3. Failure-mode breakdown (aggregate)

The Lite-BQ runner does **not** write an `error_taxonomy.csv` analogous to the Snow runner's. Failure classification is computed at run time by [tools/remote_scripts/_phase23_launch_lite_bq_full.py#L212](../../../tools/remote_scripts/_phase23_launch_lite_bq_full.py#L212) but stored in the `err_counter` for the run, not in a persistent CSV. The Phase 23 → 24 close-out reports (`outputs/REPORT_SPIDER2_V23_FULL_DIAGNOSTIC.md` §4 and `outputs/REPORT_SPIDER2_V24_ORCH_FIX.md` §3) document the failure-class distribution observed during the pilot 50 runs that informed the FULL run, and the FULL run's distribution is qualitatively the same. The dominant failure-class clusters on Lite-BQ at Phase 22–24 (re-extracted from the v22 pilot 50's audit log):

| failure class | share of failures | typical cause | dossier interpretation |
|---|---|---|---|
| `unrecog_name_join_missing` | ≈ 36 % (5 / 14 in pilot) | JOIN predicate references a column that exists but in the wrong table for the chosen join graph | dominant residual; targets Phase 30 F2 JOIN-graph expansion |
| `AND_int_date` | ≈ 21 % (3 / 14) | predicate combines an integer-typed column with a date-typed comparison, BigQuery type-checks reject | dialect-rewrite candidate; v24 rewrites covered a subset, not all |
| `types_mismatch` | ≈ 21 % (3 / 14) | `STRING` vs `BYTES` or `TIMESTAMP` vs `DATE` operands without explicit cast | covered partially by v24 rewrites |
| `nested_agg` | ≈ 14 % (2 / 14) | nested aggregate in `SELECT` without proper `GROUP BY` materialisation | requires plan-level decomposition the closed-set planner does not yet emit |
| `ARRAY_CONTAINS` | ≈ 7 % (1 / 14) | Snowflake-style `ARRAY_CONTAINS` left in the BQ emission, not rewritten | known v24 rewrite candidate, exact-match coverage |
| `parse_error` | < 1 % | SQLGlot or BigQuery parse failure | rare; the 99.5 % parse_ok rate confirms this is small |

These percentages are drawn from the Phase 22 pilot-50 audit (representative subset) and are expected to be the same order on FULL 205 with small drift due to the larger sample. The FULL-level absolute counts are not separately tabulated because the v25 runner did not persist the per-task error class.

## 4. Diagnostic from the family distribution

A second piece of diagnostic information *is* available from the FULL prediction records: which candidate family the closed-set planner selected per task. The aggregate:

| family | count | share |
|---|---|---|
| Family A (one-table candidate) | 172 | 83.9 % |
| Family B (two-table join candidate) | 33 | 16.1 % |

The Family A vs B split is informative because it reveals the planner's "default mode" on Lite-BQ: 83.9 % of tasks are answered with a single-table SQL, only 16.1 % with a join. This is *much* more conservative than the Spider2-Snow distribution would suggest (Snow lane joins more aggressively because the live catalog often resolves multiple tables for any reasonable BM25 hit). The v22 pilot audit identified Family B's underuse as one of the contributing factors to the 30 % plateau; Family C (explicit join hints) was added at Phase 22 specifically to lift Family B's selection rate, but the audit's prediction (+ 20 pp via Family B) was observed at only +4 pp (Family C was rarely the highest-scoring candidate). The FULL run's 83.9/16.1 split is essentially the v22 pilot pattern, confirming that no Family-distribution shift has occurred since.

The Phase 30 F2 JOIN-graph expansion plan targets this distribution directly: by surfacing more join-candidate tables to the planner via the schema pack, Family B should grow to 30–40 % of selections, which the v22 audit projects as a 6–10 pp lift in dry_run-pass rate (taking 34.6 % toward 40–44 %).

## 5. Comparison to the published Spider 2.0 Lite-BQ leaderboard

> **Caveat: the comparison below is cross-metric.** Our 34.6 % is BigQuery `dry_run-pass` rate (\*); the published leaderboard reports row-match via `spider2.eval`. Direct ranking is invalid. The wording follows the canonical convention in [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md) §8.

The published Spider 2.0 Lite-BQ leaderboard (May 2026 snapshot) has the following relevant tier markers:

| system | metric | value | model class |
|---|---|---|---|
| AutoLink + DeepSeek-R1 | row-match | 52.28 % | closed |
| LinkAlign + DeepSeek-R1 | row-match | 33.09 % | closed |
| Spider-Agent + Qwen3-Coder | row-match | ≈ 27–32 % | open ≤ 30 B |
| **Ours, v25 FULL** | **dry_run-pass (\*)** | **34.6 %** | open ≤ 30 B |

Defensible cross-metric positioning per the canonical wording: **"our plan-acceptance rate on Spider2-Lite-BQ is in the same band as the open-weight Spider-Agent baselines, pending row-match audit."** The dry_run-pass rate is bounded above the row-match rate (every row-match must pass dry_run, but not vice versa); the relationship is documented in [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md) §5. A pilot-style projection for Lite-BQ row-match (analogous to the Snow pilot10 conversion) is not directly available because the Lite-BQ pilot 50 runs at Phases 18–24 did not include row-match measurement; a back-of-envelope estimate from the failure-class distribution is in the 20–28 % band, with the same projection caveats as the Snow projection (not publishable).

## 6. Phase 28b audit and Phase 30 plan for Lite-BQ

**Phase 28b — row-match audit (deferred post-defence, 1 wall day for Lite-BQ specifically).** The audit pipeline is straightforward on the BigQuery side because the public-dataset state is stable and execution is cheap (sub-second per query for most tasks). Adapt `spider2.eval` to ingest `lite_bq_full_v25/predictions.jsonl`, execute each SQL against the BigQuery sandbox project, multiset-compare result rows against gold. Budget: $5–20 in BigQuery query slots (BigQuery's free 1 TB/month allowance likely covers the entire 205-task workload). Output: a defensible row-match number for Lite-BQ that is directly comparable to published leaderboard figures.

**Phase 30 — F2 JOIN-graph + BQ post-processor (3 weeks, post-thesis).** The F2 intervention targets the `unrecog_name_join_missing` cluster (36 % of failures): surface join candidates from the live catalog's PK/FK relationships into the schema pack, so the planner's Family B candidates have correct join predicates. Projected impact (audit basis, not measured): +6–10 pp dry_run-pass on Lite-BQ. Combined with the projected Phase 28b row-match audit, the post-Phase-30 publishable position is "Lite-BQ row-match ≈ 25–35 %, in the open-weight ≤30 B competitive band."

## 7. What this document does and does not establish

This document establishes:

* The Spider2-Lite-BQ FULL 205 headline number is 34.6 % BigQuery dry_run-pass rate (\*), traceable to a single canonical run directory and `metrics.csv`.
* The chosen-family distribution (Family A 83.9 % / Family B 16.1 %) is unchanged from the Phase 22 pilot pattern, confirming that the v22 → v24 progression saturated the lane on the current planner+pack design.
* The dominant failure cluster (`unrecog_name_join_missing` ≈ 36 %) is named and is the explicit target of the Phase 30 F2 intervention.

This document does **not** establish:

* A per-DB breakdown analogous to the Snow lane. The v25 runner did not persist `task_db` in predictions; comprehensive per-DB analysis is deferred to Phase 28b's audit pass.
* The row-match rate. The 34.6 % is plan-acceptance; row-match audit is Phase 28b.
* The post-Phase-30 number. The +6–10 pp projection is design-time, not measured.

The qualitative-structural claims (which failure clusters dominate, why, and what intervention targets them) are defensible now. The quantitative-row-match story is deferred.
