# Appendix Pack

Содержательная структура приложений к отчёту по практике. Каждый блок —
готовый кандидат в «Прил. X». Указано: что брать целиком, что урезать,
что упомянуть только ссылкой, что не нужно вообще.

---

## Прил. A — Полные predictions JSONL (5 файлов)

| Файл | Что внутри | Объём | Действие |
|---|---|---|---|
| `raw_data/predictions/b0_spider_smoke10_predictions.jsonl` | 10 строк JSON: idx, question, db_id, gold_sql, generated_raw, generated_sql, executable, execution_match, error_type, error_message | 4.4 KB | **Упомянуть и приложить** в виде отдельного файла или дать QR/ссылку на репо. Не печатать в pdf. |
| `raw_data/predictions/b1_spider_smoke10_predictions.jsonl` | те же поля + `selected_tables`, `schema_reduction_ratio`, `fallback_used` | 5.6 KB | **Упомянуть и приложить.** |
| `raw_data/predictions/b0_spider_smoke25_predictions.jsonl` | 25 строк, поля как у B0/smoke10 | 12.2 KB | **Упомянуть и приложить.** |
| `raw_data/predictions/b1_spider_smoke25_predictions.jsonl` | 25 строк, поля B1 | 15.0 KB | **Упомянуть и приложить.** |
| `raw_data/predictions/b2_spider_smoke10_predictions.jsonl` | 10 строк, поля B0 + `plan_raw`, `plan_parsed`, `plan_valid`, `plan_error` + B1-поля | 11.6 KB | **Упомянуть и приложить.** |

**Формулировка в отчёте:** «Полные предсказания моделей в формате JSON Lines приведены в прил. A (файлы `b{0,1,2}_spider_smoke{10,25}_predictions.jsonl`). Объём 49 KB, 80 строк суммарно».

---

## Прил. B — Run-logs (5 текстовых файлов)

| Файл | Что внутри | Действие |
|---|---|---|
| `raw_data/logs/b0_spider_smoke10_runlog.txt` | timestamp, model id, subset, total/EX/exec_count, elapsed_seconds | **Приложить целиком** (по 0.4 KB каждый). |
| `raw_data/logs/b0_spider_smoke25_runlog.txt` | то же | приложить целиком |
| `raw_data/logs/b1_spider_smoke10_runlog.txt` | то же + schema_strategy, avg_reduction_ratio | приложить целиком |
| `raw_data/logs/b1_spider_smoke25_runlog.txt` | то же | приложить целиком |
| `raw_data/logs/b2_spider_smoke10_runlog.txt` | то же + planner, plan_valid_count, plan_parse_failures, fallback_full_schema_count | приложить целиком |

5 run-log'ов помещаются на одну страницу. Это reproducibility-evidence.

---

## Прил. C — JSON Schema плана B2

| Файл | Действие |
|---|---|
| `raw_data/repo/docs/plan_schema.json` | **Приложить целиком** (3.5 KB, ~120 строк). Это центральный артефакт B2. Использовать в обсуждении при защите. |

---

## Прил. D — Листинг кода

| Файл | Размер | Действие |
|---|---|---|
| `raw_data/repo/src/evaluation/baselines.py` | 2.5 KB | **Приложить листингом** в monospace, нумерация строк. Внутри: `lexical_schema_linking`, `build_b1_prompt`, `compare_b0_b1_result_record`. |
| `raw_data/repo/src/evaluation/baselines_b2.py` | 4.6 KB | **Приложить листингом**. Внутри: `make_plan_prompt`, `extract_json_block`, `parse_and_validate_plan`, `make_plan_to_sql_prompt`. |

Оба файла вместе — ~7 KB кода, ~200 строк, 3-4 страницы листинга.

---

## Прил. E — Case diffs

| Файл | Содержимое | Действие |
|---|---|---|
| `raw_data/tables/b0_vs_b1_case_diff.md` | 5 кейсов B0 vs B1 на smoke10 (все unchanged, поскольку B0=B1) | **Приложить.** На защиту полезно — показывает, что и B0, и B1 одинаково правильно решают одни и те же задачи. |
| `raw_data/tables/b0_vs_b1_smoke25_case_diff.md` | 5 кейсов B0 vs B1 на smoke25 | **Приложить.** Аналогично. |
| `raw_data/tables/b0_b1_b2_smoke10_case_diff.md` | 5 кейсов B0/B1/B2 на smoke10 | **Приложить целиком.** Это самый ценный приложенный артефакт. |

