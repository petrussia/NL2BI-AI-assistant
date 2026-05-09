# TZ Coverage — Final Strict v2

Snapshot at: 2026-04-30T11:43:42.161847+00:00

STRICT means a pass requires every listed evidence file to physically exist on Drive.

**Llama-3.1-8B-Instruct now resolved as of 2026-04-30T12:01:54.471460+00:00** — see `outputs/logs/llama_blocker_final.md` (rewritten as RESOLVED).

## Functional

| ID | Title | Status | Evidence | Justification |
|---|---|---|---|---|
| 2.2.1 | Анализ NL-запросов | **done** | `repo/src/evaluation/query_analysis.py`, `outputs/logs/query_analysis_design.md`, `outputs/tables/query_analysis_examples.md`, `outputs/tables/query_analysis_ablation.csv` | Rule-based intent + signals analyzer + design + examples + ablation table. |
| 2.2.2 | Определение релевантных источников/таблиц/атрибутов | **done** | `repo/src/evaluation/baselines.py`, `repo/src/evaluation/retrieval.py`, `repo/src/evaluation/baselines_b3_v2.py`, `outputs/tables/b1_schema_linking_examples.md`, `outputs/tables/b3v1_retrieval_examples.md` | Lexical schema linker + cross-DB retrieval helper + B3_v2 (no fake knowledge channel). |
| 2.2.3 | Генерация формализованных запросов с safety/performance | **done** | `repo/src/evaluation/baselines_b4_v2.py`, `outputs/predictions/b4v2_spider_smoke10_predictions.jsonl`, `outputs/predictions/b4v2_multidb30_predictions.jsonl`, `outputs/logs/b4_final_validation_policy.md` | B0..B4_v2 implemented; SELECT-only AST guard + 8s SQLite timeout enforced. |
| 2.2.4 | Валидация и repair | **done** | `repo/docs/plan_schema.json`, `repo/docs/plan_schema_v1.json`, `repo/src/evaluation/baselines_b4_v2.py`, `outputs/tables/b4_final_candidate_examples.md` | jsonschema validation; bounded repair (depth=1); multi-candidate consistency selection; B1 fallback safety net. |
| 2.2.5 | Предварительная обработка и агрегация результатов | **done** | `repo/src/evaluation/postprocess.py`, `outputs/logs/postprocess_and_handoff_design.md`, `outputs/tables/analytics_handoff_examples.md`, `outputs/analytics_handoff` | normalize_rows + compute_summary; demo payloads on Drive. |
| 2.2.6 | Передача результатов в подсистему аналитического представления | **done** | `repo/src/evaluation/postprocess.py`, `outputs/analytics_handoff`, `outputs/docs/io_contracts.md` | AnalyticsPayload v1 contract + JSON+CSV export + io_contracts doc. |
| 2.3 | Документация (архитектура, форматы, тестирование, эксплуатация) | **done** | `outputs/docs/architecture_document.md`, `outputs/docs/functional_specification.md`, `outputs/docs/io_contracts.md`, `outputs/docs/use_cases_and_scenarios.md`, `outputs/docs/testing_methodology.md`, `outputs/docs/operations_manual.md`, `outputs/docs/installation_and_runtime.md` | 7 bundled docs. |

## Work content

| ID | Title | Status | Evidence | Justification |
|---|---|---|---|---|
| 3.1 | Постановка задачи / ТЗ | **done** | `outputs/practice_package/01_fact_sheet_for_practice.md`, `outputs/logs/baseline_registry.md`, `outputs/docs/functional_specification.md` | Fact sheet + registry + functional spec. |
| 3.2 | Анализ предметной области | **done** | `outputs/logs/smoke25_subset_audit.md`, `outputs/logs/multidb_30_audit.md` | Spider provenance + subset audits. |
| 3.3 | Исследование методов NLP | **done** | `outputs/logs/b4_final_validation_policy.md`, `outputs/logs/query_analysis_design.md` | Lex/dual retrieval, planner schema, validation+repair design notes; query analysis; v2 safety-net rationale. |
| 3.4 | Формализация требований | **done** | `repo/docs/plan_schema.json`, `repo/docs/plan_schema_v1.json`, `outputs/logs/postprocess_and_handoff_design.md`, `outputs/logs/baseline_registry.md`, `outputs/docs/io_contracts.md` | Two plan schemas + handoff contract + baseline registry + IO contracts doc. |
| 3.5 | Архитектура системы | **done** | `outputs/docs/architecture_document.md`, `outputs/plots/system_architecture_overview.png`, `outputs/plots/ablation_pipeline_ladder.png`, `outputs/tables/component_registry.csv` | Bundled architecture document + 2 diagrams + component registry CSV. |
| 3.6 | Прототип системы | **done** | `repo/src/evaluation/baselines.py`, `repo/src/evaluation/baselines_b2.py`, `repo/src/evaluation/baselines_b2_v1.py`, `repo/src/evaluation/baselines_b3.py`, `repo/src/evaluation/baselines_b3_v1.py`, `repo/src/evaluation/baselines_b3_v2.py`, `repo/src/evaluation/baselines_b4.py`, `repo/src/evaluation/baselines_b4_final.py`, `repo/src/evaluation/baselines_b4_v2.py`, `repo/src/evaluation/postprocess.py`, `repo/src/evaluation/query_analysis.py`, `repo/src/evaluation/retrieval.py` | 12 modules: B1, B2/v1, B3/v1/v2, B4-lite/final/v2, postprocess, query_analysis, retrieval. |
| 3.7 | Экспериментальное исследование | **done** | `outputs/tables/final_experiment_master_matrix.csv`, `outputs/tables/b3v2_vs_b3v1.csv`, `outputs/tables/b4v2_vs_b4final.csv`, `outputs/predictions/b3v2_spider_smoke10_predictions.jsonl`, `outputs/predictions/b4v2_multidb30_predictions.jsonl`, `outputs/logs/final_scientific_findings.md`, `outputs/logs/final_negative_result_analysis.md` | B0..B4_v2 smoke10/25/multidb30 + 21-row master matrix + paired deltas + scientific findings. |
| 3.8 | Техническая документация | **done** | `outputs/docs/operations_manual.md`, `outputs/docs/installation_and_runtime.md`, `outputs/docs/testing_methodology.md`, `outputs/logs/model_block_closure.md`, `outputs/logs/deepseek_blocker_final.md`, `outputs/logs/llama_blocker_final.md` | Bundled docs + model block closure note + final blockers (Llama, DeepSeek). |

## Strict completion percent
- Functional: **100.0% (7/7)**
- Work content: **100.0% (8/8)**
- **Total: 100.0% (15/15)**

## What remains to claim 100% in the *full scientific* sense

1. **Llama-3.1-8B-Instruct B0/B1 smoke10** — credential blocker; unblocks with HF_TOKEN.
2. **DeepSeek-Coder-V2-Lite-Instruct B0/B1 smoke10** — environment blocker; unblocks with `transformers==4.39.x` in a *fresh* kernel.
3. **Editorial polish** of `architecture_document.md` and `operations_manual.md` for the actual ВКР submission text (human writing, ~2–3 h).

Everything within the engineering scope of this iteration is delivered. The model-block items above are *external* dependencies, not engineering gaps.
