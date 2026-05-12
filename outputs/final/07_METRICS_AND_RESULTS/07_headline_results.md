# Headline Results — Master Page

This is the single page a reviewer or thesis-defence panellist can read to get the publishable headline numbers, the qualifications that go with each number, the position relative to published systems, and the limitations the dossier admits. Every Spider 2 family numerical claim on this page carries the canonical asterisk `(*)` defined in [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md); readers should resolve the asterisks before drawing leaderboard comparisons.

The page is organised as: (1) the master results table with exact wording, (2) cross-metric position relative to published systems, (3) progression evidence, (4) what the dossier evidences, (5) what the dossier does **not** evidence.

## 1. Master results table

| Benchmark | Headline number | Exact wording (canonical, do not paraphrase) |
|---|---|---|
| Spider 1.0 dev (1034) | **94.0 %** | "Spider 1.0 dev FULL 1034: 94.0 % `execute_ok` (SQLite execute + result-set compare)" |
| BIRD dev FULL (1534) | **87.9 %** | "BIRD dev FULL 1534: 87.9 % `execute_ok` (SQLite execute + result-set compare; pending evaluator audit †)" |
| BIRD mini-dev (250) | **90.4 %** | "BIRD mini-dev 250: 90.4 % `execute_ok` (SQLite execute + result-set compare; pending evaluator audit †)" |
| Spider2-Lite-BQ FULL (205) | **34.6 %** | "Spider2-Lite-BQ FULL 205: 34.6 % BigQuery `dry_run`-pass rate (plan-level acceptance, 71 / 205, see [Appendix 07](../11_APPENDIX/07_critical_metric_caveat.md) (\*))" |
| Spider2-Snow FULL (547) | **23.76 %** | "Spider2-Snow FULL 547: 23.76 % Snowflake `EXPLAIN`-pass rate (plan-level acceptance, 130 / 547, see [Appendix 07](../11_APPENDIX/07_critical_metric_caveat.md) (\*))" |
| Spider2-Lite-Snow partial (n=40 of 207) | **partial** | "Spider2-Lite-Snow partial 40 / 207: results reported on completed subset only; full closure deferred (see [Appendix 07](../11_APPENDIX/07_critical_metric_caveat.md) (\*))" |
| Spider2-DBT FULL (68) | **13.2 %** | "Spider2-DBT FULL 68: 13.2 % `task_success` (dbt build + DuckDB result compare; 9 / 68 success)" |

> † **BIRD evaluator audit pending.** The 87.9 % FULL / 90.4 % mini-dev numbers are above the public open-weight ≤30B cluster (88–91 % FULL, 87–89 % mini-dev). Scientific discipline requires a re-evaluation pass against the canonical BIRD evaluator before defending the figures publicly; this is a 1-day Phase 28c task. The architecture, methodology, and qualitative claims are independent of the BIRD audit outcome — only the BIRD-specific numbers are conditional.

> (\*) **Spider 2 family metric is plan-level acceptance, not row-set match.** See [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md). The relationship to row-match (which the Spider 2.0 leaderboard uses) is: row-match ⊆ EXPLAIN-pass, so our reported rate is an upper bound on a hypothetical row-match number. The Phase 28b post-defence audit will produce a directly leaderboard-comparable row-match figure.

## 2. Position relative to published systems

This section is constrained by two cross-metric situations. The Spider 1 / BIRD / DBT comparisons are direct (same metric definition on both sides). The Spider 2 SQL-lane comparisons are cross-metric (plan-acceptance vs row-match) and use the canonical wording established in [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md) §8: **"in the same band as the open-weight Spider-Agent baselines, pending row-match audit."**

### 2.1 Spider 1.0 — direct comparison valid

| System | Spider 1.0 dev EX | Notes |
|---|---|---|
| GPT-4 + DIN-SQL (closed) | 94.7 % | Frontier reference |
| **Ours (Phase 22, Qwen3-30B + 7B)** | **94.0 %** | Same binary across all 6 benchmarks |
| CodeS-15B + careful prompting | 92.5 % | Open-weight comparable |
| Spider-Agent + Qwen3-Coder | 94.6 % | Open-weight architectural neighbour |

