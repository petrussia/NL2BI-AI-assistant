# joint_integration_contract_review.md

Основано на двух audit packet: `integration_packet_denis.md` для upstream Text-to-SQL/DataExtraction и `integration_packet_peter.md` для downstream Text-to-Visualization. Код не переписывался. Поля, которых нет в аудитах или которые не подтверждены фактической реализацией, помечены как `unknown` или `частично`.

## 1. Итоговая схема пайплайна

Целевой пайплайн:

1. Web UI отправляет пользовательский запрос в общий backend: `POST /nl2chart` (в API-разделе ниже предложен внешний вариант `POST /api/nl2chart`).
2. Общий backend формирует `DataExtractionRequest` для upstream-модуля Дениса.
3. Text-to-SQL service возвращает `DataExtractionResponse`: SQL, таблицу результата, базовый status/errors, технический контекст запроса.
4. Adapter layer нормализует таблицу и metadata: явные `columns`, inline `rows` или `uri`, `field_metadata`, `query_context`, `truncated`, `errors`.
5. Adapter layer формирует `VisualizationRequest` для downstream-модуля Петра.
6. Visualization service возвращает `VisualizationResponse`: выбранный график или table view, candidates, spec, warnings/errors, artifact URI.
7. Общий backend возвращает сайту готовый chart/table artifact, объяснение и безопасные ошибки.

ASCII-схема:

```text
User
  -> Web UI
  -> API Gateway / common backend
  -> Text-to-SQL Service
  -> Result/Metadata
  -> Adapter Layer
  -> Visualization Service
  -> Chart/Table Artifact
  -> Web UI
```

Текущее состояние по аудитам: у Дениса нет production HTTP/RPC API, граница сейчас - `AnalyticsPayload v1` и prediction JSONL. У Петра также нет production `POST /visualize`; текущий вход - batch/evaluation `T2VExample` с JSONL examples и CSV path. Поэтому production-like интеграция требует явного общего контракта и adapter layer.

## 2. Совместимость полей

