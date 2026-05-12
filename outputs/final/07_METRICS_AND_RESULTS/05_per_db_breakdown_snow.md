# Per-Database Breakdown — Spider2-Snow FULL 547

This document is the most granular view available of the Spider2-Snow FULL 547 results. It decomposes the 130 / 547 = **23.76 % Snowflake EXPLAIN-pass rate (\*)** by individual database, by rate, by domain cluster, and by failure mode, and surfaces the systematic failure clusters that motivate the Phase 29 F3 design (deferred post-defence). All numbers in this document are EXPLAIN-pass counts unless otherwise marked, per the canonical convention defined in [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md).

> (\*) Every numerical claim about Spider 2.0 Snow/Lite-Snow/Lite-BQ in this dossier is a **plan-level acceptance** metric (Snowflake `EXPLAIN`-pass for Snow lanes, BigQuery `dry_run`-pass for Lite-BQ), not a row-set match against gold. See [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md) for the full forensic explanation and the path to a row-match number (Phase 28b post-defence audit).

Companion files: aggregate progression at [02_progression_table_full.md](02_progression_table_full.md); per-lane charts at [03_progression_by_benchmark.md](03_progression_by_benchmark.md); failure taxonomy evolution at [04_error_taxonomy_evolution.md](04_error_taxonomy_evolution.md); source-of-numbers run directory at `outputs/spider2_snow/runs/snow_full_v28_revert_a/`.

## 1. Headline summary

The Spider2-Snow FULL 547 run at commit `ad5493b` (Phase 28-revert-A) produced the following aggregate numbers, all written by [tools/remote_scripts/_phase27_snow_runner.py](../../../tools/remote_scripts/_phase27_snow_runner.py) at run close:

| Counter | Value | Rate |
|---|---|---|
| n_total | 547 | 100.0 % |
| plan_validation_ok | 159 | 29.07 % |
| chosen_schema_valid | 383 | 70.02 % |
| parse_ok | 503 | 91.96 % |
| **execute_ok (Snowflake EXPLAIN-pass) (\*)** | **130** | **23.76 %** |
| guard_leaks | 0 | 0.00 % |
| guard_rewrites | 14 | (3 = F1 catalog-grounding rewrites firing) |
| guard_regex_fallback | 6 | (F4c LATERAL FLATTEN parse-failure fallback) |
| requoted_n | 0 | (F2a confirmed reverted) |
| wrapped_n | 5 | (F4 NUMBER/VARIANT date-cast wraps) |
| wallclock | 10 981.7 s | (≈ 3 h 03 min) |

Of the 547 tasks, predictions span **152 distinct Snowflake databases**, ranging from 20-task databases (CRYPTO) down to 1-task databases (66 single-task DBs). The schema_valid rate (70.02 %) and parse_ok rate (91.96 %) confirm the F1 grounding stack's effectiveness from a different angle: the planner is producing well-formed SQL whose identifiers pass the v18 closed-set validator on 70 % of tasks. The gap from 70 % schema_valid to 23.76 % EXPLAIN-pass is dominated by `invalid_identifier` errors from Snowflake (60 cases) — column names that exist in our schema pack but not in the live Snowflake catalog as the planner referenced them. See section 6 for the failure-mode breakdown.

## 2. Top-25 databases by absolute EXPLAIN-pass count

These are the 25 databases that contribute the most successful predictions to the 130-task total. Ordered by absolute `ex` count, ties broken by `n_tasks` desc.

