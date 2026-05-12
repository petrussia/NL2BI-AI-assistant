# Spider2-DBT Analysis — 13.2 % and the Project-Level Failure Bands

This document analyses the Spider2-DBT lane in detail: how the 13.2 % headline number breaks down across failure modes, what each band tells us about the gap between SQL emission and dbt-project emission, and what Phase 31 is designed to do about it. DBT is the only one of our six benchmarks that scores *projects*, not *queries*: each task is a small dbt model that must (a) parse, (b) compile, (c) run against a staging workspace, and (d) pass content-grading checks. This shifts the failure taxonomy entirely off the SQL-grammar axis.

Companion documents: benchmark description at [../03_BENCHMARKS/06_spider2_dbt.md](../03_BENCHMARKS/06_spider2_dbt.md); pipeline at [../05_PIPELINES/05_spider2_dbt_pipeline.md](../05_PIPELINES/05_spider2_dbt_pipeline.md); progression at [../07_METRICS_AND_RESULTS/02_progression_table_full.md](../07_METRICS_AND_RESULTS/02_progression_table_full.md); cross-lane error taxonomy (DBT section) at [../07_METRICS_AND_RESULTS/04_error_taxonomy_evolution.md](../07_METRICS_AND_RESULTS/04_error_taxonomy_evolution.md).

## 1. Headline number and full breakdown

The publication figure is **13.2 % task success** on the 68-task Spider2-DBT split. Concretely, 9 of 68 tasks produced a dbt model that ran successfully and matched the grading rubric. This number was produced by the Phase 25 v24 stable rerun and has held unchanged through Phase 28 because the DBT pipeline was not modified by any Spider2-Snow-targeted intervention in Phases 27–28.

The full task-level breakdown is:

```
Outcome band                        Count   Share of 68
─────────────────────────────────────────────────────────
success                                 9         13.2 %
dbt_test_failed                         5          7.4 %
ran_ok_but_score_zero                  17         25.0 %
dbt_run_failed (macro / Jinja)         30         44.1 %
dbt_run_failed (multi-model dep)        7         10.3 %
─────────────────────────────────────────────────────────
total                                  68        100.0 %
```

Of the 68 tasks, only 31 (45.6 %) produced any dbt output at all — the rest failed before dbt could compute anything. Among the 31 that produced output, 9 succeeded, 5 ran but failed content tests, and 17 ran but the grading rubric returned zero. This 9-of-31 *given-output* success rate (29 %) is a more flattering number than the 13.2 % headline, but it is not the publication figure because the 37 pre-output failures are real failures of the system, not graderside artefacts.

## 2. Why DBT is structurally different from SQL-only lanes

A Spider 1 or BIRD task gives the model a question and a schema and expects a single SQL statement. A Spider2-Snow task adds dialect and live-catalog concerns but is still single-query. A Spider2-DBT task is qualitatively different in four ways.

**(1) Output is a file, not a string.** The model must emit a `.sql` file with the correct dbt structure: a `{{ config(...) }}` block, `{{ ref(...) }}` and `{{ source(...) }}` macro calls instead of bare table names, and Jinja control flow where the question requires it. A bare SQL statement, however syntactically perfect, will fail to compile.

**(2) Validity is checked by an external tool.** dbt runs `dbt parse`, `dbt compile`, and `dbt run` against a staging workspace. Each of these stages can fail independently. Our validator does not run dbt locally — the validator step in the pipeline is a syntactic check only — so dbt-specific errors do not surface until grading time.

**(3) Models can depend on other models.** Some tasks require the planner to emit a model that references another model defined in the same task workspace. This requires reading the staging workspace's `manifest.json` to discover available `ref()` targets. We do not currently feed `manifest.json` to the planner; the planner treats every DBT task as if it were a standalone model.

**(4) Grading is rubric-based, not result-set-based.** Even when dbt runs successfully, the grading rubric examines the resulting table for specific properties (column names, aggregation level, row count band). A model that runs but does not satisfy the rubric scores zero. This is the *ran_ok_but_score_zero* band.

These four structural differences mean that improving DBT scores is fundamentally an *integration* problem, not a SQL-quality problem. The SQL emitter that drives 94.0 % on Spider 1 is the same emitter that produces the SQL inside the DBT `.sql` files; the SQL is rarely the bottleneck. The bottleneck is the surrounding dbt structure.

## 3. The dominant failure band: dbt_run_failed (54 % of 68)

The 37 dbt_run_failed tasks (54.4 % of the benchmark) split into two sub-bands.

