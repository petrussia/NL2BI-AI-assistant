# 5.1 Early phases — Phase 1 через Phase 25

## Opening question

Что мы пытались узнать в этой группе фаз? Centrally — **«какие компоненты scaffolding-а реально двигают EX, и в каком порядке их строить»** для NL2BI агента, работающего на open-weight ≤30B стэке. Phase 1-25 — long iterative research period, в котором мы дошли от «пробуем разные модели и смотрим что получится» до «у нас есть единая architecture, работающая на 4 из 5 бенчмарков на competitive level, но Spider2-Snow stuck на 0%».

Цель этого файла — **narrative compression** 25 фаз в meaningful clusters. Phase reports индивидуально documented в [11_APPENDIX/04_full_phase_report_index.md](../11_APPENDIX/04_full_phase_report_index.md); здесь — high-level story arc.

## Cluster 1: Model and baseline exploration (Phase 1-17)

### What was tried

Phase 1-17 — **scratch experimentation period**. Каждая phase tested different combinations of:
- Models: Mistral-7B, Llama, Qwen2.5-Coder-7B/14B/32B, Qwen3-14B, DeepSeek-Coder, Gemma-3-12B-IT, SQLCoder-7B-2.
- Prompting strategies: zero-shot, few-shot с similar question retrieval, chain-of-thought.
- Schema representations: DDL dump, table descriptions, BM25-ranked subset.
- Decoder configurations: temperature 0.0-0.8, top_k, top_p.

Many file artifacts с suffix `b0_`, `b1_v3`, `b2_v1`, etc. в `repo/src/evaluation/baselines_*.py` documenting permutations.

### Key milestone Phase 17

Phase 17 — **systematic model swap pilot10**. 4 model families × 2 lanes (BQ + Snow):

| Model | Params | BQ pilot10 sv | Snow pilot10 sv |
|---|---|---|---|
| Mistral-7B-Instruct-v0.3 | 7B | 1/10 | 0/10 |
| Mistral-7B-Instruct BF16 | 7B | 1/10 | 0/10 |
| Qwen3-14B (general, не Coder) | 14B | 3/10 | 0/10 |
| **Qwen2.5-Coder-7B-Instruct** | **7B** | **5/10 sv** | 0/10 |
| Qwen3-Coder-30B-BF16 (joint emit) | 30B (dense) | 4/10 sv | 0/10 |

**Главный вывод Phase 17**: **family > scale**. Coder-line specialized моделей **превосходят** general-line equal-or-larger size (Qwen3-Coder-30B vs Mistral-7B both worse than Coder-7B на BQ).

Это конkretно closed выбор моделей: **Qwen2.5-Coder-7B-Instruct as emitter**, switched к **Qwen3-Coder-30B-A3B** as planner после релиза MoE variant (Phase 24-25).

### Cluster 1 transition

Phase 17 confirmed model selection. **Снижался ROI от further model swaps**. Time to focus on scaffolding. Phase 18+ direction shift.

## Cluster 2: Schema-first architecture v18 (Phase 18-22)

### Opening question

Phase 16 root-cause audit показал, что **95.7% of historical task failures были true_hallucination** — model emitted identifiers that don't exist. Phase 17 confirmed swapping модели на стronger one doesn't fix this в open-vocab generation.

Hypothesis: **closed-set planning + closed-set validator** прекратит identifier hallucination at architectural level.

### Approach taken

Phase 18 introduced **v18 stack**:
1. **Live INFORMATION_SCHEMA catalog harvest** (per-lane, one-shot): BQ ~428K columns, Snow ~587K columns.
2. **BM25 schema linker** (`schema_linking_v18`): own implementation Okapi BM25 with identifier tokenization + synonym expansion.
3. **Pack builder** (`schema_pack_builder_v18`): compact JSON-friendly schema fragment с top-K tables × top-M columns.
4. **Closed-set planner**: emits structured JSON plan referencing only pack identifiers.
5. **AST validator**: SQLGlot parse check + identifier residency check `selected_columns ⊆ pack.all_columns` + `selected_tables ⊆ pack.tables`.
6. **Candidate factory v18**: Family A (deterministic BQ render) + Family B (Coder-7B direct emit).

### What worked

Phase 18 — **first non-zero dry_run_ok**: BQ pilot10 1/10 dry_run passed. Pre-Phase-18 baseline was 0/10. Major step.

Phase 19 — v18.1 repair sprint: 7 specific patches:
- AST-aware residency replacing regex (fixed `bigquery-public-data` hyphen false-leak).
- Wildcard regex tightening.
- Description truncation.
- JSON Schema validator strictness.
- Plan retry feedback.
- Pack rendering cleanups.

Result: BQ pilot10 3/10 dry_run + 3/10 schema_valid. **Both gates cleared at 30%**.

Phase 22 STAGE A1+A2+A3 — additional refinements:
- A1: shared identifier canonicalization (FQN-aware).
- **A2: `all_columns` side-channel** для validator — reduces false-positive `schema_invalid`.
- A3: `join_hints` heuristic + Family C (JOIN-aware factory).

