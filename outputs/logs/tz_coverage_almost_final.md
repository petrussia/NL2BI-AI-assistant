# TZ Coverage — Almost Final

Snapshot at: 2026-04-29T15:32:54.510956+00:00

## Functional (2.2.*, 2.3)

| ID | Title | Status | Evidence found / required | Justification |
|---|---|---|---|---|
| 2.2.1 | Анализ NL-запросов | **done** | 4/4 | Rule-based intent + signals analyzer + design + examples + ablation table. |
| 2.2.2 | Определение релевантных источников/таблиц/атрибутов | **done** | 6/6 | Lexical schema linker + cross-DB retrieval helper + adaptive dual retrieval (B3_v1). |
| 2.2.3 | Генерация формализованных запросов с safety/performance | **done** | 4/4 | B0..B4_final implemented; SELECT-only AST guard + 8s SQLite timeout enforced. |
| 2.2.4 | Валидация и repair | **done** | 4/4 | jsonschema validation of plans; bounded repair (depth=1); multi-candidate with consistency selection. |
| 2.2.5 | Предварительная обработка и агрегация результатов | **done** | 4/4 | normalize_rows + compute_summary; demo payloads on Drive. |
| 2.2.6 | Передача результатов в подсистему аналитического представления | **done** | 4/4 | AnalyticsPayload v1 contract + JSON+CSV export + handoff section in io_contracts. |
| 2.3 | Документация (архитектура, форматы, тестирование, эксплуатация) | **done** | 7/7 | 7 bundled docs. |

## Work content (3.1–3.8)

| ID | Title | Status | Evidence found / required | Justification |
|---|---|---|---|---|
| 3.1 | Постановка задачи / ТЗ | **done** | 3/3 | Fact sheet + registry + functional spec; cleanly stated. |
| 3.2 | Анализ предметной области | **done** | 3/3 | Spider provenance + subset audits. |
| 3.3 | Исследование методов NLP | **done** | 5/5 | Lexical/dual retrieval, planner schema, validation+repair design notes; query analysis. |
| 3.4 | Формализация требований | **done** | 5/5 | Two plan schemas + handoff contract + baseline registry + IO contracts doc. |
| 3.5 | Архитектура системы | **done** | 4/4 | Bundled architecture document + 2 diagrams + component registry CSV. |
| 3.6 | Прототип системы | **done** | 10/10 | 10 modules: B1, B2, B2_v1, B3, B3_v1, B4-lite, B4_final, postprocess, query_analysis, retrieval. |
| 3.7 | Экспериментальное исследование | **done** | 8/8 | B0..B4_final smoke10 + B0/B1 smoke25 + multidb_30 5-baseline ablation + master. |
| 3.8 | Техническая документация | **done** | 7/7 | Bundled docs + tooling docs + model block closure note. |

## Coverage

- Functional: **100.0%**
- Work content: **100.0%**
- **Total: 100.0%**
