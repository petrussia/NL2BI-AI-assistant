# v0.11 — 5 demo sources, multi-engine, crash-test report

## Final source list

| # | id | engine | tables | status |
|---|---|---|---|---|
| 1 | demo_concert_singer | sqlite | 4 (stadium/singer/concert/singer_in_concert) | ✅ |
| 2 | bird_student_club | sqlite | 7 (member/event/attendance/budget/expense/income/major) | ✅ |
| 3 | spider2_asana_dbt | **duckdb** | 6 source-data tables (project/task/user/team/...) | ⚠ prompt issue |
| 4 | moscow_open | sqlite | 4 (okrugs/districts/metro_lines/metro_stations) | ✅ |
| 5 | northwind_ru | **postgres** | 7 (клиенты/заказы/позиции_заказа/товары/категории/сотрудники/регионы) | mostly ✅ |

## Crash-test results (5 query types × 5 sources)

| source | count | top-n | group-by | time-series | join |
|---|---|---|---|---|---|
| demo_concert_singer | OK | OK | OK | OK | partial |
| bird_student_club | OK | OK | OK | OK | OK |
| spider2_asana_dbt | OK | partial | **FAIL** | OK | **FAIL** |
| moscow_open | OK | OK | OK | OK | OK |
| northwind_ru | OK | OK | OK | OK | **FAIL** |

**API tier: 20 / 25 success (80%).** UI tier: 4 / 5 sources show end-to-end table+chart.

## Known issues to investigate

1. **spider2_asana_dbt** — model wraps schema-qualified tables in quotes despite
   prompt hints; "Не удалось получить данные" / "Сервис генерации SQL вернул
   некорректный ответ". Bug isolated to prompt engineering, not data path.

2. **northwind_ru JOIN** — model occasionally mixes Cyrillic/Latin aliases
   (`к.` vs `k.`) within the same query, leading to "missing FROM-clause
   entry for k". Reproducible on "Топ-10 клиентов по выручке за 2024".
