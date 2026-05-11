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

---

## v0.12 hardening on Blackwell + FK graph (final state)

Switched emitter from 4-bit NF4 to **BF16** on RTX PRO 6000 Blackwell
(95 GB VRAM). Added explicit FK graph + PK markers to the schema
prompt. Added 3 new prompt rules: no nested aggregates, follow FK paths
(don't invent direct joins through intermediate tables), check FK
targets before writing nonexistent columns.

| Source | Hard failures BEFORE | Hard failures NOW |
|---|---:|---:|
| demo_concert_singer | 0 | 0 |
| bird_student_club | 0 | 0 |
| spider2_asana_dbt | 2 | **0** |
| moscow_open | 0 | 0 |
| northwind_ru | 1 | **0** |
| **TOTAL** | **3-5** | **0/25** |

* Latency improved 4× (count query: 2.6s → 0.6s on BF16).
* All 25/25 queries generate valid executable SQL.
* Remaining 5 "partial_success" results have empty rows because the
  underlying data is sparse (asana has only 1 task in task_data, BIRD
  test slice is small), not because the SQL is wrong.

### Underlying fixes (final commits)

* `3553780` — BF16 quantization mode for fat GPUs
* `822c110` — FK graph + PK markers + nested-aggregate prompt rule
* `474c1dd` — pg_catalog query for FK collection (information_schema
  was GRANT-gated for read-only role); heuristic FK inference for
  DuckDB (dbt projects don't declare FK constraints).
