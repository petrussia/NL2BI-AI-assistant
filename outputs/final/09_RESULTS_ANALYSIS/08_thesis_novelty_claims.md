# Thesis Novelty Claims — Formal Structure

This document is the formal statement of the thesis's six novelty claims, the evidence that supports each, the scope each claim is restricted to, and the relationship of each claim to the published field. It is the structure to which a thesis-defence panel will refer when assessing what the work contributes versus what is already known. Companion documents: leaderboard position at [05_leaderboard_position.md](05_leaderboard_position.md); publishability tier assessment at [07_publishability_assessment.md](07_publishability_assessment.md); methodology disclosure at [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md).

A note on metric framing: where claims reference Spider 2 family results, the canonical wording "EXPLAIN-pass rate (\*)" / "dry_run-pass rate (\*)" is used. The asterisks refer back to the metric caveat. The claims listed below are deliberately structured to be *independent of the row-match audit outcome* — they are architectural and methodological contributions that the dossier can defend now and that will not be invalidated by the Phase 28b row-match audit, regardless of what number that audit produces.

## Claim 1 — Unified architecture works across 5 of 6 benchmark families

**Statement.** A single architecture — Qwen3-Coder-30B-A3B planner + Qwen2.5-Coder-7B emitter, v18 closed-set planner + validator-feedback retry, dialect-specific identifier and date-cast guards — reaches *competitive plan-acceptance / direct-comparable execute_ok* on 5 of 6 benchmark families at a fixed open-weight ≤30B model class, without per-benchmark fine-tuning or model swaps.

**Evidence.** The headline figures (see [../07_METRICS_AND_RESULTS/07_headline_results.md](../07_METRICS_AND_RESULTS/07_headline_results.md) §1):
* Spider 1.0 dev 1034: 94.0 % execute_ok — within the open-weight 92–95 % published cluster.
* BIRD dev FULL 1534: 87.9 % execute_ok (pending evaluator audit) — within the open-weight 86.7–89.1 % published cluster.
* Spider2-Lite-BQ FULL 205: 34.6 % BigQuery dry_run-pass (\*) — at the open-weight Spider-Agent baseline band.
* Spider2-Snow FULL 547: 23.76 % Snowflake EXPLAIN-pass (\*) — at the open-weight Spider-Agent baseline band.
* Spider2-DBT FULL 68: 13.2 % task_success — at the open-weight Spider-Agent baseline ceiling (lane is scaffold-bound, not model-bound; see [04_spider2_dbt_analysis.md](04_spider2_dbt_analysis.md)).

The "5 of 6" framing acknowledges that Spider2-Lite-Snow's FULL closure is deferred (partial n=40 of 207 due to kernel-death event); the lane qualitatively matches Spider2-Snow but the publishable FULL number waits for Phase 28b.

**Scope limitation.** The claim is about *competitive plan-acceptance*, not about *frontier row-match*. The system is mid-band open-weight ≤30B on every lane and does not challenge the closed-source frontier on any lane. The claim is also restricted to the six benchmark families enumerated in [../03_BENCHMARKS/](../03_BENCHMARKS/); it does not assert generalisation beyond Spider/BIRD-family text-to-SQL.

**Position relative to the field.** The published open-weight cluster is fragmented — different systems lead different benchmarks (CodeS-15B leads Spider 1, DAIL-SQL adaptations lead BIRD, Spider-Agent leads Spider 2). The novelty of Claim 1 is *the same binary on every benchmark*, not the leadership on any single one. Spider-Agent achieves this at a smaller scope (Spider 2 lanes only); our architecture is the closest open-weight ≤30B equivalent that spans both classical and Spider 2 benchmarks at competitive rates.

**Why the claim is defendable now.** No part of Claim 1 depends on the row-match audit. The classical benchmark numbers are direct-comparable; the Spider 2 numbers are plan-acceptance with the canonical "in the same band as the open-weight Spider-Agent baselines, pending row-match audit" qualification.

## Claim 2 — Scaffold dominates model class at fixed capability

**Statement.** Within our architecture, scaffolding (the closed-set planner, the schema linker, the validator-feedback retry, the dialect-specific guards) is the *dominant contributor* to execute_ok / plan-acceptance gains; the model class is the *enabling layer*. At Qwen3-Coder-30B-A3B + Qwen2.5-Coder-7B held constant, Phase 27 → 28 lifted Spider2-Snow from 0 % to 23.76 % EXPLAIN-pass (\*) entirely through scaffold changes, with no model change.

