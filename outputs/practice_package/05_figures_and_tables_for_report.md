# Figures & Tables for Practice Report

Полный pack того, что можно вставить в отчёт. Привязка к артефактам в `raw_data/`.

---

## Рисунки (4 PNG)

### Рис. 1 — Прогрессия baseline'ов smoke10 → smoke25

| Параметр | Значение |
|---|---|
| filename | `raw_data/plots/baseline_progression_smoke10_smoke25.png` |
| caption | Сравнение Execution Match для baseline'ов B0 (полная схема) и B1 (редуцированная схема через лексический schema linking) на подмножествах Spider smoke10 (n=10) и smoke25 (n=25). Модель Qwen2.5-Coder-7B-Instruct, 4-битная квантизация, greedy-декодинг. |
| where to place | Раздел 6 «Результаты», первый рисунок. |
| why it is useful | Показывает динамику: B0 и B1 идут вровень, оба теряют 1 case при переходе с smoke10 на smoke25. Главный визуальный аргумент про information-equivalence. |
| mandatory? | **обязательно** |

### Рис. 2 — Three-way B0 vs B1 vs B2 на smoke10

| Параметр | Значение |
|---|---|
| filename | `raw_data/plots/b0_b1_b2_smoke10_bar.png` |
| caption | Сравнение Execution Match для трёх baseline'ов на Spider smoke10 (n=10): B0 (полная схема), B1 (редуцированная схема), B2 (двухступенчатый Plan→SQL pipeline с валидацией JSON-плана). |
| where to place | Раздел 6 «Результаты», второй рисунок. |
| why it is useful | Визуально документирует регрессию B2 (0.7 vs 1.0). Это центральный качественный результат практики. |
| mandatory? | **обязательно** |

### Рис. 3 — B0 vs B1 на smoke25

| Параметр | Значение |
|---|---|
| filename | `raw_data/plots/b0_vs_b1_smoke25_bar.png` |
| caption | EX baseline'ов B0 и B1 на Spider smoke25; обе модели достигают 0.96 (24 из 25), ошибаясь на одном и том же запросе. |
| where to place | Раздел 6 «Результаты», опционально третий рисунок (если есть место). |
| why it is useful | Изолированный взгляд на smoke25; для отчёта на 12–15 страниц можно убрать в приложение, основной сюжет уже в Рис. 1. |
| mandatory? | **опционально** |

### Рис. 4 — B0 vs B1 на smoke10

| Параметр | Значение |
|---|---|
| filename | `raw_data/plots/b0_vs_b1_smoke10_bar.png` |
| caption | EX baseline'ов B0 и B1 на Spider smoke10; обе модели достигают идеальной точности 1.0 (10 из 10). |
| where to place | Можно не вставлять отдельно — данные дублируются Рис. 1 и Рис. 2. |
| why it is useful | Чисто справочно. |
| mandatory? | **необязательно** (можно опустить или поместить в приложение) |

---

## Таблицы — численные (5 ключевых CSV/MD)

### Таблица A — Главная сводка по всем baseline'ам

| Параметр | Значение |
|---|---|
| filename(s) | составить из `raw_data/metrics/{b0,b1,b2}_spider_smoke{10,25}_metrics.csv` |
| caption | Главные количественные результаты практики: EX, executable_count, n, доп. метрики на каждом baseline×subset. |
| where to place | Раздел 6 «Результаты», первая таблица. |
| why it is useful | Single-glance summary для рецензента. Нумерация: «Таблица 1». |
| mandatory? | **обязательно** |

Формат для отчёта:

| Baseline | Subset | n | EX | Executable | Plan valid | Avg reduction |
|---|---|---|---|---|---|---|
| B0 | smoke10 | 10 | 1.0000 | 10 / 10 | — | — |
| B1 | smoke10 | 10 | 1.0000 | 10 / 10 | — | 0.475 |
| B0 | smoke25 | 25 | 0.9600 | 25 / 25 | — | — |
| B1 | smoke25 | 25 | 0.9600 | 25 / 25 | — | 0.580 |
| B2 | smoke10 | 10 | 0.7000 | 9 / 10 | 9 / 10 | 0.475 |

### Таблица B — Three-way comparison на smoke10

| Параметр | Значение |
|---|---|
| filename | `raw_data/tables/b0_b1_b2_smoke10_comparison.csv` (+ `.md`) |
| caption | Three-way сравнение B0 / B1 / B2 на Spider smoke10 с дополнительными колонками `plan_valid_count` и `plan_parse_failures` для B2. |
| where to place | Раздел 6 «Результаты», вторая таблица (рядом с Рис. 2). |
| why it is useful | Содержит точные численные значения, которые видны на Рис. 2; нужна для цитирования в тексте. |
| mandatory? | **обязательно** |

### Таблица C — Прогрессия с дельтами

