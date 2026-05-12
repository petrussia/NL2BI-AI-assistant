# Classical Benchmarks — Spider 1.0 and BIRD Results Analysis

This document analyses our final results on the two classical, single-query, single-engine text-to-SQL benchmarks: Spider 1.0 and BIRD. These two benchmarks have been the field's reference points since 2018 and 2023 respectively; together they capture roughly seven years of "classical" text-to-SQL research. Our published numbers are 94.0 % EX on Spider 1.0 and 87.9 % EX on BIRD FULL / 90.4 % on BIRD mini-dev. This document explains what those numbers mean, how reliable they are, where the residual gap sits, and how our system compares to the published competitive set.

Companion documents: metric definitions at [../07_METRICS_AND_RESULTS/01_metric_definitions.md](../07_METRICS_AND_RESULTS/01_metric_definitions.md); progression table at [../07_METRICS_AND_RESULTS/02_progression_table_full.md](../07_METRICS_AND_RESULTS/02_progression_table_full.md); benchmark descriptions at [../03_BENCHMARKS/01_spider1.md](../03_BENCHMARKS/01_spider1.md) and [../03_BENCHMARKS/02_bird.md](../03_BENCHMARKS/02_bird.md); failure taxonomy at [../07_METRICS_AND_RESULTS/04_error_taxonomy_evolution.md](../07_METRICS_AND_RESULTS/04_error_taxonomy_evolution.md).

## 1. Spider 1.0 — 94.0 % EX

### 1.1 Headline number and conditions

Our Spider 1.0 EX is 94.0 % on the standard dev split of 1034 questions. The number was produced by the Phase 22 stable configuration (Qwen3-Coder-30B-A3B planner + Qwen2.5-Coder-7B emitter, v18 closed-set planner, validator-feedback retry, three-shot decode at temperature 0.0). Every phase since Phase 22 has regenerated Spider 1.0 as a regression check; the rate has stayed within ±0.3 pp at 94.0 %. We treat this as the publication figure.

### 1.2 What 94.0 % means relative to the gold answer set

Spider 1.0 EX is computed by string-matching the predicted SQL's result set against the gold SQL's result set after canonical ordering. A predicted SQL that returns semantically equivalent but row-order-different output passes. A predicted SQL that returns an additional column counts as a fail. A predicted SQL that uses a different join path but returns identical rows passes. This means the metric tolerates SQL diversity along most axes — the only unforgiving axis is the result-row set.

Our internal audit at Phase 22 sampled 60 failed items and re-sampled at Phase 28; the dominant failure category in both samples is *gold ambiguity / multi-valid SQL* at 38–40 % of failures. These are cases where the predicted SQL returns a defensible alternative result set: typically the question is genuinely ambiguous (e.g., "the most common type" with two ties), or the gold uses an implicit `WHERE` clause our SQL omits. The community recognises this caveat; the published Spider 1.0 leaderboard has been at the 92–95 % cluster since 2024 with no system breaking past the high-90s on the dev split.

### 1.3 Why this matters for the open-weight ≤30B claim

Spider 1.0 is the benchmark on which open-weight ≤30B systems have historically lagged the closed-source frontier by 5–10 pp. Our 94.0 % is competitive with the open-weight cluster (which sits at 92–95 % across systems like Qwen2.5-Coder-32B + DAIL-SQL adaptations, CodeS-15B + careful prompting, and CodeGen-25B + plan-then-emit pipelines). It is comparable to GPT-4-class closed-source systems on this benchmark (which hover at 94–96 % with extensive proprietary scaffolding).

The architectural cost of getting there is modest. The Spider 1.0 result does not require the Phase 27 grounding stack, does not require the Phase 28 dialect fixers, and does not require the closed-set planner's full machinery (a simpler join-aware planner would deliver ≈ 92 %). The 94.0 % is therefore a confirmation that the system is *correctly assembled* on classical benchmarks — it does not rest on the system's distinguishing features.

### 1.4 Methodology audit and reliability bounds

A reliable upper bound for our pipeline on Spider 1.0 is approximately 96 % EX, set by the gold-ambiguity residual. To push past that bound one would need an answer-key reconciliation pass — re-grading the disputed 38 % of failures with a semantic-equivalence rule rather than result-set string-matching. We did not perform this pass; the 94.0 % figure is reported as-measured. The audit on multi-aggregate/window patterns (27 % of failures) suggests a window-aware extension to the closed-set planner could close 1–2 pp; we did not implement it because the marginal value did not justify the engineering cost given that Spider 1 is not the load-bearing publication lane.

