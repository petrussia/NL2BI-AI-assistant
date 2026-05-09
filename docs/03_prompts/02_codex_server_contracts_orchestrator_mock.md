# Prompt 02 — Codex: server contracts, mock extraction, adapter, orchestrator

Ты работаешь в `petrussia/NL2BI-AI-assistant` на ветке `integration/server-colab-nl2chart-mvp`.

## Цель

Сделать server-side MVP pipeline, который полностью работает без Colab и без GPU в режиме `EXTRACTION_MODE=mock`.

Пайплайн:

```text
POST /api/nl2chart
  -> Nl2ChartRequest
  -> MockExtractionClient
  -> DataExtractionResponse fixture
  -> Adapter
  -> VisualizationRequest
  -> CPU visualization minimal fallback
  -> ArtifactStore
  -> Nl2ChartResponse
```

## Жёсткие ограничения

1. Не использовать OpenAI API.
2. Не импортировать `torch`, `transformers`, `bitsandbytes` в server runtime.
3. Не вызывать Colab на этом этапе.
4. Не использовать Superset/MCP.
5. Все контракты должны быть Pydantic models.
6. Все ошибки должны быть structured и user-safe.

## Реализовать contracts

Создать:

```text
contracts/common.py
contracts/extraction.py
contracts/visualization.py
contracts/nl2chart.py
```

### Common

- `ErrorItem`:
  - `code: str`
  - `message: str`
  - `source: server|colab|extraction|adapter|visualization|frontend|unknown`
  - `retryable: bool`
  - `details: dict = {}`
- `WarningItem`
- `ArtifactRef`
- status enum: `success|partial_success|failed`

### DataExtractionRequest

Fields:

- `request_id`
- `user_query`
- `locale = ru-RU`
- `timezone = Europe/Moscow`
- `data_source`
- `constraints`
- `presentation_hint`

### DataExtractionResponse

Fields:

- `request_id`
- `status`
- `user_query`
- `normalized_query`
- `data_source`
- `plan`
- `sql`
- `result_table`
- `field_metadata`
- `execution`
- `quality`
- `errors`
- `warnings`

### VisualizationRequest / Response

As in existing integration plan, but aligned with server CPU mode.

### Nl2ChartRequest / Response

Request:

```json
{
  "user_query": "string",
  "data_source_id": "demo_sales",
  "locale": "ru-RU",
  "timezone": "Europe/Moscow",
  "presentation_preferences": {
    "preferred_output": "auto|chart|table"
  }
}
```

Response:

```json
{
  "request_id": "string",
  "status": "success|partial_success|failed",
  "message": "string",
  "selected_view": {},
  "artifacts": [],
  "warnings": [],
  "errors": [],
  "debug": {}
}
```

## Реализовать mock extraction

Создать:

```text
services/extraction_client/base.py
services/extraction_client/mock_client.py
services/extraction_client/disabled_client.py
```

Mock client должен читать fixtures:

```text
demo_data/extraction_fixtures/time_series.json
demo_data/extraction_fixtures/category_comparison.json
demo_data/extraction_fixtures/top_n.json
demo_data/extraction_fixtures/empty_result.json
```

Простейшая логика выбора fixture:

- если query содержит `month|месяц|динамик|trend` -> time_series;
- если `category|категор|сравн` -> category_comparison;
- если `top|топ|лучшие` -> top_n;
- если `empty|пуст` -> empty_result;
- иначе category_comparison.

## Реализовать adapter

Создать:

```text
services/adapter/extraction_to_visualization.py
services/adapter/type_mapping.py
services/adapter/role_inference.py
services/adapter/aggregation_inference.py
```

Adapter должен:

- validate extraction response;
- ensure explicit columns;
- infer missing data_type;
- infer missing semantic_role;
- infer default/allowed aggregations;
- preserve SQL in `query_context.sql`;
- add warnings for inferred metadata;
- fail safely if rows/columns inconsistent.

## Реализовать minimal CPU visualization fallback

На этом этапе достаточно минимального правила в `services/visualization/cpu_visualization_service.py`:

- time + measure -> line;
- dimension + measure -> bar;
- top-N -> table or bar;
- 0 rows -> failed/empty_result;
- otherwise table.

Полная B1/B2 интеграция будет отдельным промптом.

## Реализовать orchestrator

Создать:

```text
services/orchestrator/nl2chart_orchestrator.py
```

Orchestrator:

1. Generates `request_id`.
2. Builds `DataExtractionRequest`.
3. Calls extraction client by `EXTRACTION_MODE`.
4. If failed -> returns safe error response.
5. Runs adapter.
6. Runs CPU visualization.
7. Stores artifacts.
8. Returns `Nl2ChartResponse`.

## Реализовать API

Create/update:

```text
services/gateway/api/routers/nl2chart.py
services/gateway/api/routers/runtime.py
services/gateway/api/routers/artifacts.py
```

Endpoints:

- `POST /api/nl2chart`
- `GET /api/nl2chart/{request_id}` optional if storage exists
- `GET /api/artifacts/{artifact_id}`
- `GET /api/runtime`

## Тесты

Create tests:

```text
tests/unit/test_contracts.py
tests/unit/test_adapter.py
tests/unit/test_mock_extraction_client.py
tests/unit/test_cpu_visualization_minimal.py
tests/integration/test_nl2chart_mock.py
```

Test cases:

1. time series -> line chart;
2. category comparison -> bar chart;
3. top-N -> table/bar;
4. empty result -> safe failed/partial response;
5. metadata incomplete -> inferred warnings;
6. invalid columns -> adapter failure.

## Проверки

```bash
pytest -q
curl http://127.0.0.1:8100/api/runtime
curl -X POST http://127.0.0.1:8100/api/nl2chart \
  -H 'Content-Type: application/json' \
  -d '{"user_query":"Покажи динамику продаж по месяцам","data_source_id":"demo_sales"}'
```

## Acceptance criteria

- Works without Colab.
- Works without GPU.
- Tests pass without `torch`/`transformers`.
- `POST /api/nl2chart` returns table/chart artifact in mock mode.
- Empty result and invalid metadata do not crash server.
- `/api/runtime` says `extraction_mode=mock` and `gpu_in_backend=false`.

## Итоговый отчёт

В конце выведи:

1. Changed files.
2. Contract summary.
3. Fixtures created.
4. Test output.
5. Example `/api/runtime` JSON.
6. Example `/api/nl2chart` JSON for time_series/category/top_n.
7. Known issues.
8. What to send to ChatGPT after this stage.
