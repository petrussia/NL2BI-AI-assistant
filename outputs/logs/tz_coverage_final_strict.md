# TZ Coverage — Final (Strict)

Snapshot at: 2026-04-29T15:32:54.510956+00:00

STRICT means a pass requires every listed evidence file to physically exist on Drive.

## Functional

| ID | Title | Status | Evidence | Justification (one line) |
|---|---|---|---|---|
| 2.2.1 | Анализ NL-запросов | **done** | `repo/src/evaluation/query_analysis.py`, `outputs/logs/query_analysis_design.md`, `outputs/tables/query_analysis_examples.md`, `outputs/tables/query_analysis_ablation.csv` | Rule-based intent + signals analyzer + design + examples + ablation table. |
| 2.2.2 | Определение релевантных источников/таблиц/атрибутов | **done** | `repo/src/evaluation/baselines.py`, `repo/src/evaluation/retrieval.py`, `outputs/tables/b1_schema_linking_examples.md`, `outputs/tables/b1_schema_linking_smoke25_examples.md`, `outputs/logs/b3_retrieval_audit.md`, `outputs/tables/b3v1_retrieval_examples.md` | Lexical schema linker + cross-DB retrieval helper + adaptive dual retrieval (B3_v1). |
| 2.2.3 | Генерация формализованных запросов с safety/performance | **done** | `outputs/predictions/b0_spider_smoke10_predictions.jsonl`, `outputs/predictions/b4_final_spider_smoke10_predictions.jsonl`, `repo/src/evaluation/baselines_b4_final.py`, `outputs/logs/b4_final_validation_policy.md` | B0..B4_final implemented; SELECT-only AST guard + 8s SQLite timeout enforced. |
| 2.2.4 | Валидация и repair | **done** | `repo/docs/plan_schema.json`, `repo/docs/plan_schema_v1.json`, `outputs/tables/b4_final_candidate_examples.md`, `outputs/logs/b4_final_validation_policy.md` | jsonschema validation of plans; bounded repair (depth=1); multi-candidate with consistency selection. |
| 2.2.5 | Предварительная обработка и агрегация результатов | **done** | `repo/src/evaluation/postprocess.py`, `outputs/logs/postprocess_and_handoff_design.md`, `outputs/tables/analytics_handoff_examples.md`, `outputs/analytics_handoff` | normalize_rows + compute_summary; demo payloads on Drive. |
| 2.2.6 | Передача результатов в подсистему аналитического представления | **done** | `repo/src/evaluation/postprocess.py`, `outputs/analytics_handoff`, `outputs/logs/postprocess_and_handoff_design.md`, `outputs/docs/io_contracts.md` | AnalyticsPayload v1 contract + JSON+CSV export + handoff section in io_contracts. |
| 2.3 | Документация (архитектура, форматы, тестирование, эксплуатация) | **done** | `outputs/docs/architecture_document.md`, `outputs/docs/functional_specification.md`, `outputs/docs/io_contracts.md`, `outputs/docs/use_cases_and_scenarios.md`, `outputs/docs/testing_methodology.md`, `outputs/docs/operations_manual.md`, `outputs/docs/installation_and_runtime.md` | 7 bundled docs. |

## Work content

| ID | Title | Status | Evidence | Justification (one line) |
|---|---|---|---|---|
| 3.1 | Постановка задачи / ТЗ | **done** | `outputs/practice_package/01_fact_sheet_for_practice.md`, `outputs/logs/baseline_registry.md`, `outputs/docs/functional_specification.md` | Fact sheet + registry + functional spec; cleanly stated. |
| 3.2 | Анализ предметной области | **done** | `data/spider/SOURCE_AND_AUDIT.md`, `outputs/logs/smoke25_subset_audit.md`, `outputs/logs/multidb_30_audit.md` | Spider provenance + subset audits. |
| 3.3 | Исследование методов NLP | **done** | `outputs/logs/b1_schema_linking_audit.md`, `outputs/logs/b3v1_design_decision.md`, `outputs/logs/b4_final_design_decision.md`, `outputs/logs/b4_final_validation_policy.md`, `outputs/logs/query_analysis_design.md` | Lexical/dual retrieval, planner schema, validation+repair design notes; query analysis. |
| 3.4 | Формализация требований | **done** | `repo/docs/plan_schema.json`, `repo/docs/plan_schema_v1.json`, `outputs/logs/postprocess_and_handoff_design.md`, `outputs/logs/baseline_registry.md`, `outputs/docs/io_contracts.md` | Two plan schemas + handoff contract + baseline registry + IO contracts doc. |
| 3.5 | Архитектура системы | **done** | `outputs/docs/architecture_document.md`, `outputs/plots/system_architecture_overview.png`, `outputs/plots/ablation_pipeline_ladder.png`, `outputs/tables/component_registry.csv` | Bundled architecture document + 2 diagrams + component registry CSV. |
| 3.6 | Прототип системы | **done** | `repo/src/evaluation/baselines.py`, `repo/src/evaluation/baselines_b2.py`, `repo/src/evaluation/baselines_b2_v1.py`, `repo/src/evaluation/baselines_b3.py`, `repo/src/evaluation/baselines_b3_v1.py`, `repo/src/evaluation/baselines_b4.py`, `repo/src/evaluation/baselines_b4_final.py`, `repo/src/evaluation/postprocess.py`, `repo/src/evaluation/query_analysis.py`, `repo/src/evaluation/retrieval.py` | 10 modules: B1, B2, B2_v1, B3, B3_v1, B4-lite, B4_final, postprocess, query_analysis, retrieval. |
| 3.7 | Экспериментальное исследование | **done** | `outputs/tables/baseline_progression_smoke10_smoke25.csv`, `outputs/tables/b0_b1_b2_smoke10_comparison.csv`, `outputs/tables/error_taxonomy_smoke25.md`, `outputs/predictions/b2v1_spider_smoke10_predictions.jsonl`, `outputs/predictions/b3v1_spider_smoke10_predictions.jsonl`, `outputs/predictions/b4_final_spider_smoke10_predictions.jsonl`, `outputs/tables/multidb30_ablation.csv`, `outputs/tables/final_ablation_master.csv` | B0..B4_final smoke10 + B0/B1 smoke25 + multidb_30 5-baseline ablation + master. |
| 3.8 | Техническая документация | **done** | `outputs/docs/operations_manual.md`, `outputs/docs/installation_and_runtime.md`, `outputs/docs/testing_methodology.md`, `tools/notebook_tooling_audit.md`, `tools/tool_manifest.md`, `tools/tooling_readme.md`, `outputs/logs/model_block_closure.md` | Bundled docs + tooling docs + model block closure note. |

## Strict completion percent
- Functional: **100.0%**
- Work content: **100.0%**
- **Total: 100.0%**

## What remains to claim 100%

Nothing — all 16 items have full evidence on Drive.