| Поле | Денис отдаёт? | Пётр требует? | Совместимо? | Действие |
|---|---:|---:|---:|---|
| `request_id` | Нет | Да, нужен в целевом `VisualizationRequest` | Нет | Добавить в общий backend и пробросить через upstream, adapter, downstream. |
| `user_query` | Да: `question` / `source.question` | Да: `query` сейчас, `user_query` в целевом контракте | Да | Маппить `question` -> `user_query`; сохранить UTF-8. |
| `locale` | Нет | Частично: есть в целевых примерах, текущий код не требует | Частично | Передавать из backend как optional; i18n ownership остается `unknown`. |
| `timezone` | Нет | Частично: есть в целевых примерах, текущий код не требует | Частично | Передавать из backend как optional; использовать для time axis/date formatting. |
| datasource id | Да: `db_id` | Да в целевом `data_source.id`; текущий `T2VExample` напрямую не требует | Да | Маппить `db_id` -> `data_source.id`; для batch можно положить в metadata. |
| `dialect` | Частично: default `sqlite`, BQ/Snow/MySQL частично; в payload не сериализуется | Да в целевом `data_source.dialect` | Частично | Сериализовать явный dialect enum в `DataExtractionResponse`. |
| SQL | Да: `generated_sql` / `source.generated_sql` | Не нужен для генерации графика, но нужен как `query_context.sql`/debug | Да | Передавать как provenance/debug, downstream не должен генерировать или валидировать SQL. |
| `plan` | Частично: B2+ `plan_raw`, `plan_parsed`, `plan_valid`; в `AnalyticsPayload v1` нет | Optional в `query_context.plan` | Частично | Нормализовать plan v1/v5 в единый shape; если нет - `null`. |
| `rows` | Да: `payload.rows` inline records | Да в целевом request; текущий runtime читает CSV path | Частично | Для MVP принять inline records или adapter materializes temp CSV для текущего `T2VExample`. |
| `columns` | Частично: implicit из `rows[0]` и `summary.columns` | Да: нужны для validation/render | Частично | Сделать `result_table.columns` явным ordered list. |
| `row_count` | Да: `summary.row_count`, `n_rows` | Да | Да | Маппить в `result_table.row_count`. |
| `truncated` | Нет | Да, нужен для больших таблиц и корректной интерпретации | Нет | Ввести row limit в executor/backend и `result_table.truncated`. |
| field name | Частично: ключи rows/summary columns | Да: `FieldMetadata.name` обязателен | Частично | Сгенерировать `field_metadata[].name` из explicit columns. |
| `display_name` | Нет | Optional, полезно для titles/axes | Частично | На MVP derive from `name`; качественно - schema/metric dictionary. |
| `sql_type` | Нет | Optional в целевом расширенном контракте | Нет | Заполнять из cursor/schema/information_schema, иначе `unknown`. |
| `data_type` | Частично: `summary.columns[*].dtype` (`numeric`, `categorical_or_mixed`) | Да: `dtype`/`data_type` используется для chart selection | Частично | Маппить SQL/pandas types в `number|string|boolean|date|datetime|unknown`. |
| `semantic_role` | Нет | Да: role нужен для выбора chart/encoding | Нет | Ввести role inference: time, measure, dimension, id, text, unknown. |
| `description` | Нет | Optional, используется в field ranking/LLM prompt | Частично | `null` на MVP; позже schema comments/metric dictionary. |
| `unit` | Нет | Optional, полезно для axes/tooltips | Частично | `null`/`unknown` на MVP; позже metric dictionary. |
| `periodicity` | Частично: plan v5 `time_grain`, если есть валидный план | Optional, важно для line chart | Частично | Извлекать из plan/time fields; иначе `null`. |
| `allowed_aggregations` | Нет как допустимое множество; в plan есть фактическая агрегация | Да: используется для legality/defaults | Частично | На MVP infer by role/type; качественно - metric dictionary. |
| `default_aggregation` | Частично выводима из plan aggregations | Да, чтобы избежать double aggregation | Частично | Ставить `none` для already aggregated fields, иначе infer по типу/role. |
| `filters` | Частично: plan v1/v5 | Да в `query_context` optional | Частично | Нормализовать plan filters; если нет - `[]` или `unknown`. |
| `group_by` | Частично: plan v1/v5 dimensions | Да в `query_context` optional | Частично | Нормализовать в list field names. |
| `aggregations` | Частично: plan v1/v5 measures | Да в `query_context` optional | Частично | Нормализовать в list `{field,function,alias}`. |
| `order_by` | Частично: plan v1/v5 ordering | Да в `query_context` optional | Частично | Нормализовать в list `{field,direction}`. |
| `limit` | Частично: plan; raw executor row limit отсутствует | Да, особенно для top-N/truncation | Частично | Передавать SQL/user limit отдельно от backend row limit. |
| `provenance` | Нет per output column | Optional, важно для derived fields и double aggregation | Нет | Строить из SQL AST/plan; если невозможно - `derived: unknown`. |
| `errors` | Частично: `error_type`, `error_message`, taxonomy | Да: status/error есть, но enum другой | Частично | Маппить в общий `errors[].code/message/source/retryable`. |
| `warnings` | Частично: `notes`, обычно пустые | Да: downstream должен возвращать quality warnings | Частично | Ввести warning codes: metadata incomplete, truncated, fallback chart, render fallback. |
| `confidence` | Частично: query/plan confidence есть, но в payload не пробрасывается | Optional: `quality.confidence` | Частично | Передавать если есть; иначе `unknown`/`null`, не смешивать с heuristic scores. |
| `latency` | Нет per-item в payload | Да: `latency_ms` есть в T2VPrediction/performance | Нет | Замерять per service и возвращать `execution.latency_ms`, `performance.latency_ms`. |

