# Error Taxonomy Evolution — Failure Categories Phase by Phase

This document tracks which failure categories dominate which benchmark, how each category's share has moved as the architecture evolved, and which categories are now load-bearing for the residual gap. The taxonomy is intentionally lane-aware: a "join inference" failure means something concrete on Spider 1, something different on Spider 2 Snow, and something different again on Spider 2 DBT. Each section therefore defines the categories locally.

Definitions of the underlying metrics are at [01_metric_definitions.md](01_metric_definitions.md). Phase-by-phase aggregate numbers at [02_progression_table_full.md](02_progression_table_full.md). Per-benchmark trajectories at [03_progression_by_benchmark.md](03_progression_by_benchmark.md).

A standard convention is used for the bar charts: each bar shows the share of *failure cases* (not of all cases) that fell into the category in a given phase, so the columns sum to 100 % within each phase, not within each category. Bars use one `█` block per 5 percentage points.

---

## 1. Spider 1.0 — Residual Categories at Saturation

Spider 1 has been at 94.0 % EX since Phase 22, so the interesting question is what the remaining 6 % consists of. We sampled 60 failed items at Phase 22 and re-sampled at Phase 28 to confirm the distribution is stable. The categories are:

* **Gold ambiguity / multi-valid SQL** — the gold answer is one of several semantically equivalent or near-equivalent queries; our prediction is also correct but does not string-match.
* **Multi-aggregate window patterns** — gold uses a window function (`ROW_NUMBER`, `RANK`) the closed-set planner does not propose because the candidate column set does not include the window key.
* **Date / numeric formatting** — gold expects a specific date format string (`%Y-%m-%d`) or a numeric precision that our SQL produces differently.
* **Genuine schema misread** — schema linking selected the wrong table or column despite the closed-set candidate menu.
* **Other** — long-tail individual oddities.

```
Category                       Phase 22 (94.0%)   Phase 28 (94.0%)
gold ambiguity / multi-valid   ████████░░  38%    ████████░░  40%
multi-aggregate / window       ██████░░░░  28%    ██████░░░░  27%
date / numeric formatting      ███░░░░░░░  17%    ███░░░░░░░  15%
genuine schema misread         ██░░░░░░░░   8%    ██░░░░░░░░   8%
other                          ██░░░░░░░░   9%    ██░░░░░░░░  10%
```

**Reading.** The dominant residual category is annotation-driven, not model-driven: at least 38 % of failed items at Phase 22 (and 40 % at Phase 28) are cases where the prediction is semantically correct. This caps the achievable EX on Spider 1 at roughly 96–97 % for our pipeline without manual answer-key reconciliation. The multi-aggregate / window category is the only one that responds to architectural changes (a window-aware candidate menu would address it, though we have not built one). Date/numeric formatting and schema misread are roughly stable; they are not load-bearing for the gap-closing strategy.

**Movement across phases.** Between Phase 18 (91.5 %) and Phase 22 (94.0 %), the categories that shrank were "schema misread" (≈ 18 % of failures at Phase 18 down to 8 % at Phase 22) and "other" (down by half). The closed-set planner is responsible for both reductions. After Phase 22 the distribution froze because we stopped intervening on Spider 1.

---

## 2. BIRD — Evidence-Driven Failure Modes

BIRD's failure categories are richer than Spider 1's because BIRD provides explicit `evidence` rows and the question often hinges on whether the model uses them correctly. We use the following local taxonomy:

* **Evidence misuse** — the question is answerable only if a fact from the evidence row is incorporated; our SQL ignored or misinterpreted that fact.
* **Numeric encoding** — evidence specifies that values like `'M'` and `'F'` encode something, or that a code column needs translation; SQL filters on the raw value.
* **Multi-step reasoning** — query requires composing two sub-aggregations; planner emits a single-pass aggregate.
* **Join key ambiguity** — schema has two plausible join keys; planner picked the wrong one.
* **Gold ambiguity / multi-valid** — as on Spider 1.

```
Category                       Phase 14 (64.1%)   Phase 22 (87.9%)
evidence misuse                ████████░░  39%    ████░░░░░░  21%
numeric encoding               ████░░░░░░  18%    ███░░░░░░░  14%
multi-step reasoning           ████░░░░░░  20%    █████░░░░░  25%
join key ambiguity             ██░░░░░░░░  10%    ██░░░░░░░░  10%
gold ambiguity / multi-valid   ██░░░░░░░░  13%    ██████░░░░  30%
```

**Reading.** Between Phase 14 and Phase 22 the absolute number of evidence-misuse failures fell sharply because the v9 evidence-block prompt and the validator-feedback retry both target this category. As the success rate climbed, gold-ambiguity rose from 13 % to 30 % of failures simply by attrition: the easy real-error categories shrank, leaving annotation-driven cases as the dominant residual. Multi-step reasoning is now the largest *fixable* category (25 % of failures), and is the natural target for a hypothetical BIRD-specific Phase 32 (deferred behind Spider 2 work).

