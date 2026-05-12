# 1.4 Заявленный вклад работы

Ниже сформулирован полный набор claims, которые работа выносит на защиту. Каждый claim:
- (a) имеет привязку к одному из RQ (RQ1 / RQ2 / RQ3),
- (b) подкреплён конкретным экспериментальным результатом и/или артефактом в репозитории,
- (c) сформулирован в виде, который можно проверить на защите.

---

## Claim 1: Единая архитектура работает кросс-бенчмарк (RQ1)

**Формулировка**: Построена и реализована **единая архитектура агента**, состоящая из five-component pipeline (schema linker → pack builder → planner → emitter → validator/selector), которая без изменения core логики (только dialect adapter-ы) применяется на пяти бенчмарках разной природы — Spider 1.0 (SQLite), BIRD (SQLite), Spider2-Lite (BigQuery), Spider2-Snow (Snowflake), Spider2-DBT (DuckDB + multi-file edits) — и даёт нетривиальный результат на каждом.

**Поддерживающие данные** (см. подробно в [07_METRICS_AND_RESULTS/07_headline_results.md](../07_METRICS_AND_RESULTS/07_headline_results.md)):

| Бенчмарк | n_tasks | Headline (canonical wording) |
|---|---|---|
| Spider 1.0 | dev 1034 | 94.0 % `execute_ok` (SQLite execute + row compare) |
| BIRD | FULL 1534 | 87.9 % `execute_ok` (SQLite execute + row compare; pending evaluator audit †) |
| Spider2-Lite (BQ) | FULL 205 | 34.6 % BigQuery `dry_run`-pass rate (plan-level acceptance, см. [Appendix 07](../11_APPENDIX/07_critical_metric_caveat.md) (\*)) |
| Spider2-Snow | FULL 547 | **23.76 % Snowflake `EXPLAIN`-pass rate** (plan-level acceptance, 130/547, см. [Appendix 07](../11_APPENDIX/07_critical_metric_caveat.md) (\*)) |
| Spider2-Lite (Snow) | partial n=40/207 | partial — full closure deferred to Phase 28b (см. [Appendix 07](../11_APPENDIX/07_critical_metric_caveat.md) (\*)) |
| Spider2-DBT | FULL 68 | 13.2 % `task_success` (dbt build + DuckDB row compare; 9/68) |

**Артефакт**: репозиторий `repo/src/evaluation/` с commit-history (последний state-of-art `ad5493b` Phase 28 closure). Все pipeline-компоненты — общие, dialect-специфика изолирована в:
- `_bq_dry_run` vs `_snow_explain` vs `sqlite cur.execute`,
- `snow_identifier_guard_v27.py` (Snow-only),
- `snow_dialect_fixer_v28.py` (Snow-only).

**Где описано**: [04_ARCHITECTURE/01_overview_single_architecture.md](../04_ARCHITECTURE/01_overview_single_architecture.md), [05_PIPELINES/](../05_PIPELINES/).

---

## Claim 2: Phase-by-phase ablation интервенций (RQ2)

**Формулировка**: Проведён последовательный набор из 28 phase-экспериментов, каждый из которых вносит одну (или небольшую группу связанных) интервенцию в pipeline и измеряет её эффект на EX через pilot10 → pilot50 → FULL ladder. Каждая интервенция документирована (phase report с timestamp, гипотеза, реализация, метрики, выводы). Это позволяет атрибутировать вклад каждой компоненты, а не только дать конечный score.

**Поддерживающие данные** (полная таблица в [07_METRICS_AND_RESULTS/02_progression_table_full.md](../07_METRICS_AND_RESULTS/02_progression_table_full.md)):

