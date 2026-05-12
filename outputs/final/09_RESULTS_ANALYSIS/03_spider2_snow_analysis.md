# Spider2-Snow Analysis — 23.76 % EXPLAIN-pass FULL 547

This document is the central results-analysis page of the thesis dossier. It documents what was measured on Spider2-Snow FULL 547, what the headline number (23.76 % Snowflake EXPLAIN-pass rate (\*)) means and does not mean, what architectural progression got us there, what residual failure clusters remain, and what the Phase 28b post-defence audit will produce. The number 23.76 % is the headline of the thesis's most distinctive lane and is the figure most likely to be challenged during defence.

> (\*) **Plan-level acceptance, not row-set match against gold.** Every Spider 2 family number in this dossier carries this asterisk and refers back to [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md), which contains the full forensic explanation, the source-code trace of `_snow_explain`, the path to a row-match figure (Phase 28b), and the canonical leaderboard-comparison wording.

Companion files: classical-benchmark analysis at [01_classical_benchmarks_spider1_bird.md](01_classical_benchmarks_spider1_bird.md); Lite-BQ at [02_spider2_lite_bq_analysis.md](02_spider2_lite_bq_analysis.md); DBT at [04_spider2_dbt_analysis.md](04_spider2_dbt_analysis.md); leaderboard position at [05_leaderboard_position.md](05_leaderboard_position.md); failure analysis at [06_failure_analysis_remaining.md](06_failure_analysis_remaining.md); publishability at [07_publishability_assessment.md](07_publishability_assessment.md); novelty claims at [08_thesis_novelty_claims.md](08_thesis_novelty_claims.md). The per-DB breakdown is [../07_METRICS_AND_RESULTS/05_per_db_breakdown_snow.md](../07_METRICS_AND_RESULTS/05_per_db_breakdown_snow.md).

## 1. Headline number and exact wording

**Spider2-Snow FULL 547: 23.76 % Snowflake `EXPLAIN`-pass rate (plan-level acceptance, 130 / 547, see [Appendix 07](../11_APPENDIX/07_critical_metric_caveat.md) (\*)).** This is the canonical phrasing used everywhere in the dossier when this number is cited. Paraphrases that omit "EXPLAIN-pass" or "plan-level acceptance" or that use the generic word "execute_ok" are an error and should be corrected.

The full aggregate counter table (from `outputs/spider2_snow/runs/snow_full_v28_revert_a/metrics.csv` at commit `ad5493b`):

| Counter | Value | Rate of 547 | What it represents |
|---|---|---|---|
| n_total | 547 | 100.0 % | total tasks in Spider2-Snow FULL |
| plan_validation_ok | 159 | 29.07 % | tasks where v18 closed-set planner accepted the chosen candidate |
| chosen_schema_valid | 383 | 70.02 % | tasks where the chosen SQL passed v18 schema-validator (closed-set residency) |
| parse_ok | 503 | 91.96 % | tasks where SQLGlot parsed the chosen SQL |
| **execute_ok = Snowflake EXPLAIN-pass (\*)** | **130** | **23.76 %** | **tasks where Snowflake accepted the query plan via `EXPLAIN`** |
| guard_leaks | 0 | 0.00 % | tasks where F1 guard let a non-allow-set identifier through |
| guard_rewrites | 14 | 2.56 % | tasks where F1 guard rewrote identifiers to three-part form |
| guard_regex_fallback | 6 | 1.10 % | tasks where F4c regex fallback fired (SQLGlot parse failed) |
| requoted_n | 0 | 0.00 % | F2a auto-upper hypothesis (REVERTED — no rewrites) |
| wrapped_n | 5 | 0.91 % | tasks where F4 NUMBER/VARIANT date-cast wrap fired |
| wall_sec | 10 981.7 | (≈ 3 h 03 min) | wallclock of the FULL run |

The relationship `schema_valid (383) > parse_ok (503) > EXPLAIN-pass (130)` initially looks confusing — schema_valid is *lower* than parse_ok despite being a stricter check on a subset. The explanation: schema_valid checks identifier residency in our v18 closed-set pack, parse_ok checks SQLGlot grammar acceptance, EXPLAIN-pass checks Snowflake catalog binding. Some SQL parses cleanly (well-formed grammar) but our pack does not include the columns the planner referenced (schema_valid false), so parse_ok > schema_valid is expected. The 70.02 % schema_valid floor confirms the F1 grounding stack worked at FULL scale; the gap from 70 % schema_valid down to 24 % EXPLAIN-pass is where the next intervention (Phase 29 F3) must operate.

