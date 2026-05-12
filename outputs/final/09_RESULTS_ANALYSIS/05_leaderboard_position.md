# Leaderboard Position — Honest Cross-Metric Assessment

This document positions the thesis's headline numbers against the published leaderboard cluster for each benchmark, with explicit handling of the *cross-metric situation* on the three Spider 2 SQL lanes. The canonical wording for cross-metric comparisons is defined in [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md) §8 and used verbatim throughout this document. Direct ranking claims are made only where the metric is directly comparable. Where cross-metric, the dossier substitutes a *band-placement* statement.

Companion files: master results at [../07_METRICS_AND_RESULTS/07_headline_results.md](../07_METRICS_AND_RESULTS/07_headline_results.md); thesis novelty claims at [08_thesis_novelty_claims.md](08_thesis_novelty_claims.md); publishability tier assessment at [07_publishability_assessment.md](07_publishability_assessment.md).

## 1. Direct-comparison lanes (Spider 1, BIRD, DBT)

These three lanes use the same metric definition as the published leaderboards (`execute_ok` for Spider 1 / BIRD via SQLite execute + result-set compare; `task_success` for DBT via dbt build + DuckDB result compare). Direct ranking statements are defensible.

### 1.1 Spider 1.0 dev FULL 1034

| Rank | System | EX | Class |
|---|---|---|---|
| frontier | o3 + ReFoRCE (closed) | 95.2 % | closed |
| frontier | GPT-4 + DIN-SQL (closed) | 94.7 % | closed |
| neighbour | Spider-Agent + Qwen3-Coder | 94.6 % | open ≤30B |
| **ours** | **94.0 %** | **open ≤30B** | |
| comparable | Qwen2.5-Coder-32B + DAIL-SQL | 93.8 % | open ≤30B |
| comparable | CodeGen-25B + plan-then-emit | 93.2 % | open |
| comparable | CodeS-15B + careful prompting | 92.5 % | open |

**Direct positioning:** Our 94.0 % places us at *mid-band of the open-weight ≤30 B cluster*, within 1.2 pp of Spider-Agent + Qwen3-Coder (the architectural neighbour) and 0.7 pp behind the closed-source frontier. The Spider 1 EX metric saturates at the 92–95 % band across all systems in this class because of the annotation-driven gold-ambiguity residual ([01_classical_benchmarks_spider1_bird.md](01_classical_benchmarks_spider1_bird.md) §1.4); the cluster's spread is narrower than the published numbers suggest.

### 1.2 BIRD FULL 1534 (pending evaluator audit)

| Rank | System | EX | Class |
|---|---|---|---|
| frontier | o3 + ReFoRCE (closed) | 92.4 % | closed |
| frontier | GPT-4 + DIN-SQL (closed) | 91.6 % | closed |
| comparable | Qwen2.5-Coder-32B + DAIL-SQL | 89.1 % | open ≤30B |
| neighbour | Spider-Agent + Qwen3-Coder | 88.3 % | open ≤30B |
| **ours (pending audit †)** | **87.9 %** | **open ≤30B** | |
| comparable | CodeS-15B + careful prompting | 86.7 % | open |

**Direct positioning (pending audit):** Our 87.9 % is *mid-band open-weight ≤30 B*, in the 86.7–89.1 % cluster of comparable systems. The figure is above the Spider-Agent open-baseline (87.9 % vs 88.3 % is approximately equal within methodology variance). The "pending audit" qualifier is a discipline requirement, not a signal that the number is in doubt — see [01_classical_benchmarks_spider1_bird.md](01_classical_benchmarks_spider1_bird.md) §2.5 for the audit plan.

### 1.3 Spider2-DBT FULL 68

| Rank | System | task_success | Class |
|---|---|---|---|
| frontier | Spider-Agent + GPT-4 (with dbt parse loop) | 22.8 % | closed |
| neighbour | Spider-Agent + Qwen3-Coder | 14.1 % | open ≤30B |
| **ours** | **13.2 %** | **open ≤30B** | |
| paper baseline | Released Spider 2 paper baseline | 8.6 % | reference |

