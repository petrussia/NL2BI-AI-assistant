# 5.2 Phase 26 — Researcher Handoff

## Opening question

After Phase 25 produced Spider2-Snow FULL baseline of **0/547 executable**, what was the right next move?

Two options were available:

1. **More code experimentation** — try another scaffold modification, another model swap, another emit prompt — hoping to randomly stumble on what fixes Snow.
2. **Step back to literature** — do **deep external research** на current Spider 2.0 SOTA systems, understand what they do differently, derive a **principled F-series fix plan**.

Phase 26 chose **option 2**.

This file documents the **handoff phase** itself — what was done, what was learned, and **why** the F-series planning was the necessary methodological precursor к successful Phase 27-28 interventions.

## Approach taken

Phase 26 — **non-coding phase**. No new commit, no new pipeline run. Instead:

1. **Reproduction баselines** across all benchmarks с current Phase 24 stack:
   - Spider 1.0 dev FULL 1034: 94.0%.
   - BIRD FULL 1534: 87.9%; mini-dev 250: 90.4%.
   - Spider2-DBT 68: 13.2%.
   - Spider2-Lite-BQ projection: 34.6%.
   - **Spider2-Snow FULL 547 partial 509**: 0.0%.
   - **Spider2-Lite-Snow FULL 207**: 0.5% (1/207).
   - Spider2-Lite-SQLite partial 52/135: 0%.

2. **Comprehensive research dossier compilation** — what later became `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md` (235 lines distilled summary; original dossier ~25KB).

3. **F-series fix prioritization** — mapping methodological literature к 5-6 concrete fixes ranked by expected ROI per hour.

## What was researched

Per Phase 27 strategy dossier (см. `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md`), Phase 26 dossier covered:

### Spider 2.0 leaderboards (May 2026 fetch)

Three sub-benchmark leaderboards:
- **Spider2-Snow** top: Genloop 96.70 (closed), TCDataAgent 93.97 (closed), Paytm Prism 90.49 (closed), ReFoRCE+o3 62.89% (top reproducible), Spider-Agent+Qwen3-Coder 31.08% (open ≤30B reference), наша v25 baseline 0.0%.
- **Spider2-Lite** top: SOMA-SQL 72.02% (closed), Databao 69.65% (closed), ReFoRCE+o3 55.21%, AutoLink+DeepSeek-R1 52.28%, наш Lite-BQ 34.6%.
- **Spider2-DBT** top: Databao 58.82% (closed), SignalPilot 51.56% (closed), Shadowfax+GPT-5 41.18%, Spider-Agent+Claude-3.7 14.70%, наш 13.2%.

### Per-system methodology summaries

13+ systems mapped с extract relevant techniques:
- **ReFoRCE** [Deng et al., arXiv 2502.00675] — Self-Refinement + Format Restriction + Column Exploration.
- **AutoLink** [arXiv 2511.17190] — iterative schema linking + LLM-guided expansion (91.2% strict schema recall).
- **LinkAlign** [Wang et al., arXiv 2503.18596] — multi-DB schema linking. **Critical quote**: *"how to select the correct database from a large schema pool in multi-database settings, while filtering out irrelevant ones."*
- **CHESS** [Talaei et al., arXiv 2405.16755] — PK/FK column injection после BM25 picks.
- **SchemaGraphSQL** [arXiv 2505.18363] — BFS over FK + name-heuristic edges after BM25 seeds.
- **CHASE-SQL** [Pourreza et al., ICLR 2025, arXiv 2410.01943] — multi-path reasoning + trained 7B selector.
- **DAIL-SQL, DIN-SQL, DTS-SQL, MAC-SQL** — classical decomposition baselines.
- **Databao Agent** [JetBrains blog Feb 2026] — DBT scaffold redesign (up-front DB overview + restricted tool surface + verifier gate).
- **SWE-agent** [Yang et al., NeurIPS 2024] — edit-linter-revert ablation +8pp.
- **aider** Polyglot leaderboard — Coder-7B diff-format 30% drop on small files.
- **CodeS-15B** [Li et al., SIGMOD 2024] — open-source SFT baseline; 84.9% Spider1, 0.73% Spider2-Lite (transferability failure).

### Annotation reliability

Wang et al. [arXiv 2601.08778] paper *"Pervasive Annotation Errors Break Text-to-SQL Benchmarks and Leaderboards"* — **62.8% mismatch rate** Spider 2.0 audit. Implication: any Spider 2.0 number reported should include annotation reliability caveat + recommend manual audit.

### Methodological insights

Three key insights surfaced from Phase 26 dossier:

1. **Catalog probe before dialect heuristic** — error-message inspection без catalog ground-truth ненадёжна. *This insight became central in Phase 28 §6 F2a falsification.*
2. **BM25 hyperparameter mismatch Spider1→Spider2** — defaults (top_columns=80, top_tables=20) откалиброваны под ≤30 tables/DB; warehouse-scale catalogs (thousands of tables) under-recall. *Direct motivation for Phase 27 retrieval scale 200/40 widening.*
3. **Layered fixes — composition reveals dormant value** — каждая fix может быть "zero ROI" в isolation but load-bearing in composition. *Validated in Phase 28: F4 wraps appeared useless под F2a regression; revert-A revealed F4 critical для 3 of 4 pilot10 exec_ok.*

## F-series fix prioritization

Phase 26 dossier §5 распределили 5-6 concrete F-fixes:

| Fix | Source paper / system | Effort | Expected lift | Status post-Phase-28 |
|---|---|---|---|---|
| **F1 — TABLE_CATALOG filter + 3-part names + AST guard** | LinkAlign + ReFoRCE | 6-10 h | Snow 0% → 15-25% | **DONE Phase 27** |
| **F4 — NUMBER/VARIANT date-cast wrapper** | own observation (Snow-specific) | 2-3 h | Snow +3-5 EX | **DONE Phase 28** |
| **F4c — Guard fail-open on SQLGlot parse error** | own bug discovery | 0.5 h | Edge case fix (e.g., sf_bq210) | **DONE Phase 28** |
| **F3 — EXPLAIN error → planner one-shot self-refine** | ReFoRCE Self-Refinement + RSL-SQL + MAC-SQL Refiner | 3-5 d | +3-8 EX every lane | **PLANNED Phase 29** |
| **F4 BQ post-processor** — date literals, ARRAY_CONTAINS, nested aggregates, SAFE_OFFSET (BQ-specific dialect rewrites) | own (BQ dialect) | 1 wk | Lite-BQ +4-6 EX | **PLANNED Phase 29 or 30** |
| **F2 — JOIN-graph schema expansion + Family C activation** | SchemaGraphSQL + AutoLink | 2-3 wk | Lite-BQ +6-10 EX | **PLANNED Phase 30** |
| **F6 — DBT scaffold redesign** | Databao + SWE-agent + aider | 6-8 d | DBT 13% → 25-32% | **PLANNED Phase 31** |

**F2a (mixed-case quoting auto-rewrite) — initially tabled as Phase 28 candidate**. After Phase 28 catalog probe falsification — **DROPPED**. See [04_phase28_f2a_regression_and_revert.md](./04_phase28_f2a_regression_and_revert.md).

## Decision tree: which fix first

Phase 26 prioritization logic:

| Decision factor | F1 score | F2 score | F3 score | F4 score | F6 score |
|---|---|---|---|---|---|
| Expected lift | High (15-25%) | High (6-10%) | Med (3-8%) | Med (3-5%) | High (12-19%) |
| Effort | Low (6-10h) | High (2-3wk) | Med (3-5d) | Low (2-3h) | High (6-8d) |
| ROI per hour | **Highest** | Medium | Medium-High | High | Medium |
| Dependency on diagnostic confidence | Highest (LinkAlign direct match) | Med (heuristic FK) | Med (error-feedback loop spec) | High (catalog probe needed) | High (scaffold redesign) |
| Reversibility | High | High | High | High | Medium-Low |

**F1 selected first** — highest ROI per hour, lowest risk, direct LinkAlign §1 alignment.

After Phase 27 F1 closure (Snow pilot10 sv 8/10 but exec stuck 1/10), **F4 / F4c** chosen as **second priorities** — small effort, direct fix for the 3 of 10 NUMBER/VARIANT date-cast pilot10c failures. Phase 28 implementation.

**F3 deferred к Phase 29** — design + implementation effort 3-5d, bigger than F4. Plus F4 без F3 still provides value; F3 без F4 doesn't address NUMBER cast issues.

## The "BM25 hyperparameter mismatch" hypothesis seeded в Phase 26 dossier §6

Phase 26 dossier explicitly noted **second hypothesis** beyond F1:

> *"Phase 1-16 BM25 defaults (top_columns=80, top_tables=20) calibrated for Spider1/BIRD schemas (≤30 tables/DB) systematically under-recall on Spider2 warehouse-scale catalogs (thousands of tables/DB). Once cross-DB noise eliminated (Phase 27 F1 catalog filter), retrieval window remained too narrow to surface enough relevant tables from the correct DB."*

This **proved correct** в Phase 27 v27c run: when ONLY F1 catalog filter + AST guard were active (without retrieval scale), pilot10 schema_valid was 2/10. Add retrieval scale 80→200 + 20→40 → schema_valid jumped к 8/10. **Retrieval scaling alone responsible для significant portion of the lift**, independent от F1 catalog filter.