| Параметр | Значение |
|---|---|
| filename | `raw_data/tables/baseline_progression_smoke10_smoke25.csv` (+ `.md` для текста заключения) |
| caption | Прогрессия baseline'ов B0 и B1 по subset'ам с указанием дельт EX и заключительного предложения о tie. |
| where to place | Раздел 6, третья таблица; можно объединить с Таблицей А, если экономить место. |
| why it is useful | Содержит готовое заключение «tie on both subsets — no benefit, no harm from schema reduction». Можно вставить дословно. |
| mandatory? | **обязательно** |

### Таблица D — Failure buckets на smoke25

| Параметр | Значение |
|---|---|
| filename | `raw_data/tables/b0_b1_failure_buckets.csv` (расширить B2-данными вручную при вставке) |
| caption | Распределение ошибок по таксономии (8 категорий) для B0 и B1 на smoke25; для smoke10 B2 добавлены отдельной колонкой. |
| where to place | Раздел 7 «Анализ ошибок», главная таблица. |
| why it is useful | Конденсированный взгляд на типы ошибок: показывает, что обе модели на smoke25 ошибаются только в 1 случае типа `wrong_aggregation`. |
| mandatory? | **обязательно** |

### Таблица E — Двухсторонние сравнения по subset'ам (одна или обе)

| Параметр | Значение |
|---|---|
| filename | `raw_data/tables/b0_vs_b1_smoke25_comparison.csv` (предпочтительно, smoke25 крупнее), либо `b0_vs_b1_smoke10_comparison.csv` |
| caption | Сравнение B0 vs B1 на Spider smoke25 с количеством улучшений / регрессий / неизменных кейсов. |
| where to place | Раздел 6, четвёртая таблица или одна из двух (smoke25 предпочтительнее, smoke10 убрать). |
| why it is useful | Документирует, что transitions B0→B1 = 0/0/25; демонстрирует «никаких изменений, но дешевле промпт». |
| mandatory? | **выбрать одну из двух** (smoke25 предпочтительно) |

---

## Error / Case артефакты (3 шт., обязательно в отчёт)

### Кейс A — B2 plan examples

| Параметр | Значение |
|---|---|
| filename | `raw_data/tables/b2_plan_examples_smoke10.md` |
| caption | Пять трасс question → JSON Plan → SQL для B2 на smoke10, иллюстрирующие формат plan-output и точки сбоя. |
| where to place | Раздел 7 «Анализ ошибок» или Прил. F. В отчёт — 1 case целиком (idx 6 или idx 8) и ссылка на остальные. |
| why it is useful | Демонстрирует, что планировщик действительно эмитит валидируемый JSON; показывает на конкретном кейсе механизм regression. |
| mandatory? | **обязательно** (хотя бы 1 case в теле) |

### Кейс B — B2 error_cases (компактная)

| Параметр | Значение |
|---|---|
| filename | `raw_data/tables/b2_spider_smoke10_error_cases.md` |
| caption | Все три случая, в которых B2 не достиг execution-match: два `result_mismatch` (плановщик свёл «youngest singer» к LIMIT 1) и один `plan_invalid` (DISTINCT + filter не выразился в схеме плана). |
| where to place | Раздел 7 «Анализ ошибок», после Таблицы D. |
| why it is useful | Краткое (1 страница), все три ошибки помещаются в одну таблицу. Цитировать целиком. |
| mandatory? | **обязательно** |

### Кейс C — Three-way case diff

| Параметр | Значение |
|---|---|
| filename | `raw_data/tables/b0_b1_b2_smoke10_case_diff.md` |
| caption | Подробный разбор пяти кейсов с тремя outcomes (B0 / B1 / B2), снабжённый комментариями о причинах различий. |
| where to place | Прил. E. В тело отчёта взять 1 case (idx 6) полностью. |
| why it is useful | Демонстрирует side-by-side различия трёх baseline'ов на одном вопросе; полезно для разбора Q&A на защите. |
| mandatory? | **обязательно в приложении** |

---

## Сводная карта «куда что вставлять»

| Раздел отчёта | Рисунки | Таблицы | Кейсы |
|---|---|---|---|
| 1. Введение | — | — | — |
| 2. Постановка задачи | — | — | — |
| 3. Среда и инструменты | — | — | — |
| 4. Данные и метрики | — | small subset table (1 строка на subset) | — |
| 5. Реализованные baseline'ы | — | "Сравнение архитектуры B0/B1/B2" (составленная вручную) | — |
| 6. Результаты | Рис. 1, Рис. 2 (+ опц. Рис. 3) | Таблицы A, B, C, E | — |
| 7. Анализ ошибок | — | Таблица D | Кейс A (1 trace), Кейс B (целиком) |
| 8. Заключение | — | — | — |
| 9. Источники | — | — | — |
| Прил. A–H | — | — | Кейс C, и остальное по `06_appendix_pack.md` |

## Минимальный набор для зачёта (если совсем сжато)

- 2 рисунка: Рис. 1 (прогрессия) + Рис. 2 (three-way).
- 2 таблицы: Таблица А (главная сводка) + Таблица D (failure buckets).
- 1 кейс: Кейс B (B2 error_cases — три строки).

С таким набором отчёт остаётся в 12 страниц и содержит ровно ту информацию, которая нужна для оценки выполненной работы.
