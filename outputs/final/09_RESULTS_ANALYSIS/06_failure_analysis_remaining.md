# Failure Analysis — Remaining Residual After Phase 28

This document characterises the failure modes that remain after the Phase 28 closure across all four Spider 2 family lanes (Snow, Lite-Snow, Lite-BQ, DBT). For each lane, the dominant failure clusters are named, the underlying mechanism is described, and the Phase 29 / 30 / 31 interventions that target each cluster are mapped. The output is the design input for the post-defence engineering roadmap.

All Spider 2 SQL-lane numbers in this document are EXPLAIN-pass / dry_run-pass (\*) per the canonical convention in [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md). Companion files: per-DB Snow at [../07_METRICS_AND_RESULTS/05_per_db_breakdown_snow.md](../07_METRICS_AND_RESULTS/05_per_db_breakdown_snow.md); error-taxonomy evolution at [../07_METRICS_AND_RESULTS/04_error_taxonomy_evolution.md](../07_METRICS_AND_RESULTS/04_error_taxonomy_evolution.md).

## 1. Spider2-Snow failure taxonomy at Phase 28-revert-A

The Phase 28 FULL run wrote an `error_taxonomy.csv` summarising the failure-class distribution on the 144-task post-resume window (resume-path artefact, see [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md) §4). The distribution is representative of the full 547-task population:

| failure class | share of failures (of 144) | typical mechanism |
|---|---|---|
| invalid_identifier | 60 (41.7 %) | column-not-found in live Snowflake catalog despite passing closed-set validator |
| ok | 36 (25.0 %) | three-gate-clean (not a failure; included for completeness) |
| schema_invalid | 25 (17.4 %) | v18 validator rejected SQL before EXPLAIN attempt |
| ProgrammingError | 11 (7.6 %) | Snowflake-side semantic errors (ambiguous column reference, type mismatch in aggregation) |
| parse_error | 6 (4.2 %) | SQLGlot parse failure (mostly LATERAL FLATTEN tail) |
| no_catalog_for_task_db | 3 (2.1 %) | task DB not in our catalog (residual catalog-gap) |
| syntax_error | 2 (1.4 %) | malformed SQL |
| parse_error_guard | 1 (0.7 %) | F1 guard exception on parse path |

The two largest failure categories are **`invalid_identifier` (41.7 %)** and **`schema_invalid` (17.4 %)**, together accounting for 59.1 % of failures. Both are identifier-resolution failures at different stages: schema_invalid is rejection by our closed-set validator (the column does not appear in our pack); invalid_identifier is rejection by Snowflake (the column appears in our pack under a name the live catalog does not recognise). These are addressable by different interventions.

## 2. Two clusters identified via per-DB analysis

The per-DB breakdown ([../07_METRICS_AND_RESULTS/05_per_db_breakdown_snow.md](../07_METRICS_AND_RESULTS/05_per_db_breakdown_snow.md) §5) reveals that the residual failures *cluster* into named groups, each with a distinct underlying mechanism. The two diagnostically rich clusters are:

### 2.1 Cluster F3a — Nested STRUCT / RECORD types (misc_other 11.1 %)

**Named DB targets**: GA360 (12 tasks, 0 EXPLAIN-pass), FIREBASE (9 tasks, 1 EXPLAIN-pass), GEO_OPENSTREETMAP (6 tasks, 0 EXPLAIN-pass), and a long tail of Google product-analytics schemas in misc_other.

**Mechanism**. These databases use Snowflake's `OBJECT` / `VARIANT` / `ARRAY` types to represent nested JSON-like structures. The natural query pattern requires dotted-path field access: e.g., `event_params.value.string_value` in Firebase. Snowflake's syntax for this is `column:field:subfield` or `GET_PATH(column, 'field.subfield')`, not the standard SQL `column.field.subfield`. The v18 planner-emitter emits the standard syntax, which Snowflake rejects.

