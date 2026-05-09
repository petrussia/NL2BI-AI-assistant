# Practice Report Outline (12–15 страниц)

Каркас отчёта, привязанный к уже готовым артефактам. На каждый раздел — какие
конкретные файлы из `raw_data/` использовать, какие цитировать, какие класть в приложения.
Объём в страницах — ориентировочный (страница ≈ 1800 знаков с пробелами, шрифт Times 12 pt, интервал 1.5).

---

## Структура

| № | Раздел | Стр. ~ |
|---|---|---|
| 0 | Титульный лист, реферат, оглавление | 3 |
| 1 | Введение | 1 |
| 2 | Постановка задачи практики | 1 |
| 3 | Среда и инструменты | 1.5 |
| 4 | Данные и метрики | 1 |
| 5 | Реализованные baseline'ы (B0, B1, B2) | 2.5 |
| 6 | Результаты экспериментов | 2 |
| 7 | Анализ ошибок | 1 |
| 8 | Заключение и следующие шаги | 1 |
| 9 | Источники | 0.5 |
| 10 | Приложения | (отдельно от 12–15 стр. лимита) |

Тело отчёта (разделы 1–9) — **~13 страниц**. Приложения — по факту, не в счёт основного объёма.

---

## 1. Введение (~1 стр.)

**Что включить:**
- Тема ВКР (одно предложение).
- Связь практической части ВКР с задачей практики (Plan→SQL pipeline для NL-запросов к гетерогенным схемам, на этой итерации реализованы baseline-уровни B0/B1/B2 на бенчмарке Spider).
- Что было сделано в практике в одном абзаце (3–4 строки).
- Структура отчёта.

**Источник текста:** `01_fact_sheet_for_practice.md` § "Что именно было сделано в практике".

---

## 2. Постановка задачи практики (~1 стр.)

**Что включить:**
- Цель практики (одна формулировка, версия `official_short`).
- Задачи практики (5 пунктов, нумерованный список).

**Источник текста:** `02_individual_task_content.md` версия А (`official_short`). Если нужно длиннее — версия B.

---

## 3. Среда и инструменты (~1.5 стр.)

**Что включить:**
- Колаб + Drive + локальный notebook схема (одна короткая диаграмма или 4 предложения).
- Выбор модели Qwen2.5-Coder-7B-Instruct, обоснование 4-битной квантизации.
- Описание собственного bridge-tool (Flask + cloudflared + `tools/exec_remote.py`) — почему понадобилось, что заменило.
- Версии библиотек.

**Артефакты для цитирования:**
- `raw_data/logs/runtime_project_root_audit.md` — версии torch, transformers, accelerate, bitsandbytes, datasets, pandas; модель GPU.
- `raw_data/logs/bridge_status_drive.md` — описание bridge endpoint, probes.
- `raw_data/logs/b2_design_decision.md` — последний абзац про tooling.

**Что НЕ включать:** долгая теория про SendKeys и причины замены; перенести в одну сноску.

---

## 4. Данные и метрики (~1 стр.)

**Что включить:**
- Spider dev split: 1034 примера, 166 SQLite БД.
- Подмножества `smoke_10`, `smoke_25` (одна БД `concert_singer`, smoke10 ⊂ smoke25). Признать ограничение single-DB здесь сразу.
- Метрика EX (Execution Match): row-multiset equality в SQLite, 8 s timeout через `func_timeout`. Дать формулу одной строкой.
- Дополнительные метрики: `executable_count`, `avg_reduction_ratio` (B1, B2), `plan_valid_count` (B2).

**Артефакты для цитирования:**
- `raw_data/data/spider/SOURCE_AND_AUDIT.md` — источник датасета, проверки целостности.
- `raw_data/logs/smoke25_subset_audit.md` — конкретное содержимое smoke25.

**Таблица в этом разделе:** небольшая описательная таблица "subset → n → unique_dbs → overlap with smoke10".

---

## 5. Реализованные baseline'ы (~2.5 стр.)

### 5.1. B0 — full schema, single-shot
- Шаблон промпта (3–4 строки кода / pseudocode).
- Параметры генерации: greedy, max_new_tokens=192.
- Артефакты: `raw_data/predictions/b0_spider_smoke{10,25}_predictions.jsonl`, `raw_data/metrics/b0_spider_smoke{10,25}_metrics.csv`.

### 5.2. B1 — reduced schema через лексический schema linking
- Описание алгоритма: tokenize question, tokenize table/column names, score table = Σ(2·overlap_table) + Σ(1·overlap_column), keep tables with score ≥ 0.5; full-schema fallback при отсутствии сигнала.
- Параметры linking-pre-pass: `min_score=0.5`, стоп-слова, lowercasing.
- Артефакты: `raw_data/repo/src/evaluation/baselines.py` (код), `raw_data/predictions/b1_spider_*.jsonl`.

### 5.3. B2 — Plan→SQL минимальный pipeline
- Архитектурная схема: question → linker → reduced schema → planner → JSON Plan → validation → planner-to-sql prompt → SQL → execute → EX.
- Что в `plan_schema.json`: required `intent` (enum из 7 значений), `tables`, `operations`; optional `columns`, `filters`, `aggregations`, `group_by`, `order_by`, `limit`, `joins`, `notes`. `additionalProperties: false` на каждом уровне.
- Шаги парсинга: `extract_json_block` (раздевает markdown fences, балансирует скобки) → `json.loads` → `jsonschema.validate`.
- Что осознанно вне scope: repair loop, multi-candidate selection, retrieval, fine-tuning. Сослаться на `b2_design_decision.md`.

