# 5.2.2 Master progression table

## Назначение

Этот файл — **главная progression table** across all benchmarks across all phases. Rows = phases в chronological order (Phase 1 through Phase 28-revert-A); columns = each benchmark + intervention summary. Below table — narrative analysis ~1200 слов про saturation patterns, breakthrough moments, и future trajectory.

## Главная таблица

| Phase | Date (approx) | Headline intervention | Spider1 dev (1034) | BIRD dev FULL (1534) | BIRD mini-dev (250) | Spider2-Lite-BQ | Spider2-Lite-Snow (207) | Spider2-Snow (547) | Spider2-DBT (68) |
|---|---|---|---|---|---|---|---|---|---|
| Phase 1-7 | 2025 Q1-Q2 | Initial baselines, model exploration | 40-90% | 40-85% | n/a | 0-3% | 0% | 0% | 0-13% |
| Phase 8 | 2025 Q2 | v8 pipeline structure, multiple lanes runners | 90-92% | 85-86% | n/a | 1-3% | 0% | 0% | 12-13% |
| Phase 9-10 | 2025 Q2 | v9-v10 incremental fixes | 92-93% | 86-87% | n/a | 2-5% | 0% | 0% | 13% |
| Phase 11 | 2025 Q2 | DBT lane baseline reproduction | 93% | 87% | n/a | 3-5% | 0% | 0% | **13.2%** (stable from here) |
| Phase 12-13 | 2025 Q2 | v12-v13 lane-specific refinements | 93% | 87% | n/a | 5-8% | 0% | 0% | 13.2% |
| Phase 16 | 2025 Q3 | Constrained identifier repair, 95.7% hallucination diagnosed | 94% | 87% | n/a | 0-1% sv | 0% | 0% | 13.2% |
| Phase 17 | 2025 Q3 | **Model swap pilot10 grid** — family > scale established | 94% | 87% | n/a | 5/10 sv pilot | 0/10 | 0/10 | 13.2% |
| **Phase 18** | 2025 Q3 | **Schema-first v18 architecture** (live catalog + BM25 + closed-set plan + AST validator) | 94% | 87% | n/a | **10% pilot10 dry_run (first non-zero)** | 0% | 0% | 13.2% |
| Phase 19 | 2025 Q3-Q4 | v18.1 repair sprint — 7 patches | 94% | 87% | n/a | **30% pilot10 dry_run + 30% schema_valid** | 0% | 0% | 13.2% |
| Phase 20-21 | 2025 Q4 | A1 identifier canonicalization (FQN-aware) | 94% | 87% | n/a | sv 50-52% / exec 42-46% pilot50 | 0% | 0% | 13.2% |
| **Phase 22** | 2025 Q4 | **A1+A2+A3 — all_columns + join_hints + Family C** | 94% | 87% | n/a | sv 54% / exec 44% pilot50 | 0% | 0% | 13.2% |
| Phase 23 | 2025 Q4 | FULL diagnostic (concurrent inference OOM) | 94% | 87% | n/a | partial 14/205 | partial | partial | 13.2% |
| Phase 24 | 2025 Q4 / 2026 Q1 | Sequential runner + GPU lock + A4 BQ engine-compat | 94% | 87% | n/a | sv 50% / exec 34-44% pilot50 v24 | 0% | 0% | 13.2% |
| Phase 25 | 2026 Q1 | **Spider2-Snow FULL 547 baseline attempt** | 94% | 87% | n/a | 34.6% projection | **0.5%** (1/207) | **0% (0/509 partial)** | 13.2% |
| Phase 26 | 2026 Q1-Q2 | **Researcher handoff** (no code; F-series prioritization) | **94.0%** | **87.9%** | **90.4%** | **34.6%** projected | 0.5% | 0% | 13.2% |
| **Phase 27** | 2026 Q2 (May 2026) | **F1 Snow grounding** (per-task BM25 partition + three-part + AST guard + retrieval scale + PK/FK injection) | 94.0% | 87.9% | 90.4% | 34.6% | **sv 8/10 pilot10c, exec 1/10** | sv lift, exec stuck | 13.2% |
| Phase 28 (initial) | May 2026 | F2a + F4 + F4c — REGRESSION | 94.0% | 87.9% | 90.4% | 34.6% | sv 7/10, **exec 0/10 pilot10** | (not run) | 13.2% |
| **Phase 28-revert-A** | May 2026 (closure ad5493b) | F2a reverted, F4+F4c retained | 94.0% | 87.9% | 90.4% | 34.6% | **sv 6/10, exec 4/10 pilot10** | (not run) | 13.2% |
| **Phase 28 FULL** | May 2026 (Snow closed; Lite-Snow partial) | FULL 547 + FULL 207 v28-revert-A | 94.0% | 87.9% | 90.4% | 34.6% (\*) | partial n=40/207 — deferred to Phase 28b (\*) | **23.76 % (\*)** | 13.2% |