The schema_valid rate within this cluster is mixed (some tasks pass schema_valid because the *top-level* column exists; the dotted-path failure occurs at EXPLAIN time). The dominant failure class within this cluster is split between `invalid_identifier` (when Snowflake cannot find the nested field) and `ProgrammingError` (when it finds something but with wrong type).

**Phase 29 F3a target design.**

1. Detect VARIANT / OBJECT / ARRAY columns at schema-pack build time; mark them as nested.
2. For nested columns, populate the pack with the available top-level fields (sampled from `INFORMATION_SCHEMA.COLUMNS` or via a probe of `SELECT GET_PATH(...)`).
3. Augment the emitter prompt with an explicit Snowflake `:field:subfield` syntax instruction when the question references a nested column.
4. Add an AST post-processor that rewrites `column.field.subfield` patterns to `column:field:subfield` when the schema pack indicates a nested column.

**Projected impact.** If correctly implemented, the misc_other cluster's 11.1 % EXPLAIN-pass rate should lift to 25–35 % (recovering the GA360 and FIREBASE tasks that currently fail only on dotted-path syntax). The lift to the global FULL number is approximately +1.5 to +2.0 pp (a few percentage points; nested-STRUCT tasks are concentrated in a small cluster).

### 2.2 Cluster F3b — Biomedical cryptic codes (biomedical cluster 16.3 %)

**Named DB targets**: TCGA (3 tasks, 0 EXPLAIN-pass), PANCANCER_ATLAS_1 (6 tasks, 0 EXPLAIN-pass), SDOH (7 tasks, 0 EXPLAIN-pass), TCGA_MITELMAN (5 tasks, 0 EXPLAIN-pass), and the cluster overall (22 DBs, 49 tasks, 8 EXPLAIN-pass, 16.3 % rate).

**Mechanism.** These databases use clinical-trial / biomedical column naming conventions that are *long, cryptic, and abbreviated*: `submitted_diagnosis_age_at_diagnosis`, `genetic_ancestry_subpopulation_code`, `treatment_protocol_modification_reason_code`. Natural-language questions reference these concepts in plain English ("patient age at biopsy", "ancestry subgroup", "why was treatment modified"). The BM25 retriever cannot bridge the lexical gap: question tokens do not overlap with column tokens.

The schema_valid rate within this cluster is reasonable (35/49 = 71 %, equal to the global rate) because the closed-set planner finds *some* columns matching question tokens, just not the *right* columns. The EXPLAIN failures are dominated by `invalid_identifier` on downstream columns the planner inferred from the wrong starting point.

**Phase 29 F3b target design.**

1. Curate a biomedical domain glossary mapping natural-language phrases to TCGA / PANCANCER / SDOH column names (e.g. "patient age at biopsy" → `submitted_diagnosis_age_at_diagnosis`). Initial scope: top 200 most common biomedical schema column-name patterns.
2. At schema-pack build time, augment the BM25 index with synonym entries from the glossary.
3. For biomedical-cluster tasks, additionally peek a small sample of column values into the pack for value-based disambiguation (e.g. `ancestry_subpopulation_code` has values like 'EUR_WGB', 'AFR_YRI' — the value pattern helps the planner choose this column).

**Projected impact.** If correctly implemented, the biomedical cluster's 16.3 % EXPLAIN-pass rate should lift to 25–30 %, recovering the TCGA / PANCANCER / SDOH tasks where the only failure mode is column-name lexical gap. The lift to the global FULL number is approximately +1.0 to +1.5 pp.

### 2.3 Cluster F3c — Generic `invalid_identifier` long tail

**Mechanism.** Beyond the F3a and F3b clusters, the 60 `invalid_identifier` failures include a long tail of cases where the planner emits a column name that is *close to* but not exactly the catalog name (e.g. `customerId` vs `customer_id`, `total_amt` vs `total_amount`). The closed-set pack contains the correct name, but the emitter generates a plausible variant. These are recoverable with a one-shot retry that surfaces the actual catalog name to the planner.

