# integration_packet_peter.md

Аудит выполнен в режиме read-only по продуктовому коду: код, тесты, скрипты экспериментов и существующие артефакты не изменялись. Итоговый файл является отдельным интеграционным отчётом для согласования post-query Text-to-Visualization модуля Петра с upstream-модулем Дениса.

## 1. Snapshot репозитория

| Поле | Значение |
|---|---|
| Branch | `experiments/peter` |
| Commit hash | `885ac18e60996b6b2822ed59991e9df79ad8105e` |
| Root path | `C:/Users/user/Учёба/4 курс/Диплом/Практика` |
| Дата/время аудита | `2026-05-09 03:30:41 +03:00` |
| Режим аудита | Без изменения продуктового кода, без коммитов, без тяжёлых LLM/Colab запусков |

Git status на момент аудита:

```text
 M reports/practice_report_materials.md
 M reports/stage9_report_materials/figures/examples_grid_gold_vs_predicted.png
 M reports/stage9_report_materials/figures/examples_grid_source.txt
 M reports/stage9_report_materials/figures/figure_manifest.json
 M reports/stage9_report_materials/practice_report_materials.md
 M reports/stage_reviews/STAGE_9_REVIEW.md
 M scripts/make_stage9_report_materials.py
?? reports/stage9_report_materials/figures/component_match_heatmap.png
```

Это уже существующее dirty-состояние рабочей копии. В рамках аудита оно не откатывалось и не нормализовывалось.

Ключевые директории и файлы:

| Путь | Назначение |
|---|---|
| `src/t2v_eval/data/schema.py` | Текущие dataclass-контракты `FieldMetadata`, `T2VExample`, `T2VPrediction`. |
| `src/t2v_eval/data/nvbench_adapter.py` | Подготовка post-query nvBench: materialized CSV tables, metadata, gold specs, examples JSONL. |
| `src/t2v_eval/data/quality.py` | Проверки качества таблиц/metadata, признаки chart intent, sampling. |
| `src/t2v_eval/baselines/rule_based.py` | B0 rule-based baseline. |
| `src/t2v_eval/baselines/constraint_ranker.py` | B1 constraint-ranker baseline. |
| `src/t2v_eval/baselines/nl4dv_adapter.py` | B2 partial recommender и best-effort NL4DV adapter. |
| `src/t2v_eval/baselines/llm_vegalite.py` | B3/B5 single-candidate LLM JSON/Vega-Lite generation, validation, repair. |
| `src/t2v_eval/baselines/llm_validator_reranker.py` | B4 multi-candidate LLM validator/reranker. |
| `src/t2v_eval/normalization/vega_lite.py` | Нормализация Vega-Lite-like spec для comparison metrics. |
| `src/t2v_eval/rendering/render.py`, `scripts/render_charts.py` | PNG rendering через `vl-convert-python`. |
| `src/t2v_eval/metrics/*.py` | Spec, ranking и system metrics. |
| `scripts/run_experiment.py` | CLI entrypoint для B0/B1/B2. |
| `scripts/run_llm_experiment.py` | CLI entrypoint для B3 и single Stage 8 models. |
| `scripts/run_llm_rerank_experiment.py` | CLI entrypoint для B4. |
| `scripts/run_stage8_large_llm.py` | Stage 8 model runner и model registry. |
| `scripts/evaluate_predictions.py` | Оценка predictions JSONL против examples JSONL. |
| `configs/stage8_large_llm_models.json` | Конфиг B5a-B5d: HF model ids, quantization, VRAM guard. |
| `reports/stage_reviews/*.md` | Stage-by-stage audit/review evidence. |
| `reports/stage9_report_materials/tables/*.csv` | Локально проверенные итоговые таблицы метрик и run inventory. |
| `tests/*.py` | Unit/smoke tests; `pytest -q` прошёл: `63 passed in 22.29s`. |

Проверенные entrypoint-команды:

```powershell
python scripts\run_experiment.py --help
python scripts\run_stage8_large_llm.py --list-models --json
pytest -q
```

`run_experiment.py --help` подтверждает поддержку `--examples`, `--method {B0_rule_based,B1_constraint_ranker,B2_partial_recommender,all}`, `--drive-root`, `--run-id`, `--sample-size`, `--top-k`, `--no-evaluate`, `--render-limit`, `--json`.

`run_stage8_large_llm.py --list-models --json` подтверждает ключи `gemma3_12b_it`, `gemma4_e2b_it`, `mistral_small_32_24b_bnb4`, `qwen3_14b` с model id, quantization, min VRAM и recommended Colab GPU.

## 2. Карта текущей архитектуры Text-to-Visualization

| Слой | Статус | Файлы/функции/классы | Назначение | Внешние зависимости |
|---|---|---|---|---|
| Input parsing | Реализован для batch/evaluation, не как production API | `T2VExample.from_dict`, `scripts/run_experiment.py`, `scripts/run_llm_experiment.py`, `scripts/run_llm_rerank_experiment.py`, `scripts/run_stage8_large_llm.py` | Читает examples JSONL, превращает строки в `T2VExample`, выбирает sample, пишет `examples_used.jsonl`. | `argparse`, project utils, `json` |
| Metadata parsing | Реализован частично | `FieldMetadata.from_dict`, `T2VExample.fields`, `metadata_from_dataframe`, `load_fields` | Читает `metadata.fields`; если metadata отсутствует, B0/B1/B2 пытаются вывести поля из CSV через pandas. | `pandas` |
| Intent extraction | Реализован эвристически | `detect_intent`, `detect_chart_hint`, `_has_top_signal`, `_has_group_signal` | Классифицирует запрос как `trend`, `comparison`, `top`, `correlation`, `distribution`, `table`, `dashboard`. | `re` |
| Candidate generation | Реализован для B0/B1/B2/B4 | `generate_candidates`, `generate_partial_candidates`, `LLMValidatorRerankerPredictor.predict` | Генерирует bar/line/scatter/histogram/text candidates, LLM candidates, сохраняет top-k. | `pandas`, `transformers` для LLM |
| Constraints/validation | Реализован частично/строго для LLM | `passes_hard_constraints`, `validate_generated_spec`, `_strict_schema_error`, `_spec_contract_error`, `validate_spec_legality` | Проверяет mark/encoding, существование полей, type compatibility, allowed aggregations, JSON strictness. | `json`, нормализатор проекта |
| Ranking | Реализован | B0 score constants, B1 `_score`, B2 `_score_fields`, B4 `score_candidate` | Выбирает top candidate по эвристикам intent, field rank, simplicity, legality, parsimony. | нет отдельных ML-зависимостей |
| LLM generation | Реализован для B3/B4/B5 | `LLMVegaLitePredictor`, `LLMValidatorRerankerPredictor`, `run_stage8_model` | Генерирует Vega-Lite JSON локальными HF-моделями, умеет retry с validator feedback. | `torch`, `transformers`, `bitsandbytes` в runtime; в `requirements.txt` не зафиксированы |
| Normalized spec | Реализован | `normalize_spec`, `normalize_encoding`, `normalize_transforms`, `canonical_json` | Делает canonical comparison core: `valid`, `chart_type`, `encoding`, `transform`, `fields`, `canonical_json`. | stdlib |
| Rendering/export | Частично реализован | `render_predictions`, `render_single` | Рендерит PNG из Vega-Lite spec + первые 500 строк CSV. SVG/HTML/PDF export как production interface не найден. | `pandas`, `vl-convert-python` |
| Metrics/evaluation | Реализован | `evaluate_spec`, `evaluate_ranking`, `summarize_system_metrics`, `evaluate_predictions` | Считает validity, chart type accuracy, field precision/recall/F1, encoding/aggregation/transform accuracy, exact match, oracle@k, latency, memory, failure rate. | `psutil`, stdlib |
| Artifacts/logging | Реализован для экспериментов | `runs/<run_id>`, `predictions/*.jsonl`, `metrics/*.csv`, `rendered/*.png`, `experiment_summary.json`, `runtime_info.json`, `pip_freeze.txt` | Сохраняет воспроизводимые артефакты batch-прогонов; production manifest API не найден. | project utils |