---

## 3. Spider2-Lite-BQ — Dialect Plateau

Spider 2-Lite-BQ's failure categories are dominated by BigQuery-specific dialect issues, not by planner quality. Local taxonomy:

* **FQN / project-dataset-table mismatch** — generated SQL uses two-part `dataset.table` where gold uses `project.dataset.table` or vice-versa; engine refuses to bind.
* **Engine-compat construct** — generated SQL uses Snowflake-flavoured `ARRAY_EXISTS`, `OFFSET(0)`, or chained CTEs that BigQuery rejects or interprets differently.
* **Join inference** — wrong join key, missing join, or extra join introduced by free-form planning.
* **Aggregate semantics** — `COUNT(DISTINCT ...)` vs `COUNT(*)` or `APPROX_QUANTILES` vs `PERCENTILE_CONT` mismatches.
* **Other (timeout, quota, permission)** — non-content failures.

```
Category                       Phase 19 (30%)     Phase 22 (30%)     Phase 28 (30%)
FQN / project mismatch         ████████░░  39%    ████░░░░░░  20%    ████░░░░░░  20%
engine-compat construct        ███░░░░░░░  15%    █████░░░░░  27%    █████░░░░░  27%
join inference                 ████░░░░░░  21%    █████░░░░░  25%    █████░░░░░  25%
aggregate semantics            ██░░░░░░░░  12%    ███░░░░░░░  15%    ███░░░░░░░  15%
other                          ██░░░░░░░░  13%    ███░░░░░░░  13%    ███░░░░░░░  13%
```

**Reading.** Phase 20 STAGE A1's identifier canonicalisation cut FQN mismatch from 39 % to 20 % of failures, validating the audit prediction for that category. But the absolute exec rate did not move past 30 % because engine-compat and join-inference grew as a share. Phase 22 STAGE A3 attempted to address engine-compat with Family C template prompts — the audit predicted +20 pp; the observed gain was +4 pp because Family C was almost never the lowest-rank candidate selected. Phase 28 inherited the same distribution unchanged because Phase 27 F1 grounding has not yet been ported to BQ.

**Plateau composition.** The 30 % plateau on Lite-BQ is therefore not a model-quality plateau but a port-the-Snow-fixes plateau. Phase 30's job is to (a) port F1 grounding to attack the join-inference and FQN bands; (b) re-attempt engine-compat with a BigQuery catalog probe to catch construct mismatches before submission.

---

## 4. Spider2-Lite-Snow & Spider2-Snow — The Two-Stage Funnel

Snow lanes have a two-stage failure funnel that became visible only at Phase 27. Stage 1 is *schema_valid* — does the SQL bind against the live Snowflake catalog? Stage 2, given schema_valid, is *exec_ok* — does it execute and match the gold result? Before Phase 27 the schema_valid rate was so low that Stage 2 categories were invisible. The two-stage taxonomy:

**Stage 1 failures (schema_invalid):**
* **Cross-DB identifier drift** — three-part name references a database the task is not connected to.
* **Table not in pack** — closed-set planner did not surface the right table because BM25 retrieved the wrong DB partition.
* **Column not in pack** — table is correct, column is wrong.

**Stage 2 failures (schema_valid but exec failed):**
* **Date-cast on NUMBER/VARIANT** — `DATE_TRUNC` applied to an UNIX timestamp or VARIANT column without explicit cast.
* **LATERAL FLATTEN binding** — SQL parses, but FLATTEN alias bindings are wrong; sometimes SQLGlot itself fails to parse and the guard's regex fallback activates.
* **Aggregate semantics / null handling** — Snowflake's `NULL`-aware aggregates differ from the planner's assumption.
* **Result-set mismatch** — SQL ran but the rows differ from gold (typically wrong join key, or wrong row order in a `LIMIT` query).

```
Stage 1 (schema_invalid share)  Phase 22 baseline  Phase 27 pilot10  Phase 28 pilot10
cross-DB identifier drift       ████████░░  85%    █░░░░░░░░░   5%   ░░░░░░░░░░   0%
table not in pack               █░░░░░░░░░  10%    ██░░░░░░░░  35%   ██░░░░░░░░  35%
column not in pack              █░░░░░░░░░   5%    ████░░░░░░  60%   ████░░░░░░  65%
```

```
Stage 2 (schema_valid → exec failures)  Phase 27 pilot10   Phase 28 pilot10
date-cast on NUMBER / VARIANT           ████████░░  60%   ███░░░░░░░  18%
LATERAL FLATTEN binding                 █░░░░░░░░░  10%   ██░░░░░░░░  20%
aggregate / null handling               ██░░░░░░░░  15%   ███░░░░░░░  22%
result-set mismatch                     ██░░░░░░░░  15%   ████░░░░░░  40%
```