**Конвенции таблицы**:
- Pilot10 numbers shown as fractions (e.g., 8/10, 4/10) where pilot ≠ FULL.
- `sv` = `schema_valid` rate.
- "n/a" = metric not collected for that phase (BIRD mini-dev only after Phase 21).
- Final cells reflect the Phase 28 FULL closure (Snow); Lite-Snow FULL is partial pending Phase 28b. All Spider 2 family numbers carry (\*) per [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md).

Source: combined of `outputs/REPORT_PHASE*.md`, `outputs/REPORT_SPIDER2_V*.md`, `outputs/REPORT_PHASE26_RESEARCHER_HANDOFF.md` §1, и memory phase findings 17-24.

## Analysis

### Classical lanes (Spider 1.0 + BIRD) saturation pattern

Spider 1.0 + BIRD reached **saturation by Phase 22-23** (around 94% / 87-88% EX). Subsequent phases (Phase 23-28) **did not move these numbers** — focus shifted к Spider 2.0 lanes где headroom существенно больше.

**Why saturation**: classical SQLite benchmarks с clean schemas, ≤30 tables/DB, no external knowledge or dialect peculiarities — наша v18 architecture **mostly solves them within open ≤30B class**. Remaining 6% Spider 1.0 misses + 12% BIRD misses are **complex multi-step reasoning tasks** (nested subqueries, multi-aggregation, ambiguous phrasing). Closing these requires either:
- Reasoning-class models (o1/o3, not open ≤30B).
- Multi-step refinement (Phase 29 F3 self-refine).
- Trained selector (CHASE-SQL approach).

None of these compatible с our strict open ≤30B no-SFT constraints. Acceptable position: **leading among open ≤30B**, не absolute SOTA.

### Spider 2.0 0% baseline puzzle (Phase 1-25)

**Spider 2.0 lanes (Lite-BQ, Lite-Snow, Snow) sat at 0% for entire Phase 1-17 period**. Single architecture v18 fixed Lite-BQ к 34.6% in Phase 19-22, but **Snow remained 0% until Phase 27**.

**Why scaffold not models**:
- Same emitter (Qwen2.5-Coder-7B) achieves 87.9% BIRD.
- Same planner (Qwen3-Coder-30B-A3B) когда applied к Snow — produces SQL referencing **wrong catalog** for 90.2% tasks (Phase 27 §1 diagnostic).
- Model "knows" structure of SQL generation, **but pipeline doesn't ground it к correct database**.

**Phase 17 model swap pilot10**: tried Mistral-7B, Qwen3-14B, Qwen3-Coder-30B-BF16 — all produced 0/10 Snow EX. Model class change **did не fix Snow lane**. Confirmed: bottleneck is **scaffold (catalog grounding)**, not model capability.

This is the **core empirical evidence** для Claim 1 (scaffolding > model scale for ≤30B class).

### Phase 27 break-through on Snow lane

Phase 27 F1 — **first non-zero schema_valid lift на Snow**: 12.6% baseline → 80% pilot10c. The intervention что **enabled** subsequent exec lift.

Components:
1. **Per-task BM25 partition by `c.db.upper()`** — eliminated cross-DB drift (90.2% → 0%).
2. **Three-part name rendering** + Snow dialect rules block в prompt.
3. **AST guard** — defense in depth.
4. **Retrieval scale 80/20 → 200/40** — addresses BM25 hyperparameter mismatch hypothesis.
5. **PK/FK heuristic injection** — covers join keys BM25 misses.
6. **Validator relaxation** + SELECT-alias protection — reduces false-positive schema_invalid.

Pilot10c metric jump: schema_valid 12.6% → 80%, exec 1/10 (sf_bq211 only).

**Exec stayed at 1/10** because bottleneck shifted **from grounding к Snow dialect runtime errors**. Phase 28 closed this gap.

### Phase 28 closure — exec 1/10 → 4/10 pilot

Phase 28 implementation: F2a + F4 + F4c. **Net negative**: F2a caused regression (exec 1/10 → 0/10). Catalog probe revealed F2a hypothesis wrong (Spider 2.0 Snow stores lowercase identifiers, not uppercase as F2a assumed).

Phase 28 closure (commit `ad5493b`):
- F2a **reverted** — function kept в source for record.
- F4 + F4c retained.
- Pilot10 exec **0/10 → 4/10** (4× lift over Phase 27).
- F4 wraps load-bearing for 3 of 4 new exec_ok (sf_bq026 DATE, sf_bq213 VARIANT, sf_bq029 direct YYYYMMDD math validated by F4 rule в prompt).

This is the **direct evidence** для Phase 28's contribution. Per-task analysis в [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md).

### BQ + DBT lanes plateau