Фактический pipeline сейчас:

1. `prepare_nvbench.py` или `nvbench_adapter.prepare_nvbench_dataset` создаёт `examples_sample*.jsonl` и CSV tables.
2. `run_experiment.py` запускает B0/B1/B2 по JSONL examples.
3. `run_llm_experiment.py`, `run_llm_rerank_experiment.py`, `run_stage8_large_llm.py` запускают LLM variants.
4. Predictions сохраняются как `T2VPrediction` JSONL.
5. `evaluate_predictions.py` считает метрики против gold specs.
6. `render_charts.py` рендерит PNG для manual inspection.
7. `make_stage9_report_materials.py` собирает отчётные таблицы и фигуры.

Архитектура остаётся experiment-first. Готового `POST /visualize` или runtime service wrapper в коде не найдено.

## 3. Текущий входной контракт модуля

Текущий реальный входной контракт задаётся `T2VExample`:

```python
class T2VExample:
    example_id: str
    query: str
    table_path: str
    metadata: dict[str, Any]
    gold_spec: dict[str, Any] = {}
    gold_spec_normalized: dict[str, Any] | None = None
    benchmark: str | None = None
    benchmark_source: str | None = None
```

`gold_spec` и `gold_spec_normalized` нужны для evaluation. Baseline-предикторы не должны использовать gold spec при inference.

### Форматы входа

| Вход | Реальный статус | Где найдено | Комментарий |
|---|---|---|---|
| JSONL examples | Реализован | `read_jsonl`, `T2VExample.from_dict`, runner scripts | Основной batch-интерфейс. |
| CSV path | Реализован | `table_path`, `pd.read_csv(example.table)` | Основной формат таблицы для inference/evaluation. |
| pandas DataFrame | Внутренне используется | `nvbench_adapter`, `profile_fields`, `render_single` | Не является публичным входным контрактом baseline runner. |
| JSON records / inline rows | Не найдено как публичный runtime input | нет production API | Stage 8 prompt включает table preview, но он строится из CSV. |
| Arrow URI | Не найдено | нет | Может быть целевым форматом интеграции, но сейчас не поддержан. |
| SQL | Не является входом downstream | `nvbench_adapter.extract_sql` только для materialization gold table | Text-to-SQL и качество SQL вне текущего модуля. |

### Формат пользовательского запроса

Реально используется строка `query: str`.

Использование:

- B0/B1: `detect_intent`, `detect_chart_hint`, `rank_fields`.
- B2: `rank_fields`, но основной выбор идёт от table/profile.
- B3/B4/B5: `build_prompt` вставляет query в prompt для LLM.

Если query отсутствует, текущий dataclass ожидает ключ `query`; безопасного production fallback не найдено. В целевом контракте `user_query` должен быть required.

### Формат metadata

Текущий `metadata` - свободный dict, где основной структурный блок:

```json
{
  "fields": [
    {
      "name": "Rank",
      "dtype": "string",
      "role": "dimension",
      "description": null,
      "unit": null,
      "periodicity": null,
      "allowed_aggregations": []
    }
  ]
}
```

`FieldMetadata` реально поддерживает только:

```python
class FieldMetadata:
    name: str
    dtype: str
    role: "dimension|measure|time|id|unknown" = "unknown"
    description: str | None = None
    unit: str | None = None
    periodicity: str | None = None
    allowed_aggregations: list[str] = []
```

### Metadata-поля из промта

| Поле | Текущий статус | Используется алгоритмами | Комментарий |
|---|---|---|---|
| `field name` / `name` | Реализовано, обязательное внутри `FieldMetadata.from_dict` | Да | Главный идентификатор поля; используется для encoding, linking, legality. |
| `source column name` | Не найдено отдельным полем | Нет | Сейчас `name` одновременно и logical field, и source column. Для интеграции лучше добавить `source_column`. |
| `data type` / `dtype` | Реализовано | Да | Влияет на role inference, Vega type, compatibility checks. |
| `semantic type` | Частично через `role` | Да | Отдельного `semantic_type` нет. |
| `role` | Реализовано | Да | `measure`, `dimension`, `time`, `id`, `unknown`; `text` не входит в Literal. |
| `description` | Реализовано | Частично | Учитывается в `rank_fields`; полезно для LLM prompt. |
| `unit` | Реализовано | Слабо | Учитывается в text haystack для field ranking; не влияет на axes formatting. |
| `periodicity` | Реализовано | Слабо | Вставляется в compact schema для LLM; deterministic logic почти не использует. |
| `allowed_aggregations` | Реализовано | Да | B1/B4/B5 проверяют legality; B0 выбирает default aggregate. |
| `default aggregation` | Не найдено отдельным полем | Нет | B0 использует `_default_aggregate` из `allowed_aggregations`, но явного поля нет. |
| `grain` | Не найдено | Нет | Нужно для временных рядов и предотвращения неверной агрегации. |
| `nullable` | Не найдено в `FieldMetadata` | Нет | Табличный profiling B2 считает non-null ratio, но не как input contract. |
| `value examples` | Не найдено в metadata | Нет | Stage 8 prompt добавляет table preview из CSV, не metadata examples. |
| `cardinality` | Не найдено как metadata поле | Частично вычисляется B2 | B2 `profile_fields` считает cardinality из CSV. |
| `source table` | Не найдено в `FieldMetadata` | Нет | В nvBench metadata есть `db_id`/`source_key`, но не per-field source table. |
| `provenance` | Не найдено как structured field | Нет | Нужна для объяснений фильтров/агрегаций. |
| `metric definition` | Не найдено | Нет | Важна для BI-качества и корректных titles. |
| `formatting hints` | Не найдено | Нет | Не используется для currency/percent/date formatting. |

Обязательные поля metadata сейчас:

- Для `FieldMetadata.from_dict`: `name` обязательно.
- `dtype` фактически optional в parser, default `unknown`.
- `role` optional, default `unknown`.
- Остальные поля optional.

Поля, реально используемые алгоритмами:

- `name`: все baselines, metrics, validation.
- `dtype`: type inference, `_kind`, `_vega_type`, validation.
- `role`: field grouping and legality.
- `description`: field ranking and LLM prompt.
- `unit`: field ranking and LLM prompt.
- `periodicity`: LLM prompt, documentation value.
- `allowed_aggregations`: aggregation legality and default aggregation.

Поля, которые нужны для лучшего качества, но отсутствуют:

- `source_column`, чтобы отделять человекочитаемый alias от физического имени.
- `semantic_type`, чтобы различать money, percent, count, ratio, category, free text.
- `default_aggregation`, чтобы не угадывать sum/mean/count.
- `grain` и `periodicity_confidence`, чтобы выбирать line chart и aggregation level.
- `nullable`, `cardinality`, `sample_values`, чтобы выбирать table/bar/scatter и обрабатывать nulls.
- `source_table` и `provenance`, чтобы объяснять использованные поля и фильтры.
- `format`, `formatting_hints`, чтобы сайт красиво отрисовывал axes/tooltips.

## 4. Текущий выходной контракт модуля

Текущий реальный выход задаётся `T2VPrediction`:

```python
class T2VPrediction:
    run_id: str
    method: str
    example_id: str
    status: "ok|failed" = "ok"
    raw_output: str | None = None
    raw_spec: dict[str, Any] | None = None
    normalized_spec: dict[str, Any] | None = None
    candidates: list[dict[str, Any]] = []
    latency_ms: float | None = None
    memory_peak_mb: float | None = None
    error: str | None = None
```

Фактические output-поля:

| Выход | Статус | Где найдено | Комментарий |
|---|---|---|---|
| raw visualization spec | Реализовано | `raw_spec` | Обычно Vega-Lite-like dict. |
| normalized spec | Реализовано | `normalized_spec` | Core для метрик; не полный production spec. |
| Vega-Lite spec | Частично реализовано | `raw_spec`, `render_single` | Specs Vega-Lite-like, не всегда полный `$schema`. |
| table spec | Частично | `mark: "text"` | Отдельного table-view contract нет. |
| candidates | Реализовано | `candidates` | B0/B1/B2 top-k, B4 ranked LLM candidates, B3/B5 single candidate wrapper. |
| scores | Реализовано внутри candidates | `score` | Score эвристический, шкалы различаются между методами. |
| selected candidate | Реализовано неявно | `raw_spec = candidates[0]` или reranked winner | Отдельного поля `selected_candidate_id` нет. |
| validation errors | Частично | `error`, candidate `validator`, `validation_attempts` | Подробно только в LLM validation paths. |
| render path | Реализовано как experiment artifact | `rendered/<method>/*.png` | Не возвращается в `T2VPrediction`. |
| PNG support | Реализовано | `render_charts.py`, `vl_convert.vegalite_to_png` | Только PNG подтверждён. |
| SVG/HTML/PDF support | Не найдено как implemented output | нет | `vl-convert` потенциально умеет больше, но код пишет только PNG. |
| manifest | Частично | `experiment_summary.json`, `stage8_model_summary.json`, `run_inventory.json` | Нет unified production manifest. |
| latency | Реализовано | `latency_ms` | Среднее попадает в metrics. |
| memory | Реализовано | `memory_peak_mb` | Через psutil/process RSS или GPU runtime JSON for LLM scripts. |
| error status | Реализовано | `status`, `error` | Значения `ok`/`failed`, не `success|partial_success|failed`. |

Различия B0-B5:

| Подход | Метод | Input | Output spec | Candidates | Validation | Rendering |
|---|---|---|---|---|---|---|
| B0 | `B0_rule_based` | `T2VExample` + CSV path + metadata | Vega-Lite-like `raw_spec` | Да, top-k эвристический | Только normalizer validity | PNG через отдельный script |
| B1 | `B1_constraint_ranker` | То же | Vega-Lite-like `raw_spec` | Да, generated + sorted | Hard constraints: fields, types, aggregation | PNG через отдельный script |
| B2 | `B2_partial_recommender` | То же + pandas profile | Vega-Lite-like `raw_spec` | Да | Normalizer validity; optional NL4DV conversion | PNG через отдельный script |
| B3 | `B3_local_llm_qwen3_8b` | То же + table preview | LLM-generated Vega-Lite JSON | Обычно 1 candidate | Strict JSON, retry, spec contract | PNG через отдельный script |
| B4 | `B4_llm_validator_reranker` | То же + table preview | Winner among LLM candidates | Да, ranked candidates with validator payload | JSON/spec legality + reranker | PNG через отдельный script |
| B5a-d | `B5_stage8_*` | То же + Stage 8 config | LLM-generated Vega-Lite JSON | Single-mode by default | Strict JSON validator + VRAM guard before run | PNG optional via render_limit |

## 5. Предлагаемый контракт `VisualizationRequest`

Целевой контракт должен отделить production inference от benchmark evaluation. Gold spec не должен приходить от upstream в runtime-запросе.

```python
class VisualizationRequest(BaseModel):
    request_id: str
    user_query: str
    locale: str = "ru-RU"
    timezone: str = "Europe/Moscow"
    data_source: DataSource
    result_table: ResultTable
    field_metadata: list[FieldMetadataV2]
    query_context: QueryContext = QueryContext()
    presentation_preferences: PresentationPreferences = PresentationPreferences()

class DataSource(BaseModel):
    id: str
    name: str
    dialect: Literal["postgresql", "sqlite", "clickhouse", "trino", "unknown"] = "unknown"
    schema_version: str | None = None

class ResultTable(BaseModel):
    format: Literal["records", "csv_uri", "arrow_uri"]
    columns: list[str]
    rows: list[dict[str, Any]] = []
    uri: str | None = None
    row_count: int
    truncated: bool = False

class FieldMetadataV2(BaseModel):
    name: str
    source_column: str | None = None
    dtype: str = "unknown"
    semantic_type: str | None = None
    role: Literal["measure", "dimension", "time", "id", "text", "unknown"] = "unknown"
    description: str | None = None
    unit: str | None = None
    periodicity: str | None = None
    allowed_aggregations: list[str] = []
    default_aggregation: str | None = None
    grain: str | None = None
    nullable: bool | None = None
    value_examples: list[Any] = []
    cardinality: int | None = None
    source_table: str | None = None
    provenance: dict[str, Any] | None = None
    metric_definition: str | None = None
    formatting_hints: dict[str, Any] = {}

class QueryContext(BaseModel):
    sql: str | None = None
    plan: dict[str, Any] | None = None
    filters: list[dict[str, Any]] = []
    group_by: list[str] = []
    aggregations: list[dict[str, Any]] = []
    order_by: list[dict[str, Any]] = []
    limit: int | None = None
    assumptions: list[str] = []

class PresentationPreferences(BaseModel):
    preferred_output: Literal["chart", "table", "auto"] = "auto"
    preferred_chart_type: str | None = None
    style_template: str | None = None
    max_candidates: int = 5
    render: bool = True
```

Полевая спецификация:

| Поле | Required | Тип | Зачем downstream | Если отсутствует | Критичность |
|---|---:|---|---|---|---|
| `request_id` | Да | string | Корреляция logs/artifacts, идемпотентность, `GET /visualize/{id}` | Сгенерировать UUID на backend boundary | High |
| `user_query` | Да | string | Intent extraction, field linking, LLM prompt, explanation | Fallback к auto chart по metadata/table profile | High |
| `locale` | Нет | string | Titles, number/date formatting, language of explanation | `ru-RU` | Medium |
| `timezone` | Нет | string | Temporal bucketing, labels, user-facing dates | `Europe/Moscow` | Medium |
| `data_source.id` | Да | string | Provenance, debugging, source-specific quirks | `"unknown"` допустимо только для smoke | Medium |
| `data_source.name` | Да | string | Explanation/UI | `"unknown"` | Low |
| `data_source.dialect` | Нет | enum | SQL/query context interpretation; future source quirks | `unknown` | Low |
| `data_source.schema_version` | Нет | string/null | Совместимость metadata/schema | `null` | Low |
| `result_table.format` | Да | enum | Как загрузить таблицу | Reject request if no table payload | High |
| `result_table.columns` | Да | list[string] | Field validation/order, fallback metadata inference | Вывести из rows/CSV header; warning | High |
| `result_table.rows` | Условно | list[object] | Inline small table | Required when format=`records` | High |
| `result_table.uri` | Условно | string/null | Large table input via CSV/Arrow | Required when format=`csv_uri`/`arrow_uri` | High |
| `result_table.row_count` | Да | integer | Edge cases: 0/1 rows, table too long, truncation | Infer after load if possible | High |
| `result_table.truncated` | Нет | boolean | Warn that visualization may be partial | `false`, but add warning if row_count unknown | Medium |
| `field_metadata` | Да | list | Main schema/semantic signal | Infer from table with low confidence | High |
| `field_metadata.name` | Да | string | Visualization field id | Reject that field; infer from columns | High |
| `field_metadata.source_column` | Нет | string/null | Map aliases to physical columns | Use `name` | Medium |
| `field_metadata.dtype` | Нет | string | Vega type and validation | Infer from data sample | High |
| `field_metadata.semantic_type` | Нет | string/null | Money/percent/count/ratio handling | Use `dtype` + `role` only | Medium |
| `field_metadata.role` | Нет | enum | Select measures/dimensions/time | Infer from dtype/name | High |
| `field_metadata.description` | Нет | string/null | Field linking and explanations | Omit; quality lower | Medium |
| `field_metadata.unit` | Нет | string/null | Axis labels and aggregation semantics | Omit unit label | Medium |
| `field_metadata.periodicity` | Нет | string/null | Time series choice and grain | Infer from dates if possible | Medium |
| `field_metadata.allowed_aggregations` | Нет | list[string] | Prevent invalid sum/avg/count | Default conservative: count for dimensions, sum/mean for measures | High |
| `field_metadata.default_aggregation` | Нет | string/null | Avoid arbitrary sum vs mean | Choose from allowed by heuristic | High |
| `field_metadata.grain` | Нет | string/null | Prevent double aggregation | Add warning, avoid aggressive regrouping | Medium |
| `field_metadata.nullable` | Нет | boolean/null | Warnings and null handling | Infer from data sample | Low |
| `field_metadata.value_examples` | Нет | list | LLM/context and field disambiguation | Build preview from rows | Medium |
| `field_metadata.cardinality` | Нет | int/null | Bar/table/scatter decision | Estimate from sample | Medium |
| `field_metadata.source_table` | Нет | string/null | Provenance/explanation | Omit | Low |
| `field_metadata.provenance` | Нет | object/null | Explain filters/joins/derived fields | Omit; explanation weaker | Medium |
| `field_metadata.metric_definition` | Нет | string/null | BI correctness | Omit; add warning for ambiguous metrics | Medium |
| `field_metadata.formatting_hints` | Нет | object | UI formatting | Default Vega/browser formatting | Low |
| `query_context.sql` | Нет | string/null | Provenance/debug only; not evaluated for quality | `null`; downstream must not generate SQL | Low |
| `query_context.plan` | Нет | object/null | Explain upstream plan, derived fields | `null` | Low |
| `query_context.filters` | Нет | list | Explanation and title | `[]` | Medium |
| `query_context.group_by` | Нет | list | Detect already aggregated table | Infer from columns/metadata | Medium |
| `query_context.aggregations` | Нет | list | Detect measures already aggregated | Infer from field names like `count(...)` | High |
| `query_context.order_by` | Нет | list | top-N/table sorting | Infer from query if possible | Medium |
| `query_context.limit` | Нет | int/null | top-N/table decision | Infer from row_count/query | Medium |
| `query_context.assumptions` | Нет | list[string] | Auditability | `[]` | Low |
| `presentation_preferences.preferred_output` | Нет | enum | Respect explicit chart/table request | `auto` | Medium |
| `presentation_preferences.preferred_chart_type` | Нет | string/null | Chart hint | Infer from user_query | Medium |
| `presentation_preferences.style_template` | Нет | string/null | UI theme | Default service style | Low |
| `presentation_preferences.max_candidates` | Нет | integer | Control top-k | `5`, clamp to safe max | Low |
| `presentation_preferences.render` | Нет | boolean | Whether to produce artifacts | `true` for site, `false` for API-only smoke | Medium |

