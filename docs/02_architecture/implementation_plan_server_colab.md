# Подробный план реализации: server-runtime + colab-runtime

## 0. Принятые ограничения

1. Код собирается в `petrussia/NL2BI-AI-assistant`.
2. Сервер без GPU на 8 GB RAM является одновременно dev и production-like машиной.
3. Google Colab Pro+ используется как внешний GPU inference endpoint.
4. Локальной dev-машины в плане нет.
5. Основной сервер не запускает LLM и не импортирует `torch`, `transformers`, `bitsandbytes`.
6. OpenAI API не используется.
7. Superset/MCP runtime удаляется или не переносится.
8. Сервер обязан работать в `EXTRACTION_MODE=mock`, даже если Colab отключён.
9. Colab обязан отвечать по HTTP-контракту `POST /extract` и возвращать `DataExtractionResponse`.

## 1. Целевая структура репозитория

```text
NL2BI-AI-assistant/
  apps/
    web/                              # Next.js chat UI, cleaned from superset_ai
  services/
    gateway/                          # FastAPI main server: dev+prod CPU runtime
      api/
      core/
      routers/
      settings.py
    orchestrator/
      nl2chart_orchestrator.py
    extraction_client/
      base.py
      mock_client.py
      colab_client.py
      disabled_client.py
    adapter/
      extraction_to_visualization.py
      analytics_payload_v1.py
      role_inference.py
      type_mapping.py
      aggregation_inference.py
    visualization/
      cpu_visualization_service.py
      rules.py
      validation.py
    artifacts/
      artifact_store.py
  contracts/
    extraction.py
    visualization.py
    nl2chart.py
    common.py
  colab/
    text_to_sql_colab_server.ipynb
    text_to_sql_colab_server.py
    README.md
  demo_data/
    extraction_fixtures/
    extraction_requests/
    nl2chart_requests/
  tests/
    unit/
    integration/
    smoke/
  docs/
    runtime_split.md
    server_runbook.md
    colab_runbook.md
    integration_smoke_checklist.md
  docker-compose.server.yml
  .env.example
```

## 2. Runtime roles

### 2.1 Server-runtime: dev + prod

Server-runtime отвечает за всё, что должно быть стабильно доступно пользователю:

- Next.js UI;
- FastAPI API;
- auth/chat persistence;
- `POST /api/nl2chart`;
- request_id generation;
- extraction client abstraction;
- mock extraction mode;
- Colab HTTP client;
- adapter;
- CPU visualization;
- artifacts;
- logs;
- health/ready/runtime;
- tests and smoke checks.

Server-runtime не делает:

- LLM inference;
- model loading;
- GPU-specific code;
- direct notebook execution;
- Superset/MCP/OpenAI calls.

### 2.2 Colab-runtime

Colab-runtime отвечает только за тяжёлый inference:

- загрузка Text-to-SQL модели;
- генерация SQL;
- SQL validation;
- safe SQL execution on demo DB;
- metadata inference;
- формирование `DataExtractionResponse`;
- `GET /health`;
- `POST /extract`;
- optional `POST /reload_model`.

Colab-runtime не делает:

- frontend;
- auth;
- chat persistence;
- artifact storage сайта;
- final visualization, кроме optional quality mode;
- хранение пользовательской истории.

## 3. Environment variables

### Server `.env.example`

```env
APP_ENV=development
API_HOST=0.0.0.0
API_PORT=8100
WEB_PORT=3001

EXTRACTION_MODE=mock
TEXT_TO_SQL_SERVICE_URL=
TEXT_TO_SQL_TIMEOUT_SECONDS=60
TEXT_TO_SQL_CONNECT_TIMEOUT_SECONDS=10

VISUALIZATION_MODE=local_cpu
ARTIFACT_STORAGE=local
ARTIFACT_DIR=./artifacts
DEMO_DATA_DIR=./demo_data

AUTH_DB_PATH=./data/auth.db
AUTH_JWT_SECRET=dev-only-change-me
AUTH_JWT_TTL_HOURS=12

API_CORS_ORIGINS=http://localhost:3001,http://127.0.0.1:3001
DEBUG_SQL_VISIBLE=false
```

### Colab environment

```env
MODEL_ID=Qwen/Qwen2.5-Coder-7B-Instruct
MODEL_QUANTIZATION=4bit_nf4
COLAB_DEMO_DB_PATH=/content/nl2bi_demo/demo.sqlite
COLAB_SCHEMA_PATH=/content/nl2bi_demo/schema.json
EXTRACT_TIMEOUT_MS=8000
EXTRACT_ROW_LIMIT=1000
```

## 4. Server API

### `POST /api/nl2chart`

Input:

```json
{
  "user_query": "Покажи выручку по месяцам",
  "data_source_id": "demo_sales",
  "presentation_preferences": {
    "preferred_output": "auto"
  }
}
```

Output:

```json
{
  "request_id": "uuid",
  "status": "success|partial_success|failed",
  "message": "Краткий ответ для чата",
  "selected_view": {},
  "artifacts": [],
  "errors": [],
  "warnings": [],
  "debug": {}
}
```

