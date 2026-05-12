# Diploma Dossier — NL2BI/Text-to-SQL агент на open-weight ≤30B стэке

> **Магистерская диссертация HSE** · автор: Денис · дата сборки: 2026-05-12 · стэк: Qwen3-Coder-30B-A3B (planner) + Qwen2.5-Coder-7B (emitter)
> **Статус**: Phase 28 FULL Snow закрыт (n=547, **23.76 % Snowflake `EXPLAIN`-pass (\*)**); Phase 28 FULL Lite-Snow partial (n=40 of 207, kernel-death event), полная закрытие deferred to Phase 28b post-defence.
>
> ⚠️ **Важно про метрики — обязательно прочитать перед использованием Spider 2 family чисел**: на Spider2-Snow / Spider2-Lite-Snow / Spider2-Lite-BQ наш `execute_ok` это **plan-level acceptance** (Snowflake `EXPLAIN`-pass / BigQuery `dry_run`-pass), **не row-set match** против gold (метрика Spider 2.0 leaderboard-а). Каждое Spider 2 число в этом dossier несёт inline `(*)` ссылающийся на [`11_APPENDIX/07_critical_metric_caveat.md`](11_APPENDIX/07_critical_metric_caveat.md) — central methodology disclosure. На Spider 1 / BIRD / Spider2-DBT метрика directly leaderboard-comparable (`(*)` не требуется). Row-match audit для Spider 2 SQL lanes — Phase 28b post-defence engineering (2-3 wall days, $20-100 warehouse credits).

---

## Назначение этой папки

Это итоговый рабочий материал для оформления ВКР. Не текст диплома сам по себе — но всё, чем подкрепляется текст: разобранная литература, описанная архитектура, табличные сводки экспериментов, разобранные ошибки, leaderboard-сравнения. Используется в трёх режимах:

| Режим использования | Куда смотреть |
|---|---|
| **Написание основного текста ВКР** (главы 1-4) | `01_INTRODUCTION/`, `02_RELATED_WORK/`, `03_BENCHMARKS/`, `04_ARCHITECTURE/`, `05_PIPELINES/` |
| **Раздел «экспериментальные результаты»** (глава 5) | `06_EXPERIMENTAL_PROGRESSION/`, `07_METRICS_AND_RESULTS/`, `09_RESULTS_ANALYSIS/` |
| **Защитная презентация и слайды** | `09_RESULTS_ANALYSIS/05_leaderboard_position.md`, `07_METRICS_AND_RESULTS/07_headline_results.md`, диаграммы из `04_ARCHITECTURE/11_full_pipeline_diagram.md` |
| **Приложения и техническая часть** | `08_CUSTOM_TOOLS/`, `10_REFERENCES/`, `11_APPENDIX/` |
| **Ответы на вопросы комиссии** | `11_APPENDIX/01_glossary.md`, `06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md`, `09_RESULTS_ANALYSIS/07_publishability_assessment.md` |

---

## Структура папки

