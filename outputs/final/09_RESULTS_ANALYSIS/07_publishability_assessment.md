# Publishability Assessment — Tier-by-Tier

This document provides a brutally honest assessment of each benchmark result's *publishability tier* — whether it can be defended in a thesis defence today, whether it can be submitted to a conference workshop now, whether it can be submitted to a top-tier conference now, and what would need to change to move from one tier to the next. Companion files: leaderboard position at [05_leaderboard_position.md](05_leaderboard_position.md); thesis novelty claims at [08_thesis_novelty_claims.md](08_thesis_novelty_claims.md); methodology caveat at [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md).

The tier system used:

* **Tier A — top-tier publishable**: defensible against rigorous peer review at ACL / NeurIPS / VLDB level; numbers are leaderboard-comparable and competitive.
* **Tier B — workshop publishable**: defensible at conference workshops or ACL Findings; numbers are interesting but require explicit caveats or are not yet leaderboard-comparable.
* **Tier C — thesis defendable**: defensible in a master's / PhD thesis defence with proper qualification; not yet at the publication bar.
* **Tier D — research-in-progress**: not yet ready for external defence; needs additional measurement or implementation.

## 1. Spider 1.0 dev 1034: 94.0 % execute_ok

**Tier — Thesis defendable (C), publishable as a baseline comparison (B/C boundary).**

* The 94.0 % figure is reproducible (three runs at Phase 22, variance ≤ 0.3 pp), comparable to the published open-weight cluster (92–95 %), saturated at the cluster ceiling.
* Spider 1 is no longer a frontier benchmark — the 92–95 % band is saturated across many systems. A standalone publication on Spider 1 from our architecture would not be Tier A material because the result is not state-of-the-art.
* In our dossier the role of Spider 1 is *baseline confirmation*, not novelty — Claim 1 (unified architecture) uses Spider 1 as one of 5 demonstrations, not as a standalone contribution.
* What it takes to move from B/C to A: nothing useful — Spider 1 is saturated and additional architectural work on this benchmark would not produce a publishable advance.

## 2. BIRD FULL 1534: 87.9 % execute_ok (pending evaluator audit)

**Tier — Thesis defendable post-audit (C), workshop publishable (B), top-tier conditional on audit (B/A boundary).**

* The 87.9 % figure is reproducible (three runs at Phase 22, variance ≤ 0.5 pp), within the open-weight 86.7–89.1 % cluster.
* The pending evaluator audit is a 1-day Phase 28c task; if it confirms the figure, the publishability tier holds.
* If the audit reveals a discrepancy (e.g. our run used a slightly different evaluator configuration that produces a higher number than the canonical), the headline might shift down by a few points. The qualitative architectural claims are not affected; only the BIRD-specific number is.
* What it takes to move from C/B to A: the audit must clear, and additional Spider 1-style or BIRD-specific architectural work would need to push the figure to ≥ 91 % to challenge the closed-source frontier band. This is not on the current roadmap.

## 3. Spider2-Lite-BQ FULL 205: 34.6 % BigQuery dry_run-pass (\*)

**Tier — Thesis defendable (C), workshop publishable with cross-metric disclosure (B), top-tier blocked by metric issue (D for top-tier).**

* The 34.6 % figure is reproducible (run at Phase 24, single canonical artefact), in the open-weight Spider-Agent baseline band.
* The cross-metric situation (BigQuery `dry_run`-pass vs leaderboard row-match) blocks Tier A publication. No top-tier venue would accept a result that explicitly does not use the leaderboard metric without a methodological-disclosure argument that may not be accepted.
* The honest workshop-tier framing is "BigQuery `dry_run`-pass rate of 34.6 % on Spider2-Lite-BQ FULL 205 places the system in the open-weight Spider-Agent baseline band; row-match audit deferred to Phase 28b."
* What it takes to move from C/B to A: complete the Phase 28b row-match audit. If the row-match figure lands at ≥ 30 %, the result is genuinely Tier A material (above the open-weight baseline cluster).