Минимальный JSON shape:

```json
{
  "request_id": "string",
  "user_query": "string",
  "locale": "ru-RU",
  "timezone": "Europe/Moscow",
  "data_source": {
    "id": "string",
    "name": "string",
    "dialect": "postgresql",
    "schema_version": null
  },
  "result_table": {
    "format": "records",
    "columns": [],
    "rows": [],
    "uri": null,
    "row_count": 0,
    "truncated": false
  },
  "field_metadata": [],
  "query_context": {
    "sql": null,
    "plan": null,
    "filters": [],
    "group_by": [],
    "aggregations": [],
    "order_by": [],
    "limit": null,
    "assumptions": []
  },
  "presentation_preferences": {
    "preferred_output": "auto",
    "preferred_chart_type": null,
    "style_template": null,
    "max_candidates": 5,
    "render": true
  }
}
```

## 6. Предлагаемый контракт `VisualizationResponse`

```python
class VisualizationResponse(BaseModel):
    request_id: str
    status: Literal["success", "partial_success", "failed"]
    selected_view: SelectedView | None
    candidates: list[VisualizationCandidate] = []
    table_view: dict[str, Any] = {}
    explanation: Explanation
    quality: QualityBlock
    performance: PerformanceBlock
    errors: list[ErrorBlock] = []

class SelectedView(BaseModel):
    type: Literal["chart", "table"]
    chart_type: Literal["bar", "line", "scatter", "pie", "area", "table", "unknown"]
    title: str
    spec: dict[str, Any]
    normalized_spec: dict[str, Any]
    rendered_artifacts: RenderedArtifacts = RenderedArtifacts()

class RenderedArtifacts(BaseModel):
    png_uri: str | None = None
    svg_uri: str | None = None
    html_uri: str | None = None

class VisualizationCandidate(BaseModel):
    candidate_id: str
    type: Literal["chart", "table"]
    chart_type: str
    spec: dict[str, Any]
    normalized_spec: dict[str, Any]
    score: float | None = None
    reason: str | None = None
    validation: dict[str, Any] = {}
    warnings: list[str] = []

class Explanation(BaseModel):
    intent: str | None = None
    used_fields: list[str] = []
    used_aggregations: list[dict[str, Any]] = []
    reason: str

class QualityBlock(BaseModel):
    confidence: float | None = None
    validation_passed: bool
    warnings: list[str] = []

class PerformanceBlock(BaseModel):
    latency_ms: int | None = None
    model: str | None = None
    mode: Literal["fast", "quality", "fallback"]

class ErrorBlock(BaseModel):
    code: str
    message: str
    field: str | None = None
    recoverable: bool = True
```

Обязательная JSON shape:

```json
{
  "request_id": "string",
  "status": "success",
  "selected_view": {
    "type": "chart",
    "chart_type": "bar",
    "title": "string",
    "spec": {},
    "normalized_spec": {},
    "rendered_artifacts": {
      "png_uri": null,
      "svg_uri": null,
      "html_uri": null
    }
  },
  "candidates": [],
  "table_view": {},
  "explanation": {
    "intent": null,
    "used_fields": [],
    "used_aggregations": [],
    "reason": "string"
  },
  "quality": {
    "confidence": null,
    "validation_passed": true,
    "warnings": []
  },
  "performance": {
    "latency_ms": null,
    "model": null,
    "mode": "fast"
  },
  "errors": []
}
```

Маппинг из текущего `T2VPrediction`:

| `VisualizationResponse` | Источник сейчас | Комментарий |
|---|---|---|
| `request_id` | `example_id` или будущий `request_id` | В production нужно не смешивать с benchmark example id. |
| `status` | `status == "ok"` -> `success`, failed -> `failed` | `partial_success` нужен, если spec есть, но render failed. |
| `selected_view.spec` | `raw_spec` | Сейчас это Vega-Lite-like dict. |
| `selected_view.normalized_spec` | `normalized_spec` | Можно отдавать для debug; сайту может быть не нужно. |
| `selected_view.chart_type` | `normalized_spec.chart_type` | `point` маппить в `scatter`, `text` в `table`. |
| `rendered_artifacts.png_uri` | Сейчас не в prediction | Нужно добавить wrapper после `render_predictions`. |
| `candidates` | `candidates` | Нормализовать candidate schema и ids. |
| `explanation.intent` | `detect_intent` или LLM/reranker reason | Сейчас не сохраняется как отдельное поле. |
| `quality.validation_passed` | `normalized_spec.valid`, validator payload | Нужно унифицировать. |
| `performance.latency_ms` | `latency_ms` | Округлить до int. |
| `performance.model` | method/config | Для B0/B1/B2 null или method; для B3-B5 model id. |
| `errors` | `error`, validation failures | Структурировать code/message. |

## 7. Какие данные критично выгружать со стороны Дениса

### 1. Минимально необходимо для построения хоть какого-то графика

| Данные | Пример | Почему влияет | Можно вывести из таблицы | Если не передать |
|---|---|---|---|---|
| Готовая таблица | `rows` или `csv_uri` с `columns` | Без данных невозможно выбрать поля и построить spec | Нет | `failed: missing_table` |
| Пользовательский запрос | `"Покажи продажи по месяцам"` | Intent и field linking | Нет | Auto chart только по schema/profile, качество ниже |
| Имена колонок | `["month", "sales"]` | Поля в Vega encoding должны существовать | Можно из header/rows | Если нет ни columns, ни rows/header: reject |
| Базовые типы колонок | `month: datetime`, `sales: number` | Выбор line/bar/scatter и Vega types | Частично из sample | Риск неверного chart type |
| Роль поля | `month=time`, `sales=measure` | Упрощает выбор x/y и aggregation | Частично из dtype/name | Больше эвристик и warning |
| Row count | `row_count: 120` | Обработка 0/1/large table | Да, если таблица загружена целиком | Нельзя заранее оценить ограничения |

### 2. Нужно для хорошего выбора типа графика