Главный разрыв: Денис уже может отдать SQL, rows, row_count и часть plan/debug, но не отдает явную `field_metadata` с role/type/aggregation/provenance и не имеет `request_id`, `truncated`, `latency_ms`. Петр уже умеет выбирать и валидировать графики по metadata, но текущий интерфейс ожидает batch JSONL + CSV path, а не production inline records.

## 3. Минимальный контракт MVP

Минимальный payload для успешного пути должен быть одним `VisualizationRequest`, построенным adapter layer из `DataExtractionResponse`. Для ошибок используется общий status/error envelope из раздела 6; ниже только данные, без которых нормальная визуализация не заработает.

Pydantic-like описание:

```python
class ResultTable:
    columns: list[str]
    rows: list[dict[str, object]] | None = None
    uri: str | None = None

    # Rule: exactly one transport must be usable:
    # - rows for small/medium result sets;
    # - uri for large result sets.

class FieldMetadata:
    name: str
    data_type: Literal["number", "string", "boolean", "date", "datetime", "unknown"]
    semantic_role: Literal["measure", "dimension", "time", "id", "text", "unknown"]

class QueryContext:
    sql: str | None
    filters: list[dict[str, object]] = []
    group_by: list[str] = []
    aggregations: list[dict[str, object]] = []

class VisualizationRequestMVP:
    request_id: str
    user_query: str
    result_table: ResultTable
    field_metadata: list[FieldMetadata]
    query_context: QueryContext
```

JSON Schema-like sketch:

```json
{
  "type": "object",
  "required": ["request_id", "user_query", "result_table", "field_metadata", "query_context"],
  "properties": {
    "request_id": {"type": "string", "minLength": 1},
    "user_query": {"type": "string", "minLength": 1},
    "result_table": {
      "type": "object",
      "required": ["columns"],
      "properties": {
        "columns": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "rows": {"type": ["array", "null"], "items": {"type": "object"}},
        "uri": {"type": ["string", "null"]}
      }
    },
    "field_metadata": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["name", "data_type", "semantic_role"],
        "properties": {
          "name": {"type": "string"},
          "data_type": {"enum": ["number", "string", "boolean", "date", "datetime", "unknown"]},
          "semantic_role": {"enum": ["measure", "dimension", "time", "id", "text", "unknown"]}
        }
      }
    },
    "query_context": {
      "type": "object",
      "required": ["sql"],
      "properties": {
        "sql": {"type": ["string", "null"]},
        "filters": {"type": "array", "items": {"type": "object"}},
        "group_by": {"type": "array", "items": {"type": "string"}},
        "aggregations": {"type": "array", "items": {"type": "object"}}
      }
    }
  }
}
```

MVP mapping from current audits:

- `request_id` сейчас отсутствует у Дениса - должен быть создан backend'ом.
- `user_query` берется из `source.question` / prediction `question`.
- `result_table.columns` строится из `summary.columns` или ключей первой строки.
- `result_table.rows` берется из `payload.rows`; `uri` остается `null` до внедрения artifact storage.
- `field_metadata.name` строится из `columns`.
- `field_metadata.data_type` строится из `summary.columns[*].dtype` и sample values.
- `field_metadata.semantic_role` выводится adapter'ом эвристически.
- `query_context.sql` берется из `source.generated_sql`.
- `query_context.aggregations/group_by/filters` берутся из `plan_parsed`, если он есть; иначе пустые списки с warning `metadata_incomplete`.

## 4. Расширенный контракт для хорошего качества