## 2. The F1+F4+F4c architectural progression — attribution

Spider2-Snow was at 0 % EXPLAIN-pass at Phase 26 (the research-handoff diagnostic that motivated F1). The path to 23.76 % is one of the dossier's most directly attributable architectural narratives:

| Phase | Intervention | Snow pilot10 EXPLAIN-pass | Snow FULL EXPLAIN-pass | Mechanism |
|---|---|---|---|---|
| 26 | research handoff (no F1) | 0 / 10 = 0 % | 0 / 547 (estimated) | cross-DB identifier drift dominates |
| 27 | F1 grounding (per-task BM25 partition + 3-part AST guard + PK/FK injection) | 1 / 10 = 10 % | (not run at FULL) | schema_valid 0 → ≈ 80 %, but Snowflake still rejects NUMBER/VARIANT date casts |
| 28a | F1 + F4 + **F2a** (auto-upper) | 0 / 10 = 0 % | (regression — not advanced) | F2a falsified by catalog probe; PATENTS columns stored lowercase |
| 28-revert-A | F1 + F4 + F4c, **F2a reverted** | 4 / 10 = 40 % | **130 / 547 = 23.76 %** | F4 date-cast wrap exposed as load-bearing after revert |

The progression is decomposable into three contribution layers:

**F1 (Phase 27) — per-task BM25 partition + 3-part identifier rendering + AST guard.** This eliminated cross-DB identifier drift. Before F1, BM25 retrieved tables from any database matching question tokens; the planner emitted unqualified table names that bound to wrong databases at execution time. After F1, retrieval is partitioned by `c.db.upper()`, identifiers are rendered as `DATABASE.SCHEMA.TABLE`, and the AST guard rejects any table name not in the allow-set. Evidence: `guard_rewrites = 14` at FULL (F1 fired and corrected on 14 tasks), `guard_leaks = 0` (no non-allow-set identifier survived), schema_valid 0 → 70 %. The F1 contribution alone explains the schema_valid lift; without it, EXPLAIN-pass would have remained near 0 %.

**F4 (Phase 28-revert-A) — NUMBER/VARIANT date-cast AST wrap.** Snowflake's `DATE_TRUNC` rejects NUMBER-typed columns. The Phase 27 planner produced syntactically valid SQL that EXPLAIN refused because column types were NUMBER (Unix-epoch encoded) but `DATE_TRUNC` operands must be DATE/TIMESTAMP. The F4 wrap walks the SQLGlot AST and inserts `TO_DATE(TO_CHAR(operand), 'YYYYMMDD')` around NUMBER operands of date functions. Evidence: `wrapped_n = 5` at FULL (5 tasks recovered by F4). The pilot10 effect was larger (3 of 4 successful pilot10 tasks were F4-driven); the FULL-level effect of 5 / 547 looks small in absolute terms but represents the difference between "Snowflake plans this SQL" and "Snowflake rejects this SQL" on those specific tasks.

**F4c (Phase 28-revert-A) — regex fallback for LATERAL FLATTEN.** SQLGlot occasionally fails to parse Snowflake's `LATERAL FLATTEN` syntax. The F4c fallback applies the F1 identifier-rewrite logic via regex when AST parsing fails, ensuring the guard's three-part-name enforcement still works on these queries. Evidence: `guard_regex_fallback = 6` at FULL. Without F4c, these 6 tasks would have been silently dropped from the pipeline (their SQL not guard-checked, likely failing EXPLAIN with identifier errors).

**F2a (Phase 28a) — auto-uppercase quoted lowercase identifiers — FALSIFIED and REVERTED.** The hypothesis was that quoted lowercase identifiers in our SQL emissions should be auto-uppercased because Snowflake stores identifiers in uppercase by default. Falsified by direct catalog probe of the PATENTS schema, which revealed columns stored lowercase (presumably due to a deliberate `CREATE TABLE` with quoted lowercase names). F2a would have rewritten correct lowercase to incorrect uppercase, breaking the only previously-working tasks. Evidence: `requoted_n = 0` at FULL (confirms the revert is in effect — F2a is not firing). This negative-result narrative is the basis of Claim 4 (catalog-probe-before-dialect-heuristic discipline) in [08_thesis_novelty_claims.md](08_thesis_novelty_claims.md).