---

## Прил. F — Развёрнутый разбор ошибок

| Файл | Действие |
|---|---|
| `raw_data/tables/error_taxonomy_smoke25.md` | **Приложить целиком.** Содержит определения 8 buckets и per-cell breakdown по smoke25 (1 строка про idx 16). |
| `raw_data/tables/b0_b1_failure_buckets.csv` | **Приложить.** 8 строк, 3 колонки. |
| `raw_data/tables/b2_spider_smoke10_error_cases.md` | Уже в теле отчёта — в приложение не дублировать. |

---

## Прил. G — Документы планирования и заключения

| Файл | Действие |
|---|---|
| `raw_data/logs/b2_design_decision.md` | **Приложить.** Содержит обоснование решения сделать B2 минимальным (без repair loop, без multi-candidate), а также объяснение, почему `plan_schema.json` был авторизован в рамках практики. |
| `raw_data/logs/b2_implementation_plan.md` | **Приложить.** Заранее зафиксированный scope B2 — показывает, что результат не «подгонялся» под цифру. |
| `raw_data/logs/next_step_after_b2.md` | **Приложить.** Зафиксированные next steps — материал для рассуждения «что планируется в ВКР». |

---

## Прил. H — Методологический trail

| Файл | Действие |
|---|---|
| `raw_data/logs/runtime_project_root_audit.md` | **Приложить.** Версии библиотек, GPU. |
| `raw_data/logs/bridge_status_drive.md` | **Приложить.** Описание bridge endpoint и проб. |
| `raw_data/logs/artifact_recheck_drive.md` | **Приложить.** Recheck 25 ключевых артефактов перед B2. |
| `raw_data/logs/b2_preflight_drive.md` | **Приложить.** Гейт перед запуском B2. |
| `raw_data/data/spider/SOURCE_AND_AUDIT.md` | **Приложить.** Источник датасета и проверки целостности. |
| `raw_data/logs/smoke25_subset_audit.md` | **Приложить.** Аудит подмножества (overlap с smoke10, db distribution). |

---

## Что НЕ нужно класть в приложения

- `outputs/tables/b{0,1}_spider_smoke{10,25}_examples.md` — первые 5 примеров каждого baseline'а; они дублируют JSONL и плохо читаются на бумаге.
- `outputs/tables/b{0,1}_spider_smoke{10}_error_cases.md` — пустые (на smoke10 ни одной ошибки).
- `outputs/tables/b1_schema_linking_examples.md` и `_smoke25_examples.md` — таблицы линкинга по строкам; одного представительного примера в теле раздела 5 достаточно.
- `outputs/logs/local_helper_script_audit.md`, `local_notebook_audit.md`, `b1_ready_checklist.md`, `next_step_readiness.md` — устарели или пересмотрены.
- `outputs/logs/_bridge_write_test.txt` — debug only, удалить из выгрузки.
- `outputs/logs/thesis_*.md` — для главы экспериментов ВКР, не для практики.

---

## Сводная таблица приложений

| № | Заголовок | Источники | Объём | Обязательно? |
|---|---|---|---|---|
| A | Полные предсказания моделей (JSONL) | 5 jsonl, 49 KB суммарно | по ссылке | да |
| B | Run-logs прогонов | 5 txt | 1 страница | да |
| C | JSON-схема плана B2 | `plan_schema.json` | 3 страницы | да |
| D | Листинг модулей `baselines.py`, `baselines_b2.py` | 2 .py | 4 страницы | да |
| E | Case diffs | 3 md | 4 страницы | да |
| F | Таксономия ошибок | 1 md + 1 csv | 1 страница | да |
| G | Планирование и заключение | 3 md | 3 страницы | да |
| H | Методологический trail | 6 файлов | 4 страницы | желательно |

**Итого приложения:** ~20 страниц + предсказания JSONL по ссылке. Это реальная нижняя оценка; можно ужать до ~12-14, если убрать H целиком и сократить F/G.