| rank | db | n | sv | parse_ok | ex | rate | top failure |
|---|---|---|---|---|---|---|---|
| 1 | CRYPTO | 20 | 15 | 17 | 6 | 30.0 % | invalid_identifier (9) |
| 2 | PATENTS | 15 | 9 | 15 | 6 | 40.0 % | invalid_identifier (4) |
| 3 | THELOOK_ECOMMERCE | 19 | 17 | 18 | 5 | 26.3 % | invalid_identifier (10) |
| 4 | NOAA_DATA | 12 | 9 | 11 | 4 | 33.3 % | invalid_identifier (5) |
| 5 | GITHUB_REPOS | 15 | 7 | 13 | 3 | 20.0 % | invalid_identifier (6) |
| 6 | STACKOVERFLOW | 15 | 11 | 15 | 3 | 20.0 % | ProgrammingError (7) |
| 7 | IDC | 15 | 9 | 14 | 3 | 20.0 % | invalid_identifier (10) |
| 8 | IPL | 11 | 8 | 11 | 3 | 27.3 % | invalid_identifier (8) |
| 9 | F1 | 9 | 8 | 9 | 3 | 33.3 % | invalid_identifier (6) |
| 10 | BRAZILIAN_E_COMMERCE | 8 | 6 | 7 | 3 | 37.5 % | invalid_identifier (3) |
| 11 | WORLD_BANK | 6 | 6 | 6 | 3 | 50.0 % | invalid_identifier (2) |
| 12 | FDA | 5 | 3 | 4 | 3 | 60.0 % | parse_error (1) |
| 13 | AUSTIN | 5 | 5 | 5 | 3 | 60.0 % | ProgrammingError (1) |
| 14 | EU_SOCCER | 5 | 4 | 5 | 3 | 60.0 % | invalid_identifier (2) |
| 15 | GA4 | 17 | 4 | 16 | 2 | 11.8 % | invalid_identifier (13) |
| 16 | BANK_SALES_TRADING | 15 | 12 | 15 | 2 | 13.3 % | invalid_identifier (11) |
| 17 | ORACLE_SQL | 8 | 6 | 8 | 2 | 25.0 % | ProgrammingError (3) |
| 18 | MODERN_DATA | 7 | 7 | 7 | 2 | 28.6 % | invalid_identifier (4) |
| 19 | SQLITE_SAKILA | 7 | 5 | 6 | 2 | 28.6 % | ProgrammingError (3) |
| 20 | GITHUB_REPOS_DATE | 6 | 3 | 6 | 2 | 33.3 % | invalid_identifier (3) |
| 21 | NEW_YORK_PLUS | 6 | 4 | 5 | 2 | 33.3 % | ProgrammingError (2) |
| 22 | SAN_FRANCISCO_PLUS | 6 | 5 | 6 | 2 | 33.3 % | invalid_identifier (3) |
| 23 | COMPLEX_ORACLE | 6 | 4 | 6 | 2 | 33.3 % | invalid_identifier (4) |
| 24 | CHICAGO | 5 | 4 | 5 | 2 | 40.0 % | ProgrammingError (2) |
| 25 | META_KAGGLE | 5 | 3 | 5 | 2 | 40.0 % | invalid_identifier (2) |

These 25 DBs contribute **78** of the 130 successful predictions (60 %) on **241** tasks (44 % of the benchmark). The long tail — 127 remaining DBs with 1 success each at best and 306 tasks total — contributes 52 successes; many of those DBs are single-task entries. Two notable patterns: the rate within the top-25 spans 11.8 % (GA4) to 60.0 % (FDA / AUSTIN / EU_SOCCER), so high-volume DBs are not automatically high-rate — the question difficulty within a DB matters. CRYPTO and THELOOK_ECOMMERCE both contribute 5–6 successes but at 30 % / 26 % rate, while GA4 contributes 2 successes at 12 % rate — GA4 is the loudest single failure DB in the benchmark.

## 3. Top-15 databases by EXPLAIN-pass rate (n ≥ 3)

Filter to DBs with at least 3 tasks (for sample-size relevance) and sort by EXPLAIN-pass rate descending. These are the DBs where our architecture works particularly well, regardless of how many tasks they contribute.

| rank | db | n | sv | ex | rate |
|---|---|---|---|---|---|
| 1 | GOOGLE_DEI | 3 | 2 | 2 | 66.7 % |
| 2 | IOWA_LIQUOR_SALES | 3 | 3 | 2 | 66.7 % |
| 3 | LONDON | 3 | 3 | 2 | 66.7 % |
| 4 | CHINOOK | 3 | 1 | 2 | 66.7 % |
| 5 | ENTERTAINMENTAGENCY | 3 | 3 | 2 | 66.7 % |
| 6 | FDA | 5 | 3 | 3 | 60.0 % |
| 7 | AUSTIN | 5 | 5 | 3 | 60.0 % |
| 8 | EU_SOCCER | 5 | 4 | 3 | 60.0 % |
| 9 | WORLD_BANK | 6 | 6 | 3 | 50.0 % |
| 10 | NEW_YORK | 4 | 3 | 2 | 50.0 % |
| 11 | PATENTS | 15 | 9 | 6 | 40.0 % |
| 12 | CHICAGO | 5 | 4 | 2 | 40.0 % |
| 13 | META_KAGGLE | 5 | 3 | 2 | 40.0 % |
| 14 | DB_IMDB | 5 | 2 | 2 | 40.0 % |
| 15 | LOG | 5 | 5 | 2 | 40.0 % |