### 1.5 Where Spider 1.0 sits in the dossier's argument

The thesis's contribution is not a Spider 1.0 leaderboard entry. The 94.0 % is the *base-case demonstration* that the architecture is intact: a system that delivers 94 % on Spider 1.0 with no benchmark-specific tweaks is a credible baseline from which to launch the harder lanes. The interesting numbers are on Spider 2.0 (where 0 → 30 → 80 % schema_valid was the journey of Phases 17–27). Spider 1.0's role is to make the harder claims auditable.

## 2. BIRD — 87.9 % EX (FULL) / 90.4 % EX (mini-dev)

### 2.1 Headline numbers and conditions

Two BIRD numbers are reported. The publication figure is 87.9 % EX on the full dev split (1534 questions). A second figure of 90.4 % EX is reported on the mini-dev split (147 questions) that BIRD's authors curated as a tractable subset for rapid iteration. Both numbers come from the same Phase 22 configuration as Spider 1.0; both have been stable to ±0.5 pp since Phase 22.

### 2.2 The FULL vs mini-dev gap (2.5 pp)

The 2.5 pp gap between FULL (87.9 %) and mini-dev (90.4 %) reflects a known curation effect: the mini-dev set is filtered for tractable questions (fewer multi-step aggregates, more obvious join keys, more direct evidence-row usage). The FULL dev split retains the long-tail of harder questions. When comparing published BIRD numbers, particular care is required — many papers report mini-dev numbers without flagging them as such, and the headline figure on the leaderboard is the FULL number. We report both to avoid this confusion.

### 2.3 What BIRD measures that Spider 1.0 does not

BIRD adds three pressures that Spider 1.0 does not test: (a) explicit `evidence` rows that the model must use to disambiguate the question (e.g., a row that defines what code `'M'` means in a `gender` column); (b) substantially wider schemas (BIRD's median schema is ~6× the column count of Spider 1's); (c) numeric-encoding traps where the question's natural-language constants are not the table's literal values. A system that scores well on Spider 1 but poorly on BIRD is typically one that does well at the SQL grammar but cannot make use of supplementary semantic context.

Our 87.9 % FULL is competitive with the open-weight cluster on BIRD (88–91 % at the comparable scale, with Qwen2.5-Coder-32B + DAIL-SQL adaptations at ≈ 89 % and CodeS-based systems at ≈ 87 %). It is competitive but does not lead. The published leaders on BIRD FULL (as of May 2026) sit at ≈ 92 % using closed-source systems with extensive proprietary scaffolding (`DIN-SQL+GPT-4`-style). Our 87.9 % is therefore a credible open-weight number, not a frontier result.

### 2.4 Failure taxonomy and what is fixable

Our Phase 22 audit of 60 failed BIRD items showed the failure mix described in [../07_METRICS_AND_RESULTS/04_error_taxonomy_evolution.md](../07_METRICS_AND_RESULTS/04_error_taxonomy_evolution.md). The two largest fixable categories at Phase 22 are *multi-step reasoning* (25 % of failures) and *evidence misuse* (21 % of failures). Multi-step reasoning would benefit from a sub-aggregation planner that decomposes "the average of the maximum per group" type questions; we did not build one. Evidence misuse responds to a sharper evidence-block prompt (Phase 14 already cut this category in half) but the residual 21 % are cases where the evidence row contradicts the schema header (e.g., a column described as `INT` in the schema actually contains text-encoded codes that the evidence row explains). Resolving these requires the catalog-probe methodology we built for Spider 2 Snow at Phase 28, ported to BIRD's SQLite engine.

The annotation-driven residual on BIRD is smaller as a share than on Spider 1 (30 % of failures vs 40 %), but in absolute terms it is similar — BIRD has more total failures so the absolute count of "gold ambiguous" items is comparable.

### 2.5 Methodology audit and reliability bounds

A reliable upper bound for our pipeline on BIRD FULL is approximately 92 % EX, set by the combination of gold-ambiguity residual (≈ 30 % of failures = ≈ 3.6 pp) and the long tail of evidence-contradiction cases (≈ 2 pp recoverable with a SQLite catalog probe). To reach 92 % we would need (a) the catalog-probe port and (b) the multi-step decomposition planner. Neither is on the current roadmap; BIRD is, like Spider 1, in regression-only status during the Spider 2 phases.

### 2.6 BIRD's role in the dossier's argument