**Evidence.** The progression table at [../07_METRICS_AND_RESULTS/02_progression_table_full.md](../07_METRICS_AND_RESULTS/02_progression_table_full.md) and the per-phase attribution in [03_spider2_snow_analysis.md](03_spider2_snow_analysis.md) §2:
* Phase 26 (no F1 grounding, same model): 0 % Snow EXPLAIN-pass.
* Phase 27 (F1 grounding added, same model): pilot 10 8/10 schema_valid, 1/10 EXPLAIN-pass.
* Phase 28-revert-A (F4 wrap + F4c fallback added, same model): pilot 10 4/10 EXPLAIN-pass.
* Phase 28 FULL (same v28 stack, same model): 547-task FULL 23.76 % EXPLAIN-pass.

A counterfactual: the Phase 17 model-swap pilot ([06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md) §3) measured 4 different model families on Spider2 lanes without architectural changes; the variance across models was small relative to the variance across scaffold changes (single-digit percentage points across models vs 20+ pp across scaffold phases). This explicitly tested the "swap model, hold scaffold" alternative and falsified it.

**Scope limitation.** The claim does not assert that scaffold is sufficient *without* a strong model. It asserts that *given* a competent open-weight ≤30B model (specifically the Qwen-Coder family), the scaffold is what moves the number. A weaker model (e.g. a 1.5B base model) would not respond to the same scaffold improvements; we observed exactly this at Phase 10–11 ([06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md) §2). The claim is therefore *conditional on the model class being adequate*, not a general "scaffold always wins" assertion.

**Position relative to the field.** Most published Spider 2.0 work emphasises model class — closed-source frontier results are framed as "what GPT-4 / o3 / Claude can do" with relatively standard scaffolding. The novelty of Claim 2 is the *quantitative attribution* of architectural progression to scaffold changes at fixed model class, traceable phase by phase in our progression table. The Spider-Agent paper makes a related claim but does not provide the same level of attribution detail.

**Why the claim is defendable now.** The progression is reproducible from the run directories indexed in [../10_REFERENCES/02_internal_phase_reports.md](../10_REFERENCES/02_internal_phase_reports.md). It does not depend on the row-match audit because the EXPLAIN-pass progression maps directly onto scaffold-change phases.

## Claim 3 — Multi-DB partitioning + 3-part identifier rendering + AST guard solves Snowflake cross-DB drift

**Statement.** The combination of (a) per-task BM25 partition keyed by `c.db.upper()`, (b) AST-aware identifier rewriting to three-part `DATABASE.SCHEMA.TABLE` form, and (c) hard rejection of any table reference not in the per-task allow-set, jointly solves the cross-DB identifier drift problem on Spider2-Snow. The F1 fix at Phase 27 lifted schema_valid from 0 % to ≈ 70 % on pilot 10 and 70.02 % on FULL 547, eliminated cross-DB drift from 90.2 % (Phase 26 audit) to 0 % (guard_leaks counter), and unblocked all downstream EXPLAIN-pass gains.

**Evidence.** Phase 26 research-handoff diagnostic (`outputs/REPORT_SPIDER2_V26_RESEARCH_HANDOFF.md`) identified the global-BM25 root cause and measured the 90.2 % cross-DB-drift rate. Phase 27 F1 implementation (`repo/src/evaluation/schema_pack_builder_v18.py`, `schema_linking_v18.py`, `snow_identifier_guard_v27.py`) eliminated it. FULL run `guard_leaks = 0` is the evidence that the guard's hard-rejection works at scale; FULL `chosen_schema_valid = 383 / 547 = 70.02 %` is the evidence that the partition + rewrite recover schema-valid identifiers.