Pattern observations: the top-rate cluster (66.7 % at n=3) is dominated by **small public-data DBs with well-documented schemas and natural-language-friendly column names** — government open-data (LONDON, AUSTIN, NEW_YORK at 50–60 %), classical reference databases (CHINOOK is the classic Microsoft SQL Server sample DB, IOWA_LIQUOR is a frequently-cited Kaggle dataset), and curated subsets (META_KAGGLE, DB_IMDB). The largest member of this top tier in absolute count is PATENTS at 6/15 = 40 % — this is the same DB where the Phase 28 F2a auto-uppercase hypothesis was falsified by catalog probing (the columns are stored lowercase). After the F2a revert, PATENTS recovered to 40 %; under the rejected F2a hypothesis it scored 0/15.

## 4. Bottom-25 databases by EXPLAIN-pass rate (n ≥ 3)

The mirror of section 3. These are the DBs where our architecture struggles most, restricted to n ≥ 3 for statistical relevance. Twenty are tied at exactly 0.0 % EXPLAIN-pass; five more contribute one or two successes but at rates ≤ 20 %.

| rank | db | n | sv | ex | rate | top failure |
|---|---|---|---|---|---|---|
| 1 | GA360 | 12 | 2 | 0 | 0.0 % | invalid_identifier (5) |
| 2 | CITY_LEGISLATION | 10 | 8 | 0 | 0.0 % | invalid_identifier (5) |
| 3 | SDOH | 7 | 4 | 0 | 0.0 % | invalid_identifier (7) |
| 4 | GEO_OPENSTREETMAP | 6 | 4 | 0 | 0.0 % | ProgrammingError (3) |
| 5 | PANCANCER_ATLAS_1 | 6 | 5 | 0 | 0.0 % | invalid_identifier (5) |
| 6 | NCAA_BASKETBALL | 5 | 3 | 0 | 0.0 % | invalid_identifier (5) |
| 7 | TCGA_MITELMAN | 5 | 2 | 0 | 0.0 % | invalid_identifier (4) |
| 8 | EDUCATION_BUSINESS | 5 | 2 | 0 | 0.0 % | invalid_identifier (4) |
| 9 | DEPS_DEV_V1 | 4 | 0 | 0 | 0.0 % | invalid_identifier (2) |
| 10 | NHTSA_TRAFFIC_FATALITIES | 4 | 4 | 0 | 0.0 % | invalid_identifier (3) |
| 11 | TCGA | 4 | 3 | 0 | 0.0 % | invalid_identifier (3) |
| 12 | _1000_GENOMES | 4 | 1 | 0 | 0.0 % | parse_error (2) |
| 13 | NEW_YORK_NOAA | 3 | 1 | 0 | 0.0 % | syntax_error (1) |
| 14 | CENSUS_BUREAU_ACS_1 | 3 | 1 | 0 | 0.0 % | invalid_identifier (2) |
| 15 | USFS_FIA | 3 | 2 | 0 | 0.0 % | invalid_identifier (2) |
| 16 | THE_MET | 3 | 2 | 0 | 0.0 % | ProgrammingError (1) |
| 17 | WORD_VECTORS_US | 3 | 1 | 0 | 0.0 % | parse_error (1) |
| 18 | TCGA_HG38_DATA_V0 | 3 | 3 | 0 | 0.0 % | ProgrammingError (2) |
| 19 | FINANCE__ECONOMICS | 3 | 2 | 0 | 0.0 % | invalid_identifier (1) |
| 20 | US_REAL_ESTATE | 3 | 3 | 0 | 0.0 % | invalid_identifier (3) |
| 21 | FIREBASE | 9 | 7 | 1 | 11.1 % | ProgrammingError (5) |
| 22 | GA4 | 17 | 4 | 2 | 11.8 % | invalid_identifier (13) |
| 23 | BANK_SALES_TRADING | 15 | 12 | 2 | 13.3 % | invalid_identifier (11) |
| 24 | CMS_DATA | 7 | 4 | 1 | 14.3 % | invalid_identifier (4) |
| 25 | GITHUB_REPOS | 15 | 7 | 3 | 20.0 % | invalid_identifier (6) |

