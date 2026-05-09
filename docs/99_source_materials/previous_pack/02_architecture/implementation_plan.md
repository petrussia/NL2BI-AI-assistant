# Подробный план реализации объединения систем

## 0. Принятые предположения

1. Код собирается в `petrussia/NL2BI-AI-assistant/tree/main`.
2. `SHUBINDENIS/superset_ai` используется как donor для пользовательского чата, shell, auth и части FastAPI backend.
3. Superset, MCP, scan/preview/recommend/share в Superset-смысле и OpenAI API должны быть удалены.
4. MVP не должен требовать `OPENAI_API_KEY`.
5. Для первого демонстрационного контура достаточно sync fast path: Text-to-SQL → Adapter → Text-to-Visualization B1/B2 → chat artifact.
6. LLM quality mode можно добавить после MVP как async job.

## 1. Target architecture

```text
apps/web                         # Next.js UI from superset_ai, cleaned and renamed
services/gateway                 # FastAPI common backend from superset_ai, cleaned
services/extract                 # Денис: Text-to-SQL/DataExtraction service wrapper
services/visualize               # Пётр: Text-to-Visualization service wrapper
packages/contracts               # shared Pydantic models / JSON schema
packages/adapter                 # DataExtractionResponse -> VisualizationRequest
packages/artifacts               # artifact storage abstraction
packages/testing                 # shared fixtures, contract asserts
tests                            # unit/integration/e2e tests
docker-compose.mvp.yml           # assistant web + gateway + extract + visualize
```

## 2. End-to-end runtime

### Main flow

1. `POST /api/chats/{session_id}/messages` receives user text.
2. Chat router persists user message.
3. `Nl2biOrchestrator.run()` creates `request_id`.
4. Orchestrator builds `DataExtractionRequest`.
5. Calls `extract_client.extract(request)`.
6. If extraction fails, returns user-safe error artifact.
7. Adapter normalizes extraction result into `VisualizationRequest`.
8. Calls `visualize_client.visualize(request)`.
9. Artifacts are stored or embedded:
   - `chart_spec` JSON;
   - `table` records;
   - `png_uri` if render works;
   - warnings/errors.
10. Chat router persists assistant message with artifacts.
11. UI renders table/chart/error in chat.

### Endpoint flow

```text
POST /api/nl2chart
  -> validate Nl2ChartRequest
  -> DataExtractionRequest
  -> POST /extract or in-process extract()
  -> adapter.normalize_extraction_response()
  -> POST /visualize or in-process visualize()
  -> store artifacts
  -> Nl2ChartResponse
```

## 3. Workstream A — перенос и очистка `superset_ai`

### A1. Import donor code

Source from `superset_ai`:

- `superset-ai-assistant-mcp/frontend-next` → `apps/web`;
- `superset-ai-assistant-mcp/api` → `services/gateway/api`;
- auth/chat persistence modules → `services/gateway/backend` or `services/gateway/core`;
- `frontend_logs`, `health`, API proxy pattern.

Do not import:

- `superset/`;
- `mcp_client`;
- `us13_15_viz_service` as Superset service;
- Superset docker compose services;
- Superset docs except as historical notes.

### A2. Remove OpenAI runtime

Remove or replace:

- `langchain_openai.ChatOpenAI`;
- `OpenAISafeLangChainAdapter`;
- `MCPAgent`;
- `OPENAI_API_KEY` startup requirement;
- `OPENAI_MODEL` config;
- `mcp-use`, `langchain-openai`, `openai` dependencies.

Replacement:

```python
class Nl2biChatAgent:
    async def chat(self, messages, response_style="business", detail_level="standard") -> dict:
        user_query = extract_latest_user_message(messages)
        result = await nl2bi_orchestrator.run(user_query=user_query, ...)
        return format_chat_response(result)
```

### A3. Rebrand UI

- Rename product title: `NL2BI AI Assistant`.
- Keep routes:
  - `/login`;
  - `/register`;
  - `/app/chat`.