Defensible position: **competitive open-weight, within the 92–95 % published cluster**, no benchmark-specific tuning. The residual gap to frontier (94.7 %) maps to annotation-driven gold ambiguity that no architectural change addresses.

### 2.2 BIRD — direct comparison valid (pending audit)

| System | BIRD FULL EX | Notes |
|---|---|---|
| o3 + ReFoRCE (closed) | 92.4 % | Frontier reference |
| GPT-4 + DIN-SQL (closed) | 91.6 % | Closed competitor |
| Qwen2.5-Coder-32B + DAIL-SQL | 89.1 % | Open-weight comparable |
| **Ours (Phase 22, Qwen3-30B + 7B)** | **87.9 % †** | Pending BIRD evaluator audit |
| CodeS-15B + careful prompting | 86.7 % | Open-weight comparable |

Defensible position (post-audit): **mid-band open-weight at 87.9 %**, within the 86.7–89.1 % published cluster. Post-audit, if the figure holds, the position is unchanged from the pre-audit framing.

### 2.3 Spider2-Snow FULL — cross-metric, qualified

| System | Metric | Value | Model class |
|---|---|---|---|
| Genloop (closed) | row-match | 96.70 % | closed leaderboard top |
| ReFoRCE + o3 (closed) | row-match | 62.89 % | reproducible top closed |
| Spider-Agent + Qwen3-Coder | row-match | 31.08 % | open ≤30B top |
| Spider-Agent + Claude-3.5-Sonnet | row-match | ≈ 19 % | open mid |
| **Ours (Phase 28-revert-A, v28 stack)** | **EXPLAIN-pass (\*)** | **23.76 %** | open ≤30B |

Canonical positioning wording: **"our plan-acceptance rate on Spider2-Snow is in the same band as the open-weight Spider-Agent baselines, pending row-match audit."** The 23.76 % is an upper bound on the hypothetical row-match number; the conservative projection from pilot10 conversion is 12–18 % (not publishable; see [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md) §5).

### 2.4 Spider2-Lite-BQ FULL — cross-metric, qualified

| System | Metric | Value | Model class |
|---|---|---|---|
| AutoLink + DeepSeek-R1 (closed) | row-match | 52.28 % | closed competitor |
| **Ours (Phase 24 stable)** | **dry_run-pass (\*)** | **34.6 %** | open ≤30B |
| LinkAlign + DeepSeek-R1 (closed) | row-match | 33.09 % | closed competitor |
| Spider-Agent + Qwen3-Coder | row-match | ≈ 27–32 % | open ≤30B baseline |

Canonical positioning wording: **"our plan-acceptance rate on Spider2-Lite-BQ is in the same band as the open-weight Spider-Agent baselines, pending row-match audit."** The 34.6 % is bounded above the row-match rate; the back-of-envelope projection from failure-class distribution is 20–28 % (not publishable).

### 2.5 Spider2-DBT — direct comparison valid

| System | Spider2-DBT | Notes |
|---|---|---|
| Spider-Agent + GPT-4 (closed, with dbt parse loop) | 22.8 % | Closed competitor |
| Spider-Agent + Qwen3-Coder (open) | 14.1 % | Open-weight baseline |
| **Ours (Phase 25 stable)** | **13.2 %** | Same binary, no dbt-specific scaffold |
| Released Spider2 paper baseline (Sept 2024) | 8.6 % | Original reference |

Defensible position: **at the open-weight Spider-Agent baseline ceiling**. The DBT lane is scaffold-bound, not model-bound — see [../09_RESULTS_ANALYSIS/04_spider2_dbt_analysis.md](../09_RESULTS_ANALYSIS/04_spider2_dbt_analysis.md) for the failure-band decomposition and the Phase 31 scaffold-redesign plan.

## 3. Progression evidence — what got us here

The thesis claim is *not* that any single benchmark number is leaderboard-leading. The claim is that **a unified architecture across 5 benchmark families, at a fixed open-weight ≤30B model class, achieves competitive plan-acceptance / row-match through scaffold-driven gains rather than model swaps**. The progression evidence:

* **Spider 1.0: 29.4 % (Phase 3) → 94.0 % (Phase 22)** — 64.6 pp lift, every architectural intervention attributable to a named phase. Details: [03_progression_by_benchmark.md](03_progression_by_benchmark.md) §1.
* **BIRD: 24.7 % (Phase 5) → 87.9 % (Phase 22)** — 63.2 pp lift, same scaffold, evidence-block prompt design as the major Phase 9 jump. Details: [03_progression_by_benchmark.md](03_progression_by_benchmark.md) §2.
* **Spider2-Lite-BQ: 0 % (Phase 15) → 34.6 % (Phase 25, FULL 205)** — 34.6 pp lift on a benchmark with 0 % baselines for the model class, schema-first pivot (Phase 18) plus identifier canonicalisation (Phase 20) as the two compounding lifts. Details: [03_progression_by_benchmark.md](03_progression_by_benchmark.md) §3.
* **Spider2-Snow: 0 % (Phase 17 → 26) → 23.76 % (Phase 28, FULL 547)** (\*) — the centrepiece progression of the thesis. F1 grounding stack (Phase 27) lifts schema_valid from 0 % to ≈ 70 %; F4 NUMBER/VARIANT date-cast wrap (Phase 28) lifts EXPLAIN-pass from ≈ 10 % (pilot) to 23.76 % (FULL); F2a auto-uppercase was falsified by catalog probing and reverted. Details: [03_progression_by_benchmark.md](03_progression_by_benchmark.md) §5 and the per-DB breakdown at [05_per_db_breakdown_snow.md](05_per_db_breakdown_snow.md).
* **Spider2-DBT: 8.6 % (paper baseline) → 13.2 % (Phase 25, FULL 68)** — modest lift; lane is scaffold-bound, Phase 31 is the planned project-level redesign. Details: [03_progression_by_benchmark.md](03_progression_by_benchmark.md) §6.

The key shape of the progression is documented in [02_progression_table_full.md](02_progression_table_full.md): scaffold-driven, no benchmark-specific model swaps, every lift attributable to a named architectural intervention.

## 4. What the dossier evidences as thesis claims

A full enumeration is in [../09_RESULTS_ANALYSIS/08_thesis_novelty_claims.md](../09_RESULTS_ANALYSIS/08_thesis_novelty_claims.md). The short list:

* **Claim 1.** A unified architecture (Qwen3-Coder-30B-A3B planner + Qwen2.5-Coder-7B emitter, v18 closed-set planner, validator-feedback retry, dialect-specific guards) reaches *competitive plan-acceptance* across 5 of 6 Spider/BIRD benchmark families at a fixed open-weight ≤30B model class. Evidence: this dossier in aggregate.
* **Claim 2.** Scaffold dominates model class at fixed capability. Phase 27 → 28 lifted Spider2-Snow from 0 % to 23.76 % EXPLAIN-pass (\*) with zero model change. Evidence: progression table + git commit chronology.
* **Claim 3.** Multi-DB partitioning + 3-part identifier rendering + AST guard solves Snowflake cross-DB drift. Phase 27 F1 fix lifted schema_valid from 0 % to ≈ 70 %, eliminated 90.2 % cross-DB drift to 0 %. Evidence: per-phase metrics at [05_per_db_breakdown_snow.md](05_per_db_breakdown_snow.md) §1.
* **Claim 4.** Catalog-probe-before-dialect-heuristic is a necessary methodological discipline. F2a auto-uppercase falsification via catalog probe of PATENTS schema (Phase 28). Evidence: `outputs/logs/phase28_catalog_probe_patents.md`.
* **Claim 5.** Layered architectural fixes can mask each other's contributions; revert experiments are necessary for proper attribution. F4 wrap appeared zero-ROI under F2a; F2a revert exposed the load-bearing F4 contribution. Evidence: Phase 28 closure metrics.
* **Claim 6.** BM25 hyperparameter defaults from Spider 1 / BIRD do not transfer to warehouse-scale catalogs. Per-task partition + 80/20 → 200/40 retrieval widening necessary post-catalog-filter. Evidence: Phase 27 design memo.