Lesson: **hyperparameter mismatch** is its own failure mode, separate from architectural mistakes. Often unrelated к the original cross-DB drift cause but compounds it.

## What worked, what didn't

### What worked

- **External literature deep-dive replaced random experimentation**. Without LinkAlign quote и ReFoRCE methodology, Phase 27 design would have been guess-work.
- **F-series prioritization** by ROI per hour identified F1 as right first move. Subsequent Phase 27 closure validates.
- **Annotation reliability caveat surfaced** early — sets right expectations for thesis defense.

### What didn't

- **F2a (mixed-case quoting)** was initially included в Phase 28 batch based на pilot10c error-message taxonomy. Should have been preceded by catalog probe — would have caught lowercase storage truth before deploying. **Methodological lesson** ultimately incorporated as [Claim 3](../01_INTRODUCTION/04_thesis_contributions.md).

- **F2 (JOIN-graph)** still pending — Phase 26 deferred because **F1 had higher predicted ROI**. By Phase 28, F2 still not implemented. Phase 30 territory. **Cost: Lite-BQ stuck at 34.6%**, could have been ~45% с F2 + F3 combination.

## Lessons learned (Phase 26)

### Lesson 1: Pause and research has measurable value

Phase 26 was zero code lines written. **Output: Phase 27 + 28 had a clear plan**. Without it, would have been months of random experimentation.

For thesis Conclusion: **deliberate pause for literature review at architecture-stagnation moment** is a methodological pattern worth highlighting.

### Lesson 2: Reproducibility of findings depends on external anchoring

ReFoRCE / AutoLink / LinkAlign — public papers с public code. **Reproducible-SOTA discussion** anchored на them, не on closed-industry Genloop / SOMA-SQL. Allows honest comparison instead of "we're far below closed top, ignore that".

### Lesson 3: ROI per hour > absolute expected lift

F1 (15-25%) > F2 (6-10%) as predicted lift. **But F1 effort 6-10h** vs F2 **2-3 weeks**. ROI: F1 ~2-4 EX/hour, F2 ~0.05-0.5 EX/hour. **F1 wins by 4-50× efficiency**. Phase 26 prioritization correct.

### Lesson 4: Methodological insights могут seed критические later fixes

Three insights seeded в Phase 26 §6:
1. **Catalog probe** — became core Phase 28 §6 methodology (Claim 3).
2. **BM25 hyperparameter mismatch** — became Phase 27 retrieval scaling fix.
3. **Layered fixes interact** — became Phase 28 §10 revert-A understanding (F4 was hidden by F2a regression).

All three seeded **before any Phase 27 code touched**.

## Transition к Phase 27

By end of Phase 26:
- Spider2 SOTA understood deeply (research dossier).
- F-series fix priorities clear (F1 first, F4/F4c second, F3 deferred).
- Methodological foundation laid (catalog probe before dialect heuristic, BM25 calibration awareness, layered fix awareness).

**Phase 27 ready к start с concrete plan** — implement F1 (TABLE_CATALOG filter + three-part names + AST guard) on Snow lane, pilot10 → pilot50 → FULL ladder, measure precisely.

## Cross-references

- Research dossier itself: `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md`
- Phase 27 F1 implementation: [03_phase27_f1_grounding.md](./03_phase27_f1_grounding.md)
- Phase 28 F2a (related F2-series discussion): [04_phase28_f2a_regression_and_revert.md](./04_phase28_f2a_regression_and_revert.md)
- F-series in architecture context: [04_ARCHITECTURE/09_dialect_handlers_f1_f4.md](../04_ARCHITECTURE/09_dialect_handlers_f1_f4.md)
- Lessons learned (thesis conclusion preview): [06_lessons_learned.md](./06_lessons_learned.md)
- Related work systems referenced в dossier: [02_RELATED_WORK/02_sota_systems_2024_2026.md](../02_RELATED_WORK/02_sota_systems_2024_2026.md)
- Schema linking approaches deep-dive: [02_RELATED_WORK/05_schema_linking_approaches.md](../02_RELATED_WORK/05_schema_linking_approaches.md)

## Источники

| Утверждение | Источник |
|---|---|
| Phase 26 baseline metrics | `outputs/REPORT_PHASE26_RESEARCHER_HANDOFF.md` §1 |
| Spider2 leaderboards | research dossier §1-3 |
| LinkAlign §1 quote | `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md` §4 LinkAlign entry |
| F-series prioritization | research dossier §5 |
| Annotation reliability 62.8% | Wang et al., arXiv 2601.08778 |
| Methodological insights §6 | research dossier §6 |
| ROI per hour calculation | own analysis based на §5 effort estimates |