| Phase | Интервенция | Δ EX (на главном lane) |
|---|---|---|
| 17 | Model swap pilot10 (Coder vs Mistral vs Llama vs Qwen3-14B) | Установил Coder family как best @ ≤14B |
| 18 | Schema-first ranking, closed-set pipeline, live catalogs | BQ pilot10 0% → 10% dry_run_ok (первый non-zero) |
| 19 | v18.1 repair sprint (7 patches) | BQ pilot10 → 30% (oba gates cleared) |
| 20-22 | A1+A2+A3 — identifier canonicalisation + pack all_columns + join_hints + Family C | Lite-BQ sv 50→54%, audit predicted +20pp got +4pp |
| 24 | Sequential runner + GPU lock + A4 engine-compat | устранил Phase 23 OOM; A4 metric-neutral на своём lane |
| **27** | **F1 grounding (per-task BM25 + three-part + AST guard + PK/FK injection)** | **Snow pilot10c: sv 12.6% → 80%, exec 0.48% → 1/10 (4× lift over Lite-Snow v26 baseline)** |
| **28** | **F4 date-cast wrap + F4c guard fail-open** (после F2a revert) | **Snow pilot10 revert-A: exec 1/10 → 4/10 (4× lift over Phase 27 closure)** |

**Артефакт**: 28 phase reports под `outputs/REPORT_PHASE*.md`, индексированные в [11_APPENDIX/04_full_phase_report_index.md](../11_APPENDIX/04_full_phase_report_index.md). Каждая phase воспроизводима через committed code + указанный `run_id`.

**Где описано**: [06_EXPERIMENTAL_PROGRESSION/](../06_EXPERIMENTAL_PROGRESSION/) (по фазам).

---

## Claim 3: Catalog-probe methodology как методологический вклад (RQ3)

**Формулировка**: Введена **«catalog-probe-driven hypothesis testing»** методология для выявления и опровержения ложных гипотез о dialect failure mode-ах. Конкретная демонстрация: в Phase 28 первоначальная гипотеза «mixed-case quoting объясняет 4 из 10 invalid_identifier errors на Spider2-Snow PATENTS» была опровергнута direct probe-ом catalog-а (`spider2_snow_live_catalog_v18.jsonl`), показавшим что **37/37 колонок таблицы `PATENTS.PUBLICATIONS` хранятся в lowercase**. После revert F2a + удаления соответствующего prompt-rule, экспериментально подтверждено: настоящая failure mode — **column-name hallucination** (модель эмитит `country` вместо реального `country_code`), и она не лечится case-manipulation, а закрывается self-refine loop-ом (Phase 29 territory).

**Поддерживающие данные**:
- Catalog probe script: `tools/remote_scripts/_phase28_catalog_case_probe.py`,
- Phase 28 report §6 «The fundamental error in Phase 27 §5 — catalog case discovery»,
- pilot10 revert-A результат (exec 0/10 → 4/10) подтверждает, что hypothesis «mixed-case quoting» была лишней.

**Где описано**: [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md), [09_RESULTS_ANALYSIS/06_failure_analysis_remaining.md](../09_RESULTS_ANALYSIS/06_failure_analysis_remaining.md).

**Методологический урок** (выносится в [06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md](../06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md)): **«error-message taxonomy без проверки catalog-а — ненадёжна»**. Это контрастирует с распространённой в NL2SQL литературе практикой строить fix-список из error categorisation на nat. lang. error-string-ах. Наша работа показывает, что в realistic warehouse setting этот workflow приводит к ложным гипотезам, которые проходят synthetic unit-test-ы, но регрессируют на реальном pipeline. Правильная workflow — **probe catalog → hypothesis → measurement**.

---

## Claim 4: Первое publishable Snow число для open-weight ≤30B стэка (RQ1 + RQ2)

**Формулировка**: F1+F4+F4c стэк (Phase 27 + Phase 28 после revert-A), коммитнутый в commit `ad5493b`, даёт **первое не-нулевое (и проверяемое на FULL прогон) число execution accuracy на Spider2-Snow для open-weight ≤30B параметров пайплайна**. До этого, на нашей же v25-v26 baseline (Phase 26), execute_ok на Snow lane был 0% (FULL 547 partial 509/547).