| Данные | Пример | Почему влияет | Можно вывести из таблицы | Если не передать |
|---|---|---|---|---|
| `periodicity` | `month`, `day`, `year` | Line chart и temporal grain | Частично по датам | Возможен bar вместо line или неправильная ось |
| `cardinality` | `category.cardinality=12` | Bar vs table; color grouping | Да по полному/семплированному столбцу | Может выбрать нечитаемый bar |
| `default_aggregation` | `sales -> sum` | Sum vs avg vs count | Плохо выводится без домена | Неверная бизнес-агрегация |
| `allowed_aggregations` | `["sum", "mean"]` | Validator не пропустит запрещённую агрегацию | Частично по role | Риск некорректной агрегации |
| `preferred_output` / chart hint | `chart`, `table`, `bar` | Уважение явного запроса пользователя | Из query частично | Может проигнорировать пользовательское намерение |
| `order_by` и `limit` | `order_by sales desc`, `limit 10` | Top-N и сортировка | Частично из SQL/query | Top chart может быть несортированным |

### 3. Нужно для надёжности и предотвращения неправильных графиков

| Данные | Пример | Почему влияет | Можно вывести из таблицы | Если не передать |
|---|---|---|---|---|
| Признак truncated | `truncated: true` | Нельзя выдавать chart как полный результат без warning | Нет, только upstream знает | Пользователь может увидеть неполную картину |
| Nullability/null counts | `nullable=true`, `null_count=15` | Warnings и фильтрация nulls | Да по полученной таблице | Возможны пропуски/ошибки осей |
| Provenance derived fields | `sales=sum(amount)` | Понимание уже агрегированных мер | Частично по имени | Риск double aggregation |
| Filters provenance | `region='Moscow'` | Title/explanation и корректный контекст | Можно парсить SQL плохо | График без контекста фильтра |
| Source column mapping | `display name -> db column` | Не ломать field references | Нет | Ошибки, если alias не совпадает с column |
| SQL error / empty result status | `sql_status=success_empty` | Отличать 0 строк от сбоя | Нет | Downstream может вернуть misleading table/chart |

### 4. Нужно для BI-качества и красивого отчёта

| Данные | Пример | Почему влияет | Можно вывести из таблицы | Если не передать |
|---|---|---|---|---|
| `metric_definition` | `ARPU = revenue / users` | Корректный title/explanation | Нет | Объяснение будет поверхностным |
| `formatting_hints` | `currency=RUB`, `percent=true` | Красивые axes/tooltips | Частично из unit | Без форматирования |
| Human descriptions | `"Количество активных пользователей"` | Better field linking and labels | Нет | Labels останутся technical |
| Semantic type | `money`, `ratio`, `count`, `geo` | Chart rules and formatting | Частично | Неверный scale/aggregation |
| Source table/domain | `orders`, `users` | Audit and trust | Нет | Слабая explainability |
| Assumptions | `timezone applied`, `limit enforced` | Transparent BI answer | Нет | Пользователь не знает ограничений |

## 8. Fallback-логика при неполных metadata

| Ситуация | Действие downstream | Warning/error |
|---|---|---|
| Нет `unit` | Строить график без unit в axis title; если semantic type money/percent выводится из name, добавить предполагаемый формат с low confidence. | `missing_unit` |
| Нет `periodicity` | Если есть time field, попытаться определить grain по значениям; иначе line chart только при явном temporal dtype/name. | `missing_periodicity` |
| Нет `role` | Infer role: datetime/name tokens -> time, numeric -> measure, id-like -> id, else dimension/text. | `role_inferred` |
| Нет `description` | Field linking только по `name`, query tokens, dtype/role; LLM prompt без business description. | `missing_descriptions` |
| Нет `allowed_aggregations` | Conservative defaults: measure -> `sum/mean/min/max/count`, dimension/id/text -> `count`; для сомнительных полей избегать агрегации. | `aggregation_defaults_used` |
| Таблица слишком широкая | Ограничить candidate generation top-N полями: query-mentioned fields, measures/time/dimensions с высоким confidence; для остальных не генерировать candidates. | `wide_table_pruned` |
| Таблица слишком длинная | Для inline rows использовать sampling/preview; для render ограничивать data values; если `truncated=true`, явно предупреждать. | `large_table_previewed` |
| Все поля текстовые | Если row_count небольшой - table view; если есть low-cardinality dimension - bar count by category; иначе table. | `text_only_table` |
| Все поля числовые | 2+ measures -> scatter; 1 measure -> histogram or KPI/table; если query просит comparison, нужна dimension, иначе warning. | `numeric_only_table` |
| Запрос просит `график`, но данные подходят только для таблицы | Вернуть `partial_success`, `selected_view.type=table`, explanation: chart unsafe/impossible. | `chart_request_fell_back_to_table` |
| Запрос просит `таблицу`, но данные подходят для графика | Уважать запрос: вернуть table; можно добавить chart candidate ниже. | `chart_candidate_available` |
| SQL вернул 0 строк | Не строить график; вернуть пустую table view и explanation. | `empty_result_table` |
| SQL вернул 1 строку | Если одна мера - KPI/table; chart только если есть explicit request и это не misleading. | `single_row_result` |
| Значения содержат null/NaN | Для render/metrics оставить Vega-compatible nulls; предупредить, при high null ratio предпочесть table or aggregate excluding nulls. | `null_values_present` |

Нужный invariant: downstream не должен придумывать SQL или дополнительные данные. Если данных недостаточно для безопасного графика, он возвращает таблицу/ошибку качества, а не уверенный chart.

## 9. Микросервисная готовность

Текущий модуль готов как библиотека/CLI experiment runner, но не как микросервис. Основные функции уже можно обернуть:

- `T2VExample`/`FieldMetadata` как внутренний адаптерный слой.
- B0/B1/B2 как fast CPU path.
- B3/B4/B5 как quality LLM path при наличии GPU.
- `normalize_spec` и validators как обязательный post-processing.
- `render_single` как optional artifact generation.

Что готово:

- Inference-функции `predict(example, run_id, top_k)` для B0/B1/B2.
- LLM predictor classes для B3/B4/B5.
- Evaluation metrics и PNG rendering.
- Error/status в `T2VPrediction`.

Что нужно реализовать:

- HTTP API wrapper.
- Adapter `VisualizationRequest -> T2VExample` без benchmark gold fields.
- Adapter `T2VPrediction -> VisualizationResponse`.
- Artifact storage abstraction: local/S3/minio/static directory.
- Async job storage для LLM quality mode.
- Request size limits, schema validation, structured errors.
- Unified table view contract.
- SVG/HTML support, если нужен сайту.

Рекомендуемые endpoint'ы:

| Endpoint | Метод | Режим | Назначение |
|---|---|---|---|
| `/visualize` | `POST` | sync для fast, async option для quality | Принять `VisualizationRequest`, вернуть `VisualizationResponse` или job id. |
| `/visualize/{request_id}` | `GET` | async polling | Получить результат сохранённого запроса. |
| `/artifacts/{artifact_id}` | `GET` | static/stream | Отдать PNG/SVG/HTML artifact. |
| `/health` | `GET` | sync | Процесс жив, базовые imports работают. |
| `/ready` | `GET` | sync | Модель/renderer/artifact storage готовы. |

Sync vs async:

- `fast` mode: B1/B2 CPU, sync. По метрикам latency порядка `0.4-7 ms` на experiment samples без HTTP overhead.
- `fallback` mode: B0/B1 deterministic при metadata gaps или LLM failure, sync.
- `quality` mode: B3/B4/B5, лучше async. По текущим таблицам latency: B5b около `6045 ms`, B5a около `8133 ms`, B3 около `20101 ms`, B4 около `66826 ms`, B5c около `69238 ms`.

Где хранить render artifacts:

- Dev/local: `artifacts/{request_id}/{candidate_id}.png`.
- Production: object storage с expiring signed URL или backend static storage.
- В response отдавать `png_uri`, `svg_uri`, `html_uri`; если render failed, status `partial_success`.

Ограничения по размеру таблицы:

- Inline `records`: до нескольких тысяч строк или configurable byte limit.
- `csv_uri`/`arrow_uri`: для больших таблиц, читать preview для LLM и полный/ограниченный набор для render.
- Rendering сейчас использует `table.head(500)`; это фактический limit в `render_single`.
- Для очень широких таблиц ограничивать candidates по полям, иначе combinatorial explosion B1/B2.

