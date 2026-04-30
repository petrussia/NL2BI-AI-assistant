# TZ Closure Preflight

Audited at: 2026-04-29T14:57:48.789437+00:00
Status is **derived from physical files only**, no carry-forward of prior claims.

## Functional (2.2.*, 2.3)

| ID | Title | current_status | evidence_present/required | gap_to_close |
|---|---|---|---|---|
| 2.2.1 | Анализ NL-запросов | **partial** | 2/6 | Need explicit query analysis layer (intent + signals) — STAGE 1 in this iteration. |
| 2.2.2 | Определение релевантных источников/таблиц/атрибутов | **done** | 4/4 | Already done. |
| 2.2.3 | Генерация формализованных запросов с safety/performance | **done** | 6/6 | Already done. |
| 2.2.4 | Валидация и repair | **done** | 4/4 | Already done. |
| 2.2.5 | Предварительная обработка и агрегация результатов | **done** | 4/4 | Already done. |
| 2.2.6 | Передача результатов в подсистему аналитического представления | **done** | 3/3 | Already done. |
| 2.3 | Документация (архитектура, форматы, тестирование, эксплуатация) | **not_started** | 0/7 | Need bundled docs/ package — STAGE 2 in this iteration. |

## Work content (3.1–3.8)

| ID | Title | current_status | evidence_present/required | gap_to_close |
|---|---|---|---|---|
| 3.1 | Постановка задачи / ТЗ | **not_started** | 0/3 | Already done. |
| 3.2 | Анализ предметной области | **partial** | 2/3 | Already done. |
| 3.3 | Исследование методов NLP | **partial** | 4/5 | Already done; query_analysis_design.md will reinforce it. |
| 3.4 | Формализация требований | **partial** | 3/5 | Already done. |
| 3.5 | Архитектура системы | **not_started** | 0/4 | Need bundled architecture artefacts — STAGE 3. |
| 3.6 | Прототип системы | **partial** | 6/7 | Already done; query_analysis adds extra component. |
| 3.7 | Экспериментальное исследование | **partial** | 4/8 | Need B2_v1 rerun + B3_v1 + B4_final + multidb_30 ablation — STAGES 4/5/6/8. |
| 3.8 | Техническая документация | **not_started** | 0/5 | Need bundled docs — STAGE 2. |

## Still partial (gaps to close in this iteration)

- **2.2.1** Анализ NL-запросов → Need explicit query analysis layer (intent + signals) — STAGE 1 in this iteration.
- **2.3** Документация (архитектура, форматы, тестирование, эксплуатация) → Need bundled docs/ package — STAGE 2 in this iteration.
- **3.1** Постановка задачи / ТЗ → Already done.
- **3.2** Анализ предметной области → Already done.
- **3.3** Исследование методов NLP → Already done; query_analysis_design.md will reinforce it.
- **3.4** Формализация требований → Already done.
- **3.5** Архитектура системы → Need bundled architecture artefacts — STAGE 3.
- **3.6** Прототип системы → Already done; query_analysis adds extra component.
- **3.7** Экспериментальное исследование → Need B2_v1 rerun + B3_v1 + B4_final + multidb_30 ablation — STAGES 4/5/6/8.
- **3.8** Техническая документация → Need bundled docs — STAGE 2.
