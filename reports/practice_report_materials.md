# Материалы для отчета по преддипломной практике

## Введение

В рамках практики реализован и проверен post-query Text-to-Visualization контур для ВКР. Граница работы: Text-to-SQL и качество SQL/БД не оцениваются; на вход визуализационного модуля уже поступают готовая таблица, естественно-языковой запрос и метаданные. Выходом является Vega-Lite спецификация, таблица, рекомендация графика или заготовка дашборда.

Цель практической части: подготовить воспроизводимый бенчмарк, реализовать несколько базовых подходов и сравнить их по валидности Vega-Lite, совпадению с эталонными (gold) спецификациями, выбору полей, устойчивости и вычислительным затратам.

## Что реализовано

Реализованы базовые подходы B0-B4 и дополнительные Stage 8 LLM-подходы B5a-B5d:

| Подход | Метод | Семейство | Sample | run_id | Роль |
| --- | --- | --- | --- | --- | --- |
| B0 | B0_rule_based | Детерминированный baseline | 200 | stage4_cpu_sample200 | Правила без LLM |
| B1 | B1_constraint_ranker | Детерминированный baseline | 200 | stage4_cpu_sample200 | Ограничения и ранжирование кандидатов |
| B2 | B2_partial_recommender | Подход в стиле существующих инструментов | 200 | stage5_partial_sample200 | Частичный recommender fallback |
| B3 | B3_local_llm_qwen3_8b | Локальная LLM | 50 | stage6_qwen3_8b_fast_sample50 | Один кандидат Qwen3-8B |
| B4 | B4_llm_validator_reranker | Локальная LLM + validation | 20 | stage7_b4_sample20_tokens384 | 3 кандидата + validator/reranker |
| B5a | B5_stage8_qwen3_14b | Stage 8 LLM + strict JSON validator | 20 | stage8_qwen3_14b_sample20 | Qwen3-14B, один кандидат, validator retry |
| B5b | B5_stage8_mistral_small_32_24b_bnb4 | Stage 8 LLM + strict JSON validator | 20 | stage8_mistral_small_32_24b_bnb4_sample20 | Mistral Small 3.2 24B bnb-4bit, один кандидат |
| B5c | B5_stage8_gemma3_12b_it | Stage 8 LLM + strict JSON validator | 20 | stage8_gemma3_12b_it_sample20 | Gemma 3 12B IT, gated HF model |
| B5d | B5_stage8_gemma4_e2b_it | Stage 8 LLM + strict JSON validator | 20 | stage8_gemma4_e2b_it_sample20 | Gemma 4 E2B IT, малый контрольный LLM baseline |

Этап 8 добавлен отдельным блоком: `B5a`-`B5d` сравнивают новые LLM-модели с тем же строгим JSON/Vega-Lite validator и retry-контуром. Эти прогоны выполнены на `sample20`, поэтому они полезны для выбора LLM-кандидата, но не заменяют полное сравнение `B0`-`B2` на `sample200`.

## Методика экспериментов

1. nvBench адаптирован под post-query постановку: SQL используется только в upstream-части для материализации таблицы; downstream-примеры содержат CSV-таблицу, метаданные, NL-запрос и эталонную (gold) Vega-Lite-like spec.
2. Все runs сохранялись в канонической папке Google Drive: `/content/drive/MyDrive/diploma/petr_text_to_visualization_part`.
3. Для каждого метода сохранялись файлы предсказаний jsonl, агрегированные и попримерные метрики, информация о среде выполнения, pip freeze и артефакты рендеринга.
4. Основные метрики: `vega_lite_validity`, `field_selection_f1`, `encoding_accuracy`, `aggregation_accuracy`, `normalized_exact_match`, `failure_rate`, `latency_ms`, `memory_peak_mb`.
5. Для B4 дополнительно сохраняются все 3 кандидата на пример и считается `oracle_success_at_k`; для Stage 8 моделей фиксируется один основной кандидат после validator retry.

## Итоговые результаты

### Метрики качества

| Подход | Validity | Chart type | Field F1 | Encoding | Aggregation | Exact match | Oracle@3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 | 1.0 | 0.84 | 0.9595 | 0.5 | 0.915 | 0.225 | 0.55 |
| B1 | 1.0 | 0.955 | 0.995 | 0.5308333333333334 | 0.915 | 0.285 | 0.59 |
| B2 | 1.0 | 0.855 | 0.973 | 0.5766666666666667 | 0.92 | 0.22 | 0.22 |
| B3 | 0.92 | 0.84 | 0.92 | 0.5533333333333333 | 0.66 | 0.28 | 0.28 |
| B4 | 0.95 | 0.9 | 0.95 | 0.5333333333333333 | 0.75 | 0.3 | 0.35 |
| B5a | 1.0 | 0.9 | 1.0 | 0.575 | 0.85 | 0.3 | 0.3 |
| B5b | 1.0 | 0.85 | 0.99 | 0.4 | 0.8 | 0.25 | 0.25 |
| B5c | 0.15 | 0.15 | 0.15 | 0.075 | 0.15 | 0.05 | 0.05 |
| B5d | 0.9 | 0.7 | 0.89 | 0.35 | 0.65 | 0.1 | 0.1 |

### Задержка, память и ошибки