```
outputs/final/
├── 00_README.md                          ← вы здесь
│
├── 01_INTRODUCTION/                      Глава 1: введение и постановка
│   ├── 01_problem_statement.md
│   ├── 02_motivation_and_relevance.md
│   ├── 03_research_questions.md
│   └── 04_thesis_contributions.md
│
├── 02_RELATED_WORK/                      Глава 2: литература
│   ├── 01_text2sql_evolution.md
│   ├── 02_sota_systems_2024_2026.md
│   ├── 03_open_source_text2sql_models.md
│   ├── 04_agentic_frameworks_for_dbt.md
│   └── 05_schema_linking_approaches.md
│
├── 03_BENCHMARKS/                        Глава 3.1: бенчмарки
│   ├── 01_spider1.md                     Spider 1.0
│   ├── 02_bird.md                        BIRD
│   ├── 03_spider2_overview.md
│   ├── 04_spider2_lite_bq.md
│   ├── 05_spider2_lite_snow.md
│   ├── 06_spider2_snow.md
│   ├── 07_spider2_dbt.md
│   └── 08_comparative_table.md
│
├── 04_ARCHITECTURE/                      Глава 3.2: архитектура агента
│   ├── 01_overview_single_architecture.md
│   ├── 02_models_qwen3_qwen2.5.md
│   ├── 03_schema_linker_v18_bm25.md
│   ├── 04_pack_builder_v18.md
│   ├── 05_planner_emitter_decomposition.md
│   ├── 06_candidate_factories_family_abc.md
│   ├── 07_validators_json_ast_engine.md
│   ├── 08_candidate_selector.md
│   ├── 09_dialect_handlers_f1_f4.md
│   ├── 10_execution_engines.md
│   └── 11_full_pipeline_diagram.md
│
├── 05_PIPELINES/                         Глава 4: конкретные pipeline на каждый бенчмарк
│   ├── 01_spider1_pipeline.md
│   ├── 02_bird_pipeline.md
│   ├── 03_spider2_lite_bq_pipeline.md
│   ├── 04_spider2_snow_pipeline.md
│   └── 05_spider2_dbt_pipeline.md
│
├── 06_EXPERIMENTAL_PROGRESSION/          Глава 5.1: хронология эксперимента
│   ├── 01_early_phases_overview.md
│   ├── 02_phase26_research_handoff.md
│   ├── 03_phase27_f1_grounding.md
│   ├── 04_phase28_f2a_regression_and_revert.md
│   ├── 05_phase28_full_baseline.md       ← FULL числа после закрытия
│   └── 06_lessons_learned.md
│
├── 07_METRICS_AND_RESULTS/               Глава 5.2: метрики и сводные результаты
│   ├── 01_metric_definitions.md
│   ├── 02_progression_table_full.md
│   ├── 03_progression_by_benchmark.md
│   ├── 04_error_taxonomy_evolution.md
│   ├── 05_per_db_breakdown_snow.md       ← FULL числа
│   ├── 06_per_db_breakdown_bq.md
│   └── 07_headline_results.md
│
├── 08_CUSTOM_TOOLS/                      Приложение А: код и инструменты
│   ├── 01_schema_pack_builder_v18.md
│   ├── 02_schema_linker_v18.md
│   ├── 03_candidate_factories.md
│   ├── 04_validators_suite.md
│   ├── 05_snow_identifier_guard_v27.md
│   ├── 06_snow_dialect_fixer_v28.md
│   ├── 07_candidate_selector.md
│   ├── 08_runner_orchestration.md
│   └── 09_resilience_patterns.md
│
├── 09_RESULTS_ANALYSIS/                  Глава 6: анализ и обсуждение
│   ├── 01_classical_benchmarks_spider1_bird.md
│   ├── 02_spider2_lite_bq_analysis.md
│   ├── 03_spider2_snow_analysis.md
│   ├── 04_spider2_dbt_analysis.md
│   ├── 05_leaderboard_position.md
│   ├── 06_failure_analysis_remaining.md
│   ├── 07_publishability_assessment.md
│   └── 08_thesis_novelty_claims.md
│
├── 10_REFERENCES/                        Список литературы
│   ├── 01_papers.md
│   ├── 02_repos_and_codebases.md
│   ├── 03_benchmark_datasets.md
│   └── 04_official_documentation.md
│
└── 11_APPENDIX/                          Приложения Б-Г
    ├── 01_glossary.md
    ├── 02_sample_queries_per_benchmark.md
    ├── 03_key_code_excerpts.md
    ├── 04_full_phase_report_index.md
    ├── 05_acronyms.md
    └── 06_acknowledgments.md
```

---

## Сводный рекомендуемый порядок чтения

### Для пишущего основной текст (Денис)
1. `01_INTRODUCTION/01_problem_statement.md` — формальная постановка задачи
2. `01_INTRODUCTION/03_research_questions.md` — что мы спросили
3. `01_INTRODUCTION/04_thesis_contributions.md` — что мы заявляем как вклад
4. `04_ARCHITECTURE/01_overview_single_architecture.md` — общая картинка системы
5. `06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md` + `04_phase28_f2a_regression_and_revert.md` — ключевая methodological story
6. `09_RESULTS_ANALYSIS/05_leaderboard_position.md` + `07_publishability_assessment.md` — итоговый результат и его место в мире
7. `06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md` — meta-выводы для главы выводы

### Для слайдов защиты
1. `07_METRICS_AND_RESULTS/07_headline_results.md` — один-страничный summary
2. `04_ARCHITECTURE/11_full_pipeline_diagram.md` — diagram целиком
3. `06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md` — пример empirical falsification гипотезы (хороший рассказ-история)
4. `09_RESULTS_ANALYSIS/05_leaderboard_position.md` — наша позиция vs SOTA
5. `09_RESULTS_ANALYSIS/06_failure_analysis_remaining.md` — что осталось (будущая работа)