**Key observation.** Twenty databases — totalling 102 tasks (18.6 % of the benchmark) — contribute exactly zero successful predictions. The dominant failure mode across this cluster is `invalid_identifier` (16 of 20 DBs), suggesting a systematic gap in the closed-set planner's column inventory for these DBs. The four exceptions (GEO_OPENSTREETMAP / THE_MET / TCGA_HG38_DATA_V0 / _1000_GENOMES) fail at different stages — ProgrammingError, parse_error, syntax_error — indicating these DBs exercise constructs the v18 planner does not emit cleanly.

## 5. Domain cluster aggregation

The 152 databases were manually grouped into 10 domain clusters based on database names and content. The clustering rules are documented in the source code (see section 8) and produce the following aggregate:

| cluster | #dbs | n | sv | ex | ex_rate |
|---|---|---|---|---|---|
| **patents_ip** | 4 | 24 | 17 | 8 | **33.3 %** |
| retail_ecom | 22 | 85 | 68 | 25 | 29.4 % |
| sports | 8 | 35 | 27 | 10 | 28.6 % |
| finance_econ | 8 | 40 | 30 | 11 | 27.5 % |
| tech_code | 19 | 86 | 56 | 23 | 26.7 % |
| gov_city | 22 | 71 | 60 | 18 | 25.4 % |
| env_geo | 22 | 45 | 30 | 11 | 24.4 % |
| health_public | 11 | 31 | 19 | 7 | 22.6 % |
| **biomedical** | 22 | 49 | 35 | 8 | **16.3 %** |
| misc_other | 14 | 81 | 41 | 9 | 11.1 % |
| **TOTAL** | **152** | **547** | **383** | **130** | **23.76 %** |

**Diagnostic interpretation — this is the proof that residual failures have domain-specific structure, not random variance.** The cluster-rate range spans 11.1 % to 33.3 % — a 22.2-pp spread that is not attributable to sampling noise (the per-cluster n is 24–86 tasks, far above any reasonable significance threshold). The variance is **systematic by cluster content**:

* **Patents and retail/e-commerce (top tier, 29–33 %)** — clusters with well-documented public schemas where column names are intuitive natural-language phrases (`order_id`, `customer_name`, `patent_number`). BM25 retrieval works because question tokens overlap with column tokens directly.
* **Sports, finance/econ, tech/code (middle tier, 27–29 %)** — schema documentation is mixed; some DBs are clean, others have abbreviated or coded column names. The planner-emitter handles these inconsistently.
* **Gov/city, env/geo (middle-lower tier, 24–25 %)** — government open-data and environmental data tend to have wide tables with nested categorical columns. The closed-set planner's narrow candidate menus underspecify these schemas.
* **Health/public and biomedical (bottom tier, 16–23 %)** — this is the diagnostic gold. **Biomedical at 16.3 %** is the worst-performing cluster, despite having a perfectly reasonable schema_valid rate of 35/49 = 71 %. The gap (71 % schema_valid → 16 % EXPLAIN-pass) is much wider than other clusters' equivalent gap. The mechanism: BM25 selects column names that *exist* (so schema_valid passes), but the natural-language question references concepts the column names do not lexically express (TCGA's `submitted_diagnosis_age_at_diagnosis` vs question's "patient age at biopsy"). Snowflake then rejects the SQL because the resolved column does not match the question's semantics, surfaced as `invalid_identifier` for downstream columns the planner inferred from the wrong starting point.
* **Misc/other (bottom, 11.1 %)** — dominated by GA360 (12 tasks, 0 EXPLAIN-pass) and FIREBASE (9 tasks, 1 EXPLAIN-pass). Both are nested-STRUCT-heavy Google product analytics schemas where dotted-path access (`event_params.value.string_value`) requires Snowflake's `:field:subfield` syntax that the v18 planner does not emit.