**Артефакты для цитирования:**
- `raw_data/repo/docs/plan_schema.json` — упомянуть; полный текст в Прил. C.
- `raw_data/repo/src/evaluation/baselines_b2.py` — упомянуть; полный текст в Прил. D.
- `raw_data/logs/b2_design_decision.md` — обоснование scope.

**Таблица в этом разделе:** «Сравнение архитектуры B0 / B1 / B2» — 3 колонки, 5–6 строк (input prompt, schema, шаги модели, валидация, артефакты).

---

## 6. Результаты экспериментов (~2 стр.)

**Главная таблица отчёта:**

| baseline | smoke10 EX | smoke25 EX | reduction | plan_valid |
|---|---|---|---|---|
| B0 | 1.0000 | 0.9600 | — | — |
| B1 | 1.0000 | 0.9600 | 0.475 / 0.580 | — |
| B2 | 0.7000 | n/a | 0.475 | 9/10 |

Источник: `raw_data/tables/baseline_progression_smoke10_smoke25.csv` + `raw_data/metrics/b2_spider_smoke10_metrics.csv`.

**Рисунки в этом разделе (3 шт.):**
- Рис. 1 — `raw_data/plots/baseline_progression_smoke10_smoke25.png` — общая прогрессия B0/B1 на двух subset'ах.
- Рис. 2 — `raw_data/plots/b0_b1_b2_smoke10_bar.png` — three-way на smoke10.
- (Опционально) Рис. 3 — `raw_data/plots/b0_vs_b1_smoke25_bar.png` — отдельно на smoke25, если нужно показать выпуклость.

**Что вынести в текст:**
- B1 экономит ~50% schema-промпта, не теряя ни одного правильного ответа vs B0 (на этих subset'ах).
- B2 регрессирует на smoke10 на 0.3 EX. Из 9 валидных планов 7 дают правильный SQL, 2 — нет (idx 6, 7); один план не проходит валидацию (idx 8).
- На smoke25 B0 и B1 ошибаются на одной и той же ячейке idx 16 (`wrong_aggregation`).

---

## 7. Анализ ошибок (~1 стр.)

**Что включить:**
- Краткое описание 8-bucket таксономии.
- Таблица: bucket counts B0 / B1 / B2 (упрощённая — собрать из `b0_b1_failure_buckets.csv` + B2 stats).
- 1–2 разобранных кейса B2 regression (idx 6 и idx 8). Покажет, что неправильно сделал planner.

**Артефакты для цитирования:**
- `raw_data/tables/error_taxonomy_smoke25.md` — bucket definitions + per-cell.
- `raw_data/tables/b2_spider_smoke10_error_cases.md` — 3 случая B2 (короткая таблица).
- `raw_data/tables/b2_plan_examples_smoke10.md` — 1–2 трассировки question → plan → SQL.

**Что НЕ включать:** все 25 строк per-cell breakdown — в Прил. F.

---

## 8. Заключение и следующие шаги (~1 стр.)

**Что включить:**
- Что сделано (пункты в логике задач 5.1–5.3).
- Главные количественные находки (3 строки).
- Главное методологическое наблюдение: schema linking на single-DB данных information-equivalent; planner добавляет risk на простых вопросах.
- Зафиксированные next steps:
  1. B2 error triage on smoke10 + tighten planner prompt + re-run.
  2. B2 на smoke25.
  3. Multi-DB sample.
  4. B2.5 retrieval-enhanced.
- Что вне scope: B3, B4, fine-tuning, multi-modal источники.

**Артефакты для цитирования:** `raw_data/logs/next_step_after_b2.md` (можно цитировать дословно "Recommended ordering").

---

## 9. Источники (~0.5 стр.)

Минимальный список:
- Yu et al., "Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task" (2018).
- Hugging Face model card: `Qwen/Qwen2.5-Coder-7B-Instruct`.
- `bitsandbytes` documentation, `nf4` quantisation reference.
- `func_timeout` PyPI page.
- JSON Schema draft-2020-12.
- `cloudflared` quick-tunnel docs.

---

## 10. Приложения (вне 12–15 стр. лимита)

См. `06_appendix_pack.md` для детальной структуры приложений. Ориентир:
- Прил. A — Полные predictions JSONL (5 файлов, по ссылке).
- Прил. B — Run-logs пяти прогонов.
- Прил. C — `plan_schema.json` целиком.
- Прил. D — Листинг `baselines.py` и `baselines_b2.py`.
- Прил. E — `case_diff` файлы (smoke10, smoke25, three-way).
- Прил. F — `error_taxonomy_smoke25.md` per-cell breakdown.
- Прил. G — `b2_design_decision.md`, `b2_implementation_plan.md`, `next_step_after_b2.md`.
- Прил. H — `bridge_status_drive.md`, `artifact_recheck_drive.md`, `b2_preflight_drive.md` — методологический trail.

---

## Что убрать, чтобы не перегружать

- Длинные теоретические преамбулы про NL2SQL — выделить максимум абзацем во введении и переходить к делу.
- Описание истории отбраковки SendKeys — одна сноска, не отдельный раздел.
- Сравнение с другими бенчмарками (BIRD, WikiSQL и т.д.) — упомянуть в одном предложении в § Источники, не разворачивать.
- Подробную теорию JSON Schema — упомянуть draft-2020-12 в источниках.

---

## Сводка по объёму (тело)

| Раздел | Стр. |
|---|---|
| Введение | 1.0 |
| Постановка задачи | 1.0 |
| Среда и инструменты | 1.5 |
| Данные и метрики | 1.0 |
| Реализованные baseline'ы | 2.5 |
| Результаты | 2.0 |
| Анализ ошибок | 1.0 |
| Заключение | 1.0 |
| Источники | 0.5 |
| **Итого тело** | **11.5 стр.** |

С титульным листом, рефератом, оглавлением — **~14.5 страниц**, попадает в лимит 12–15.