**Phase 29 F3c target design** (this was the original Phase 29 plan before the cluster analysis added F3a / F3b).

1. When Snowflake's EXPLAIN returns `invalid_identifier`, extract the offending identifier from the error message.
2. Fuzzy-match against the live catalog column inventory for the task's database.
3. If a high-confidence match is found, re-prompt the planner with the suggestion as a natural-language hint.
4. Run a one-shot retry with the corrected hint.

**Projected impact.** If correctly implemented, F3c should recover 15–25 % of the 60 `invalid_identifier` failures (≈ 9–15 tasks). Lift to the global FULL number: +1.6 to +2.7 pp.

### 2.4 F3 cumulative projection

If F3a + F3b + F3c are all implemented as described, the projected cumulative lift on Spider2-Snow FULL EXPLAIN-pass is approximately:

* F3a: +1.5 to +2.0 pp (nested-STRUCT cluster)
* F3b: +1.0 to +1.5 pp (biomedical cluster)
* F3c: +1.6 to +2.7 pp (generic invalid_identifier long tail)
* Combined (with some overlap between F3c and F3b): **+4 to +6 pp**, lifting Snow FULL from 23.76 % to **27.5 % – 30 %**.

The combined projection is more conservative than the earlier 35–40 % target stated in [03_spider2_snow_analysis.md](03_spider2_snow_analysis.md) §8 because the cluster analysis revealed that F3c alone (the original Phase 29 plan) cannot address the nested-STRUCT and biomedical clusters — these need F3a / F3b specifically. The 35–40 % target assumed F3c would carry more of the lift than the cluster analysis now suggests.

The combined projection at 27.5–30 % EXPLAIN-pass corresponds to a row-match projection (at the pilot10 conversion ratio of 50 %) of approximately **14–18 %** at FULL — competitive with Spider-Agent + Qwen3-Coder's published 31.08 % row-match if the conversion ratio holds and F3 delivers its projected gains.

## 3. Spider2-Lite-BQ failure taxonomy

The Lite-BQ failure-class distribution is documented in [02_spider2_lite_bq_analysis.md](02_spider2_lite_bq_analysis.md) §3 and is reproduced here as design input for the Phase 30 plan:

| failure class | share (Phase 22 pilot 50 audit) | targeted by |
|---|---|---|
| `unrecog_name_join_missing` | ≈ 36 % | Phase 30 F2 (JOIN-graph expansion) |
| `AND_int_date` | ≈ 21 % | Phase 30 F4 BQ post-processor (date-type rewrite) |
| `types_mismatch` | ≈ 21 % | Phase 30 F4 BQ post-processor (cast insertion) |
| `nested_agg` | ≈ 14 % | not currently planned; requires planner-level decomposition |
| `ARRAY_CONTAINS` | ≈ 7 % | Phase 30 F4 BQ post-processor (idiom rewrite) |
| `parse_error` | < 1 % | covered by v24 stack |

**Phase 30 F2 design**: surface join candidates from the live catalog's PK/FK relationships into the schema pack, enabling Family B (two-table join) candidates to have correct join predicates. Projected impact: +6 to +10 pp dry_run-pass on Lite-BQ, lifting 34.6 % to 40–44 %.

**Phase 30 F4 BQ post-processor design**: AST-aware rewrites for `AND_int_date`, `types_mismatch`, and `ARRAY_CONTAINS` (analogous to F4 on Snow). Projected impact: +3 to +5 pp dry_run-pass, lifting the post-F2 figure to 43–49 %.

## 4. Spider2-DBT failure taxonomy

The DBT failure-class distribution is documented in detail at [04_spider2_dbt_analysis.md](04_spider2_dbt_analysis.md). The summary:

| failure band | tasks (of 68) | targeted by |
|---|---|---|
| dbt_run_failed (macro/Jinja) | 30 (44.1 %) | Phase 31 F6a (dbt-parse pre-check + retry) |
| dbt_run_failed (multi-model dep) | 7 (10.3 %) | Phase 31 F6b (manifest-aware planning) |
| ran_ok_but_score_zero | 17 (25.0 %) | Phase 31 F6c (rubric-feedback retry) |
| dbt_test_failed | 5 (7.4 %) | Phase 31 F6c (test-feedback retry) |
| success | 9 (13.2 %) | (current baseline) |

**Phase 31 cumulative projection** (from [04_spider2_dbt_analysis.md](04_spider2_dbt_analysis.md) §7): F6a + F6b + F6c lift Spider2-DBT from 13.2 % to **30–35 %**, with the bound coming from the 10 % of tasks that are deeper logic errors not addressable by feedback retry.

## 5. Spider2-Lite-Snow failure modes

Partial result (n=40 of 207). The qualitative behaviour is expected to mirror Spider2-Snow (same scaffold, same dialect, smaller scope). The pilot 10 v28-revert-A on Lite-Snow had 4/10 EXPLAIN-pass with the same F1+F4+F4c stack. The failure modes are expected to be the same `invalid_identifier` + `schema_invalid` + `ProgrammingError` mix; the per-DB cluster diagnostic should also be similar (the Lite-Snow split is a curated subset of Snow databases). Phase 28b will close Lite-Snow FULL alongside the row-match audit.

## 6. Forward-looking failure-mode analysis

After Phase 28b + 29 + 30 + 31, the residual failure modes on each lane are projected to be:

* **Spider 1 / BIRD**: gold-ambiguity and multi-aggregate-window residuals (saturated cluster, not addressable architecturally).
* **Spider2-Snow (post Phase 29)**: deeper logical-correctness failures that pass EXPLAIN but fail row-match — invisible to our pipeline today, will become visible after Phase 28b. The Phase 29 F3 stack does not address these; a multi-shot synthesis with execution feedback (a hypothetical Phase 32) would.
* **Spider2-Lite-BQ (post Phase 30)**: residual `nested_agg` cluster (14 %) plus row-match-only failures (post-Phase-28b audit).
* **Spider2-DBT (post Phase 31)**: deeper logical errors in `ran_ok_but_score_zero` band, plus content-correctness failures that even rubric-feedback retry cannot recover.

These post-roadmap residual failures are the natural research targets for a hypothetical Phase 32+ (multi-shot synthesis, deeper execution feedback). They are not on the current dossier's scope and are recorded here only for completeness.

## 7. Summary table — failure clusters → interventions → projections

| Lane | Failure cluster | Intervention | Phase | Projected lift |
|---|---|---|---|---|
| Snow | nested-STRUCT (misc 11.1 %) | F3a STRUCT-aware emitter | 29 | +1.5–2.0 pp global |
| Snow | biomedical (16.3 %) | F3b domain glossary | 29 | +1.0–1.5 pp global |
| Snow | generic invalid_identifier | F3c self-refine retry | 29 | +1.6–2.7 pp global |
| Snow | (row-match audit) | spider2.eval ingestion | 28b | converts to row-match |
| Lite-BQ | unrecog_name_join_missing (36 %) | F2 JOIN-graph expansion | 30 | +6–10 pp |
| Lite-BQ | AND_int_date / types_mismatch / ARRAY_CONTAINS | F4 BQ post-processor | 30 | +3–5 pp |
| DBT | macro/Jinja (44 %) | F6a dbt-parse pre-check | 31 | +9–15 pp |
| DBT | multi-model dep (10 %) | F6b manifest-aware planner | 31 | +5–7 pp |
| DBT | ran_ok / dbt_test_failed (32 %) | F6c rubric/test feedback retry | 31 | +5–10 pp |

This table is the design input for the post-defence engineering roadmap, also summarised in [../06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md](../06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md) §3.