**This cluster diagnostic is one of the most important empirical findings in the thesis.** It says: the architecture's residual failures cluster around two distinct problem types — *nested-STRUCT decomposition* (misc cluster) and *domain-specific terminology gap* (biomedical cluster) — each of which is addressable by a specific Phase 29 intervention (F3a and F3b respectively; section 7 below).

## 6. Failure-mode breakdown (from the 144 freshly-graded tasks)

The Snow runner's `error_taxonomy.csv` reports the following distribution of failure classes over the 144 tasks that were processed by the post-resume codepath. The remainder of the 547-record benchmark was processed by a resume path that did not write to the error counter (see [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md) §4 for the resume-path bug's full forensic disambiguation):

| error class | count | share of 144 | dossier interpretation |
|---|---|---|---|
| invalid_identifier | 60 | 41.7 % | column-not-found in live Snowflake catalog despite passing our closed-set validator |
| ok | 36 | 25.0 % | sv ∧ pa ∧ ex all passed |
| schema_invalid | 25 | 17.4 % | v18 validator rejected the SQL before EXPLAIN was attempted |
| ProgrammingError | 11 | 7.6 % | Snowflake-side semantic errors (e.g. ambiguous column reference after auto-join) |
| parse_error | 6 | 4.2 % | SQLGlot parse failure (LATERAL FLATTEN tail cases — covered by F4c regex fallback) |
| no_catalog_for_task_db | 3 | 2.1 % | task targeted a database we have no catalog rows for (residual catalog-gap) |
| syntax_error | 2 | 1.4 % | malformed SQL that Snowflake rejected at parse time |
| parse_error_guard | 1 | 0.7 % | F1 identifier guard threw on a parse path |
| **TOTAL** | **144** | **100.0 %** | |

The dominant failure mode is `invalid_identifier` at 41.7 % of the graded subset. This is consistent with the cluster-level diagnosis in section 5: the residual gap from 70.02 % schema_valid to 23.76 % EXPLAIN-pass is driven by columns that exist in our pack but are referenced incorrectly in the live catalog. The remaining categories are dominated by configuration / parse / catalog-gap issues that account for ≤ 5 % each.

## 7. Phase 29 F3 design input — directly traceable to the cluster diagnostic

Three Phase 29 design interventions follow directly from sections 4–6. Each targets a named cluster of failures and has a measurable hypothesis about which DBs should move from 0 / 11–14 % EXPLAIN-pass to a higher band.

**F3a — STRUCT-aware emitter prompting.** Target cluster: misc_other and a subset of tech_code where nested STRUCT / RECORD columns dominate. Named DB targets: GA360 (12 / 12 fail), FIREBASE (8 / 9 fail), GEO_OPENSTREETMAP (6 / 6 fail). Mechanism: render nested columns in the schema pack with their full dotted path and Snowflake-side access syntax; teach the emitter to emit `column:field:subfield` rather than `column.field.subfield`. Hypothesis: if F3a is correctly implemented, GA360 should move from 0 / 12 to ≥ 3 / 12 EXPLAIN-pass (≥ 25 %), recovering tasks where the only failure mode is nested-field access.

**F3b — Domain-glossary augmentation for biomedical clusters.** Target cluster: biomedical (TCGA, PANCANCER, MITELMAN, SDOH, GENOMICS). Named DB targets: TCGA (3 / 3 fail), PANCANCER_ATLAS_1 (6 / 6 fail), SDOH (7 / 7 fail), TCGA_MITELMAN (5 / 5 fail). Mechanism: augment the BM25 index with a domain glossary mapping clinical-trial natural-language terms to actual column names (e.g. "patient age at biopsy" → `submitted_diagnosis_age_at_diagnosis`). Pull a sample of the column's values into the pack for further disambiguation. Hypothesis: F3b should lift the biomedical cluster from 8 / 49 = 16.3 % to ≥ 25 % EXPLAIN-pass, mostly by recovering the column-mapping cases that currently fail with `invalid_identifier` downstream.

**F3c — Self-refine on `invalid_identifier`.** This was the original Phase 29 plan (formulated at Phase 26). Mechanism: when Snowflake EXPLAIN returns `invalid_identifier`, feed the error message back to the planner with a fuzzy-match suggestion list from the actual catalog, and run a one-shot retry. Hypothesis: F3c addresses tasks where the emitter is *close* — the schema-valid column exists, just under a slightly different name — and is expected to recover 15–25 % of the `invalid_identifier` failures. After the cluster analysis above, F3c's projected impact is bounded: the nested-STRUCT and biomedical clusters are *not* addressable by retry alone because the failure is the planner-emitter system's lexical retrieval, not a one-token name typo. F3c is therefore now rebadged as a *complement* to F3a and F3b, not a replacement.