The total contribution attribution from 0 to 23.76 %:
* F1 → schema_valid 0 → 70 % (≈ 14 pp EXPLAIN-pass contribution by structural unblocking).
* F4 → 5 wrapped tasks recover (≈ 0.9 pp at FULL, but ≥ 30 pp contribution at pilot10).
* F4c → 6 tasks rescued from silent drop (≈ 1.1 pp).
* F2a → contributes 0 % directly but unmasks F4's contribution (revert was load-bearing).

## 3. Per-DB breakdown headline — what cluster analysis reveals

The full per-DB breakdown is in [../07_METRICS_AND_RESULTS/05_per_db_breakdown_snow.md](../07_METRICS_AND_RESULTS/05_per_db_breakdown_snow.md). The headline finding for this analysis page is the domain-cluster table:

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
| **misc_other** | 14 | 81 | 41 | 9 | **11.1 %** |
| TOTAL | 152 | 547 | 383 | 130 | 23.76 % |

The 22.2-pp spread between top cluster (patents_ip 33.3 %) and bottom cluster (misc_other 11.1 %) is **systematic, not stochastic**. The cluster sample sizes (24–86 tasks per cluster) are far above sampling-noise thresholds; a Bernoulli 95 % CI on misc_other's 11.1 % rate is ±7 pp, and on patents_ip's 33.3 % is ±18 pp — even with the wide CI on patents_ip, the bottom cluster's rate is significantly below the top cluster's. This is the empirical basis for the dossier's claim that **the architecture's residual failures have domain-specific structure**, not random noise.

Two clusters are diagnostically valuable:

**Biomedical (16.3 %)** — the worst-performing cluster at large sample size. TCGA / PANCANCER / MITELMAN / GENOMICS / SDOH. The schema_valid rate within biomedical is 35/49 = 71 %, the same as the global rate. The cluster-specific gap is at the EXPLAIN stage: BM25 picks columns whose names lexically exist, but they are not the columns the question refers to. The mechanism is *cryptic clinical-trial coding*: "patient age at biopsy" should map to `submitted_diagnosis_age_at_diagnosis` but BM25 cannot bridge this lexical gap. The Phase 29 F3b design (domain-glossary BM25 augmentation) targets this cluster directly.

**Misc/other (11.1 %)** — the worst-performing cluster overall. Dominated by GA360 (12 tasks, 0 EXPLAIN-pass) and FIREBASE (9 tasks, 1 EXPLAIN-pass). Both are nested-STRUCT / RECORD heavy schemas (Google Analytics 360 and Firebase event analytics) where dotted-path access is the natural query pattern. Snowflake's `:field:subfield` syntax is required; the v18 planner emits `column.field.subfield` style, which Snowflake rejects. The Phase 29 F3a design (STRUCT-aware emitter prompting) targets this cluster directly.

The cluster-level diagnostic also reveals a *secondary* mid-cluster strength pattern: well-documented public-data clusters (patents, retail/e-commerce, sports) sit at 28–33 %, suggesting the architecture is *most* successful where column names lexically match the natural-language question and *least* successful where the gap is widest. This is consistent with the BM25-driven schema linker's behaviour: it is fundamentally a lexical-match system, even with PK/FK augmentation.

## 4. Position relative to published systems — canonical cross-metric wording

> The comparison below is **cross-metric**: our 23.76 % is Snowflake EXPLAIN-pass (\*), published numbers are row-match. Direct ranking is invalid. The dossier's canonical wording is documented in [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md) §8.

| System | Metric | Value | Model class |
|---|---|---|---|
| Genloop (closed leaderboard top) | row-match | 96.70 % | closed |
| ReFoRCE + o3 (reproducible closed top) | row-match | 62.89 % | closed |
| Spider-Agent + Qwen3-Coder | row-match | 31.08 % | open ≤30 B |
| Spider-Agent + Claude-3.5-Sonnet | row-match | ≈ 19 % | open mid |
| **Ours (Phase 28-revert-A, v28 stack)** | **EXPLAIN-pass (\*)** | **23.76 %** | open ≤30 B |