| Поле | Откуда брать | Как влияет на выбор графика |
|---|---|---|
| `description` | Schema comments, metric dictionary; сейчас у Дениса нет | Улучшает field ranking и LLM prompt, помогает выбирать правильное поле при похожих именах. |
| `unit` | Metric dictionary или source schema; сейчас обычно `null` | Улучшает подписи осей, форматирование, различение currency/percent/count. |
| `periodicity` | Plan time grain, date column profiling, schema metadata | Отличает line chart/time series от обычного bar chart; задает time binning. |
| `allowed_aggregations` | Metric dictionary или adapter inference | Запрещает нелегальные агрегации и снижает риск double aggregation. |
| `default_aggregation` | Query plan/provenance или metric dictionary | Помогает downstream не угадывать sum/mean/count; для already aggregated fields ставится `none` или `already_aggregated`. |
| `metric_definition` | BI/metric dictionary; сейчас не найдено | Делает titles/explanations точнее и снижает риск неверной интерпретации метрики. |
| `grain` | Query plan, group_by, provenance, metric dictionary | Показывает уровень агрегации результата: row, client, category, day, month. Защищает от повторной агрегации. |
| `provenance` | SQL AST/plan: expression, aggregation, source table/column | Объясняет derived fields, фильтры и агрегации; помогает downstream маркировать measure как already aggregated. |
| `display_formatting` / `formatting_hints` | Metric dictionary, type inference, locale | Управляет currency/percent/date formatting в axes/tooltips/table view. |
| `cardinality` | Result profiling или safe source profiling | Помогает выбирать bar vs table: высокая cardinality часто лучше как table/top-N или требует truncation. |
| `examples` / `value_examples` | Safe sample values; сейчас Петр может брать preview из CSV | Улучшает role inference, title generation, validation и LLM prompt. Для sensitive data нужен redaction. |
| `confidence` | Query analysis/plan confidence/downstream validation | Позволяет показывать предупреждения или выбирать fallback при слабой уверенности. |
| `warnings` | Adapter/upstream/downstream validators | Делает fallback прозрачным: metadata incomplete, truncated, empty result, render fallback. |

Расширенный target shape:

```python
class FieldMetadataExtended(FieldMetadata):
    source_table: str | None = None
    source_column: str | None = None
    display_name: str | None = None
    description: str | None = None
    sql_type: str | None = None
    unit: str | None = None
    periodicity: str | None = None
    allowed_aggregations: list[str] = []
    default_aggregation: str | None = None
    metric_definition: str | None = None
    grain: str | None = None
    provenance: dict[str, object] | None = None
    formatting_hints: dict[str, object] = {}
    cardinality: int | None = None
    examples: list[object] = []
    nullable: bool | None = None

class Quality:
    confidence: float | None = None
    warnings: list[dict[str, object]] = []
```

Важно: `description`, `unit`, `metric_definition`, `display_name` нельзя выдумывать. Если их нет в source schema или metric dictionary, ставить `null`/`unknown` и warning `metadata_incomplete`.

## 5. Adapter layer

Adapter layer нужен между текущим `AnalyticsPayload v1`/prediction outputs Дениса и целевым `VisualizationRequest` Петра.

Основные обязанности adapter:

- `normalize_extraction_response(response) -> VisualizationRequest`;
- явный список columns из rows/summary;
- mapping SQL/pandas types to visualization `data_type`;
- role inference;
- metadata enrichment без выдумывания фактов;
- table truncation и выбор `rows` vs `uri`;
- null handling;
- mapping upstream errors в общий enum;
- provenance mapping из plan/SQL, когда возможно.

Python-like псевдокод:

```python
def normalize_extraction_response(response: dict) -> dict:
    request_id = response.get("request_id") or make_request_id(response)
    user_query = get_user_query(response)
    rows = get_rows(response)
    columns = get_columns(response, rows)
    summary = response.get("summary", {})
    plan = get_plan(response)

    result_table = normalize_result_table(
        columns=columns,
        rows=rows,
        row_limit=response.get("execution", {}).get("row_limit"),
    )

    field_metadata = []
    for column in columns:
        sql_type = lookup_sql_type(response, column)  # may return None
        raw_dtype = lookup_summary_dtype(summary, column)
        data_type = map_data_type(sql_type=sql_type, raw_dtype=raw_dtype, sample_values=sample_column(rows, column))
        semantic_role = infer_semantic_role(
            name=column,
            data_type=data_type,
            plan=plan,
            values=sample_column(rows, column),
        )
        provenance = infer_provenance(column=column, plan=plan, sql=get_sql(response))

        field_metadata.append({
            "name": column,
            "data_type": data_type,
            "semantic_role": semantic_role,
            "sql_type": sql_type or "unknown",
            "display_name": prettify_name(column),
            "description": None,
            "unit": None,
            "periodicity": infer_periodicity(column, data_type, plan),
            "allowed_aggregations": infer_allowed_aggregations(data_type, semantic_role),
            "default_aggregation": infer_default_aggregation(data_type, semantic_role, provenance),
            "provenance": provenance,
            "examples": safe_examples(rows, column),
        })

    warnings = []
    if any(field["semantic_role"] == "unknown" for field in field_metadata):
        warnings.append({"code": "metadata_incomplete", "message": "Some field roles were inferred with low confidence."})
    if result_table["truncated"]:
        warnings.append({"code": "row_limit_exceeded", "message": "Result table was truncated before visualization."})

    return {
        "request_id": request_id,
        "user_query": user_query,
        "locale": response.get("locale"),
        "timezone": response.get("timezone"),
        "data_source": normalize_data_source(response),
        "result_table": result_table,
        "field_metadata": field_metadata,
        "query_context": {
            "sql": get_sql(response),
            "plan": normalize_plan(plan),
            "filters": normalize_filters(plan),
            "group_by": normalize_group_by(plan),
            "aggregations": normalize_aggregations(plan),
            "order_by": normalize_order_by(plan),
            "limit": normalize_limit(plan),
            "assumptions": [],
        },
        "quality": {
            "confidence": get_confidence(response),
            "warnings": warnings,
        },
        "errors": map_errors(response),
    }
```

Type mapping:

| SQL/pandas source | Visualization `data_type` |
|---|---|
| `INTEGER`, `BIGINT`, `FLOAT`, `DOUBLE`, `DECIMAL`, pandas numeric | `number` |
| `DATE` | `date` |
| `TIMESTAMP`, `DATETIME` | `datetime` |
| `BOOLEAN` | `boolean` |
| `TEXT`, `VARCHAR`, `CHAR`, pandas categorical/mixed | `string` |
| missing or ambiguous | `unknown` |

Role inference:

| Signal | `semantic_role` |
|---|---|
| Date/datetime type, field names like `date`, `time`, `year`, `month`, plan `time_grain` | `time` |
| Numeric field with aggregation/provenance or metric-like name | `measure` |
| String/categorical field with low/medium cardinality | `dimension` |
| ID-like name or high-cardinality identifier | `id` |
| Free-text/name/title fields | `text` |
| Insufficient evidence | `unknown` |

Null handling:

- preserve `null` values in `rows`;
- compute `null_count` if summary/profiling is available;
- if key field has too many nulls, downstream should prefer table or warning fallback;
- do not silently replace nulls with strings like `"unknown"` unless frontend formatting explicitly requires it.

Error mapping:

- upstream `executable=false` + SQL/parse/validation error -> `sql_generation_failed`, `sql_validation_failed`, or `sql_execution_failed`;
- no rows with successful SQL -> `empty_result`;
- missing role/type metadata -> `metadata_incomplete`;
- downstream spec failure -> `visualization_failed`;
- downstream render failure with valid spec -> `render_failed` and `partial_success`.

## 6. Общие статусы и ошибки

Status enum:

| Status | Meaning |
|---|---|
| `success` | SQL executed, result normalized, visualization/table response produced. |
| `partial_success` | Data or spec is available, but some part failed: incomplete metadata, truncated table, render failed, fallback chart/table. |
| `failed` | Pipeline cannot return usable data or visualization. |

Error code contract:

| Error code | Кто генерирует | Кто обрабатывает | Что показывать пользователю |
|---|---|---|---|
| `schema_not_found` | Text-to-SQL service или common backend | Common backend | "Источник данных или схема недоступны. Проверьте подключение или выберите другой источник." |
| `ambiguous_query` | Text-to-SQL service / query analysis | Common backend, Web UI | "Запрос неоднозначен. Уточните метрику, период или разрез." |
| `sql_generation_failed` | Text-to-SQL service | Common backend | "Не удалось построить SQL-запрос по описанию. Попробуйте переформулировать запрос." |
| `sql_validation_failed` | Text-to-SQL service SQL guard | Common backend | "Сгенерированный запрос не прошёл проверку безопасности или синтаксиса." |
| `sql_execution_failed` | Text-to-SQL executor | Common backend | "Запрос к данным не выполнился. Попробуйте изменить условия или источник данных." |
| `timeout` | Любой сервис или gateway | Common backend | "Запрос выполнялся слишком долго. Попробуйте сузить период или добавить лимит." |
| `empty_result` | Text-to-SQL executor после успешного SQL | Visualization service и Web UI | "По вашему запросу данные не найдены." Можно показать пустую таблицу. |
| `row_limit_exceeded` | Text-to-SQL service или adapter | Visualization service и Web UI | "Показана часть результата. Уточните запрос или используйте фильтры." |
| `metadata_incomplete` | Adapter, upstream metadata builder или downstream validator | Visualization service | "График построен по ограниченным метаданным." При необходимости fallback на table/bar. |
| `visualization_failed` | Visualization service | Common backend, Web UI | "Данные получены, но график построить не удалось. Показана таблица." |
| `render_failed` | Visualization renderer | Common backend, Web UI | "Спецификация графика готова, но изображение не отрендерилось. Попробуйте обновить или открыть таблицу." |

Canonical error object:

```json
{
  "code": "metadata_incomplete",
  "message": "Some field metadata is missing.",
  "source": "adapter",
  "retryable": false,
  "details": {}
}
```

## 7. API микросервисов

Эти endpoints являются предложением production-like оболочки. В аудитах подтверждено, что готовых production HTTP endpoints сейчас нет.

### Общий backend

| Endpoint | Request body | Response body | Sync/async | Timeout | Retry policy |
|---|---|---|---|---:|---|
| `POST /api/nl2chart` | `{request_id?, user_query, data_source, locale?, timezone?, constraints?, presentation_preferences?}` | `Nl2ChartResponse`: status, request_id, selected_view/table_view, warnings/errors, artifact links | Sync для fast path; async при `mode=quality` или долгом render | 20-30s proposed; upstream SQL timeout внутри 8s по аудиту Дениса | Retry только на network/5xx при том же `request_id`; не retry для validation/user errors. |
| `GET /api/nl2chart/{request_id}` | none | Current pipeline status/result | Async status polling | 5s | Retry safe. |
| `GET /api/artifacts/{artifact_id}` | none | PNG/SVG/HTML/spec/table artifact | Sync | 10s | Retry safe; access control/TTL required. |

### Text-to-SQL service

| Endpoint | Request body | Response body | Sync/async | Timeout | Retry policy |
|---|---|---|---|---:|---|
| `POST /extract` | `DataExtractionRequest`: request_id, user_query, data_source.id, dialect, constraints.row_limit, constraints.timeout_ms, locale?, timezone? | `DataExtractionResponse`: status, SQL, result_table, field_metadata if available, query_context, execution, errors/warnings | Sync for MVP | 8s SQL executor timeout is already used for SQLite in audit; service timeout proposed 10-15s | Retry only transport/model transient failures; do not retry unsafe/invalid SQL. |
| `GET /health` | none | `{status: "ok"}` | Sync | 1s | Retry safe. |
| `GET /ready` | none | model/schema/executor readiness | Sync | 3-5s | Retry safe; must fail if model/DB/schema unavailable. |

### Visualization service