CPU/GPU требования:

- B0/B1/B2: CPU, `pandas`, `psutil`; B2 использует CSV profiling.
- Rendering: CPU, `vl-convert-python`; может требовать системные runtime dependencies через Python wheel.
- B3/B4/B5: GPU желательно; Stage 8 config задаёт min VRAM: Qwen3-14B `16 GB`, Gemma 3 12B `16 GB`, Mistral Small 24B bnb4 `28 GB`, Gemma 4 E2B `12 GB`.

Зависимости:

- В `requirements.txt`: `pandas`, `numpy`, `pyyaml`, `tqdm`, `jsonschema`, `altair`, `vl-convert-python`, `psutil`, `scikit-learn`, `matplotlib`, `pytest`, `nbformat`, `jupyter`.
- LLM dependencies (`torch`, `transformers`, `bitsandbytes`, возможно model-specific processors) в `requirements.txt` не зафиксированы; они предполагаются в Colab/HF runtime.

## 10. Метрики и экспериментальные результаты

Источник метрик: локальные файлы `reports/stage9_report_materials/tables/quality_metrics.csv`, `latency_memory_failure.csv`, `comparison_solutions.csv`, `final_runs.json`. Полные canonical run-папки из `run_inventory.csv` указывают на `/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/...`; локально они не найдены как полные папки. В `codex_tmp` найдены только частичные репродукции Stage 4, поэтому ниже используются только локальные отчётные CSV.

| Подход | Метод | run_id | Sample | Validity | Chart type accuracy | Field F1 | Encoding accuracy | Aggregation accuracy | Exact match | Oracle@3 | Latency ms | Memory MB | Failure rate | Ограничения сравнения |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| B0 | `B0_rule_based` | `stage4_cpu_sample200` | 200 | 1.0 | 0.84 | 0.9595 | 0.5 | 0.915 | 0.225 | 0.55 | 0.331945 | 108.227 | 0.0 | Детерминированный baseline; metrics из агрегированной таблицы, не из локальной full run папки. |
| B1 | `B1_constraint_ranker` | `stage4_cpu_sample200` | 200 | 1.0 | 0.955 | 0.995 | 0.5308333333333334 | 0.915 | 0.285 | 0.59 | 0.39675499999999997 | 220.566 | 0.0 | Сравним с B0 на sample200; exact-match-oriented метрика не равна пользовательской полезности. |
| B2 | `B2_partial_recommender` | `stage5_partial_sample200` | 200 | 1.0 | 0.855 | 0.973 | 0.5766666666666667 | 0.92 | 0.22 | 0.22 | 7.05238 | 109.949 | 0.0 | Partial recommender, не полноценный NL4DV из-за dependency risk. |
| B3 | `B3_local_llm_qwen3_8b` | `stage6_qwen3_8b_fast_sample50` | 50 | 0.92 | 0.84 | 0.92 | 0.5533333333333333 | 0.66 | 0.28 | 0.28 | 20101.22146 | 1981.508 | 0.08 | Sample50, LLM latency/GPU environment не сопоставим напрямую с CPU B0-B2. |
| B4 | `B4_llm_validator_reranker` | `stage7_b4_sample20_tokens384` | 20 | 0.95 | 0.9 | 0.95 | 0.5333333333333333 | 0.75 | 0.3 | 0.35 | 66825.6801 | 2127.145 | 0.05 | Sample20; multi-candidate, поэтому latency выше. |
| B5a | `B5_stage8_qwen3_14b` | `stage8_qwen3_14b_sample20` | 20 | 1.0 | 0.9 | 1.0 | 0.575 | 0.85 | 0.3 | 0.3 | 8133.003999999999 | 2064.027 | 0.0 | Sample20; promising quality mode, но не full sample200. |
| B5b | `B5_stage8_mistral_small_32_24b_bnb4` | `stage8_mistral_small_32_24b_bnb4_sample20` | 20 | 1.0 | 0.85 | 0.99 | 0.4 | 0.8 | 0.25 | 0.25 | 6045.25885 | 1889.961 | 0.0 | Sample20; fastest LLM in table, requires larger VRAM per config. |
| B5c | `B5_stage8_gemma3_12b_it` | `stage8_gemma3_12b_it_sample20` | 20 | 0.15 | 0.15 | 0.15 | 0.075 | 0.15 | 0.05 | 0.05 | 69237.6294 | 2556.523 | 0.85 | Current prompt/schema mode fails often; not recommended without fixes. |
| B5d | `B5_stage8_gemma4_e2b_it` | `stage8_gemma4_e2b_it_sample20` | 20 | 0.9 | 0.7 | 0.89 | 0.35 | 0.65 | 0.1 | 0.1 | 44562.2476 | 2200.0 | 0.1 | Sample20; smaller control LLM baseline, quality below B5a/B5b. |

Метрики, не найденные в локальных артефактах:

- Полные per-example metrics для всех canonical Stage 5-8 run folders локально не найдены.
- Полные predictions JSONL для canonical Stage 5-8 run folders локально не найдены.
- Render counts для всех canonical Stage 8 runs в локальных `tables/*.csv` не найдены.
- Full run `summary`/`metrics`/`predictions` booleans в `run_inventory.csv` пустые.

## 11. Интеграционные тест-кейсы

### 11.1 Time series

Request:

```json
{
  "request_id": "req_ts_001",
  "user_query": "Покажи динамику выручки по месяцам линейным графиком",
  "locale": "ru-RU",
  "timezone": "Europe/Moscow",
  "data_source": {
    "id": "sales_dw",
    "name": "Sales DWH",
    "dialect": "postgresql",
    "schema_version": "2026-05"
  },
  "result_table": {
    "format": "records",
    "columns": ["month", "revenue"],
    "rows": [
      {"month": "2026-01-01", "revenue": 1200000},
      {"month": "2026-02-01", "revenue": 1350000},
      {"month": "2026-03-01", "revenue": 1280000}
    ],
    "uri": null,
    "row_count": 3,
    "truncated": false
  },
  "field_metadata": [
    {
      "name": "month",
      "source_column": "month",
      "dtype": "date",
      "semantic_type": "date",
      "role": "time",
      "description": "Месяц продажи",
      "unit": null,
      "periodicity": "month",
      "allowed_aggregations": [],
      "default_aggregation": null,
      "grain": "month",
      "nullable": false,
      "value_examples": ["2026-01-01"],
      "cardinality": 3,
      "source_table": "sales_monthly",
      "provenance": {"derived_from": "date_trunc('month', paid_at)"},
      "metric_definition": null,
      "formatting_hints": {"date_format": "MMM yyyy"}
    },
    {
      "name": "revenue",
      "source_column": "revenue",
      "dtype": "number",
      "semantic_type": "money",
      "role": "measure",
      "description": "Выручка",
      "unit": "RUB",
      "periodicity": "month",
      "allowed_aggregations": ["sum", "mean"],
      "default_aggregation": "sum",
      "grain": "month",
      "nullable": false,
      "value_examples": [1200000],
      "cardinality": 3,
      "source_table": "sales_monthly",
      "provenance": {"derived_from": "sum(amount)"},
      "metric_definition": "Сумма оплаченных заказов за месяц",
      "formatting_hints": {"format": "currency", "currency": "RUB"}
    }
  ],
  "query_context": {
    "sql": "SELECT date_trunc('month', paid_at) AS month, sum(amount) AS revenue FROM orders GROUP BY 1 ORDER BY 1",
    "plan": null,
    "filters": [],
    "group_by": ["month"],
    "aggregations": [{"field": "amount", "function": "sum", "alias": "revenue"}],
    "order_by": [{"field": "month", "direction": "asc"}],
    "limit": null,
    "assumptions": []
  },
  "presentation_preferences": {
    "preferred_output": "chart",
    "preferred_chart_type": "line",
    "style_template": null,
    "max_candidates": 3,
    "render": true
  }
}
```

Expected shortened response:

```json
{
  "request_id": "req_ts_001",
  "status": "success",
  "selected_view": {
    "type": "chart",
    "chart_type": "line",
    "title": "Динамика выручки по месяцам",
    "spec": {
      "mark": "line",
      "encoding": {
        "x": {"field": "month", "type": "temporal"},
        "y": {"field": "revenue", "type": "quantitative"}
      }
    },
    "normalized_spec": {"valid": true, "chart_type": "line"},
    "rendered_artifacts": {"png_uri": "/artifacts/req_ts_001/selected.png", "svg_uri": null, "html_uri": null}
  },
  "candidates": [],
  "table_view": {},
  "explanation": {
    "intent": "trend",
    "used_fields": ["month", "revenue"],
    "used_aggregations": [{"field": "revenue", "aggregation": "already_aggregated"}],
    "reason": "В запросе есть динамика и поле времени с месячной периодичностью."
  },
  "quality": {"confidence": 0.9, "validation_passed": true, "warnings": []},
  "performance": {"latency_ms": 25, "model": null, "mode": "fast"},
  "errors": []
}
```

### 11.2 Category comparison

Request:

```json
{
  "request_id": "req_cat_001",
  "user_query": "Сравни продажи по категориям товаров",
  "locale": "ru-RU",
  "timezone": "Europe/Moscow",
  "data_source": {"id": "sales_dw", "name": "Sales DWH", "dialect": "postgresql", "schema_version": "2026-05"},
  "result_table": {
    "format": "records",
    "columns": ["category", "sales_sum"],
    "rows": [
      {"category": "Ноутбуки", "sales_sum": 950000},
      {"category": "Смартфоны", "sales_sum": 1420000},
      {"category": "Аксессуары", "sales_sum": 330000}
    ],
    "uri": null,
    "row_count": 3,
    "truncated": false
  },
  "field_metadata": [
    {
      "name": "category",
      "source_column": "category",
      "dtype": "string",
      "semantic_type": "category",
      "role": "dimension",
      "description": "Категория товара",
      "unit": null,
      "periodicity": null,
      "allowed_aggregations": ["count"],
      "default_aggregation": "count",
      "grain": null,
      "nullable": false,
      "value_examples": ["Ноутбуки"],
      "cardinality": 3,
      "source_table": "products",
      "provenance": null,
      "metric_definition": null,
      "formatting_hints": {}
    },
    {
      "name": "sales_sum",
      "source_column": "sales_sum",
      "dtype": "number",
      "semantic_type": "money",
      "role": "measure",
      "description": "Сумма продаж",
      "unit": "RUB",
      "periodicity": null,
      "allowed_aggregations": ["sum"],
      "default_aggregation": "sum",
      "grain": "category",
      "nullable": false,
      "value_examples": [950000],
      "cardinality": 3,
      "source_table": "orders",
      "provenance": {"derived_from": "sum(order_amount)"},
      "metric_definition": "Сумма заказов в категории",
      "formatting_hints": {"format": "currency", "currency": "RUB"}
    }
  ],
  "query_context": {
    "sql": null,
    "plan": null,
    "filters": [],
    "group_by": ["category"],
    "aggregations": [{"field": "order_amount", "function": "sum", "alias": "sales_sum"}],
    "order_by": [{"field": "sales_sum", "direction": "desc"}],
    "limit": null,
    "assumptions": []
  },
  "presentation_preferences": {"preferred_output": "chart", "preferred_chart_type": "bar", "style_template": null, "max_candidates": 3, "render": true}
}
```

Expected shortened response:

```json
{
  "request_id": "req_cat_001",
  "status": "success",
  "selected_view": {
    "type": "chart",
    "chart_type": "bar",
    "title": "Продажи по категориям товаров",
    "spec": {
      "mark": "bar",
      "encoding": {
        "x": {"field": "category", "type": "nominal", "sort": "-y"},
        "y": {"field": "sales_sum", "type": "quantitative"}
      }
    },
    "normalized_spec": {"valid": true, "chart_type": "bar"},
    "rendered_artifacts": {"png_uri": "/artifacts/req_cat_001/selected.png", "svg_uri": null, "html_uri": null}
  },
  "candidates": [],
  "table_view": {},
  "explanation": {
    "intent": "comparison",
    "used_fields": ["category", "sales_sum"],
    "used_aggregations": [{"field": "sales_sum", "aggregation": "already_aggregated"}],
    "reason": "Категориальное поле и числовая мера подходят для bar chart."
  },
  "quality": {"confidence": 0.88, "validation_passed": true, "warnings": []},
  "performance": {"latency_ms": 20, "model": null, "mode": "fast"},
  "errors": []
}
```

### 11.3 Table/top-N

Request:

```json
{
  "request_id": "req_top_001",
  "user_query": "Покажи топ-5 клиентов по выручке таблицей",
  "locale": "ru-RU",
  "timezone": "Europe/Moscow",
  "data_source": {"id": "crm_dw", "name": "CRM DWH", "dialect": "postgresql", "schema_version": "2026-05"},
  "result_table": {
    "format": "records",
    "columns": ["client_name", "region", "revenue"],
    "rows": [
      {"client_name": "Client A", "region": "Москва", "revenue": 500000},
      {"client_name": "Client B", "region": "Санкт-Петербург", "revenue": 420000}
    ],
    "uri": null,
    "row_count": 5,
    "truncated": false
  },
  "field_metadata": [
    {"name": "client_name", "source_column": "client_name", "dtype": "string", "semantic_type": "name", "role": "dimension", "description": "Название клиента", "unit": null, "periodicity": null, "allowed_aggregations": ["count"], "default_aggregation": "count", "grain": "client", "nullable": false, "value_examples": ["Client A"], "cardinality": 5, "source_table": "clients", "provenance": null, "metric_definition": null, "formatting_hints": {}},
    {"name": "region", "source_column": "region", "dtype": "string", "semantic_type": "region", "role": "dimension", "description": "Регион клиента", "unit": null, "periodicity": null, "allowed_aggregations": ["count"], "default_aggregation": "count", "grain": "client", "nullable": true, "value_examples": ["Москва"], "cardinality": 3, "source_table": "clients", "provenance": null, "metric_definition": null, "formatting_hints": {}},
    {"name": "revenue", "source_column": "revenue", "dtype": "number", "semantic_type": "money", "role": "measure", "description": "Выручка клиента", "unit": "RUB", "periodicity": null, "allowed_aggregations": ["sum"], "default_aggregation": "sum", "grain": "client", "nullable": false, "value_examples": [500000], "cardinality": 5, "source_table": "orders", "provenance": {"derived_from": "sum(order_amount)"}, "metric_definition": "Выручка по клиенту", "formatting_hints": {"format": "currency", "currency": "RUB"}}
  ],
  "query_context": {
    "sql": null,
    "plan": null,
    "filters": [],
    "group_by": ["client_name", "region"],
    "aggregations": [{"field": "order_amount", "function": "sum", "alias": "revenue"}],
    "order_by": [{"field": "revenue", "direction": "desc"}],
    "limit": 5,
    "assumptions": []
  },
  "presentation_preferences": {"preferred_output": "table", "preferred_chart_type": null, "style_template": null, "max_candidates": 3, "render": false}
}
```

Expected shortened response:

```json
{
  "request_id": "req_top_001",
  "status": "success",
  "selected_view": {
    "type": "table",
    "chart_type": "table",
    "title": "Топ-5 клиентов по выручке",
    "spec": {},
    "normalized_spec": {},
    "rendered_artifacts": {"png_uri": null, "svg_uri": null, "html_uri": null}
  },
  "candidates": [
    {
      "candidate_id": "bar_1",
      "type": "chart",
      "chart_type": "bar",
      "score": 0.72,
      "reason": "Top-N данные также подходят для sorted bar chart."
    }
  ],
  "table_view": {
    "columns": ["client_name", "region", "revenue"],
    "rows": [
      {"client_name": "Client A", "region": "Москва", "revenue": 500000},
      {"client_name": "Client B", "region": "Санкт-Петербург", "revenue": 420000}
    ],
    "order_by": [{"field": "revenue", "direction": "desc"}],
    "limit": 5
  },
  "explanation": {
    "intent": "table",
    "used_fields": ["client_name", "region", "revenue"],
    "used_aggregations": [{"field": "revenue", "aggregation": "already_aggregated"}],
    "reason": "Пользователь явно запросил таблицу; top-N порядок передан upstream."
  },
  "quality": {"confidence": 0.92, "validation_passed": true, "warnings": []},
  "performance": {"latency_ms": 15, "model": null, "mode": "fast"},
  "errors": []
}
```