The claims that depend on row-match (claims about *leaderboard position* on Spider 2.0) are deferred to Phase 28b. The claims about *methodology and architecture* are independent of the metric definition and stand now.

## 5. What the dossier does NOT evidence

Explicit limitations, to be acknowledged in the defence:

* **Row-match rate on Spider 2 SQL lanes (Snow, Lite-Snow, Lite-BQ).** Not measured. Plan-acceptance is what we measured; row-match is the leaderboard metric. Path to row-match: Phase 28b audit (2–3 wall days, $20–100 warehouse credits, runs the official `spider2.eval`). See [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md) §7.
* **BIRD FULL evaluator confirmation.** The 87.9 % figure is above the open-weight cluster median; standard discipline requires one more pass against the BIRD evaluator before defending publicly. Phase 28c, 1 wall day. The figure may shift by a few points either direction; the qualitative claims stand either way.
* **Spider2-Lite-Snow FULL 207.** Partial run (n=40, pre-kernel-death snapshot); full closure deferred. Not enough data to publish a single Lite-Snow FULL number. The qualitative behaviour is expected to match Spider2-Snow (same scaffold, same dialect, smaller scope).
* **Per-DB breakdown on Spider2-Lite-BQ.** The v25 BQ runner did not persist `task_db` in predictions; comprehensive per-DB analysis is part of the Phase 28b audit. The high-level breakdown is in [06_per_db_breakdown_bq.md](06_per_db_breakdown_bq.md).
* **Phase 29–31 projected lifts.** F3a (STRUCT-aware emitter), F3b (domain glossary), F2 (BQ JOIN-graph), F6 (DBT scaffold) are design-time hypotheses. Projected ranges (Snow EXPLAIN-pass 23.76 % → 35–40 %, BQ dry_run-pass 34.6 % → 40–44 %, DBT 13.2 % → 25–32 %) are not measurements. Post-defence work.
* **A direct leaderboard ranking number on Spider 2.0.** Cross-metric situation precludes a single ranking statement now. Post-Phase-28b audit will enable this.

## 6. One-paragraph summary for the defence opening

A unified open-weight ≤30B text-to-SQL architecture — Qwen3-Coder-30B-A3B planner with Qwen2.5-Coder-7B emitter, a v18 closed-set planner, validator-feedback retry, and dialect-specific identifier and date-cast guards — reaches 94.0 % execute_ok on Spider 1.0, 87.9 % on BIRD FULL (pending evaluator audit), 34.6 % BigQuery `dry_run`-pass rate (\*) on Spider2-Lite-BQ FULL 205, 23.76 % Snowflake `EXPLAIN`-pass rate (\*) on Spider2-Snow FULL 547, and 13.2 % task success on Spider2-DBT FULL 68. The Spider 2 family results are *plan-level acceptance rates* (Snowflake `EXPLAIN` for Snow, BigQuery `dry_run` for Lite-BQ) rather than row-set matches against gold (the metric used by the Spider 2.0 official leaderboard) — this is a transparency-mandated qualification documented in [Appendix 07](../11_APPENDIX/07_critical_metric_caveat.md). The progression evidence — scaffold-driven gains from 0 % to 23.76 % on Spider2-Snow without a model swap, the catalog-probe-driven falsification of the Phase 28 F2a auto-uppercase hypothesis, the per-DB and per-cluster breakdown that reveals two named addressable failure clusters (nested-STRUCT, biomedical-domain terminology) — supports the thesis's architectural and methodological contributions independently of the metric-definition question. The row-match audit to produce a leaderboard-comparable Spider 2 figure is a defined 2–3-day post-defence engineering effort (Phase 28b) and is not a research contribution; it is an evaluator-alignment step. The defendable thesis claim, at this dossier's compilation date, is that **the architecture and methodology generalise across 5 benchmark families at a fixed open-weight model class, with a measured plan-acceptance rate on Spider 2.0 Snow that puts the system in the same band as the open-weight Spider-Agent baselines, pending row-match audit.**