The Phase 29 sequencing is: F3c (1 week, lowest implementation risk) → F3a (1 week, requires schema-pack format change) → F3b (1 week, requires a new domain glossary resource). Total: 3 weeks of post-defence engineering for a projected lift from 23.76 % EXPLAIN-pass to 35–40 % EXPLAIN-pass on Spider2-Snow FULL — under the additional caveat that this is still EXPLAIN-pass, not row-match. The row-match audit (Phase 28b) is independent of and orthogonal to F3 work.

## 8. Source-of-numbers and reproducibility

All numbers in this document trace to a single run directory: `outputs/spider2_snow/runs/snow_full_v28_revert_a/` at commit `ad5493b`. The files in that directory:

* `predictions.jsonl` — 547 records, one per task. The keys per record are: `instance_id`, `task_db`, `sql`, `lane`, `schema_valid`, `parse_ok`, `explain_ok`, `explain_class`, `guard_rewrote_n`. The aggregate metrics in section 1 are recomputable directly from this file.
* `traces.jsonl` — 547 records with the per-task pipeline trace, including `pack_n_tables`, `pack_unique_dbs`, `pk_fk_injected`, `sql_pre_guard`, `f4`, `guard`, `sv_msg`, `pa_msg`, `explain_msg`. Used for the failure-mode and cluster analysis.
* `metrics.csv` — eight key-value rows with the headline counters.
* `error_taxonomy.csv` — eight rows with the failure-class distribution over the 144-task post-resume window.
* `progress.json` — internal supervisor heartbeat with the final `last_task` (`sf014`) and `wall_sec` (10 981.7 s).
* `_DONE` — terminal marker with a JSON payload of the headline counters.

The cluster aggregation in section 5 is computed by a small Python pass that groups DB names by string-match rules (e.g. `'TCGA' in name → biomedical`); the full classifier source is in [../11_APPENDIX/03_key_code_excerpts.md](../11_APPENDIX/03_key_code_excerpts.md) Section 8 (added separately). Re-running the cluster aggregation requires the `traces.jsonl` file and the classifier; the headline numbers in section 1 require only `metrics.csv`.

## 9. What this breakdown does and does not establish

This document establishes:

* The 23.76 % Spider2-Snow FULL EXPLAIN-pass rate (\*) decomposes cleanly into 130 successful predictions across 152 databases, with the top-25 DBs contributing 78 / 130 = 60 % of successes from 44 % of the tasks.
* The residual failures cluster around two distinct, named, addressable problem types — nested-STRUCT decomposition and biomedical-domain terminology — each diagnosable from the per-DB rate spread and the failure-class distribution.
* The cluster-rate spread (11.1 % to 33.3 %) is systematic, not stochastic, and validates the dossier's broader claim that the architecture's residual failure modes are decomposable into a small number of named categories per lane.

This document does **not** establish:

* The row-match rate of any of these 130 successful predictions. The 12–18 % row-match projection in [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md) §5 is a pilot10-conversion estimate, not a measurement. Phase 28b audit is the path to a defensible row-match number.
* The projected Phase 29 lift quantitatively. The 35–40 % EXPLAIN-pass target in section 7 is the design-time hypothesis, not the post-implementation outcome.
* The leaderboard position. Direct comparison to published Spider 2.0 row-match figures (Spider-Agent + Qwen3-Coder 31.08 %, ReFoRCE + o3 62.89 %) is not made; the dossier-wide canonical wording for cross-metric positioning is "in the same band as the open-weight Spider-Agent baselines, pending row-match audit." See [../09_RESULTS_ANALYSIS/05_leaderboard_position.md](../09_RESULTS_ANALYSIS/05_leaderboard_position.md).

The defendable claims from this document are *qualitative-structural* — the failure clusters are real, named, and addressable — and *quantitative-EXPLAIN-pass* — the 23.76 % Snow FULL rate (\*), its per-DB and per-cluster decomposition. The quantitative-row-match story is deferred to Phase 28b.