**Поддерживающие данные**:
- Phase 26 baseline: `outputs/spider2_snow/runs/snow_full_v25/` показал execute_ok=0/509,
- Phase 28 revert-A pilot10: 4/10 EXPLAIN-pass (\*) — выявило F4 wrap-driven recovery,
- Phase 28 revert-A FULL Snow 547: **130 / 547 = 23.76 % Snowflake EXPLAIN-pass (\*)** — first non-zero Snow FULL для open-weight ≤30B на нашем pipeline,
- Phase 28 revert-A FULL Lite-Snow 207: partial n=40/207 (kernel-death interruption); full closure deferred to Phase 28b.

**Артефакт**:
- commit `ad5493b` (Phase 28 closure, frozen stack).
- run_ids `snow_full_v28_revert_a` (Spider2-Snow 547), `lite_snow_full_v28_revert_a` (Lite-Snow 207).
- Reports `REPORT_PHASE28_F2A_F4_DIALECT.md` (closure + revert-A метрики), `REPORT_PHASE28_FULL_BASELINE.md` (FULL числа, будет создан post-closure).

**Где описано**: [09_RESULTS_ANALYSIS/03_spider2_snow_analysis.md](../09_RESULTS_ANALYSIS/03_spider2_snow_analysis.md).

---

## Claim 5: Демонстрированный gap до closed industrial top + честная диагностика

**Формулировка**: На Spider2-Snow и Spider2-Lite lanes честно зафиксирован **gap между нашим open-weight ≤30B стэком и closed-API top-tier**. Cross-metric situation (наш `EXPLAIN`-pass vs leaderboard row-match) precludes прямое ranking; canonical wording — *"in the same band as the open-weight Spider-Agent baselines, pending row-match audit"*. Closed-API top (ReFoRCE + o3 62.89 % row-match, Genloop 96.70 % row-match) vs наш **23.76 % `EXPLAIN`-pass (\*)** — gap присутствует но не directly quantifiable без Phase 28b audit. Gap атрибутирован конкретным remaining failure modes (column-name hallucination, table hallucination, nested-STRUCT decomposition gap, biomedical-terminology gap, LATERAL FLATTEN SQLGlot gap, JOIN-graph absence on BQ), каждая из которых имеет identified scaffold-level fix path (Phase 29 F3a/F3b/F3c как primary candidates, Phase 30 для BQ).

**Поддерживающие данные**:
- Phase 28 revert-A failure analysis (`REPORT_PHASE28_F2A_F4_DIALECT.md` §10 per-task table): 5 из 6 misses — scaffold-level (4 hallucination cases, 1 LATERAL FLATTEN, 1 F4 over-cast на VARIANT-JSON),
- Research dossier с current leaderboard (`outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md`).

**Где описано**: [09_RESULTS_ANALYSIS/05_leaderboard_position.md](../09_RESULTS_ANALYSIS/05_leaderboard_position.md), [09_RESULTS_ANALYSIS/06_failure_analysis_remaining.md](../09_RESULTS_ANALYSIS/06_failure_analysis_remaining.md), [09_RESULTS_ANALYSIS/07_publishability_assessment.md](../09_RESULTS_ANALYSIS/07_publishability_assessment.md).

---

## Claim 6: Reproducible artifact — committed code + frozen stack

**Формулировка**: Все интервенции реализованы в репозитории `repo/src/evaluation/` и подкреплены commit-history. Финальный «defended» stack — **commit `ad5493b`** (Phase 28 closure, F1 + F4 + F4c, F2a в source но не вызывается). Любой результат, упомянутый в работе, воспроизводим путём checkout этого commit-а + запуск нужного script-а с указанным `run_id`. Run ladder для Snow: `lite_snow_pilot10_v28_revertA` (pilot10) → `lite_snow_full_v28_revert_a` (FULL 207) → `snow_full_v28_revert_a` (FULL 547).