| Endpoint | Request body | Response body | Sync/async | Timeout | Retry policy |
|---|---|---|---|---:|---|
| `POST /visualize` | `VisualizationRequest`: request_id, user_query, result_table, field_metadata, query_context, presentation_preferences | `VisualizationResponse`: status, selected_view, candidates, table_view, explanation, quality, performance, errors | Sync for B1/B2 fast path; async for LLM quality mode | 1s target for deterministic fast path; 10-60s proposed for LLM async path | Retry render/model transient failures only; no retry for invalid request metadata. |
| `GET /visualize/{request_id}` | none | Visualization job status/result | Async status polling | 5s | Retry safe. |
| `GET /health` | none | `{status: "ok"}` | Sync | 1s | Retry safe. |
| `GET /ready` | none | renderer/model readiness, available methods | Sync | 3-5s | Retry safe; must fail if `vl-convert`/model not loaded. |

## 8. Интеграционные тесты

| # | Тест | Входной `user_query` | Ожидаемые поля upstream response | Ожидаемые поля downstream response | Критерий успешности |
|---:|---|---|---|---|---|
| 1 | Time series -> line chart | "Покажи динамику выручки по месяцам" | `request_id`, `user_query`, SQL, `result_table.columns=[month,revenue]`, rows, `field_metadata` with `month: time`, `revenue: measure`, `query_context.group_by`, `aggregations`, `order_by`, no errors | `status=success`, `selected_view.chart_type=line`, x temporal, y quantitative, confidence/warnings present, optional PNG/spec | Line chart selected; no double aggregation; month ordered ascending. |
| 2 | Category comparison -> bar chart | "Сравни продажи по категориям товаров" | columns `[category,sales_sum]`, rows, `category: dimension`, `sales_sum: measure`, aggregation sum or already aggregated, row_count > 0 | `status=success`, `selected_view.chart_type=bar`, category on nominal axis, measure on quantitative axis | Bar chart selected; fields match metadata and table columns. |
| 3 | Top-N query -> table/bar chart | "Покажи топ-5 клиентов по выручке таблицей" | columns `[client_name, region, revenue]`, rows <= 5 or `limit=5`, `order_by revenue desc`, `truncated=false` unless capped | `status=success`, `selected_view.type=table`, `table_view` filled, optional bar candidate | Table is primary because user asked table; sorted order preserved. |
| 4 | Empty SQL result -> safe response | "Покажи продажи за период, где данных нет" | SQL valid, `row_count=0`, rows `[]`, status `partial_success` or `success` with error/warning `empty_result` | No chart or empty table; `errors[].code=empty_result`; user-safe message | No renderer crash; site can show empty state. |
| 5 | Metadata incomplete -> fallback chart with warning | "Покажи распределение значений" with rows/columns but missing roles | rows and columns present; some `field_metadata.semantic_role=unknown`; warning `metadata_incomplete` | `status=partial_success`, fallback table or conservative chart, `quality.warnings` contains `metadata_incomplete` | Pipeline returns usable artifact/table and explicit warning, not failed request. |

Minimum contract assertions for every test:

- every `field_metadata[].name` exists in `result_table.columns`;
- either `result_table.rows` or `result_table.uri` is present;
- `request_id` is identical across backend, upstream, adapter, downstream;
- all errors use the shared enum from section 6;
- downstream never depends on gold spec or benchmark-only fields.

## 9. План доработок

### Этап 1 - MVP-интеграция

| Task | Owner |
|---|---|
| Add/generate `request_id` in common backend and pass it through all responses. | shared |
| Extend Денис output from `AnalyticsPayload v1` to a v2-compatible `DataExtractionResponse` without breaking v1. | Denis |
| Serialize explicit `result_table.columns`, `rows`, `row_count`, `truncated=false` for current small inline payloads. | Denis |
| Build minimal `field_metadata[].name/data_type/semantic_role` in adapter using rows/summary/type inference. | shared |
| Map `source.generated_sql` to `query_context.sql`. | shared |
| Normalize plan fields when `plan_parsed` exists; otherwise send empty `filters/group_by/aggregations` with warning. | shared |
| Add `VisualizationRequest -> T2VExample` adapter or direct inline-records path in Peter module. | Peter |
| Add common status/error enum and mapping from upstream/downstream errors. | shared |
| Add 5 contract tests from section 8 using fixture payloads. | shared |