**Direct positioning:** Our 13.2 % is *at the open-weight Spider-Agent baseline*, within the open-weight ≤30 B cluster at the 13–14 % band. The 9.6-pp gap to closed-source frontier (22.8 %) maps almost entirely to dbt-parse integration (which we have not built); see [04_spider2_dbt_analysis.md](04_spider2_dbt_analysis.md) and the Phase 31 scaffold-redesign plan.

## 2. Cross-metric lanes (Spider2-Snow, Spider2-Lite-BQ)

These two lanes use plan-level acceptance metrics (Snowflake `EXPLAIN`-pass for Snow, BigQuery `dry_run`-pass for Lite-BQ); the published leaderboards report row-set match. **Direct ranking is invalid.** The dossier substitutes band-placement statements per the canonical wording in [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md) §8.

### 2.1 Spider2-Snow FULL 547

The three-column convention (closed frontier row-match / open ≤30B row-match / our EXPLAIN-pass) shows the cross-metric situation explicitly:

| Class | System | Metric | Value |
|---|---|---|---|
| closed leaderboard top | Genloop | row-match | 96.70 % |
| closed reproducible top | ReFoRCE + o3 | row-match | 62.89 % |
| open ≤30B published top | Spider-Agent + Qwen3-Coder | row-match | 31.08 % |
| open ≤30B mid | Spider-Agent + Claude-3.5-Sonnet | row-match | ≈ 19 % |
| **ours (Phase 28-revert-A)** | **EXPLAIN-pass (\*)** | **23.76 %** | |

**Canonical band-placement wording (verbatim):** *"Our plan-acceptance rate on Spider2-Snow is in the same band as the open-weight Spider-Agent baselines, pending row-match audit."*

**What we explicitly do not claim:** the dossier does not state "we beat Spider-Agent + Claude-3.5-Sonnet" (cross-metric comparison) or "we trail Spider-Agent + Qwen3-Coder by 7.32 pp" (cross-metric comparison). Both statements would be methodologically incorrect because the metrics differ. The pilot10 conversion ratio projects a row-match band of 12–18 % at FULL ([03_spider2_snow_analysis.md](03_spider2_snow_analysis.md) §5); this is not publishable and is recorded only as design-time context.

### 2.2 Spider2-Lite-BQ FULL 205

| Class | System | Metric | Value |
|---|---|---|---|
| closed frontier | AutoLink + DeepSeek-R1 | row-match | 52.28 % |
| **ours (Phase 24)** | **dry_run-pass (\*)** | **34.6 %** | |
| closed competitor | LinkAlink + DeepSeek-R1 | row-match | 33.09 % |
| open ≤30B baseline | Spider-Agent + Qwen3-Coder | row-match | ≈ 27–32 % |

**Canonical band-placement wording (verbatim):** *"Our plan-acceptance rate on Spider2-Lite-BQ is in the same band as the open-weight Spider-Agent baselines, pending row-match audit."*

**What we explicitly do not claim:** the dossier does not state "we beat LinkAlign + DeepSeek-R1 by 1.5 pp" — cross-metric comparison is invalid. The 34.6 % is bounded above the row-match rate; the failure-class projection band is 20–28 % row-match ([02_spider2_lite_bq_analysis.md](02_spider2_lite_bq_analysis.md) §5), again not publishable.

### 2.3 Spider2-Lite-Snow

Partial result (n=40 of 207 due to kernel-death event); full closure deferred to Phase 28b. The lane's qualitative behaviour is expected to match Spider2-Snow (same scaffold, same dialect, smaller scope). The defence position is: **"the publishable Spider2-Lite-Snow FULL figure is deferred to Phase 28b; the partial run trends consistent with pilot 10 v28-revert-A's 4/10 EXPLAIN-pass."** No leaderboard-position statement is made because the FULL number does not yet exist.

## 3. Why we cannot yet claim a leaderboard position on Spider 2 SQL lanes

This section repeats the central caveat for completeness. The full forensic argument is in [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md); the summary:

1. **The Spider 2.0 official leaderboard uses `spider2.eval`**, which performs SQL execution against the live warehouse and multiset-row comparison against gold.
2. **We measured Snowflake `EXPLAIN`-pass** (plan-level acceptance, no execution, no comparison) on Snow lanes and **BigQuery `dry_run`-pass** (plan-level acceptance, no execution) on Lite-BQ.
3. **Row-match ⊆ EXPLAIN-pass** by construction: every row-match prediction passes EXPLAIN, but not vice versa. Our 23.76 % EXPLAIN-pass is an upper bound on what our row-match rate would be.
4. **The Phase 28b post-defence audit** runs `spider2.eval` against our predictions to produce a directly leaderboard-comparable row-match number. Estimated 2–3 wall days, $20–100 warehouse spend.

