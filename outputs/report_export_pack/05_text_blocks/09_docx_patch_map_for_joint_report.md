# DOCX patch map для общей ВКР (первая версия)

> Применять блоки в порядке снизу вверх для одного раздела (избегает смещения нумерации).
> Не трогать секции и абзацы Петухова (визуализация, BI, UI). Оставлять структурную нумерацию текущего merged draft.

| # | Destination section / подзаголовок | Action | Source block (file in 05_text_blocks/) | Source figure / table | Note |
|---|---|---|---|---|---|
| 1 | Раздел 3. Подсистема интерпретации запросов и извлечения данных | replace | `01_section3_shubin_ready_blocks.md` целиком | `04_figures/system_architecture_overview.png` (после §3.1), `04_figures/ablation_pipeline_ladder.png` (после §3.2) | Если в текущем draft есть generic NL→SQL описание — заменить на этот блок. Сохранить заголовок "3." и номер. |
| 2 | Раздел 5.1. Реализованные модули | replace | `02_section5_shubin_ready_blocks.md` §5.1 | `03_tables/component_registry.csv` сразу после блока | Перечень 14 модулей. Если в текущем draft есть отдельные таблички — удалить. |
| 3 | Раздел 5.2. Архитектурная схема Шубина | insert_after предыдущего абзаца про модули | `02_section5_shubin_ready_blocks.md` §5.2 | `04_figures/system_architecture_overview.png` | Фигура с подписью «Архитектура подсистемы извлечения». |
| 4 | Раздел 5.3. Безопасность исполнения | replace | `02_section5_shubin_ready_blocks.md` §5.3 | — | Если в draft есть сходный материал — заменить. |
| 5 | Раздел 5.4. Контракт интеграции | replace или insert_after предыдущего раздела | `02_section5_shubin_ready_blocks.md` §5.4 | — | Один абзац про AnalyticsPayload v1; обязательно сохранить. |
| 6 | Раздел 6. Методика и результаты экспериментов | replace всю экспериментальную главу части Шубина | `03_section6_shubin_ready_blocks.md` целиком | См. ниже | Внутри блока размечены подзаголовки 6.1–6.8. |
| 6.1 | Раздел 6.1. Конфигурация экспериментов | (часть `03_section6...`) | — | — | Таблица бенчмарков и моделей в тексте. |
| 6.2 | Раздел 6.2. Главные результаты на внутренних подмножествах | (часть `03_section6...`) | таблица 1 из `02_numbers/final_numbers_for_joint_report.md` | `04_figures/master_overview.png` | Главная диаграмма. |
| 6.3 | Раздел 6.3. Главный научный результат (multi-DB) | (часть `03_section6...`) | `03_tables/multidb30_strongest_configs.md` | `04_figures/multidb30_strongest_configs.png` | Главный научный вывод. |
| 6.4 | Раздел 6.4. Right-sizing | (часть `03_section6...`) | `03_tables/qwen14b_vs_qwen7b_comparison.md` | `04_figures/model_comparison_multidb30.png` + `model_comparison_smoke25.png` | 14B vs 7B. |
| 6.5 | Раздел 6.5. Внешняя валидация | (часть `03_section6...`) | `03_tables/external_validation_matrix.md` | `04_figures/external_validation_overview.png` | BIRD + Spider 2.0-Lite. |
| 6.6 | Раздел 6.6. Эффект v2-фикса | (часть `03_section6...`) | `03_tables/b3v2_vs_b3v1.csv` + `b4v2_vs_b4final.csv` | — | Парная дельта таблица. |
| 6.7 | Раздел 6.7. Production-рекомендация | (часть `03_section6...`) | — | `04_figures/strongest_baselines_overview.png` | Финальный визуальный итог. |
| 6.8 | Раздел 6.8. Ограничения | replace | `06_limitations_and_blockers_ready_block.md` | — | Полный честный блок. |
| 7 | Заключение | replace всю секцию заключения часть Шубина | `04_conclusion_shubin_ready_blocks.md` | — | 4 абзаца академического стиля. |
| 8 | Личный вклад (Шубин) | replace | `05_personal_contribution_shubin_ready_block.md` | — | Точная граница с Петуховым. |
| 9 | Аннотация / реферат (если есть отдельный) | append или замена куска про результаты | `07_results_summary_short_block.md` | — | Однострочные / двух-абзацные сводки. |
| 10 | Приложение A — Master matrix | append | `01_master/final_experiment_master_matrix.md` или CSV | `03_tables/master_matrix.md` | Полный сводный реестр всех прогонов. |
| 11 | Приложение B — Gap matrix | append | `03_tables/full_closure_gap_matrix.md` | — | Reproducibility audit. |
| 12 | Приложение C — Blocker artifacts | append | `06_limitations_and_blockers_ready_block.md` + ссылки на `outputs/logs/deepseek_blocker_final_h100.md` | — | Честная документация неосуществлённого. |

### Что НЕ трогать в текущем draft
- Любые разделы / абзацы Петухова (BI, дашборды, UI, визуализация).
- Practice-package narrative.
- Общую структурную нумерацию глав (только содержимое внутри).

### Чеклист после применения patch map
1. Все цифры в тексте совпадают с `02_numbers/final_numbers_for_joint_report.md`.
2. Все рисунки имеют подпись из `04_figures/figure_captions_ready.md`.
3. Все таблицы имеют caption из `03_tables/table_list_for_joint_report.md`.
4. Spell-check (ru-RU).
5. Нумерация рисунков / таблиц перепроверена.