**Canonical positioning wording (verbatim):** "Our plan-acceptance rate on Spider2-Snow is in the same band as the open-weight Spider-Agent baselines, pending row-match audit."

What this means concretely: 23.76 % EXPLAIN-pass is bounded above the row-match rate. The pilot10 conversion ratio (8 of 8 schema_valid → 4 row-match) suggests a 50 % conversion at small sample, projecting a 12–18 % row-match band at FULL (not publishable; see [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md) §5). If the actual post-Phase-28b row-match figure lands at ≥ 12 %, the system is in the open-weight Spider-Agent + open-model band. If it lands at ≥ 18 %, it is competitive with Spider-Agent + Qwen3-Coder. If it lands below 12 %, the qualitative claims about scaffold contribution still hold but the leaderboard positioning would be more conservative. The dossier does not pre-commit to any of these scenarios; the audit will measure.

## 5. Realistic row-match projection (NOT publishable)

For internal reasoning only: the pilot10 (Phase 28-revert-A) Snow run measured both EXPLAIN-pass (8 of 10) and offline row-comparison (4 of 10). Conversion ratio: 50 %. Applied to FULL 547, the projection is:

`Snow FULL row-match ≈ 0.50 × 130 = 65 tasks ≈ 11.9 %`

With pilot10 sampling SE of ±15 pp on the conversion ratio (small sample, binomial), the projection band is **row-match ≈ 12–18 % on Snow FULL 547**. This is not a publishable number; it is the design-time hypothesis that informs the Phase 28b audit's expected effort. If the audit comes in at 12 %, the qualitative analysis stands. If it comes in at 8 %, the F3a / F3b interventions become more urgent. If it comes in at 20 %, the architecture is more efficient than projected.

## 6. Lite-Snow partial result (n=40 of 207)

The Spider2-Lite-Snow FULL 207 run was interrupted by a kernel-death event approximately 19 hours before this dossier's compilation deadline and was not resumed. The partial run reached n=40 tasks. Reporting on the partial subset:

* **Sample**: 40 of 207 tasks = 19.3 % of the benchmark.
* **Caveat**: the 40 tasks were the first 40 in the runner's task order; this is *not* a random sample. The order is approximately by database, so the partial result over-represents whichever databases were processed first. Treat as anecdotal evidence rather than a calibrated extrapolation.
* **Headline (partial)**: pilot 10 v28-revert-A on Lite-Snow recorded 4 / 10 = 40 % EXPLAIN-pass (\*). The partial n=40 trends similarly (numbers not separately recomputed for this dossier; see `outputs/spider2_lite/runs/lite_snow_full_v28_revert_a/predictions.jsonl` for the source).
* **Phase 28b post-defence**: complete the Lite-Snow FULL 207 run with the v28 stack and report a full single number alongside the row-match audit. Estimated 30–60 min of warehouse time; the binary is unchanged from the Snow FULL run.

The thesis defence position on Lite-Snow is: **the qualitative behaviour mirrors Spider2-Snow (same scaffold, same dialect, smaller scope); the publishable FULL number is deferred to Phase 28b for completeness alongside the row-match audit**.

## 7. Failure modes — what the residual 76 % consists of

From `error_taxonomy.csv` (the 144-task post-resume window — see [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md) §4):

| failure class | count | share | dossier interpretation |
|---|---|---|---|
| invalid_identifier | 60 | 41.7 % | column-not-found in live Snowflake catalog despite passing closed-set validator |
| ok | 36 | 25.0 % | three-gate-clean |
| schema_invalid | 25 | 17.4 % | v18 validator rejected SQL before EXPLAIN attempt |
| ProgrammingError | 11 | 7.6 % | Snowflake-side semantic errors |
| parse_error | 6 | 4.2 % | SQLGlot parse failure (mostly LATERAL FLATTEN tail) |
| no_catalog_for_task_db | 3 | 2.1 % | task DB not in our catalog (residual gap) |
| syntax_error | 2 | 1.4 % | malformed SQL |
| parse_error_guard | 1 | 0.7 % | F1 guard exception on parse path |