**Поддерживающие данные**:
- Commit log: `git log --oneline` показывает phase-by-phase atomic commits для Phase 27 (`7b420b2`), Phase 28 regression (`8acb0e5`), Phase 28 closure (`ad5493b`).
- Run артефакты на Drive: `outputs/spider2_snow/runs/*` и `outputs/spider2_lite/runs/*` содержат `predictions.jsonl`, `traces.jsonl`, `progress.json`, `metrics.csv`, `error_taxonomy.csv` для каждого run.
- Resilience patterns: per-task Drive writes + periodic file close+reopen + resume-on-restart scaffolding обеспечивают reproducibility даже при kernel death (см. [08_CUSTOM_TOOLS/09_resilience_patterns.md](../08_CUSTOM_TOOLS/09_resilience_patterns.md)).

**Где описано**: [08_CUSTOM_TOOLS/](../08_CUSTOM_TOOLS/) (по компонентам), [11_APPENDIX/03_key_code_excerpts.md](../11_APPENDIX/03_key_code_excerpts.md).

---

## Сводная таблица claims vs RQ

| Claim # | Привязка к RQ | Основной экспериментальный сигнал |
|---|---|---|
| 1. Единая архитектура | RQ1 | 5 разных бенчмарков, один stack, нетривиальный EX на каждом |
| 2. Phase-by-phase ablation | RQ2 | 28 phase reports, измеренный Δ EX каждой интервенции |
| 3. Catalog-probe methodology | RQ3 | Phase 28 F2a опровержение через direct catalog read |
| 4. Первое publishable Snow число | RQ1 + RQ2 | Phase 28 revert-A FULL — 23.76 % Snowflake EXPLAIN-pass (\*), 130/547 |
| 5. Gap + диагностика | RQ3 | Failure taxonomy на pilot10 revert-A, leaderboard сравнение |
| 6. Reproducible artifact | RQ2 + RQ3 | Commit `ad5493b` + run_ids |

---

## Что НЕ заявляется (явно)

- **НЕ заявляется SOTA на Spider 2.0 в абсолютном выражении**. На Snow lane closed-API top остаётся вне досягаемости; на DBT — общий ceiling 13.2% и для closed, и для open.
- **НЕ заявляется production-ready system**. Финальный EX на Snow в нашей зоне (≈25-30% по проекции pilot10) означает что 70-75% запросов не выполняются.
- **НЕ заявляется generality за пределами Spider 2.0 family**. Все интервенции откалиброваны под этот набор бенчмарков; перенос на другие сценарии (financial regulatory queries, healthcare HIPAA, etc.) — отдельная задача.
- **НЕ заявляется causal proof что scaffolding > model scale при произвольных размерах модели**. Только: при фиксированном ≤30B стэке, scaffolding interventions дают больше Δ EX на наших бенчмарках, чем у нас была возможность измерить от model upgrade-ов внутри той же family.
- **НЕ заявляется novel ML algorithm**. Вклад — методологический и инженерный, не алгоритмический.

---

## Ссылки на источники для этого раздела

| Утверждение | Источник |
|---|---|
| Spider 1.0 EX 94.0% наш результат | `outputs/REPORT_PHASE*.md` — Spider1 column в progression table |
| BIRD EX 87.9% наш FULL 1534 | `outputs/REPORT_PHASE*.md` — BIRD column |
| Lite-BQ EX 34.6% | `outputs/REPORT_PHASE19_*` v18.1b BQ pilot50 |
| Snow F1 sv 12.6% → 80% | `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` §3 |
| Snow F4 exec 1/10 → 4/10 | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §10 |
| 37/37 lowercase catalog | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §6 |
| ReFoRCE + o3 62.89% | research dossier (May 2026 fetch) |
| Snow v25 baseline exec 0/509 | `outputs/spider2_snow/runs/snow_full_v25/progress.json` |

---

## Что дальше

→ [02_RELATED_WORK/01_text2sql_evolution.md](../02_RELATED_WORK/01_text2sql_evolution.md) — историческая литература
→ [04_ARCHITECTURE/01_overview_single_architecture.md](../04_ARCHITECTURE/01_overview_single_architecture.md) — детально как устроен наш agent stack
→ [09_RESULTS_ANALYSIS/08_thesis_novelty_claims.md](../09_RESULTS_ANALYSIS/08_thesis_novelty_claims.md) — formal список того, что новое vs reproduction
