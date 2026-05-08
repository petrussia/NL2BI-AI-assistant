# Отчет по проверке этапа 9: финальные материалы для отчета по практике

Дата: 2026-05-08

Статус: завершен.

Этап 8 включен в обновленную сборку: добавлены Stage 8 LLM baseline `B5a`-`B5d`, включая Qwen3-14B, Mistral Small 3.2, Gemma 3 12B и Gemma 4 E2B.

## Финальные запуски

| Подход | Метод | run_id | Папка метрик | Sample | Семейство | Роль |
| --- | --- | --- | --- | --- | --- | --- |
| B0 | B0_rule_based | stage4_cpu_sample200 | B0_rule_based | 200 | Детерминированный baseline | Правила без LLM |
| B1 | B1_constraint_ranker | stage4_cpu_sample200 | B1_constraint_ranker | 200 | Детерминированный baseline | Ограничения и ранжирование кандидатов |
| B2 | B2_partial_recommender | stage5_partial_sample200 | B2_partial_recommender | 200 | Подход в стиле существующих инструментов | Частичный recommender fallback |
| B3 | B3_local_llm_qwen3_8b | stage6_qwen3_8b_fast_sample50 | B3_local_llm_qwen3_8b | 50 | Локальная LLM | Один кандидат Qwen3-8B |
| B4 | B4_llm_validator_reranker | stage7_b4_sample20_tokens384 | B4_llm_validator_reranker | 20 | Локальная LLM + validation | 3 кандидата + validator/reranker |
| B5a | B5_stage8_qwen3_14b | stage8_qwen3_14b_sample20 | B5_stage8_qwen3_14b | 20 | Stage 8 LLM + strict JSON validator | Qwen3-14B, один кандидат, validator retry |
| B5b | B5_stage8_mistral_small_32_24b_bnb4 | stage8_mistral_small_32_24b_bnb4_sample20 | B5_stage8_mistral_small_32_24b_bnb4 | 20 | Stage 8 LLM + strict JSON validator | Mistral Small 3.2 24B bnb-4bit, один кандидат |
| B5c | B5_stage8_gemma3_12b_it | stage8_gemma3_12b_it_sample20 | B5_stage8_gemma3_12b_it | 20 | Stage 8 LLM + strict JSON validator | Gemma 3 12B IT, gated HF model |
| B5d | B5_stage8_gemma4_e2b_it | stage8_gemma4_e2b_it_sample20 | B5_stage8_gemma4_e2b_it | 20 | Stage 8 LLM + strict JSON validator | Gemma 4 E2B IT, малый контрольный LLM baseline |

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
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\05_make_report_materials.ipynb -Action cell -CellId stage9-setup -WaitForCellCompletion -CompletionText STAGE9_SETUP_OK -WaitSeconds 1800 -ReloadFromDisk:$false -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\05_make_report_materials.ipynb -Action cell -CellId stage9-build-materials -WaitForCellCompletion -CompletionText STAGE9_BUILD_OK -WaitSeconds 1800 -ReloadFromDisk:$false -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\05_make_report_materials.ipynb -Action cell -CellId stage9-verify-artifacts -WaitForCellCompletion -CompletionText STAGE9_VERIFY_OK -WaitSeconds 1800 -ReloadFromDisk:$false -Json
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

Найдено папок runs: 8

Файл инвентаризации:

```text
reports/stage9_report_materials/run_inventory.json
```

Финальные run_id, использованные в отчете:

- `stage4_cpu_sample200`: B0, B1
- `stage5_partial_sample200`: B2
- `stage6_qwen3_8b_fast_sample50`: B3
- `stage7_b4_sample20_tokens384`: B4
- `stage8_qwen3_14b_sample20`: B5a
- `stage8_mistral_small_32_24b_bnb4_sample20`: B5b
- `stage8_gemma3_12b_it_sample20`: B5c
- `stage8_gemma4_e2b_it_sample20`: B5d

## Проверка

- Aggregate metrics объединены в один пакет сравнения.
- Создано не менее 3 рисунков; локальные PNG визуально проверены на читаемость.
- `stage9_tables.xlsx` содержит встроенные PNG-графики для метрик качества и системных метрик; исходные значения графиков сохранены как числовые ячейки.
- Colab-проверка нашла обязательные Drive-артефакты и вывела `STAGE9_VERIFY_OK`.
- Итоговая рекомендация включена в `practice_report_materials.md`.
- Все финальные run_id и пути к артефактам перечислены.
- Этап 8 пересчитан на sample20. Qwen3-14B стал лучшим новым одиночным LLM baseline; Gemma 3 12B показала высокий failure rate и требует отдельной доработки prompt/chat template.

## Проблемы и замечания

- Этап 8 включен в отчет как дополнительное сравнение LLM-моделей. Метрики Stage 8 нужно читать с учетом sample20.
- B3/B4/Stage8 запускались на меньших выборках из-за GPU-задержки; B4 может немного плавать по `oracle_success_at_k`, потому что часть кандидатов генерируется с температурой.
- Логика B0/B1/B2 не менялась после финального Stage 4/5 прогона; для Stage 9 обновлены только метрики и материалы.
- Локальная пересборка workbook может быть пропущена, если `stage9_tables.xlsx` открыт в Excel; Colab создает workbook штатно.
- Сетка примеров генерируется из Drive-артефактов финального B4 run; при локальной пересборке без Drive генератор использует резервную схему.

## Следующие шаги

- Использовать `reports/practice_report_materials.md` как основной источник для написания отчета на 12-15 страниц.
- Использовать `reports/stage9_report_materials/stage9_tables.xlsx` и `tables/*.csv` для таблиц.
- Использовать `reports/stage9_report_materials/figures/*.png` для иллюстраций.
- После принятия review закоммитить материалы отчета, сводные таблицы, notebook, script и review markdown.