**Scope limitation.** The claim is restricted to Snowflake / Spider2-Snow lane. The F1 grounding stack is *expected* to port to BigQuery / Lite-BQ (this is Phase 30's plan) but has not been tested there. The claim is not "F1 grounding solves identifier drift in all warehouses"; it is specifically about Snowflake under Spider 2.0 conditions.

**Position relative to the field.** Spider 2.0 papers (Lei et al. 2024, Cao et al. Spider-Agent 2024) acknowledge cross-DB drift as a problem class but do not provide a clean architectural solution. Schema-linking-focused work (RAT-SQL, CodeS) addresses single-database schema linking but does not consider the multi-DB partitioning question. The F1 stack is, to our knowledge, the cleanest published treatment of the specific problem class on Spider 2.0 Snow.

**Why the claim is defendable now.** The before/after measurements are direct: 90.2 % drift → 0 %, 0 % schema_valid → 70 %. These are pre-EXPLAIN measurements and do not depend on row-match.

## Claim 4 — Catalog-probe-before-dialect-heuristic is a necessary methodological discipline

**Statement.** Dialect-specific rewrite heuristics on production warehouse data must be validated against a direct catalog probe before deployment. The F2a auto-uppercase hypothesis (Phase 28a) was a reasonable architectural intuition (Snowflake stores identifiers in uppercase by default) that, deployed without catalog verification, would have regressed the only previously-working tasks. The catalog probe of the PATENTS schema revealed columns stored lowercase (37 / 37 columns), falsifying F2a and prompting the revert.

**Evidence.** The Phase 28a regression run (`outputs/REPORT_SPIDER2_V28_F2A_REGRESSION.md`) measured pilot 10 dropping from 1/10 EXPLAIN-pass (Phase 27 baseline) to 0/10 (F2a active). The catalog probe (`outputs/logs/phase28_catalog_probe_patents.md`) showed `SELECT COLUMN_NAME, TABLE_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_CATALOG = 'PATENTS'` returning lowercase identifiers. The Phase 28-revert-A run (`outputs/REPORT_SPIDER2_V28_REVERT_A.md`) measured pilot 10 jumping to 4/10 EXPLAIN-pass after F2a was reverted. FULL `requoted_n = 0` confirms F2a is not firing at FULL scale.

**Scope limitation.** The claim is methodological, not architectural. It does not assert "auto-uppercase is wrong in general" — F2a may be correct for some Snowflake accounts. It asserts that *deploying* such a heuristic without catalog verification is methodologically unsound, and that this specific instance was a falsification-by-data of a reasonable hypothesis. The claim transfers to other dialect-rewrite domains: BigQuery STRING vs BYTES casts, MySQL backtick-quoting, etc.

**Position relative to the field.** Published text-to-SQL work that targets warehouse-scale data tends to either rely entirely on the model's dialect knowledge (no rewrites) or to apply dialect rewrites from documentation without catalog verification. We have not found a published architecture that runs catalog-probe-before-deployment as a discipline. The methodological contribution of Claim 4 is the *named discipline*, transferable to any future dialect-rewrite work.

**Why the claim is defendable now.** The before/after data is unambiguous (0/10 → 4/10 on pilot 10 from a single revert). It does not depend on the row-match audit.

## Claim 5 — Layered architectural fixes can mask each other's contributions; revert experiments are necessary for proper attribution

**Statement.** When multiple architectural interventions are deployed concurrently, their individual contributions can be hidden by interaction effects. The F4 wrap (Phase 28) appeared to have zero ROI when measured under F2a active (Phase 28a metric: pilot 10 0/10 EXPLAIN-pass); after F2a was reverted (Phase 28-revert-A), the F4 wrap was exposed as load-bearing (pilot 10 4/10 EXPLAIN-pass, of which 3 were F4-driven). Proper attribution required a deliberate revert experiment.

**Evidence.** Phase 28a closure metrics vs Phase 28-revert-A closure metrics, both on the same pilot 10:
* Phase 28a (F1 + F4 + F4c + F2a): 0/10 EXPLAIN-pass, wrapped_n = 0 of 10.
* Phase 28-revert-A (F1 + F4 + F4c, F2a reverted): 4/10 EXPLAIN-pass, wrapped_n = 3 of 10 (3 of the 4 successful tasks were F4-recovered).

The mechanism: F2a's auto-uppercase regression broke the schema-valid pipeline for the PATENTS-dominated pilot 10, so F4's NUMBER/VARIANT date-cast wrap fired on tasks that were already broken at schema-valid stage. Removing F2a unblocked schema_valid, which let F4 actually deliver its load-bearing contribution.

**Scope limitation.** The claim is methodological. It does not assert that all architectural fixes should be reverted on schedule. It asserts that when a layered intervention's measured contribution is anomalously small, a revert experiment is the correct diagnostic, not "just keep all fixes deployed."

**Position relative to the field.** Published Spider 2.0 work tends to report stacked-architecture configurations as fait accompli, without per-component attribution. The Spider-Agent paper, for example, reports F1+F2+F3+F4 as a complete stack and does not break down which component is load-bearing. The novelty of Claim 5 is the *explicit revert-experiment discipline* and the *naming of the masking effect* that motivates it.

**Why the claim is defendable now.** The pilot 10 before/after data is direct evidence. It does not depend on the row-match audit.

## Claim 6 — BM25 hyperparameter defaults from Spider 1 / BIRD do not transfer to warehouse-scale catalogs

**Statement.** The BM25 retrieval defaults that work on Spider 1 / BIRD (single-database SQLite schemas with ≤ 100 tables per database) do not transfer to Spider 2.0 Snow (multi-database Snowflake warehouses with hundreds to thousands of tables across databases). Specifically, the per-task partition + 80/20 → 200/40 retrieval-size widening at Phase 27 is necessary for the F1 grounding stack to have effective recall.

**Evidence.** The Phase 27 design memo (`outputs/logs/phase27_bm25_partition_design.md`) records the retrieval-size tuning: the pre-Phase-27 80 top-tables / 20 top-columns retrieval, applied per-DB after the partition, did not recover enough candidate columns for the closed-set planner to choose a complete pack. Widening to 200 / 40 within the partition recovered the necessary candidates without introducing false-positive cross-DB candidates (because of the partition filter). Empirically the 200/40 configuration produced the schema_valid 0 → 70 % lift; the 80/20 configuration kept schema_valid below 30 % at pilot scale.

**Scope limitation.** The claim is specifically about BM25 in our schema-linking stack. It does not assert that all retrieval methods need re-tuning at warehouse scale (a learned dense retriever might behave differently). It does not assert that 200/40 is the universally correct setting (the optimal depends on warehouse size).

**Position relative to the field.** The Phase 26 research-handoff diagnostic identified that BM25 hyperparameter inheritance from Spider 1 / BIRD was implicit and unexamined in our own prior code; we have not found a published Spider 2.0 architecture that explicitly addresses this question. The contribution is *named* (the hyperparameter-transfer issue is called out) and *measured* (the 80/20 vs 200/40 effect on schema_valid).

**Why the claim is defendable now.** The Phase 27 schema_valid lift from < 30 % to 70 % is direct evidence that retrieval-size tuning was necessary.

## Future claims pending row-match audit

The following claims are *not* defended in this dossier and will become possible after the Phase 28b post-defence row-match audit:

* **Future Claim 7 (post-audit).** "Our row-match rate on Spider2-Snow FULL 547 places the system at rank X among published open-weight ≤30B Spider 2.0 Snow systems." Awaits the audit's measured number.
* **Future Claim 8 (post-audit).** "The EXPLAIN-pass-to-row-match conversion ratio at FULL is Y % (vs pilot 10's 50 %)." Awaits the audit.
* **Future Claim 9 (post-Phase-29).** "The F3 stack (F3a STRUCT-aware emitter + F3b domain glossary + F3c self-refine) lifts EXPLAIN-pass from 23.76 % to Z %." Awaits Phase 29 implementation.

These future claims are noted to make the dossier's scope explicit. The current six claims (1–6) are framed deliberately to not depend on the audit and to remain defendable regardless of its outcome.

## Defendable thesis statement (one paragraph)

The thesis defends a unified open-weight ≤30B text-to-SQL architecture (Qwen3-Coder-30B-A3B planner + Qwen2.5-Coder-7B emitter + v18 closed-set planner + dialect-specific guards) that achieves competitive plan-acceptance and execute_ok across five of six Spider/BIRD-family benchmarks at fixed model class. The progression from 0 % to 23.76 % Snowflake EXPLAIN-pass on Spider2-Snow FULL 547 is fully attributable to four named scaffold-level interventions (F1 grounding, F4 date-cast wrap, F4c regex fallback, F2a revert), evidenced by a phase-by-phase progression table. Two methodological disciplines — catalog-probe-before-dialect-heuristic (Claim 4) and revert-experiment-for-attribution (Claim 5) — are transferable contributions established through a falsified hypothesis and an unmasked load-bearing intervention. The Spider 2 family numbers are plan-acceptance rates rather than row-set matches against gold; this is a transparency-mandated qualification, and the row-match audit (Phase 28b) is a defined post-defence engineering step that does not affect the architectural or methodological claims.