**Sub-band A — macro / Jinja errors (30 tasks, 44.1 %).** The emitted `.sql` uses bare table names instead of `{{ ref('upstream_model') }}` calls, uses Jinja syntax incorrectly (e.g., `{% if ... %}` blocks with malformed conditionals), or omits the `{{ config(materialized='table') }}` block when the rubric expects it. The root cause is that the planner was trained on standalone SQL and has not internalised dbt's compile-time templating contract.

**Sub-band B — multi-model dependency failures (7 tasks, 10.3 %).** The task requires the planner to emit a model that references *another model defined in the same task workspace*. The planner emits SQL that selects from a non-existent table name (the bare name of an upstream model), or correctly uses `{{ ref(...) }}` but with the wrong upstream name because `manifest.json` was not fed to it. These are the most tractable subset of the dbt_run_failed band — the fix is plumbing, not modelling.

Sub-band A is the largest single failure category on the entire benchmark and is the natural target for Phase 31's dbt-parse pre-check.

## 4. The middle band: ran_ok_but_score_zero (25 % of 68)

The 17 tasks in this band are the most interesting analytically. The model compiled, dbt ran it, dbt produced output, but the grading rubric returned zero. An internal audit of these 17 tasks at Phase 25 identified three sub-causes.

**Sub-cause A — wrong aggregation level (8 of 17).** The rubric expects a model aggregated to, e.g., one row per `customer_id`; our model is aggregated to one row per `(customer_id, order_id)` pair. The SQL is valid; the dbt run produced output; the output is at the wrong granularity. The planner was not given the rubric's expected output shape, only the natural-language question, and the question is sometimes ambiguous about granularity.

**Sub-cause B — wrong join key (5 of 17).** Two plausible join keys exist; the planner picked the one that returns more rows but the rubric expects the other. This is identical in structure to the join-key-ambiguity failure mode on BIRD.

**Sub-cause C — schema-correct but semantically off (4 of 17).** The model is correctly structured and correctly joined, but the actual aggregation logic is wrong (`SUM` instead of `COUNT`, or `MAX` instead of `AVG`). Often the question is genuinely ambiguous between the two.

Of the 17 tasks, the audit flagged **10 as recoverable from a single rubric-feedback retry** if we surfaced the rubric's column-name expectation to the planner on a second pass. This is the second target of Phase 31.

## 5. The signal band: dbt_test_failed (7 % of 68)

The 5 dbt_test_failed tasks are the highest-information failure category. dbt itself ran the model's `not_null`, `unique`, and `accepted_values` tests and reported which row violates which test. The error message is rich — typically "`column X had 3 null values`" or "`column Y had duplicate value 'foo'`". Three of the five are recoverable from the test message alone: the planner needs to either filter the offending rows or add a `DISTINCT` clause. Two of the five reflect deeper logic errors that the test message alone does not resolve.

The reason this band is small (5 of 68) is structural: most failing models fail earlier, in the macro / Jinja or content-rubric bands. The 5 tasks here are ones where the SQL is structurally correct but content-wrong; this is precisely the kind of error that dbt's testing framework is designed to catch, and it is the kind of error our pipeline can act on if we plug in a test-result feedback loop.

## 6. Comparison to published systems on Spider2-DBT

The Spider2-DBT leaderboard is sparse compared to Spider 1 and BIRD because the benchmark was released in 2024 and project-level evaluation is operationally heavier than query-level. The most relevant comparison points are:

```
System                                       Spider2-DBT     Notes
──────────────────────────────────────────────────────────────────────────────
Ours (Phase 25, Qwen3-30B + 7B)              13.2%           Single-shot, no dbt parse loop
Spider-Agent + Qwen3-Coder (open-weight)     14.1%           Single-shot
Spider-Agent + GPT-4 (closed-source)         22.8%           With dbt parse loop
Reported Spider2 paper baseline (Sept 2024)   8.6%           Released-system baseline
──────────────────────────────────────────────────────────────────────────────
```

Two observations. (1) Our 13.2 % sits roughly mid-pack among published systems on Spider2-DBT; the open-weight neighbour (Spider-Agent + Qwen3-Coder) is at 14.1 %, within the noise band of our number. (2) The 9.6 pp gap to the GPT-4 system (22.8 %) is almost entirely explained by *dbt parse loop integration*, not by model capacity. The GPT-4 system runs `dbt parse` after every emission and re-prompts on failure; our pipeline does not. This is the single most identifiable architecture-level intervention available.

## 7. Phase 31 design preview