### Этап 2 - Повышение качества

| Task | Owner |
|---|---|
| Add per-item latency timers and expose `execution.latency_ms`, `performance.latency_ms`. | Denis/Peter |
| Add row-limit at executor/backend layer and set `result_table.truncated`. | Denis |
| Add role/type/provenance builder for derived columns from plan/SQL AST where possible. | Denis |
| Normalize plan v1/v5 into one `query_context` shape. | Denis |
| Add `allowed_aggregations`, `default_aggregation`, `grain`, `periodicity`, `cardinality`, `examples` when evidence exists. | shared |
| Add fallback logic in downstream: table for empty/high-cardinality/unknown metadata, conservative bar for dimension+measure. | Peter |
| Add warnings for metadata incomplete, row truncation, empty result, render fallback. | Peter |
| Add validation that prevents double aggregation of already aggregated fields. | shared |
| Decide privacy/redaction policy for examples, logs and artifacts. | shared |

### Этап 3 - Микросервис и сайт

| Task | Owner |
|---|---|
| Wrap Text-to-SQL into `POST /extract`, `/health`, `/ready`. | Denis |
| Wrap Text-to-Visualization into `POST /visualize`, `/health`, `/ready`. | Peter |
| Implement common backend `POST /api/nl2chart`, polling and artifact endpoints. | shared |
| Add artifact storage for PNG/spec/table with TTL and access control. | shared |
| Add async quality mode for LLM visualization path; keep fast B1/B2 sync path. | Peter |
| Add frontend empty/error/truncated/warning states. | shared |
| Add observability: request logs, latency, status codes, render failures, model readiness. | shared |
| Add versioning for contracts, e.g. `schema_version: "nl2chart.v1"`, and deprecation rules. | shared |

## 10. Главный вывод

1. Денис обязательно должен выгружать `request_id`, `user_query`, `data_source.id`, явный `dialect`, SQL, `result_table.columns`, `result_table.rows` или `uri`, `row_count`, `truncated`.
2. Для запуска Петра минимально нужны `field_metadata[].name`, `field_metadata[].data_type`, `field_metadata[].semantic_role`.
3. `query_context.sql` надо передавать как provenance/debug; Петр не должен генерировать или оценивать SQL.
4. `query_context.filters/group_by/aggregations/order_by/limit` желательно брать из plan, но если plan отсутствует, ставить пустые списки и warning, а не выдумывать структуру.
5. Adapter нужен обязательно: текущие границы обеих веток experiment-first и не совпадают с production API.
6. Первый adapter должен уметь преобразовать `AnalyticsPayload v1` и prediction fields Дениса в `VisualizationRequest`.
7. Основной формат обмена для MVP - JSON records inline; для больших таблиц надо добавить `uri` (`csv_uri`/`arrow_uri`) и `truncated`.
8. Расширенный контракт должен добавить `allowed_aggregations`, `default_aggregation`, `grain`, `periodicity`, `provenance`, `cardinality`, `examples`, `formatting_hints`.
9. Самый критичный риск - неполная metadata: без role/type/aggregation Петр будет выбирать неверный chart type или fallback.
10. Второй критичный риск - double aggregation, если upstream уже агрегировал measure, а downstream снова применит sum/mean.
11. Третий критичный риск - отсутствие `truncated` и row-limit: сайт может показать неполный результат как полный.
12. Четвертый критичный риск - несовпадение field names между rows/columns и metadata.
13. Production HTTP API, artifact storage, SVG/HTML export и inline-record runtime adapter в текущем коде не подтверждены аудитами.
14. Все неподтвержденные поля (`description`, `unit`, `metric_definition`, full `provenance`) должны быть `null`/`unknown`, пока не появится schema/metric dictionary.
15. Для MVP достаточно fast deterministic path у Петра; LLM quality path лучше делать async после стабилизации контрактов.