**Reading.** Phase 27 F1 grounding effectively eliminated the cross-DB identifier drift category (85 % → 0 %), which had been the dominant Stage 1 failure since Phase 17. Phase 28 closure dropped date-cast failures from 60 % to 18 % of Stage 2 failures — this is the F4 wrap's contribution and it is what generates the pilot 10 exec gain (1/10 → 4/10). What remains in Stage 2 at Phase 28 is dominated by *result-set mismatch* — SQL that runs and produces *some* result, but not the gold rows. This is the natural target for Phase 29's multi-shot synthesis: the schema is already correct, the query is syntactically valid, what is missing is the right reasoning over the schema. The F4c regex fallback's activation rate on the pilot 10 was low (≤ 20 % of LATERAL FLATTEN tasks); the audit at Phase 28 has flagged this for a coverage review on the FULL run.

**Phase 28 FULL impact (pending).** The pilot10 distribution is robust on Stage 1 because F1 grounding's catalog filter is deterministic; we expect the FULL run to confirm the ≈ 0 % cross-DB drift number. The Stage 2 distribution is the unknown: at FULL scope, the long-tail databases may exercise LATERAL FLATTEN and aggregate-semantic categories more heavily than pilot 10 did.

---

## 5. Spider2-DBT — Project-Level Failure Bands

DBT failure modes are categorically different from SQL-only benchmarks because each task is a small dbt project, not a single query. Local taxonomy (with absolute counts on the 68 final tasks):

* **dbt_run_failed (37 of 68)** — dbt itself errored before producing output. Sub-bands: missing `ref()` / `source()` macro (≈ 20), Jinja syntax error (≈ 10), multi-model dependency resolution failure (≈ 7).
* **ran_ok_but_score_zero (17 of 68)** — dbt produced output, but the grading rubric returned 0 because the model is logically wrong (typically wrong aggregation level or wrong join key).
* **dbt_test_failed (5 of 68)** — dbt ran the model, the model's own content tests failed (`unique`, `not_null`, `accepted_values`).
* **success (9 of 68)** — model ran, tests passed, grading rubric returned 1.

```
DBT failure category               Phase 23 (10.4%)   Phase 25 (13.2%)   Phase 28 (13.2%)
dbt_run_failed (macro / Jinja)     ████████░░  55%    ███████░░░  54%    ███████░░░  54%
dbt_run_failed (multi-model dep)   ██░░░░░░░░  10%    █░░░░░░░░░  10%    █░░░░░░░░░  10%
ran_ok_but_score_zero              ████░░░░░░  20%    █████░░░░░  25%    █████░░░░░  25%
dbt_test_failed                    █░░░░░░░░░   5%    █░░░░░░░░░   7%    █░░░░░░░░░   7%
success                            ██░░░░░░░░  10%    ███░░░░░░░  13%    ███░░░░░░░  13%
```

**Reading.** The dominant failure band on DBT — macro / Jinja errors — is exactly the band Phase 31's planned dbt-parse pre-check is designed to attack. If the pre-check catches and re-prompts on ≥ 50 % of macro errors, the lane should lift from 13.2 % to ≈ 20 %. The ran_ok_but_score_zero band (17 cases) is the natural target for a content-test feedback retry: of the 17, an internal audit identified 10 cases where the failure is recoverable from the test message alone. The 5 dbt_test_failed cases are the highest signal-to-noise category — dbt itself tells us exactly what is wrong.

---

## 6. Cross-Cutting Patterns

Three patterns repeat across all lanes.

**(1) Annotation-driven residuals dominate at saturation.** On Spider 1 (Phase 28: 94 %) the largest residual is gold ambiguity. On BIRD (Phase 22+: 87.9 %) the largest residual is also gold ambiguity. Pushing further on these lanes requires answer-key audits, not architecture changes.

**(2) Identifier / dialect drift is structural, not model-side.** Spider2-Lite-BQ's plateau and Spider2-Snow's pre-Phase 27 floor are both explained by identifier / dialect drift that no model swap addresses. Catalog probing and per-task grounding are the load-bearing interventions.

**(3) Late-phase progress comes from category-targeted tools.** Every interface that moved a number was built to attack one named category: F1 grounding (cross-DB drift), F4 wrap (date-cast on NUMBER/VARIANT), F4c fallback (LATERAL FLATTEN parse), validator-feedback retry (evidence misuse), closed-set planner (schema misread). Phase 29-31's interventions will follow the same pattern — multi-shot synthesis for result-set-mismatch on Snow, F1 port for join-inference on BQ, dbt-parse pre-check for macro errors on DBT. The lesson, repeated across this document, is that the residual gap is decomposable into a small number of named categories per lane and that each category responds to a single targeted intervention rather than to a general-purpose capability boost.