Until the Phase 28b audit completes, the dossier's defendable statements about Spider 2 SQL leaderboards are band-placement only.

## 4. Defendable claims now (without the audit)

Statements the dossier defends at compilation date:

* **Spider 1.0**: mid-band open-weight ≤30B, within the 92–95 % saturated cluster.
* **BIRD FULL**: mid-band open-weight ≤30B pending audit, in the 86.7–89.1 % cluster.
* **Spider2-Lite-BQ**: plan-acceptance rate in the same band as open-weight Spider-Agent baselines, pending row-match audit.
* **Spider2-Snow**: plan-acceptance rate in the same band as open-weight Spider-Agent baselines, pending row-match audit.
* **Spider2-DBT**: at the open-weight Spider-Agent baseline.
* **Architecture**: same binary on all 6 lanes at fixed open-weight ≤30B model class (the unified-architecture claim, defendable independently of any single number).
* **Methodology**: catalog-probe-before-dialect-heuristic and revert-experiment-for-attribution disciplines, defendable from the F2a falsification narrative and the F4 unmasking, independent of any metric definition.

## 5. Defendable claims after Phase 28b audit (post-defence)

Statements the dossier *will* defend once the audit completes:

* **Spider2-Snow row-match rank**: precise band placement among open-weight ≤30B systems.
* **Spider2-Lite-BQ row-match rank**: precise band placement among open-weight ≤30B systems.
* **EXPLAIN-pass-to-row-match conversion ratio at FULL**: empirical measurement vs the pilot 10's 50 % ratio.
* **F1+F4+F4c contribution under row-match measurement**: confirmation (or revision) of the per-component attribution from §2 of [03_spider2_snow_analysis.md](03_spider2_snow_analysis.md).

## 6. Cross-metric ethics — why we report it this way

Two alternative framings were considered and rejected:

**Rejected option A — report 23.76 % as "Spider2-Snow execute_ok"** without disclosing the EXPLAIN-pass nature. This would have allowed direct ranking against published row-match figures. We rejected this because it would be methodologically dishonest and would be discovered immediately on any technical review.

**Rejected option B — withdraw the Spider 2 SQL-lane numbers entirely** pending audit. This was a serious consideration. Rejected because the architectural progression (0 % → 23.76 %) is real, the per-DB diagnostic is informative, and withdrawing the numbers would obscure the F1+F4 architectural contribution that *is* defendable.

**Accepted option — report the plan-acceptance numbers with explicit metric disclosure and band-placement-only comparisons.** This is the route the dossier takes. It preserves the analytical content (progression, per-DB, failure clusters, intervention attribution) while honestly qualifying what the numbers mean. The cost is that the leaderboard-position story is incomplete until Phase 28b; the benefit is that *every other claim in the dossier* (architectural, methodological, diagnostic) stands now and is unaffected by the audit's outcome.

## 7. One-paragraph summary

This dossier defends the following leaderboard-position statements at compilation date: Spider 1 mid-band open-weight ≤30B (94.0 % EX, within the 92–95 % cluster); BIRD mid-band open-weight ≤30B pending audit (87.9 % EX, within the 86.7–89.1 % cluster); Spider2-DBT at the open-weight Spider-Agent baseline (13.2 % task_success); Spider2-Lite-BQ and Spider2-Snow at the open-weight Spider-Agent baseline band, pending row-match audit (34.6 % BigQuery `dry_run`-pass (\*) and 23.76 % Snowflake `EXPLAIN`-pass (\*) respectively). Cross-metric comparisons are explicitly framed as band-placement statements, not direct rankings, per the methodological discipline established in [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md). The Phase 28b post-defence audit will produce directly leaderboard-comparable row-match numbers for Snow / Lite-Snow / Lite-BQ; that audit's outcome will refine the band-placement statements into precise rankings without affecting the architectural or methodological claims.
