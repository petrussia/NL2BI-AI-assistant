# Отчет по проверке этапа 9: финальные материалы для отчета по практике

Дата: 2026-04-26

Статус: завершен.

Этап 8 намеренно пропущен как опциональный. Новые LLM-эксперименты не запускались, логика базовых подходов не изменялась.

## Финальные запуски

| Подход | Метод | run_id | Папка метрик | Sample | Семейство | Роль |
| --- | --- | --- | --- | --- | --- | --- |
| B0 | B0_rule_based | stage4_cpu_sample200 | B0_rule_based | 200 | Детерминированный baseline | Правила без LLM |
| B1 | B1_constraint_ranker | stage4_cpu_sample200 | B1_constraint_ranker | 200 | Детерминированный baseline | Ограничения и ранжирование кандидатов |
| B2 | B2_partial_recommender | stage5_partial_sample200 | B2_partial_recommender | 200 | Подход в стиле существующих инструментов | Частичный recommender fallback |
| B3 | B3_local_llm_qwen3_8b | stage6_qwen3_8b_fast_sample50 | B3_local_llm_qwen3_8b | 50 | Локальная LLM | Один кандидат Qwen3-8B |
| B4 | B4_llm_validator_reranker | stage7_b4_sample20_tokens384 | B4_llm_validator_reranker | 20 | Локальная LLM + validation | 3 кандидата + validator/reranker |

## Выходные материалы

Локальный пакет:

```text
reports/stage9_report_materials
```

Пакет в Google Drive:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/reports/stage9_report_materials
```

## Выполненные команды

Локально:

```powershell
python scripts/make_stage9_report_materials.py
Set-Location reports/stage9_report_materials/latex
& "$env:USERPROFILE\.codex\plugins\cache\openai-bundled\latex-tectonic\0.1.0\bin\tectonic.exe" --outdir . quality_metrics_table.tex
Set-Location ..\..\..
python -m pytest -q
```

Colab через runner:

```powershell
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\05_make_report_materials.ipynb -Action cell -CellId stage9-setup -WaitSeconds 20 -ReloadFromDisk:$false -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\05_make_report_materials.ipynb -Action cell -CellId stage9-build-materials -WaitSeconds 30 -ReloadFromDisk:$false -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\05_make_report_materials.ipynb -Action cell -CellId stage9-verify-artifacts -WaitSeconds 15 -ReloadFromDisk:$false -Json
```

## Таблицы

- `tables/comparison_solutions.csv`
- `tables/quality_metrics.csv`
- `tables/latency_memory_failure.csv`
- `tables/applicability.csv`
- `tables/risks_limitations.csv`
- `stage9_tables.xlsx`

## Рисунки

- `figures/pipeline_architecture.png`
- `figures/nvbench_postquery_flow.png`
- `figures/key_metrics_comparison.png`
- `figures/system_metrics_comparison.png`
- `figures/examples_grid_gold_vs_predicted.png`

## Markdown для отчета

- `reports/practice_report_materials.md`
- `reports/stage9_report_materials/practice_report_materials.md`

## Инвентаризация runs

Найдено папок runs: 4

Файл инвентаризации:

```text
reports/stage9_report_materials/run_inventory.json
```

Финальные run_id, использованные в отчете:

- `stage4_cpu_sample200`: B0, B1
- `stage5_partial_sample200`: B2
- `stage6_qwen3_8b_fast_sample50`: B3
- `stage7_b4_sample20_tokens384`: B4

## Проверка

- Aggregate metrics объединены в один пакет сравнения.
- Создано не менее 3 рисунков; локальные PNG визуально проверены на читаемость.
- `stage9_tables.xlsx` содержит встроенные PNG-графики для метрик качества и системных метрик; исходные значения графиков сохранены как числовые ячейки.
- Colab-проверка нашла обязательные Drive-артефакты и вывела `STAGE9_VERIFY_OK`.
- Итоговая рекомендация включена в `practice_report_materials.md`.
- Все финальные run_id и пути к артефактам перечислены.
- Работа по этапу 8 не начиналась.

## Проблемы и замечания

- Этап 8 намеренно пропущен, потому что уже сравнены пять подходов, а дополнительные LLM runs увеличили бы GPU-затраты.
- Новые LLM-эксперименты на этом этапе не запускались.
- Логика базовых подходов не изменялась.
- Локальная пересборка workbook может быть пропущена, если `stage9_tables.xlsx` открыт в Excel; Colab создает workbook штатно.
- Сетка примеров генерируется из Drive-артефактов финального B4 run; при локальной пересборке без Drive генератор использует резервную схему.

## Следующие шаги

- Использовать `reports/practice_report_materials.md` как основной источник для написания отчета на 12-15 страниц.
- Использовать `reports/stage9_report_materials/stage9_tables.xlsx` и `tables/*.csv` для таблиц.
- Использовать `reports/stage9_report_materials/figures/*.png` для иллюстраций.
- После принятия review закоммитить материалы отчета, сводные таблицы, notebook, script и review markdown.
