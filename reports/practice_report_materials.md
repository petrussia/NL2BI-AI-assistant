# Материалы для отчета по преддипломной практике

## Введение

В рамках практики реализован и проверен post-query Text-to-Visualization контур для ВКР. Граница работы: Text-to-SQL и качество SQL/БД не оцениваются; на вход визуализационного модуля уже поступают готовая таблица, естественно-языковой запрос и метаданные. Выходом является Vega-Lite спецификация, таблица, рекомендация графика или заготовка дашборда.

Цель практической части: подготовить воспроизводимый бенчмарк, реализовать несколько базовых подходов и сравнить их по валидности Vega-Lite, совпадению с эталонными (gold) спецификациями, выбору полей, устойчивости и вычислительным затратам.

## Что реализовано

Реализованы пять подходов:

| Подход | Метод | Семейство | Sample | run_id | Роль |
| --- | --- | --- | --- | --- | --- |
| B0 | B0_rule_based | Детерминированный baseline | 200 | stage4_cpu_sample200 | Правила без LLM |
| B1 | B1_constraint_ranker | Детерминированный baseline | 200 | stage4_cpu_sample200 | Ограничения и ранжирование кандидатов |
| B2 | B2_partial_recommender | Подход в стиле существующих инструментов | 200 | stage5_partial_sample200 | Частичный recommender fallback |
| B3 | B3_local_llm_qwen3_8b | Локальная LLM | 50 | stage6_qwen3_8b_fast_sample50 | Один кандидат Qwen3-8B |
| B4 | B4_llm_validator_reranker | Локальная LLM + validation | 20 | stage7_b4_sample20_tokens384 | 3 кандидата + validator/reranker |

Этап 8 намеренно пропущен как опциональный: дополнительные LLM-эксперименты требуют GPU-времени, а для отчета уже есть сравнение пяти подходов `B0`-`B4`.

## Методика экспериментов

1. nvBench адаптирован под post-query постановку: SQL используется только в upstream-части для материализации таблицы; downstream-примеры содержат CSV-таблицу, метаданные, NL-запрос и эталонную (gold) Vega-Lite-like spec.
2. Все runs сохранялись в канонической папке Google Drive: `/content/drive/MyDrive/diploma/petr_text_to_visualization_part`.
3. Для каждого метода сохранялись файлы предсказаний jsonl, агрегированные и попримерные метрики, информация о среде выполнения, pip freeze и артефакты рендеринга.
4. Основные метрики: `vega_lite_validity`, `field_selection_f1`, `encoding_accuracy`, `aggregation_accuracy`, `normalized_exact_match`, `failure_rate`, `latency_ms`, `memory_peak_mb`.
5. Для B4 дополнительно сохраняются все 3 кандидата на пример и считается `oracle_success_at_k`.

## Итоговые результаты

### Метрики качества

| Подход | Validity | Chart type | Field F1 | Encoding | Aggregation | Exact match | Oracle@3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 | 1.0 | 0.84 | 0.9595 | 0.5 | 0.915 | 0.225 | 0.55 |
| B1 | 1.0 | 0.955 | 0.995 | 0.5308333333333334 | 0.915 | 0.285 | 0.59 |
| B2 | 1.0 | 0.855 | 0.973 | 0.5766666666666667 | 0.92 | 0.22 | 0.22 |
| B3 | 0.92 | 0.84 | 0.92 | 0.5533333333333333 | 0.66 | 0.28 | 0.28 |
| B4 | 0.95 | 0.9 | 0.95 | 0.5333333333333333 | 0.75 | 0.3 | 0.35 |

### Задержка, память и ошибки

| Подход | Latency ms | Memory MB | Failure rate | Sample |
| --- | --- | --- | --- | --- |
| B0 | 0.331945 | 108.227 | 0.0 | 200 |
| B1 | 0.39675499999999997 | 220.566 | 0.0 | 200 |
| B2 | 7.05238 | 109.949 | 0.0 | 200 |
| B3 | 20101.22146 | 1981.508 | 0.08 | 50 |
| B4 | 66825.6801 | 2127.145 | 0.05 | 20 |

Ключевой результат: `B4_llm_validator_reranker` дает лучший top-1 exact match среди финальных запусков, но проверен на меньшей выборке и дороже по задержке, так как генерирует три кандидата на пример. Среди быстрых детерминированных подходов сильнее всего выглядит `B1_constraint_ranker`, а `B2_partial_recommender` стал заметно лучше после пересборки данных. Практический вариант для интеграции - гибрид: быстрый детерминированный резервный подход (`B1`/`B2`) плюс B4 для случаев, где важнее качество и допустима задержка.

## Выбор подхода для дальнейшей интеграции

Рекомендация:

- Для рабочего резервного варианта: `B1_constraint_ranker` или `B2_partial_recommender`, потому что они быстрые, валидные и воспроизводимые.
- Для исследовательского качества и демонстрации LLM-возможностей: `B4_llm_validator_reranker`.
- Для одиночного LLM-подхода без reranking: `B3_local_llm_qwen3_8b`, если нужно снизить задержку относительно B4.

Итоговая архитектура интеграции: сначала быстрый базовый подход формирует гарантированную валидную визуализацию; при наличии GPU/времени B4 генерирует несколько кандидатов, валидатор фильтрует незаконные спецификации, reranker выбирает лучший результат.

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

- Метрики B3/B4 получены на меньших sample sizes из-за задержки на GPU.
- B2 является частичным резервным подходом в стиле существующих инструментов, а не полноценной NL4DV интеграцией.
- Rendered PNG используется как smoke/inspection artifact; корректность графика определяется метриками качества и ручным анализом.
- Text-to-SQL не входит в оценку.