### What didn't

Phase 20-21 audit: **identifier canonicalization** (FQN unification) lifted `plan_validation_ok` 42→54% but **didn't move `chosen_schema_valid`**. Gap was engine-compat (BQ-specific `ARRAY_EXISTS`, `NTH`, multi-CTE), not FQN.

Phase 22 STAGE A3 (Family C JOIN-aware): predicted +20pp EX lift на pilot50. **Actual: +4pp**. Reason: Family C output frequently fails AST validator (join hints heuristic — false-positive joins). Selector rarely picks Family C.

Lesson: **architecture interventions** need real-data validation, не just unit tests. Family C unit-tested correctly, но on real schema noise — failed selector tie-break.

### Why

Architecture v18 fixed **identifier hallucination** at structural level. Phase 18-22 lifted Spider2-Lite-BQ from ~0% to ~34% EX. This is **the big jump** в проекте — about 30 EX points from scaffold work alone, при model class unchanged.

### Cluster 2 transition

By Phase 22 — Spider1/BIRD saturated at 94/88% EX. Spider2-Lite-BQ stable 34% EX. **Spider2-Snow inexplicably at 0% — same architecture but doesn't work**.

## Cluster 3: Orchestration challenges (Phase 23-25)

### Opening question

Why we can't run Spider2-Snow FULL evaluations reliably?

### Phase 23: concurrent inference experiments

Tried running BQ + Snow + DBT lanes **concurrently** на single A100-80GB to maximize throughput. Result: **CUDA OOM** on multi-model concurrent inference. Qwen3-Coder-30B-A3B planner + Coder-7B emitter together fit 76 GB. Adding multiple concurrent inference calls (multiple tasks at once) exceeded 80 GB → fail.

BQ FULL 14/205 partial — incomplete due to OOM. Both Snow FULL CANCELLED.

Lesson: **multi-task batching на single GPU doesn't scale** для our model combination. Phase 23 — orchestration failure, not algorithmic.

### Phase 24: sequential runner + GPU lock

Phase 24 introduced:
- `run_spider2_sequential_v24.py` — process tasks one-at-a-time, no batching.
- `gpu_lock_v24.py` — file-based mutex preventing concurrent inference в same kernel.
- A4 BQ engine-compat rewrites — separate intervention applied к BQ Family A output.

Pilot50 v24 ran reliably (sv 54%, exec 44% — **same as v22**). A4 rewrites measurably **metric-neutral** в audit — не disruptive, не lift either.

Lesson: **orchestration matters as much as algorithm**. Reliable execution needed before any FULL benchmark possible.

### Phase 25: Spider2-Snow FULL baseline attempt

Phase 25 ran v25 stack на Spider2-Snow FULL 547 — **first serious FULL Snow attempt**. Result after 509/547 tasks: **execute_ok = 0/547 (0.0%)**.

**Zero executable**. This — the **shocking baseline** that motivated Phase 26 handoff. Spider1 and BIRD at 94%/88%, but Snow at 0%. Architecture works on classical bench, fails on enterprise warehouse.

Pre-Phase-26 understanding of root cause: **none**. Diagnostic was needed.

### Cluster 3 transition

Phase 25 closure produced two artifacts:
1. `outputs/spider2_snow/runs/snow_full_v25/` — partial 509/547 record, exec=0, schema_valid=59 (11.4%).
2. Phase 26 handoff trigger — *внешний research dossier* needed.

By Phase 25, **classical / BIRD lanes saturated, Spider2 lanes inexplicably at 0**. Required external research.

## Cluster 4: Phase 26 — researcher handoff (separate file)

См. [02_phase26_research_handoff.md](./02_phase26_research_handoff.md) для full detail.

Short version: Phase 26 — **methodological pivot**. Not coding phase, но research dossier compilation (`outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md`) — 8-section deep-dive внешней literature на Spider2-SOTA systems, methodological insights, F-series fix recommendations.

Key insight seeded в Phase 26:
- **LinkAlign** [arXiv 2503.18596] §1 quote: *"how to select the correct database from a large schema pool в multi-database settings"* — **exactly described Spider2-Snow 0% baseline root cause**.
- **F1 fix** prioritized as highest-ROI first intervention (estimated +15-25% Snow EX, 6-10h effort).

## Lessons learned (Cluster 1-3)

### Lesson 1: Architecture interventions > model swaps for current ≤30B class

Phase 17 model swap pilot10: maximum lift между models within Coder family — marginal. Phase 18 architecture overhaul (v18 stack): +30 EX points на Lite-BQ alone. Architecture won.

### Lesson 2: Identifier hallucination — dominant failure mode

Phase 16 audit: 95.7% failures были identifier-name issues. Closed-set planning + AST validator targets exactly это failure class. Most scaffolding interventions trace к this insight.

### Lesson 3: Real-data audit > unit tests для heuristics