| Подход | Latency ms | Memory MB | Failure rate | Sample |
| --- | --- | --- | --- | --- |
| B0 | 0.331945 | 108.227 | 0.0 | 200 |
| B1 | 0.39675499999999997 | 220.566 | 0.0 | 200 |
| B2 | 7.05238 | 109.949 | 0.0 | 200 |
| B3 | 20101.22146 | 1981.508 | 0.08 | 50 |
| B4 | 66825.6801 | 2127.145 | 0.05 | 20 |
| B5a | 8133.003999999999 | 2064.027 | 0.0 | 20 |
| B5b | 6045.25885 | 1889.961 | 0.0 | 20 |
| B5c | 69237.6294 | 2556.523 | 0.85 | 20 |
| B5d | 44562.2476 | 2200.0 | 0.1 | 20 |

Ключевой результат: среди быстрых детерминированных подходов сильнее всего выглядит `B1_constraint_ranker`, а среди новых LLM baseline лучший результат на `sample20` дал `Qwen3-14B` (`B5a`): он повторил B4 по exact match, получил 100% validity и оказался заметно быстрее B4. `Mistral Small 3.2` (`B5b`) выглядит как быстрый LLM-кандидат, но немного уступает Qwen3-14B по качеству. `Gemma 3 12B` (`B5c`) в текущем prompt/schema режиме не рекомендуется из-за высокого failure rate. Практический вариант для интеграции - гибрид: быстрый детерминированный резервный подход (`B1`/`B2`) плюс `Qwen3-14B` или B4 для случаев, где важнее качество и допустима задержка.

## Выбор подхода для дальнейшей интеграции

Рекомендация:

- Для рабочего резервного варианта: `B1_constraint_ranker` или `B2_partial_recommender`, потому что они быстрые, валидные и воспроизводимые.
- Для исследовательского качества и демонстрации LLM-возможностей: `B5_stage8_qwen3_14b` как лучший одиночный LLM baseline на sample20; B4 остается полезным как reranker/validator baseline.
- Для быстрого одиночного LLM-подхода без reranking: `B5_stage8_mistral_small_32_24b_bnb4`, если важна задержка и допускается небольшое снижение качества относительно Qwen3-14B.

Итоговая архитектура интеграции: сначала быстрый базовый подход формирует гарантированную валидную визуализацию; при наличии GPU/времени LLM-контур генерирует Vega-Lite JSON, validator не пропускает некорректные спецификации, а reranker используется только там, где несколько кандидатов реально улучшают качество.

## Рисунки для отчета

Минимальный набор рисунков:

1. `reports/stage9_report_materials/figures/pipeline_architecture.png` - архитектура экспериментального pipeline.
2. `reports/stage9_report_materials/figures/nvbench_postquery_flow.png` - адаптация nvBench под post-query.
3. `reports/stage9_report_materials/figures/key_metrics_comparison.png` - сравнение ключевых метрик качества.
4. `reports/stage9_report_materials/figures/system_metrics_comparison.png` - сравнение latency, memory и failure rate.
5. `reports/stage9_report_materials/figures/examples_grid_gold_vs_predicted.png` - сетка "эталон vs предсказание" для финального B4 run.

## Список артефактов

Финальные папки runs:

- `stage4_cpu_sample200`: `/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage4_cpu_sample200`
- `stage5_partial_sample200`: `/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage5_partial_sample200`
- `stage6_qwen3_8b_fast_sample50`: `/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage6_qwen3_8b_fast_sample50`
- `stage7_b4_sample20_tokens384`: `/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage7_b4_sample20_tokens384`
- `stage8_qwen3_14b_sample20`: `/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage8_qwen3_14b_sample20`
- `stage8_mistral_small_32_24b_bnb4_sample20`: `/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage8_mistral_small_32_24b_bnb4_sample20`
- `stage8_gemma3_12b_it_sample20`: `/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage8_gemma3_12b_it_sample20`
- `stage8_gemma4_e2b_it_sample20`: `/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage8_gemma4_e2b_it_sample20`

Материалы этапа 9:

- `reports/stage9_report_materials/stage9_tables.xlsx`
- `reports/stage9_report_materials/tables/*.csv`
- `reports/stage9_report_materials/latex/quality_metrics_table.tex`
- `reports/stage9_report_materials/latex/quality_metrics_table.pdf`, если доступна компиляция LaTeX
- `reports/stage9_report_materials/figures/*.png`
- `reports/stage9_report_materials/run_inventory.json`

Копия в Google Drive:

`/content/drive/MyDrive/diploma/petr_text_to_visualization_part/reports/stage9_report_materials`

## Приложение: команды

### Запуск финального B4

```powershell
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\03_run_local_llm.ipynb -Action cell -CellId stage7-run20 -WaitForCellCompletion -CompletionText STAGE7_RUN20_OK -WaitSeconds 5400 -ReloadFromDisk:$false -Json
```

### Генерация материалов этапа 9

```powershell
python scripts/make_stage9_report_materials.py
```

### Проверка outputs в notebook

```powershell
python -c "import nbformat; nb=nbformat.read('notebooks/03_run_local_llm.ipynb', as_version=4); nbformat.validate(nb)"
```

### Тесты

```powershell
python -m pytest -q
```

## Ограничения

- Метрики B3/B4/B5 получены на меньших sample sizes из-за задержки на GPU; B0-B2 посчитаны на sample200, B3 на sample50, B4/B5 на sample20.
- B2 является частичным резервным подходом в стиле существующих инструментов, а не полноценной NL4DV интеграцией.
- Rendered PNG используется как smoke/inspection artifact; корректность графика определяется метриками качества и ручным анализом.
- Text-to-SQL не входит в оценку.