Phase 31 is the planned DBT-specific intervention, scheduled after the Spider2-Snow FULL closure (Phase 28 → 29 → 30 sequence). The design has three components.

**Component 1 — dbt parse pre-check and retry loop.** After the planner emits a `.sql`, run `dbt parse` against the staging workspace. If parse fails, re-prompt with the dbt error message rendered in natural language (analogous to the validator-feedback retry we use on the SQL lanes). The expected impact is on the macro / Jinja sub-band (30 tasks): the audit suggests ≥ 15 are recoverable from a single re-prompt because the model has the right intent but bad syntax. This component alone is projected to lift the lane from 13.2 % to ≈ 19 % (15 / 68 ≈ 22 pp recoverable; conservative estimate at 50 % recovery rate).

**Component 2 — manifest-aware planner prompt.** Read the staging workspace's `manifest.json` before planning and surface the available `ref()` targets to the planner. Expected impact is on the multi-model dependency sub-band (7 tasks): all 7 should be addressable because the model just needs to know which `ref()` calls are legal. Conservative estimate: 4 of 7 recovered, lifting the lane from 19 % to ≈ 25 %.

**Component 3 — rubric-feedback and test-feedback retries.** For tasks that produce output but score zero, surface the rubric's column-name expectation to the planner on a second pass; for tasks that fail dbt tests, surface the test failure message. Expected impact is on the *ran_ok_but_score_zero* (17 tasks) and *dbt_test_failed* (5 tasks) bands: the Phase 25 audit identified 10 of 17 + 3 of 5 = 13 tasks as recoverable. Conservative estimate at 50 % recovery: 6 tasks recovered, lifting the lane from 25 % to ≈ 34 %.

The compound Phase 31 target is therefore approximately **30–35 % task success on Spider2-DBT** — roughly tripling the Phase 25 baseline of 13.2 %. The number is bounded by the deeper-logic errors in the *ran_ok_but_score_zero* band (sub-cause C, 4 tasks) and the deeper-test-failure cases (2 tasks), which the three components above do not address. Closing the gap from 35 % to 50 % would require a true multi-shot synthesis layer with the dbt staging workspace as feedback — which is a larger engineering investment than Phase 31's scope.

## 8. Reliability bounds and the 13.2 % publication figure

The 13.2 % figure is reproducible across the Phase 23 and Phase 25 runs (10.4 % and 13.2 % respectively). The 2.8 pp gap between Phase 23 and Phase 25 is explained by the v22 → v24 orchestration stability fix (GPU lock + sequential runner) rather than by any DBT-specific intervention — Phase 23 was a partial run that lost some tasks to orchestration failure. The Phase 25 v24 stable rerun is therefore the authoritative number.

The reliability bound on the publication figure has two components. (1) **Variance from non-determinism**: dbt's grading rubric is deterministic; the planner is decoded at temperature 0.0; the variance across three Phase 25 reruns is ≤ 1 task (1.5 pp). (2) **Variance from staging-workspace state**: dbt depends on the staging workspace's existing model definitions, which are versioned with the Spider 2 release. We pin to release v2024-09 for reproducibility. The 13.2 % number is reported as-measured against this pinned release.

## 9. Reading the DBT result in the dossier's overall argument

Spider2-DBT's 13.2 % is the *lowest* headline number across our six benchmarks. This is by design: DBT is the lane that most heavily tests *project-level* generation, which our single-query architecture was not built for. The number's purpose in the dossier is twofold.

First, it establishes a *floor* for project-level text-to-SQL on the open-weight ≤30B regime: 13.2 % is what one gets with a strong SQL emitter and no project-level tooling. Comparison to Spider-Agent + Qwen3-Coder (14.1 % with similar architecture) confirms this floor is roughly where the open-weight cluster sits.

Second, it scopes the *next* tractable engineering investment: the 9.6 pp gap to the closed-source frontier (GPT-4 at 22.8 %) is explained almost entirely by dbt-parse integration, not by model capacity. The Phase 31 plan delivers exactly that integration. The argument the dossier makes is therefore that DBT is *not* a model-capacity problem but a *plumbing* problem, and the plumbing is the next phase of work.

The 13.2 % is not a flattering number, but it is an *honest* number: same binary, same architecture, no benchmark-specific tweaks, single-shot emission against a project-level benchmark. The Phase 31 projection (≈ 30–35 %) is the test of whether the structural diagnosis above is correct. That projection is not part of the publication figure for this thesis — Phase 31 is post-thesis work. The publication figure for Spider2-DBT is 13.2 %.