Phase 22 STAGE A3 — Family C predicted +20pp, delivered +4pp. Unit tests passed; real-data behavior different. Subsequent phases shifted к **pilot10 → pilot50 → FULL ladder** discipline.

### Lesson 4: Orchestration robustness не optional

Phase 23 OOM cost a week of wall time. Phase 24 GPU lock + sequential runner — **enabling technology** для all subsequent FULL evaluations.

### Lesson 5: Different lanes have different failure modes

Phase 25 made obvious: same v24 architecture делает 94%/88%/34% на Spider1/BIRD/Lite-BQ, но **0% Spider2-Snow**. **Bench-specific bottlenecks** require bench-specific interventions.

## Cluster 1-3 metrics summary

| Phase group | Spider1 EX | BIRD EX | Lite-BQ EX | Lite-Snow EX | Snow EX | DBT task_success |
|---|---|---|---|---|---|---|
| Phase 1-17 (pre-v18) | 40-90% | 40-85% | 0-3% | 0% | 0% | 0-13% |
| Phase 18 v18.0 | 92% | 86% | 10% pilot10 | 0% | 0% | 12-13% |
| Phase 19 v18.1 | 93% | 87% | 30% pilot10 | 0% | 0% | 13% |
| Phase 20-22 (A1/A2/A3) | 94% | 87% | 50-54% sv / 34-44% exec на pilot50 | 0% | 0% | 13.2% |
| Phase 24 v24 | 94% | 87.9% | 34.6% projected FULL | 0% | 0% | 13.2% |
| Phase 25 v25 | (unchanged) | (unchanged) | (unchanged) | **0.5%** (1/207) | **0% (0/509)** | (unchanged) |

**Critical observation**: Spider2-Lite-Snow и Spider2-Snow lanes — **non-zero на Lite-Snow only because 1 task survived** (sf_bq211 — turned out to be lucky tâche where model emitted clean lowercase-quoted SQL). **Zero true ROI** from any Phase 1-25 intervention on Snow lane. Required Phase 26-27-28 F1 + F4 interventions to break.

## Transition to next phase group

**By Phase 25, the project state**:
- Spider 1.0 + BIRD саturated at top tier для open ≤30B class.
- Spider2-Lite-BQ stable 34.6% EX.
- Spider2-DBT stable 13.2% (Spider-Agent ceiling, scaffold-bound).
- **Spider2-Snow + Lite-Snow at 0%** — single-architecture failure mode.

**Phase 26 was the deliberate pause** to do external research instead of more code experiments. **Phase 27 F1 + Phase 28 F4** would be the two interventions, designed by researcher dossier insights, that closed the Snow 0% problem.

Continue к [02_phase26_research_handoff.md](./02_phase26_research_handoff.md).

## Cross-references

- All Phase 1-25 reports indexed: [11_APPENDIX/04_full_phase_report_index.md](../11_APPENDIX/04_full_phase_report_index.md)
- v18 stack architecture: [04_ARCHITECTURE/01_overview_single_architecture.md](../04_ARCHITECTURE/01_overview_single_architecture.md)
- Phase 17 model evidence: [04_ARCHITECTURE/02_models_qwen3_qwen2.5.md](../04_ARCHITECTURE/02_models_qwen3_qwen2.5.md)
- Phase 24 BQ engine-compat: [05_PIPELINES/03_spider2_lite_bq_pipeline.md](../05_PIPELINES/03_spider2_lite_bq_pipeline.md)
- Phase 23 GPU OOM: [08_CUSTOM_TOOLS/09_resilience_patterns.md](../08_CUSTOM_TOOLS/09_resilience_patterns.md)
- Phase 25 baseline: [03_BENCHMARKS/06_spider2_snow.md](../03_BENCHMARKS/06_spider2_snow.md)
- Phase 26 handoff: [02_phase26_research_handoff.md](./02_phase26_research_handoff.md)

## Источники

| Утверждение | Источник |
|---|---|
| Phase 17 family > scale | memory `spider2_phase17_findings.md`; `outputs/REPORT_SPIDER2_V17.md` |
| Phase 18 first non-zero dry_run | memory `spider2_phase18_findings.md`; `outputs/REPORT_SPIDER2_V18.md` |
| Phase 19 v18.1 7 patches | `outputs/REPORT_SPIDER2_V19.md` |
| Phase 22 A1/A2/A3 audit | memory `spider2_phase22_findings.md`; `outputs/REPORT_SPIDER2_V22.md` |
| Phase 23 OOM | memory `spider2_phase23_findings.md`; `outputs/REPORT_SPIDER2_FULL_DIAGNOSTIC_V23.md` |
| Phase 24 sequential + A4 | memory `spider2_phase24_findings.md`; `outputs/REPORT_SPIDER2_PHASE24_LITE_BQ.md` |
| Phase 25 v25 baseline 0/509 | `outputs/spider2_snow/runs/snow_full_v25/progress.json` |