## 4. Spider2-Lite-Snow partial (n=40 of 207)

**Tier — Research-in-progress (D) for partial, deferred to Phase 28b for full.**

* The partial n=40 result is not publishable in any form because the sample is non-random (first 40 by runner task order) and is too small to extrapolate reliably to FULL 207.
* The pilot 10 result (4/10 EXPLAIN-pass) is publishable as a *pilot-scale architecture-progression demonstration* but not as a Spider 2.0 benchmark result.
* What it takes: complete the Spider2-Lite-Snow FULL 207 run (30–60 min warehouse time, runner unchanged) plus the Phase 28b row-match audit.

## 5. Spider2-Snow FULL 547: 23.76 % Snowflake EXPLAIN-pass (\*)

**Tier — Thesis defendable (C), workshop publishable with cross-metric disclosure (B), top-tier blocked by metric issue (D for top-tier).**

* The 23.76 % figure is reproducible (canonical run `snow_full_v28_revert_a`, single artefact), in the open-weight Spider-Agent baseline band. This is the lane with the most distinctive architectural progression in the dossier (0 → 23.76 % via F1+F4+F4c+F2a-revert).
* The same cross-metric situation as Lite-BQ blocks Tier A. The Snow case is the most acute because Spider 2.0 Snow is the lane where the leaderboard story is most active (Genloop 96.70 %, ReFoRCE+o3 62.89 %, Spider-Agent+Qwen3-Coder 31.08 %) — comparing 23.76 % EXPLAIN-pass to 31.08 % row-match invites the obvious objection.
* The honest workshop-tier framing is well established (see [05_leaderboard_position.md](05_leaderboard_position.md)).
* What it takes to move from C/B to A: complete the Phase 28b row-match audit. If the row-match figure lands at ≥ 20 %, the result is competitive with Spider-Agent + Qwen3-Coder and Tier A. If it lands at 12–18 % (the pilot10 projection band), the result is mid-pack open-weight ≤30B and B-tier with the right framing. If below 12 %, the architectural progression is still defensible but the leaderboard placement narrative weakens.
* **Conditional Tier A path**: if Phase 28b row-match ≥ 20 % AND Phase 29 F3a/F3b/F3c lifts EXPLAIN-pass to 35+ %, the result is a Tier A workshop / conference contribution centered on the F1+F4+F4c architectural narrative.

## 6. Spider2-DBT FULL 68: 13.2 % task_success

**Tier — Thesis defendable (C), workshop publishable as a baseline (C/B), not novel for publication (D for top-tier).**

* The 13.2 % figure is at the Spider-Agent open-weight baseline ceiling. No published open-weight ≤30B system has gone meaningfully higher (Spider-Agent + Qwen3-Coder is at 14.1 %, within methodology variance).
* The DBT lane in our dossier serves a *negative-result-narrative* role: it shows that the unified SQL architecture, applied directly to DBT without the scaffold redesign, lands at the open-weight ceiling and is scaffold-bound, not model-bound.
* What it takes to move from C/B to A: implement Phase 31 (dbt-parse pre-check + manifest-aware planner + content-test feedback retry) and demonstrate a lift to ≥ 25 %. The Phase 31 design is described in [04_spider2_dbt_analysis.md](04_spider2_dbt_analysis.md) §7 and the projected lift is 25–32 %. If implemented and confirmed, Spider2-DBT is the strongest standalone publication candidate from the dossier — the project-level integration story is genuinely novel.

## 7. Architectural contribution (unified architecture + scaffold-dominance claims)

**Tier — Workshop publishable now (B), top-tier conditional on additional benchmark (B/A boundary).**