BIRD's role in the thesis is twofold. First, it confirms that the architecture is *not over-fit to Spider 1's narrow distribution*: real-world schemas, wider tables, and evidence-row reasoning all behave as expected with our closed-set planner. Second, it sets the bar for what "credible open-weight ≤30B on real schemas" looks like: 87.9 % on BIRD FULL is roughly the median of the published open-weight cluster, and our system delivers that without any benchmark-specific tweaks. The system that produces 87.9 % on BIRD is *the same binary* that produces the Spider 2 numbers — there is no per-benchmark fork.

## 3. Comparison to the published competitive set

The table below summarises where our numbers sit relative to the published open-weight ≤30B cluster (May 2026 snapshot). All numbers are EX on the standard dev splits. Closed-source frontier numbers are included for orientation but are not the comparison target — the thesis's claim is about the open-weight ≤30B regime.

```
System                                  Spider 1.0    BIRD FULL    Notes
─────────────────────────────────────────────────────────────────────────────────────
Ours (Phase 22, Qwen3-30B + 7B)         94.0%         87.9%        Same binary on both
Qwen2.5-Coder-32B + DAIL-SQL            93.8%         89.1%        Comparable open-weight
CodeS-15B + careful prompting           92.5%         86.7%        Comparable open-weight
CodeGen-25B + plan-then-emit            93.2%         87.4%        Comparable open-weight
Spider-Agent + Qwen3-Coder              94.6%         88.3%        Architectural neighbour
─────────────────────────────────────────────────────────────────────────────────────
GPT-4 + DIN-SQL (closed-source)         94.7%         91.6%        Frontier reference
o3 + ReFoRCE scaffold (closed-source)   95.2%         92.4%        Frontier reference
─────────────────────────────────────────────────────────────────────────────────────
```

Two observations on this table. (1) The open-weight cluster on Spider 1 is genuinely saturated at the 92–95 % band; the gold-ambiguity residual described in §1.2 caps every system in this regime. Our 94.0 % is competitive but is not the frontier point. (2) BIRD's spread is wider (86.7 % to 91.6 %) and is where architecture choices visibly matter. Our 87.9 % is mid-pack open-weight; the 3.7 pp gap to the closed-source frontier (91.6 %) maps cleanly to the categories we did not address (multi-step decomposition + SQLite catalog probing).

## 4. What the classical numbers do and do not establish

The classical numbers establish three claims:

* **The architecture is competitive at the open-weight ≤30B scale on classical benchmarks** — 94.0 % Spider 1 / 87.9 % BIRD FULL are within the publishable open-weight band.
* **No benchmark-specific tuning was required** — the binary that runs Spider 1 is the same binary that runs BIRD; the per-benchmark configuration differs only in the dialect adapter and the evidence-block flag.
* **The system saturates the easy lanes early** — Phase 22 numbers have held flat for six phases; further investment on Spider 1 / BIRD would be in answer-key reconciliation, not architecture.

The classical numbers do *not* establish the thesis's distinctive claim. Spider 1 and BIRD are SQLite-style single-database, single-query benchmarks. Our distinctive claim — that an open-weight ≤30B stack can produce schema-valid SQL on production Snowflake and BigQuery schemas via catalog-grounded closed-set planning — is established by the Spider 2 lanes, not by these classical numbers. See [02_spider2_full_analysis.md](02_spider2_full_analysis.md) once the Phase 28 FULL run closes, and [04_spider2_dbt_analysis.md](04_spider2_dbt_analysis.md) for the project-level DBT lane analysis already drafted.

## 5. Caveats and methodological reliability

Two caveats apply to all classical numbers in this document.

**Caveat 1 — EX as a proxy.** EX measures result-set equivalence, not query correctness. A system that returns the right rows for the wrong reason scores high; a system that returns slightly different but equally valid rows scores low. The 38–40 % gold-ambiguity residual on Spider 1 is the empirical signature of this proxy gap. The numbers in this document are reproducible and comparable against the published cluster, but they should not be over-interpreted as a measure of *query quality* — they are a measure of *result-set agreement with the gold key*.

**Caveat 2 — Decode determinism.** Both numbers are reported at temperature 0.0 with seed-controlled decoding. We re-ran the full dev split three times at Phase 22 to confirm reproducibility; the variance across runs was ≤ 0.3 pp on Spider 1 and ≤ 0.5 pp on BIRD. The single-run numbers reported here (94.0 % and 87.9 %) are the median of three runs. Higher-temperature decoding with three-shot retries was attempted at Phase 14 and showed no gain over deterministic decoding with validator-feedback retry, so the deterministic configuration is the published one.

These caveats apply equally to the published comparison cluster; the comparison in §3 is therefore methodologically aligned. The Spider 2 lanes have additional caveats (annotation reliability, catalog drift) that are documented in their own analysis files.
