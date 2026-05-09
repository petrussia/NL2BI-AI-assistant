# Prompt 03 — Claude / Denis: Colab Text-to-SQL `/extract` endpoint

Ты работаешь над Text-to-SQL частью NL2BI. Нужно подготовить Colab-compatible GPU inference service, который будет вызываться основным сервером по HTTP.

## Среда

- Google Colab Pro+.
- GPU может быть L4/A100/T4, поэтому код должен проверять доступную GPU.
- Основной сайт/backend работает отдельно на server-runtime без GPU.
- Colab — внешний HTTP inference service, не frontend и не основной backend.

## Цель

Создать `colab/text_to_sql_colab_server.ipynb` и/или `colab/text_to_sql_colab_server.py`, который поднимает FastAPI service:

```text
GET /health
POST /extract
POST /reload_model
```

и возвращает `DataExtractionResponse` по общему контракту.

## Жёсткие ограничения

1. Не использовать OpenAI API.
2. Не хранить токены в notebook cells.
3. Не зависеть от frontend/backend code для старта Colab service.
4. Не возвращать raw tracebacks пользователю.
5. SQL должен проходить SELECT-only guard.
6. Timeout обязателен.
7. Row limit обязателен.
8. Service должен поддерживать mock-model режим для smoke tests без загрузки полной модели.

## Вход: DataExtractionRequest

```json
{
  "request_id": "string",
  "user_query": "string",
  "locale": "ru-RU",
  "timezone": "Europe/Moscow",
  "data_source": {
    "id": "demo_sales",
    "dialect": "sqlite|postgresql|unknown",
    "connection_ref": "string|null",
    "schema_version": "string|null"
  },
  "constraints": {
    "read_only": true,
    "timeout_ms": 8000,
    "row_limit": 1000
  },
  "presentation_hint": {
    "preferred_output": "auto|chart|table",
    "requested_fields": [],
    "requested_metrics": []
  }
}
```

## Выход: DataExtractionResponse

```json
{
  "request_id": "string",
  "status": "success|partial_success|failed",
  "user_query": "string",
  "normalized_query": "string|null",
  "data_source": {
    "id": "string",
    "name": "string|null",
    "dialect": "sqlite|postgresql|unknown",
    "schema_version": "string|null"
  },
  "plan": {
    "raw": {},
    "validated": true,
    "intent": "string|null",
    "tables": [],
    "columns": [],
    "filters": [],
    "aggregations": [],
    "group_by": [],
    "order_by": [],
    "limit": null,
    "joins": [],
    "assumptions": []
  },
  "sql": {
    "query": "string|null",
    "dialect": "sqlite",
    "validated": true,
    "read_only": true
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
  "execution": {
    "latency_ms": 0,
    "row_limit": 1000,
    "timeout_ms": 8000,
    "executable": true
  },
  "quality": {
    "confidence": null,
    "warnings": []
  },
  "errors": [],
  "warnings": []
}
```

`field_metadata` item:

```json
{
  "name": "string",
  "source_table": "string|null",
  "source_column": "string|null",
  "display_name": "string|null",
  "description": "string|null",
  "sql_type": "string|null",
  "data_type": "number|string|date|datetime|boolean|unknown",
  "semantic_role": "measure|dimension|time|id|text|unknown",
  "unit": "string|null",
  "periodicity": "day|week|month|quarter|year|null",
  "allowed_aggregations": ["sum", "avg", "count", "min", "max", "none"],
  "default_aggregation": "sum|avg|count|min|max|none|null",
  "nullable": "boolean|null",
  "examples": [],
  "provenance": {
    "expression": "string|null",
    "aggregation": "string|null",
    "derived": "boolean"
  }
}
```

## Реализовать

1. GPU check:
   - device;
   - GPU name;
   - total/free VRAM;
   - model_loaded flag.
2. Model loading:
   - default `Qwen/Qwen2.5-Coder-7B-Instruct` or current best Text-to-SQL model;
   - 4-bit quantization if available;
   - fallback mock mode if env `COLAB_MOCK_MODEL=true`.
3. Demo DB:
   - support SQLite demo database;
   - schema loading from JSON or SQLite introspection;
   - safe connection handling.
4. SQL generation:
   - build prompt from `user_query` + schema;
   - extract SQL from model output;
   - clean markdown fences;
   - static SELECT-only validation.
5. SQL execution:
   - enforce read-only;
   - apply row limit;
   - apply timeout;
   - capture errors.
6. Metadata inference:
   - SQL type -> data_type;
   - date/time names/types -> time;
   - numeric aggregate -> measure;
   - string low-cardinality -> dimension;
   - id-like names -> id;
   - aggregation from SQL aliases/provenance if possible.
7. Error enum:
   - `model_not_loaded`;
   - `schema_not_found`;
   - `ambiguous_query`;
   - `sql_generation_failed`;
   - `sql_validation_failed`;
   - `sql_execution_failed`;
   - `timeout`;
   - `empty_result`;
   - `row_limit_exceeded`;
   - `metadata_incomplete`.
8. Tunnels:
   - add instructions for cloudflared or ngrok;
   - print public URL;
   - do not print tokens.

## Health endpoint

`GET /health` should return:

```json
{
  "status": "ok",
  "model_loaded": true,
  "model_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
  "mock_model": false,
  "device": "cuda",
  "gpu_name": "NVIDIA L4",
  "vram_total_gb": 23,
  "demo_db_ready": true,
  "server_role": "colab-runtime"
}
```

## Smoke tests

Add smoke examples:

```bash
curl https://<tunnel>/health
curl -X POST https://<tunnel>/extract \
  -H 'Content-Type: application/json' \
  -d @demo_data/extraction_requests/time_series.json
```

Also add a Python smoke script:

```text
colab/smoke_extract.py
```

## Acceptance criteria

- Colab service starts.
- `/health` works.
- `/extract` returns valid JSON matching `DataExtractionResponse`.
- `request_id` is preserved.
- SQL is SELECT-only.
- timeout and row_limit are enforced.
- Empty result handled safely.
- Mock-model mode can be used for endpoint testing without full model.

## Итоговый отчёт

В конце выведи:

1. Files created.
2. How to start Colab service.
3. How to expose tunnel.
4. `/health` example output.
5. `/extract` example output.
6. GPU info.
7. Known limitations.
8. What to send to ChatGPT after this stage:
   - Claude report;
   - health JSON;
   - extract JSON;
   - GPU name/VRAM;
   - errors if any.
