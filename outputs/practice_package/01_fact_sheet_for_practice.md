# Fact Sheet for Practice Report

Концентрат фактов о выполненной работе. Без теории, без вступлений. Использовать как
single source of truth при заполнении отчёта, индивидуального задания, дневника.

---

## Тема ВКР

**Development of Technology for Extracting and Processing Data from an Array of Heterogeneous Sources.**

Практическая часть моей доли ВКР — Plan→SQL pipeline для NL-запросов к сложным гетерогенным схемам:
dual retrieval (schema + domain docs) → Planner (JSON Plan) → SQL Synthesizer → validation/repair → execution-guided selection. На преддипломной практике реализованы baseline-уровни этого pipeline (B0/B1/B2) на бенчмарке Spider.

## Что именно было сделано в практике

1. Развёрнута воспроизводимая среда экспериментов: локальный Jupyter notebook, подключённый к Google Colab runtime, с проектным root на Google Drive (`/content/drive/MyDrive/diploma_plan_sql/`).
2. Разработан собственный инструментальный контур для управления notebook'ом из агентского окружения: bridge через Flask + cloudflared tunnel (`AGENT_BRIDGE_SETUP` cell + локальный `tools/exec_remote.py`).
3. Скачан и проверен датасет Spider (1034 dev-запросов, 166 SQLite БД); подготовлены подмножества `smoke_10`, `smoke_25`, `smoke_50`.
4. Реализован и прогнан baseline B0 (full-schema NL→SQL) на smoke10 и smoke25 с моделью Qwen2.5-Coder-7B-Instruct, 4-bit nf4 bitsandbytes, greedy-декодинг.
5. Реализован и прогнан baseline B1 (reduced schema через лексический schema linking, table×2 + column×1, min_score=0.5, со стоп-словами) на smoke10 и smoke25.
6. Реализован и прогнан минимальный B2 (Plan→SQL pipeline: planner emits strict JSON Plan, validated against `plan_schema.json`, then plan→SQL prompt) на smoke10.
7. Построены сравнения: B0 vs B1 (на двух subset'ах), aggregate progression smoke10→smoke25, three-way B0/B1/B2 на smoke10.
8. Проведён error-анализ: 8-bucket таксономия (syntax error, wrong join, wrong aggregation, wrong filter, etc.), per-cell breakdown.
9. Подготовлен evidence pack для практики и материалы-черновики для главы экспериментов ВКР.

## Какие baseline реализованы

- **B0** — single-shot full-schema prompt → SQL.
- **B1** — single-shot reduced-schema prompt (lexical token overlap selects relevant tables) → SQL.
- **B2** — two-stage pipeline: prompt → strict JSON Plan (валидация против `plan_schema.json`) → prompt с планом и schema → SQL.

Все три используют один model setup (Qwen2.5-Coder-7B-Instruct, 4-bit nf4, greedy, max_new_tokens=192 для SQL, 256 для plan), один SQL extractor (regex + первый balanced JSON object), один EX-эвалюатор (row-multiset equality в SQLite с 8-сек timeout через `func_timeout`).

## Какие subsets прогнаны

| baseline | smoke10 | smoke25 | smoke50 | dev (n=1034) |
|---|---|---|---|---|
| B0 | ✓ | ✓ | — | — |
| B1 | ✓ | ✓ | — | — |
| B2 | ✓ | — | — | — |

`smoke_10` и `smoke_25` оба полностью из БД `concert_singer` (4 таблицы, smoke10 ⊂ smoke25). Multi-DB sample не прогнан (вне scope практики).

## Какие метрики получены

| baseline / subset | EX | executable | plan_valid | avg schema reduction |
|---|---|---|---|---|
| B0 / smoke10 | **1.0000** (10/10) | 10/10 | — | — |
| B1 / smoke10 | **1.0000** (10/10) | 10/10 | — | 0.475 |
| B0 / smoke25 | **0.9600** (24/25) | 25/25 | — | — |
| B1 / smoke25 | **0.9600** (24/25) | 25/25 | — | 0.580 |
| B2 / smoke10 | **0.7000** (7/10) | 9/10 | 9/10 | 0.475 |

(EX — Execution Match against gold SQL on SQLite; avg schema reduction — средняя доля исходной схемы, которую linker оставил в промпте.)

## Какие артефакты созданы

- 5 файлов predictions JSONL (один на baseline×subset).
- 5 файлов metrics CSV (один на baseline×subset).
- 4 PNG-графика для визуализации сравнений.
- 8 comparison-таблиц (csv + md) — B0vsB1 на двух subset'ах, three-way, aggregate progression, failure buckets.
- 11 logs/audit MD — runtime audit, schema linking audits, design decisions, B2 readiness, etc.
- 5 файлов practice-evidence pack (worklog, checklist, mapping, figure_index, table_index).
- 3 файла кода (B1 module, B2 module, plan schema).
- Инструментальный контур: cell `AGENT_BRIDGE_SETUP`, `tools/exec_remote.py`, `tools/run_cell.py`, `tools/notebook_status.py`, 17 remote scripts.

Полный список с классификацией — `00_inventory.md` / `00_inventory.csv`.

## Что получилось хорошо

- Воспроизводимая среда: каждый запуск сохраняет run-log, audit, predictions; bridge tool позволяет полностью автоматизировать прогон без SendKeys-зависимостей.
- B0 и B1 на single-DB данных дают высокий EX (1.0 на smoke10, 0.96 на smoke25 — обе модели падают на одном и том же запросе idx 16 типа `wrong_aggregation`).
- B1 reduces промпт ~на 50% и не теряет ни одного правильного ответа vs B0 — economically equivalent на этом slice.
- B2 planner выдаёт валидный JSON в 9/10 случаев, parse failures = 0/10. То есть planner *как механизм* работает.
- Ясно зафиксировано failure-mode'ов B2: 2 `result_mismatch` из-за misframe intent ("youngest singer" → LIMIT 1 вместо ALL songs of singer), 1 `plan_invalid` (DISTINCT + filter не вписался в текущую `intent` enum).

## Какие ограничения выявлены

- **Single-DB ограничение subset'ов.** smoke10 и smoke25 целиком из `concert_singer` (4 таблицы). Schema linking может только убрать ненужные таблицы внутри одной БД, но не выбрать правильную БД из многих — самый сильный сигнал недоступен. Вывод: tie B0=B1 на этом slice — не доказательство бесполезности linker'а.
- **B2 регрессия = малая выборка.** На простых single-step single-DB вопросах planner добавляет риск без выгоды. На сложных multi-step вопросах ситуация может развернуться, но multi-step subset вне scope практики.
- **Quantisation 4-bit.** Не измерено, как меняется качество относительно fp16/bf16.
- **Greedy decoding.** Без sampling, без self-consistency, без multi-candidate selection.
- **Cloudflare quick-tunnel ~100s timeout.** Длинные inference-runs обходятся через background-thread pattern на kernel-стороне (см. `13_b2_smoke10_bg.py`), но ngrok auth + named tunnel был бы надёжнее.
- **Один эвалюатор.** EX считает только execution-equivalence; logical-form / partial-credit метрики не вычислены.

## Почему B2 пока хуже B0/B1

Три кейса B2-failure (smoke10), все с `concert_singer`:

| idx | вопрос | bucket | что произошло |
|---|---|---|---|
| 6 | "Show the name and the release year of the song by the youngest singer." | `result_mismatch` | Planner свёл к "выбрать youngest singer", сгенерировал SQL `… LIMIT 1`. |
| 7 | "What are the names and release years for all the songs of the youngest singer?" | `result_mismatch` | Тот же план, та же ошибка — `LIMIT 1` вместо ALL песен этого исполнителя. |
| 8 | "What are all distinct countries where singers above age 20 are from?" | `plan_invalid` | JSON-план не прошёл валидацию против `plan_schema.json` (DISTINCT+filter не выразились в схеме). |

B0 и B1 (без planner) все три случая обрабатывают правильно. Вывод: на простых single-step вопросах planner — pure cost. Это ожидаемое поведение и оно зафиксировано как часть эксперимента (см. `next_step_after_b2.md`).

## Какие результаты можно считать основными для отчёта по практике

Главная количественная таблица:

```
| baseline | smoke10 EX | smoke25 EX | reduction | plan_valid |
| B0       | 1.0000     | 0.9600     | —         | —          |
| B1       | 1.0000     | 0.9600     | 0.475/0.58| —          |
| B2       | 0.7000     | (не запускался) | 0.475 | 9/10      |
```

Главная качественная находка:
- B1 экономит ~50% schema-промпта без потери EX — schema linking рабочая, но на single-DB data доказать gain невозможно.
- B2 на smoke10 регрессирует — planner добавляет риск misframe intent. Methodologically clean signal: B2 даст value только на сложных multi-step / multi-DB вопросах.

Главный методологический результат:
- Построен полный воспроизводимый pipeline B0 → B1 → B2 c artefacts на каждом шаге, error-таксономией и evidence-pack'ом для дальнейших экспериментов.

---

## Ключевые количественные результаты

- **EX_B0 = 1.0 (smoke10), 0.96 (smoke25)**.
- **EX_B1 = 1.0 (smoke10), 0.96 (smoke25)**.
- **EX_B2 = 0.7 (smoke10)**.
- **Avg reduction ratio (B1)**: 0.475 на smoke10, 0.580 на smoke25 (B1 keeps ~48-58% schema).
- **B2 plan_valid_count**: 9/10. **B2 plan_parse_failures**: 0/10.
- **Failure buckets (smoke25)**: `unchanged_correct` 24/25 для обоих B0+B1; единственная ошибка — `wrong_aggregation` на idx 16, *одинаковая для обеих моделей*.

## Ключевые практические результаты

- Подготовлены воспроизводимые артефакты для всех экспериментов (predictions JSONL + run-logs + audits + provenance).
- Реализован собственный bridge-tool для управления notebook'ом без SendKeys-зависимости.
- Документирована trade-off "schema linking economy vs no quality gain" — это сама по себе negative result, который поучительно описать.
- Реализован B2 как полный Plan→SQL pipeline, документированы три специфические ошибки planner'а — основа для дальнейших экспериментов.
- Сформирован evidence pack для дальнейшей сборки главы экспериментов ВКР.

## Ограничения и честные выводы

1. На текущих subset'ах (single-DB) сравнение B0/B1/B2 даёт ограниченный сигнал. Multi-DB sample, B2 на smoke25, и попытки исправить planner — это next steps, явно зафиксированные в `next_step_after_b2.md`.
2. EX — единственная метрика; logical-form / partial-credit не вычислены.
3. 4-bit квантизация может скрывать или вносить численные эффекты, не измерено.
4. Greedy decoding без multi-candidate; B2 без repair-loop.
5. Спайдер benchmark — single-domain; гетерогенные источники (тема ВКР) симулируются разными БД, но не разными модальностями.
6. Practice writeup опирается ровно на полученные числа, без экстраполяций.