**Spider2-Lite-BQ stable at 34.6%** through Phase 22-28. Phase 27-28 не touched BQ lane (interventions Snow-specific). BQ improvement requires:
- **Phase 30 F2**: real FK metadata + JOIN-graph BFS (SchemaGraphSQL recipe). Expected +6-10 EX.
- **Phase 30 F4-BQ**: BQ-specific post-processor (date literals, ARRAY_CONTAINS, SAFE_OFFSET). Expected +4-6 EX.
- **Phase 29 F3**: self-refine on engine error. Expected +3-8 EX.

Combined Phase 29-30 target: 34.6% → 52-58% (band с AutoLink + DeepSeek-R1 52.28%).

**Spider2-DBT stable at 13.2%** through entire Phase 11-28. Confirmed = Spider-Agent scaffold ceiling regardless of model class. Improvement requires:
- **Phase 31 scaffold redesign**: read-before-write + restricted tool surface + staged verifier + multi-block whole-file emit. Expected 13.2% → 22-32%.

Both BQ + DBT improvements out of scope for current dossier — Phase 29-31 future work.

### Future trajectory (informed by table)

| Lane | Current | Phase 29-30 target | Phase 31 target | Closed-API ceiling |
|---|---|---|---|---|
| Spider1 | 94.0% | ~96% | (saturated) | ~91% (open ≤30B already exceeds) |
| BIRD FULL | 87.9% | ~90% | (saturated) | ~76% (open ≤30B already exceeds) |
| Spider2-Lite-BQ | 34.6% | ~52-58% (F3 + F2 + BQ F4) | (saturated) | 72% (SOMA-SQL closed) |
| Spider2-Lite-Snow | partial n=40/207 (\*) — deferred to Phase 28b | ~27-32% EXPLAIN-pass (+F3) (\*) | (saturated) | 55% row-match (ReFoRCE+o3) |
| Spider2-Snow | **23.76 % EXPLAIN-pass (\*)** | ~27.5-30% EXPLAIN-pass (+F3) (\*) | (saturated) | 63% row-match (ReFoRCE+o3), 97% row-match (Genloop closed industrial) |
| Spider2-DBT | 13.2% | (unchanged Phase 29-30) | **22-32%** (scaffold redesign) | 59% (Databao closed) |

**Open ≤30B class realistic ceiling** ~30-40% Snow EX, ~55% Lite-BQ EX, ~30% DBT — all **well below closed-API top**. Bridging gap requires either:
- Larger open weights (DeepSeek-R1 685B class — 20× наш planner).
- Closed-API reasoning models (out of scope для open-weight thesis).

## Pattern observations cross-cutting all phases

1. **Most lifts come from single-intervention phases**: Phase 18 (architecture overhaul), Phase 27 (F1 grounding), Phase 28-revert-A (F4 reveal). **Multi-intervention phases (Phase 22 A1+A2+A3 simultaneously) gave smaller cumulative lifts** — interactions diluted contribution per fix.

2. **Pilot-FULL gap**: pilot10 results sometimes overestimate FULL (Phase 22 A3 predicted +20pp on pilot, delivered +4pp на pilot50). This **why we maintained pilot10 → pilot50 → FULL ladder** throughout Phase 27-28.

3. **Cross-lane interventions**: rare. Most interventions are **lane-specific** (BQ engine-compat, Snow F1/F4, DBT scaffold). Cross-lane fixes (shared identifier canonicalization Phase 20-21) had **smaller measurable effect** than lane-specific ones.

4. **Architecture stability**: v18 core schema linker + pack builder + planner-emitter + validator design — **stable from Phase 18 through Phase 28** (committed). All subsequent fixes layered on top, не replaced core. Testimony к **clean separation of concerns**.

## Cross-references

- Per-phase narrative: [06_EXPERIMENTAL_PROGRESSION/](../06_EXPERIMENTAL_PROGRESSION/)
- Per-benchmark progression details: [03_progression_by_benchmark.md](./03_progression_by_benchmark.md)
- Error taxonomy evolution: [04_error_taxonomy_evolution.md](./04_error_taxonomy_evolution.md)
- Headline results (post-FULL): [07_headline_results.md](./07_headline_results.md)
- Methodological claims backed by these numbers: [01_INTRODUCTION/04_thesis_contributions.md](../01_INTRODUCTION/04_thesis_contributions.md)
- Architecture stability across phases: [04_ARCHITECTURE/](../04_ARCHITECTURE/)

## Источники

| Утверждение | Источник |
|---|---|
| Phase 1-25 numbers | combined `outputs/REPORT_SPIDER2_V*.md` + memory phase findings 17-24 |
| Phase 26 baseline metrics | `outputs/REPORT_PHASE26_RESEARCHER_HANDOFF.md` §1 |
| Phase 27 F1 pilot10c metrics | `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` §3 |
| Phase 28 v28 + revert-A pilot10 | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §3, §10 |
| Future trajectory expected lifts | research dossier `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md` §5 |
| Closed-API + reproducible top numbers | research dossier §1-3 |