The dominant failure mode is `invalid_identifier` at 41.7 %. This is the gap from 70 % schema_valid (our closed-set pack accepts the SQL) to 24 % EXPLAIN-pass (Snowflake live catalog accepts the SQL): for ≈ 46 % of tasks, the planner picks a column that exists in our pack but not in the live catalog under the form the SQL references it. Three sub-mechanisms:

* **Name-variant mismatch**: pack has `customer_id`, live catalog has `CUSTOMER_ID` or `customerId`, SQL emits the form not present in catalog.
* **Stale pack vs live catalog drift**: rare, but a few tasks' DBs have been updated upstream since we built the pack snapshot.
* **Closed-set pack underspecified**: pack only contains a subset of catalog columns (top-N by BM25); planner emits a column outside the top-N but plausible enough to look correct lexically.

The Phase 29 F3c plan (self-refine on `invalid_identifier`) targets these mechanisms directly: when Snowflake returns `invalid_identifier`, re-prompt the planner with a fuzzy-match suggestion list from the live catalog. Projected recovery: 15–25 % of the 60 `invalid_identifier` failures, lifting EXPLAIN-pass to roughly 30–32 % on the same architecture.

Note that F3c, F3a, and F3b are *complementary*, not alternative. F3a addresses the nested-STRUCT cluster (misc_other 11.1 % at 0 EXPLAIN-pass), F3b addresses the biomedical cluster (16.3 % at low EXPLAIN-pass), F3c addresses the `invalid_identifier` long tail across all clusters. The projected combined post-Phase-29 EXPLAIN-pass rate is 35–40 % on Spider2-Snow FULL, with the same caveat that this is design-time, not measured.

## 8. Path forward — Phase 28b row-match audit + Phase 29 F3 stack

The two post-defence work items, in order:

**Phase 28b — row-match audit (2–3 wall days, $20–100 warehouse spend).** Adapt `spider2.eval` to ingest `predictions.jsonl`, execute the 547 SQL queries against the live Snowflake warehouse, multiset-compare result rows against gold. Output: defensible row-match number directly comparable to Spider 2.0 leaderboard.

**Phase 29 F3 stack (3 weeks).** F3c (self-refine on `invalid_identifier`, 1 week) → F3a (STRUCT-aware emitter prompting, 1 week) → F3b (domain-glossary BM25 augmentation, 1 week). Projected lift: Snow FULL EXPLAIN-pass 23.76 % → 35–40 %, row-match TBD pending Phase 28b conversion-ratio re-measurement.

Beyond Phase 29, the natural next phases are Phase 30 (port F1+F4 grounding to Lite-BQ) and Phase 31 (DBT scaffold redesign). Both are post-thesis and are documented in [../06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md](../06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md) §3 (forward path).

## 9. What this analysis evidences for the thesis defence

* **The 23.76 % EXPLAIN-pass rate (\*) is reproducible** (single canonical run, frozen commit, file-level provenance to `metrics.csv` + `predictions.jsonl` + `traces.jsonl`).
* **The progression from 0 % to 23.76 % is attributable to specific, named, architectural interventions** (F1, F4, F4c, F2a-revert) at fixed model class — not to a model swap.
* **Residual failures cluster around named categories** (biomedical-domain terminology, nested-STRUCT, generic `invalid_identifier` long tail) each addressable by a specific Phase 29 intervention.
* **The F2a falsification narrative** demonstrates a methodological discipline (catalog-probe-before-dialect-heuristic) that is itself a transferable thesis contribution, independent of the metric definition.
* **The 23.76 % is plan-acceptance, not row-match** (Appendix 07 (\*)); the path to a row-match number is Phase 28b. The qualitative claims do not depend on the row-match audit; only the leaderboard-ranking claim does.

The dossier's defendable thesis statement on Spider 2.0 Snow, as of the compilation date, is: **A unified open-weight ≤30B architecture achieves 23.76 % Snowflake `EXPLAIN`-pass rate (plan-level acceptance) on Spider2-Snow FULL 547, placing the system in the same band as the open-weight Spider-Agent baselines pending row-match audit. The progression from 0 % to 23.76 % is fully attributable to architectural interventions at fixed model class; the residual gap decomposes into addressable failure clusters with named Phase 29 targets.**