## 12. Риски интеграции

| Риск | Причина | Влияние | Как обнаружить | Как исправить | Владелец |
|---|---|---|---|---|---|
| Несовпадение field names между таблицей и metadata | Сейчас `name` используется как фактическая колонка | Validator отклонит spec или график не отрендерится | Contract test: все `field_metadata.name/source_column` есть в columns | Ввести `source_column`, adapter aliases | shared |
| Double aggregation | Upstream уже агрегировал measure, downstream добавляет `sum/mean` | Неверные значения на графике | Сравнить `query_context.aggregations`, field provenance и spec aggregate | Передавать `default_aggregation`, `grain`, `already_aggregated` | shared |
| Неверный chart type при слабой metadata | Нет role/periodicity/cardinality | Bar вместо line, table вместо chart | Quality warnings, test cases with missing metadata | Role inference + warnings + обязательные minimal fields | Denis/upstream + Peter/downstream |
| LLM latency неприемлема для sync UI | B3/B4/B5 занимают секунды/десятки секунд | Таймаут сайта | Load/latency мониторинг, endpoint timeout | Fast sync B1, LLM async quality mode | Peter/downstream |
| LLM dependency drift | `torch/transformers/bitsandbytes` не зафиксированы в `requirements.txt` | Runtime breaks, разные результаты | `/ready` model load check, CI image build | Зафиксировать LLM environment или вынести в отдельный image | Peter/downstream |
| Render failed despite valid spec | `vl-convert` может не принять spec/data | Нет PNG для сайта | Track `render_failures.json`, response `partial_success` | Return JSON spec even if PNG failed; add SVG/HTML fallback | Peter/downstream |
| Пустая таблица | SQL вернул 0 строк | График misleading/ошибка Vega | `row_count == 0` contract test | Return empty table response, no chart | shared |
| Большая таблица | Inline rows слишком много или CSV большой | Slow render/LLM prompt overflow | Request size limits, row_count, truncation flag | `csv_uri`/`arrow_uri`, preview sampling, async | shared |
| Приватные данные в artifacts/logs | Табличные rows попадают в PNG/spec/logs | Privacy issue | Artifact/log audit | Redaction policy, artifact TTL, no raw rows in logs | shared |
| Сайт ожидает table view, а модуль отдаёт Vega text mark | Сейчас table spec отдельным контрактом не реализован | Frontend integration complexity | Contract tests for table request | Добавить explicit `table_view` в response | Peter/downstream |
| Score несопоставим между methods | B0/B1/B2/B4 score шкалы разные | Нельзя смешивать candidates на UI | Inspect candidate method/source | Normalize confidence separately from internal score | Peter/downstream |
| Stage 8 model availability/gated HF | Некоторые HF модели gated/требуют токены | LLM path не стартует | `/ready` and model load failure | Fast fallback, pre-pull models, secret management | Peter/downstream |
| Upstream не сообщает truncation/limit | Downstream думает, что таблица полная | Неправильная аналитическая интерпретация | Compare row_count/limit/query_context | Required `truncated`, `limit`, assumptions | Denis/upstream |

## 13. Открытые вопросы к Денису

1. Какие metadata-поля upstream уже может отдавать сейчас: `name`, `dtype`, `role`, `description`, `unit`, `periodicity`, `allowed_aggregations`, `default_aggregation`, `cardinality`, `source_table`?
2. Может ли upstream отдавать `source_column` отдельно от display/logical field name?
3. Может ли upstream отдавать structured query plan: выбранные таблицы, join path, filters, group_by, aggregations, order_by, limit?
4. Может ли upstream отдавать provenance для derived fields: например `revenue = sum(order_amount)` или `month = date_trunc('month', paid_at)`?
5. Как upstream сообщает, что таблица уже агрегирована и её нельзя повторно агрегировать?
6. Как upstream ограничивает строки: hard `LIMIT`, sampling, top-N, pagination, truncation?
7. Может ли upstream передавать большие таблицы как `csv_uri` или `arrow_uri`, а не inline rows?
8. Как upstream сообщает SQL errors, empty result, partial result и timeout?
9. Какие SQL dialect/source types поддерживаются сейчас: PostgreSQL, SQLite, ClickHouse, Trino, CSV, API?
10. Может ли upstream отдавать null counts/cardinality/sample values без раскрытия чувствительных данных?
11. Какие поля считаются чувствительными и должны редактироваться перед render/logging?
12. Нужно ли сайту получать только PNG/HTML, или можно отдавать Vega-Lite spec и рендерить на frontend?
13. Какой SLA ожидается от сайта: fast ответ до 1 секунды или допустим async quality mode?
14. Где должен жить artifact storage и кто отвечает за TTL/доступ?
15. Нужны ли русскоязычные titles/explanations от downstream или это делает общий backend/frontend?

## Затыки аудита

- Полные canonical run-папки `stage4_cpu_sample200`, `stage5_partial_sample200`, `stage6_qwen3_8b_fast_sample50`, `stage7_b4_sample20_tokens384`, `stage8_*` локально не найдены; `run_inventory.csv` содержит только Colab/Drive paths, а флаги наличия summary/metrics/predictions/rendered пустые.
- Локально найдены частичные `codex_tmp` репродукции Stage 4, но они не заменяют canonical results из `reports/stage9_report_materials/tables/*.csv`.
- Тяжёлые LLM/Colab прогоны не запускались, потому что инструкция требует аудит текущего состояния, а не новые эксперименты.
- Production HTTP API, storage layer, SVG/HTML/PDF export, inline records runtime adapter и отдельный table response contract в коде не найдены.
- LLM runtime dependencies не полностью зафиксированы в `requirements.txt`; Stage 8 model config есть, но production image spec не найден.

## Executive summary

1. Для интеграции лучше принять явный контракт `VisualizationRequest -> VisualizationResponse`, а текущий `T2VExample/T2VPrediction` оставить внутренним adapter layer.
2. Минимально upstream обязан передавать `request_id`, `user_query`, готовую result table, `columns`, `row_count`, `truncated` и `field_metadata` с `name`, `dtype`, `role`.
3. Для качества графиков критично добавить `allowed_aggregations`, `default_aggregation`, `periodicity`, `cardinality`, `grain` и provenance derived fields.
4. Downstream не должен оценивать SQL и не должен генерировать SQL; SQL можно хранить только как provenance/debug.
5. Текущий модуль реально работает в batch/evaluation режиме через JSONL examples и CSV path, а не как production API.
6. B1 выглядит лучшим fast CPU default среди deterministic подходов: validity `1.0`, chart type `0.955`, field F1 `0.995`, failure rate `0.0`.
7. B5a Qwen3-14B выглядит лучшим quality-mode кандидатом в локальных таблицах: validity `1.0`, field F1 `1.0`, exact match `0.3`, failure rate `0.0`.
8. B5b быстрее среди Stage 8 LLM в таблице, но требует больше VRAM по конфигу и уступает B5a по части quality metrics.
9. B5c в текущем режиме не рекомендуется: failure rate `0.85`, validity `0.15`.
10. Сайт должен получать не только Vega-Lite spec, но и `table_view`, warnings, explanation, performance и render artifact URIs.
11. Если render падает, response должен быть `partial_success`: spec валиден, PNG отсутствует, ошибка лежит в `errors`.
12. Для sync UI нужен fast path B1/B2; LLM path лучше делать async или optional quality rerun.
13. Основная зона shared-риска с Денисом - metadata completeness, alias mapping, truncation, already-aggregated measures и provenance фильтров.
14. Следующий инженерный шаг - реализовать adapters `VisualizationRequest -> T2VExample` и `T2VPrediction -> VisualizationResponse`, затем добавить contract tests на три кейса из раздела 11.