### Для глубокого вопроса от комиссии
- Любые vопросы по архитектуре → `04_ARCHITECTURE/` + `08_CUSTOM_TOOLS/`
- Любые вопросы по конкретному бенчмарку → `03_BENCHMARKS/0X_*.md` + `05_PIPELINES/0X_*.md` + `09_RESULTS_ANALYSIS/0X_*.md`
- Любые вопросы по числам → `07_METRICS_AND_RESULTS/02_progression_table_full.md`
- Вопрос «а это новое или повтор?» → `09_RESULTS_ANALYSIS/08_thesis_novelty_claims.md`
- Вопрос про конкретный термин → `11_APPENDIX/01_glossary.md`

---

## Финальные числа и что отложено

**Закрыто на момент сборки:**

| Бенчмарк | n | Headline (canonical wording) |
|---|---|---|
| Spider 1.0 dev | 1034 | 94.0 % `execute_ok` (SQLite execute + result-set compare) |
| BIRD FULL | 1534 | 87.9 % `execute_ok` (SQLite execute + result-set compare; pending evaluator audit †) |
| BIRD mini-dev | 250 | 90.4 % `execute_ok` |
| Spider2-Lite-BQ FULL | 205 | 34.6 % **BigQuery `dry_run`-pass rate** (plan-level acceptance, см. Appendix 07 (\*)) |
| Spider2-Snow FULL | 547 | **23.76 % Snowflake `EXPLAIN`-pass rate** (plan-level acceptance, см. Appendix 07 (\*)) |
| Spider2-DBT FULL | 68 | 13.2 % `task_success` (dbt build + DuckDB result compare) |

**Отложено к Phase 28b (post-defence):**

- Spider2-Lite-Snow FULL 207: partial n=40 (pre-kernel-death snapshot), полная closure deferred.
- Row-match audit для всех Spider 2 SQL lanes — `spider2.eval` ingestion + warehouse execution + multiset row compare.
- BIRD evaluator audit (Phase 28c, 1 wall day).

Подробности см. [`11_APPENDIX/07_critical_metric_caveat.md`](11_APPENDIX/07_critical_metric_caveat.md) §7 (audit план) + [`09_RESULTS_ANALYSIS/05_leaderboard_position.md`](09_RESULTS_ANALYSIS/05_leaderboard_position.md) §4-5 (что defendable сейчас vs post-audit).

---

## Соглашения по оформлению

- **Язык**: основной текст — русский. Технические термины (`text-to-SQL`, `BM25`, `AST`, `dry_run`, `EXPLAIN`, `schema linker`, `MoE`, и т.п.) — английские, без транслитерации. Имена файлов, классов, идентификаторов, моделей — английские, в `code` форматировании. Цитаты из статей — оригинал + краткий русский парафраз.
- **Метрики**: единственный канонический набор определений в `07_METRICS_AND_RESULTS/01_metric_definitions.md`. Все остальные файлы ссылаются туда вместо повторного определения.
- **Числа**: каждое числовое значение имеет ссылку на phase report (e.g. «согласно `REPORT_PHASE27_F1_SNOW_GROUNDING.md` §4») или paper (e.g. «[ReFoRCE, arXiv 2502.00557]»). Числа без citation запрещены.
- **Cross-references**: между файлами папки даются как `[название](относительный/путь.md)`.
- **Diagrams**: ASCII там, где помещается; Mermaid в код-блоках с языком `mermaid` для сложных потоков.
- **Code excerpts**: с line numbers где это помогает чтению, всегда с языком `python` / `sql` / `json` / `yaml`.

---

## Что НЕ входит в этот dossier

- Сам текст ВКР (Денис пишет на основе материала)
- Презентация (Денис делает сам)
- Phase 29 F3 self-refine design — это отдельный workstream, запустится после Phase 28 FULL closure
- Все pre-Phase-26 интервенции в подробностях (только сводка в `06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md`)

---

## Контакт по dossier

Если в одном из файлов обнаружится фактическая ошибка / устаревшая ссылка / противоречие — внести правку в соответствующий файл и в одну строку обновить отметку даты в первом параграфе данного `00_README.md`.