- Remove or hide:
  - `/app/preview`;
  - `/app/recommend`;
  - `/app/share`;
  - `/app/scan`.
- Optional new route:
  - `/app/history` or keep history in sidebar only.

### A4. Adapt artifacts

Old artifact types:

- `table_preview`;
- `chart_preview`;
- `link`.

New artifact types:

- `table`;
- `chart_spec`;
- `chart_image`;
- `warning`;
- `error`;
- `debug_sql` only in technical mode.

## 4. Workstream B — contracts

Create `packages/contracts/nl2bi_contracts.py` and mirror `01_contracts/nl2bi_contracts.md`.

Required tests:

- every fixture validates;
- invalid field role fails;
- invalid missing columns fails;
- `request_id` must be non-empty;
- errors/warnings use enum/source.

Versioning:

```python
CONTRACT_VERSION = "nl2chart.v1"
```

Add this to responses:

```json
"schema_version": "nl2chart.v1"
```

## 5. Workstream C — adapter

Create `packages/adapter`:

```text
packages/adapter/
  __init__.py
  extraction_to_visualization.py
  analytics_payload_v1.py
  type_mapping.py
  role_inference.py
  aggregation_inference.py
  errors.py
  tests/
```

### Adapter responsibilities

- Accept `DataExtractionResponse` or legacy `AnalyticsPayload v1`.
- Produce `VisualizationRequest`.
- Never invent descriptions/units/metric definitions.
- Fill unknown fields as `null`/`unknown`.
- Add warnings for inferred roles/metadata gaps.
- Ensure every `field_metadata.name` exists in `result_table.columns`.
- Ensure row truncation is explicit.
- Preserve SQL as provenance/debug.

### Legacy AnalyticsPayload v1 mapping

| Legacy field | Target field |
|---|---|
| `source.question` | `user_query` |
| `source.db_id` | `data_source.id` |
| `source.generated_sql` | `sql.query`, `query_context.sql` |
| `rows` | `result_table.rows` |
| `summary.row_count` / `n_rows` | `result_table.row_count` |
| `summary.columns` or row keys | `result_table.columns` |
| `source.baseline` | `quality/model/debug` |
| `error_type/error_message` | `errors[]` |

## 6. Workstream D — Денис / extraction service

### D1. Function boundary

Implement:

```python
def extract(request: DataExtractionRequest) -> DataExtractionResponse:
    ...
```

### D2. FastAPI wrapper

```python
@router.post("/extract", response_model=DataExtractionResponse)
async def extract_endpoint(request: DataExtractionRequest):
    return await run_extract(request)
```

### D3. Minimal output for MVP

Must include:

- `request_id`;
- `status`;
- `user_query`;
- `data_source.id`;
- `data_source.dialect`;
- `sql.query`;
- `sql.validated`;
- `result_table.columns`;
- `result_table.rows`;
- `result_table.row_count`;
- `result_table.truncated`;
- `errors`.

Should include when possible:

- `plan`;
- `field_metadata`;
- `execution.latency_ms`;
- `warnings`.

### D4. Safety

- SELECT-only guard;
- read-only DB connection;
- timeout default 8s;
- row limit default 1000;
- no DDL/DML/PRAGMA/ATTACH;
- no secret in logs;
- SQL errors mapped to shared enum.

## 7. Workstream E — Пётр / visualization service

### E1. Function boundary

Implement:

```python
def visualize(request: VisualizationRequest) -> VisualizationResponse:
    ...
```

### E2. Fast path

Default MVP method:

- `B1_constraint_ranker` as primary;
- `B0_rule_based` fallback;
- `B2_partial_recommender` optional when profiling is needed.

### E3. Input adapter

Current Peter code expects `T2VExample` + CSV path. MVP options:

1. Preferred: add inline records runtime path.
2. Temporary: materialize `result_table.rows` to a temp CSV and create `T2VExample`.

### E4. Output

Return:

- `selected_view.spec`;
- `selected_view.normalized_spec`;
- `selected_view.rendered_artifacts.png_uri` when render succeeds;
- `table_view` always for fallback;
- `candidates`;
- `warnings`;
- `performance.latency_ms`;
- `errors`.

### E5. Fallbacks

| Condition | Behavior |
|---|---|
| `row_count=0` | no chart, empty table, `empty_result` |
| one row | table or KPI-like table |
| all text | table |
| all numeric | scatter if query asks correlation, otherwise table/histogram |
| missing roles | infer + `metadata_incomplete` warning |
| high cardinality category | top-N table/bar or table fallback |
| render fails | return spec + `render_failed`, status `partial_success` |

## 8. Workstream F — gateway orchestration

Create:

```text
services/gateway/api/routers/nl2chart.py
services/gateway/core/orchestrator.py
services/gateway/core/extract_client.py
services/gateway/core/visualize_client.py
services/gateway/core/artifact_store.py
services/gateway/core/chat_response_formatter.py
```

### Orchestrator pseudocode

```python
async def run_nl2chart(request: Nl2ChartRequest, user: User) -> Nl2ChartResponse:
    request_id = request.request_id or uuid4()

    extraction_request = DataExtractionRequest(
        request_id=request_id,
        user_query=request.user_query,
        data_source=request.data_source or resolve_default_data_source(user),
        constraints=request.constraints,
        presentation_hint=request.presentation_preferences,
    )

    extraction = await extract_client.extract(extraction_request)
    if extraction.status == "failed":
        return failed_response_from_extraction(extraction)

    visualization_request = normalize_extraction_response(extraction)
    visualization_request.presentation_preferences = request.presentation_preferences

    visualization = await visualize_client.visualize(visualization_request)

    artifacts = artifact_store.save_from_visualization(visualization)
    assistant_message = format_user_facing_message(extraction, visualization)

    return Nl2ChartResponse(
        request_id=request_id,
        status=merge_status(extraction.status, visualization.status),
        assistant_message=assistant_message,
        extraction=maybe_hide_sql(extraction, technical_mode=request.technical_mode),
        visualization=visualization,
        artifacts=artifacts,
        warnings=merge_warnings(extraction, visualization),
        errors=merge_errors(extraction, visualization),
    )
```

## 9. Workstream G — frontend chat

### UI requirements

In `/app/chat`:

- message input;
- history/sidebar;
- response style toggle: business/technical;
- detail level toggle;
- render artifacts inside assistant messages.

### Artifact rendering

| Artifact type | UI behavior |
|---|---|
| `table` | compact table with horizontal scroll |
| `chart_spec` | client-side Vega-Lite renderer if available, or show JSON in technical mode |
| `chart_image` | image card with download |
| `warning` | yellow info card |
| `error` | safe error card with retry/clarify text |
| `debug_sql` | collapsible block, technical mode only |

### User-safe language

- Do not expose raw stack traces.
- For SQL errors: «Не удалось выполнить запрос к данным. Попробуйте уточнить формулировку или источник.»
- For metadata gaps: «График построен по ограниченным метаданным, поэтому выбран безопасный вариант отображения.»
- For empty result: «По этому запросу данные не найдены.»

## 10. Workstream H — Docker/CI

### MVP compose services

- `assistant-web`;
- `assistant-api` / gateway;
- `extract-service`;
- `visualize-service`;
- optional `postgres-demo`;
- optional `artifact-volume`.

No Superset, no Redis unless needed for async jobs later.

### CI checks

- Python unit tests;
- contract tests;
- adapter tests;
- frontend build;
- OpenAPI schema validation;
- docker compose smoke if feasible.

## 11. Definition of Done for MVP

- `docker compose -f docker-compose.mvp.yml up` starts web/backend/services.
- `/api/health` and `/api/ready` pass.
- User can login/register.
- User asks one of 3 fixture questions in chat.
- System returns a chart/table artifact.
- `request_id` is visible in backend logs.
- Contract tests pass.
- No dependency on Superset services.
- No dependency on `OPENAI_API_KEY`.