### `GET /api/runtime`

Shows current runtime split:

```json
{
  "server_runtime": true,
  "gpu_in_backend": false,
  "extraction_mode": "mock|colab|disabled",
  "visualization_mode": "local_cpu",
  "colab_service_url_configured": true,
  "colab_available": true,
  "server_allows_llm_imports": false
}
```

### `GET /api/health`

Basic liveness.

### `GET /api/ready`

Readiness including DB, artifact dir and configured extraction mode.

### `GET /api/artifacts/{artifact_id}`

Returns chart/table/spec artifact.

## 5. Extraction modes

### `EXTRACTION_MODE=mock`

Server reads fixtures from `demo_data/extraction_fixtures/`.

Purpose:

- development on server without GPU;
- demo if Colab is off;
- CI tests;
- deterministic E2E checks.

### `EXTRACTION_MODE=colab`

Server calls:

```text
POST {TEXT_TO_SQL_SERVICE_URL}/extract
```

Requirements:

- timeout;
- retry at most once, optional;
- safe error mapping;
- request_id pass-through;
- no stack traces to frontend;
- structured logs.

### `EXTRACTION_MODE=disabled`

Server returns safe `extraction_unavailable` error.

## 6. Adapter requirements

Adapter receives `DataExtractionResponse` and outputs `VisualizationRequest`.

Must do:

- map `user_query`;
- map datasource;
- ensure explicit ordered columns;
- ensure rows are records;
- ensure row_count/truncated;
- infer data_type if missing;
- infer semantic_role if missing;
- infer allowed/default aggregations conservatively;
- preserve SQL as provenance/debug;
- add warnings for missing/inferred metadata;
- map errors to common enum.

Must not do:

- generate SQL;
- execute SQL;
- fabricate metric definitions, descriptions or units;
- silently drop columns;
- hide truncation.

## 7. CPU visualization requirements

Default visualization path runs on server CPU.

Allowed:

- deterministic rules;
- B0/B1/B2 from Peter branch if cleanly importable;
- pandas/numpy/jsonschema/Altair/vl-convert.

Disallowed in default server path:

- torch;
- transformers;
- bitsandbytes;
- local LLM inference.

Fallback rules:

| Data pattern | Output |
|---|---|
| time + measure | line chart |
| dimension + measure | bar chart |
| two measures | scatter chart |
| top-N/order_by | table or bar |
| 0 rows | safe empty_result error/warning |
| 1 row | table or single-value card |
| too many rows | truncate with warning |
| missing metadata | infer role/type and add warning |

## 8. Colab service requirements

Colab service exposes:

```text
GET /health
POST /extract
POST /reload_model
```

`GET /health`:

```json
{
  "status": "ok",
  "model_loaded": true,
  "model_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
  "device": "cuda",
  "gpu_name": "NVIDIA L4",
  "vram_total_gb": 23,
  "demo_db_ready": true
}
```

`POST /extract` returns `DataExtractionResponse`.

Required safety:

- SELECT-only guard;
- DDL/DML forbidden;
- timeout;
- row_limit;
- no secrets in logs;
- no raw tracebacks in response;
- errors in common enum.

## 9. Stage order

1. Server bootstrap and cleanup.
2. Server contracts + mock pipeline.
3. Server CPU visualization.
4. Colab `/extract` service.
5. Server Colab client + server->Colab smoke.
6. Frontend artifact rendering.
7. Final integration review.

## 10. Acceptance criteria by stage

### Stage 1: server bootstrap

Pass if:

- `superset_ai` donor code cleaned;
- Superset/MCP/OpenAI removed from default runtime;
- server starts;
- `/api/health` works;
- no required `OPENAI_API_KEY`.

### Stage 2: server mock pipeline

Pass if:

- `pytest -q` passes without GPU;
- `/api/runtime` returns `gpu_in_backend=false`;
- `/api/nl2chart` returns chart/table with fixtures;
- Colab not required.

### Stage 3: Colab service

Pass if:

- `/health` returns `model_loaded=true` or clear model status;
- `/extract` returns valid `DataExtractionResponse`;
- SQL safety and row limit work.

### Stage 4: server->Colab

Pass if:

- server calls Colab;
- same `request_id` appears in server and Colab logs;
- adapter consumes Colab response;
- visualization returns artifact;
- Colab outage returns safe error.

### Stage 5: UI

Pass if:

- user sends prompt in chat;
- assistant returns table/chart/error artifact;
- warnings visible but not scary;
- debug SQL hidden unless technical mode.

## 11. What to send to ChatGPT for review

After server mock pipeline:

- `GET /api/runtime` JSON;
- `POST /api/nl2chart` mock JSON;
- test logs.

After Colab service:

- `GET /health` JSON;
- `POST /extract` JSON;
- GPU info;
- Claude report.

After server->Colab integration:

- `POST /api/nl2chart` with `EXTRACTION_MODE=colab` JSON;
- server logs for request_id;
- Colab logs for request_id;
- artifact spec/table;
- UI screenshot or description.

After final stage:

- final integration review;
- pass/fail table for 5 E2E scenarios;
- list of remaining risks.