* The unified-architecture claim (Claim 1) and scaffold-dominance claim (Claim 2) are defensible independently of the row-match audit because they are about the *progression* and the *cross-benchmark coverage*, not about any single benchmark's absolute number.
* For a top-tier publication on the architecture, the natural framing is "scaffold-driven gains at fixed open-weight model class, demonstrated on 5 benchmark families." This is workshop-tier as-is; for top-tier (ACL / NeurIPS), additional evidence would be useful: an ablation study showing the scaffold contributions in isolation, and a comparison against an open-weight system that lacks the scaffold (e.g. raw Qwen3-Coder-30B + simple prompting on the same benchmarks).
* The ablation work is approximately 1 month of additional engineering and is not on the current roadmap.

## 8. Methodological contributions (catalog-probe + revert-experiment disciplines)

**Tier — Workshop publishable independently (B), top-tier as a methodological note (B/A).**

* Claim 4 (catalog-probe-before-dialect-heuristic) and Claim 5 (revert-experiment-for-attribution) are defensible from the F2a falsification narrative alone, without dependency on the row-match audit or further architectural work.
* A standalone workshop-tier paper on the F2a story is plausible: "Catalog-Probe Discipline for Dialect Heuristics: A Negative Result from Spider2-Snow" or similar. This would document the falsification, the methodological lesson, and the broader applicability to dialect-rewrite work.
* For top-tier, the methodological note would need to be embedded in a larger architecture paper (where Claim 1–6 together form the contribution) rather than published standalone — top venues prefer integrated contributions over single-lesson methodology notes.

## 9. Strongest defendable thesis statement (publication strategy)

The thesis defence and the post-defence publication strategy should foreground the *unified-architecture-plus-scaffold-progression* claim (Claims 1+2) as the headline contribution, supported by the *methodological discipline* claims (Claims 4+5) as a secondary contribution, with the per-benchmark numbers as evidence rather than as standalone results.

The natural publication outputs after Phase 28b + Phase 29:

* **Primary paper (post-Phase-28b + post-Phase-29)**: "Scaffold-Driven Open-Weight Text-to-SQL Across Six Benchmark Families: Unified Architecture, F1 Grounding, and Catalog-Probe Methodology." Target venue: ACL / NAACL / EMNLP main track or VLDB / SIGMOD.
* **Workshop paper (post-Phase-28b)**: "F2a Falsified — Catalog-Probe Discipline for Dialect Heuristics on Production Snowflake Schemas." Target venue: any text-to-SQL workshop.
* **Workshop paper (post-Phase-31)**: "DBT Scaffold Redesign: Project-Level Text-to-SQL via dbt-Parse Pre-Check, Manifest-Aware Planning, and Test-Feedback Retry." Target venue: same.

Each output is independently publishable; together they form the thesis's claim to a complete contribution at the open-weight ≤30B scale. The thesis itself (the current dossier) is the consolidated record of the work that produced these outputs.

## 10. Honest assessment of dossier-as-of-deadline

What this dossier can defend today, at thesis defence:

* The architecture and methodology contributions (Claims 1–6) at C/B tier.
* The progression-driven Spider 2 Snow narrative as plan-acceptance at B tier with proper framing.
* The classical-lane numbers as direct-comparable B/C tier.

What this dossier cannot defend at A tier today:

* The row-match leaderboard position on Spider 2 SQL lanes (Phase 28b blocks this).
* A standalone top-tier publication centered on any single benchmark.
* An ablation study isolating scaffold-component contributions (Phase 27 metric did this implicitly; a formal ablation has not been run).

The path from today's C/B tier to A tier is the Phase 28b audit (lifts Spider 2 SQL lanes to B/A boundary), Phase 29 F3 (lifts Spider 2 SQL absolute numbers), Phase 31 (creates a standalone DBT publication candidate), and an ablation study (clarifies Claim 2). All are post-defence work and are documented in [../06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md](../06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md) §3 (forward path).

The defendable position today is *honest C/B tier* across all benchmarks with explicit qualification, supported by methodologically novel discipline contributions defensible at workshop tier independently. This is sufficient for the thesis defence; it is the realistic starting point for the post-defence publication trajectory.
