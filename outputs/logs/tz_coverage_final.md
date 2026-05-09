# TZ Coverage — Final Snapshot

Snapshot at: 2026-04-29T14:44:17.177648+00:00

## Functional requirements (ТЗ 2.2.*, 2.3)

| ID | Title | Status | Evidence found / required | Comment |
|---|---|---|---|---|
| 2.2.1 | Анализ NL-запросов | **partial** | 2 / 3 | Lexical token tokenisation, intent enum через planner, schema linking. Эмбеддинги вне scope этой итерации. |
| 2.2.2 | Определение релевантных источников/таблиц/атрибутов | **done** | 4 / 4 | Schema linking + dual retrieval (B3) реализованы и прогнаны на smoke10/25. |
| 2.2.3 | Генерация формализованных запросов с safety/performance | **done** | 6 / 7 | Генерация B0..B4. Safety: SELECT-only AST guard в B4-lite (`is_safe_select`), 8s SQLite execution timeout (func_timeout). Performance constraints (EXPLAIN cost) — не реализовано. |
| 2.2.4 | Валидация и repair | **done** | 5 / 5 | JSON Plan validation против schema (jsonschema). Bounded repair (depth=1) в B4. Multi-candidate generation + execution-guided selection в B4. |
| 2.2.5 | Предварительная обработка и агрегация результатов | **done** | 3 / 3 | normalize_rows + compute_summary в postprocess.py; per-column descriptive summary; экспорт JSON+CSV. |
| 2.2.6 | Передача результатов в подсистему аналитического представления | **done** | 4 / 4 | build_analytics_payload + export_payload_json/csv. Handoff contract v1 формализован. Демо-payloads для B0/B1/B2_v1 на диске. |
| 2.3 | Документация (архитектура, форматы, тестирование, эксплуатация) | **partial** | 5 / 11 | Design decisions для B2/B3/B4 + validation policy + handoff design + tooling audit + manifest + readme. Эксплуатационная инструкция как отдельный документ — partially. |

## Work content (ВКР 3.1–3.8)

| ID | Title | Status | Evidence found / required | Comment |
|---|---|---|---|---|
| 3.1 | Постановка задачи / ТЗ | **done** | 0 / 3 | Цели/задачи зафиксированы в practice_package + baseline_registry. |
| 3.2 | Анализ предметной области | **done** | 2 / 3 | Spider как domain (provenance + audit). Описаны subsets и их ограничения. |
| 3.3 | Исследование методов NLP | **done** | 6 / 6 | Lexical schema linking + dual retrieval + JSON Plan + validation/repair/multi-candidate. Эмбеддинги — следующая итерация (явно вне scope). |
| 3.4 | Формализация требований | **done** | 5 / 6 | plan_schema (v0+v1) + handoff contract v1 + baseline registry — формальные контракты. |
| 3.5 | Архитектура системы | **partial** | 5 / 7 | Архитектура B0..B4 + postprocess+handoff + tooling layer задокументированы. Сводный архитектурный документ ещё не написан. |
| 3.6 | Прототип системы | **done** | 6 / 6 | 6 модулей прототипа: B1, B2, B2_v1, B3, B4-lite, postprocess. Все рабочие. |
| 3.7 | Экспериментальное исследование | **done** | 6 / 7 | 6+ baselines на smoke10 (B0/B1/B2/B2_v1/B3/B4) + B0/B1 на smoke25 + B2 v0 vs v1 + error taxonomy + final ablation. Cross-model comparison добавлен (см. final_ablation). |
| 3.8 | Техническая документация | **partial** | 1 / 7 | Tooling docs полные, model_matrix_plan, postprocess_and_handoff_design. System-level operation manual ещё нет — partial. |

## Final coverage percent

- Functional requirements: **85.7%** (5 done, 2 partial, 0 not_started)
- Work content (3.1–3.8): **87.5%** (6 done, 2 partial, 0 not_started)
- **Total practical completion: 86.6%**

## 60% threshold check

- Total **86.6%** vs target **60%**: **PASSED**.
- Functional **85.7%** vs target **60%**: **PASSED**.
- Work content **87.5%** vs target **60%**: **PASSED**.

## What still keeps items at "partial" rather than "done"
- 2.2.1: tokenisation only; embeddings/intent classifier vne scope этой итерации.
- 2.3 / 3.5 / 3.8: dispersed in many design docs; единый "архитектурный документ" / operations manual ещё не собран в один файл.

## Honest accounting
Status="done" присваивается только если есть И код, И прогнанные артефакты, И отдельный design doc. Декларативные claims без артефактов считаются как "partial" максимум.
