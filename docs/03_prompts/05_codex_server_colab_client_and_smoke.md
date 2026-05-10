# Prompt 05 — Codex: server Colab client and interservice smoke

Ты работаешь в `petrussia/NL2BI-AI-assistant` на ветке `integration/server-colab-nl2chart-mvp`.

## Цель

Подключить server-runtime к внешнему Colab Text-to-SQL service через HTTP и проверить межсервисное взаимодействие.

Flow:

```text
Server POST /api/nl2chart
  -> ColabExtractionClient
  -> Colab POST /extract
  -> DataExtractionResponse
  -> Adapter
  -> CPU Visualization
  -> Nl2ChartResponse
```

## Жёсткие ограничения

1. Server не импортирует `torch`, `transformers`, `bitsandbytes`.
2. Server не запускает модель.
3. Server вызывает только HTTP endpoint Colab.
4. Все ошибки Colab/tunnel/network должны маппиться в safe errors.
5. Нельзя отдавать frontend raw stack trace, tunnel internals, private URLs in public message.
6. Mock mode должен сохраниться.

## Реализовать

### `services/extraction_client/colab_client.py`

Requirements:

- reads `TEXT_TO_SQL_SERVICE_URL`;
- calls `POST /extract`;
- timeout from `TEXT_TO_SQL_TIMEOUT_SECONDS`;
- connect timeout;
- validates response as `DataExtractionResponse`;
- maps errors:
  - connection refused -> `colab_unavailable`;
  - timeout -> `extraction_timeout`;
  - invalid JSON -> `invalid_extraction_response`;
  - schema validation -> `invalid_extraction_response`;
  - 5xx -> `colab_service_error`;
  - 4xx -> `colab_request_error`.

### Runtime endpoint

Update `GET /api/runtime`:

```json
{
  "extraction_mode": "colab",
  "colab_service_url_configured": true,
  "colab_available": true,
  "colab_health": {
    "model_loaded": true,
    "gpu_name": "NVIDIA L4"
  }
}
```

If health check fails:

```json
{
  "colab_available": false,
  "colab_error_code": "colab_unavailable"
}
```

### Orchestrator

Update extraction client factory:

```text
EXTRACTION_MODE=mock -> MockExtractionClient
EXTRACTION_MODE=colab -> ColabExtractionClient
EXTRACTION_MODE=disabled -> DisabledExtractionClient
```

### Smoke scripts

Create:

```text
scripts/smoke_server_colab.py
scripts/smoke_nl2chart_colab.sh
```

Smoke must:

1. call server `/api/runtime`;
2. call Colab `/health` through server client or direct URL;
3. call server `/api/nl2chart`;
4. print request_id;
5. print status;
6. save response to `artifacts/smoke/<request_id>.json`.

## Tests

Use mocked HTTP via `respx` or similar if available. Otherwise use monkeypatch.

Create:

```text
tests/unit/test_colab_extraction_client.py
tests/integration/test_nl2chart_colab_mocked_http.py
```

Cases:

1. successful Colab response;
2. timeout;
3. invalid JSON;
4. response missing required fields;
5. Colab status failed;
6. Colab unavailable;
7. mock mode unaffected.

## Manual smoke

On server, after Colab is running:

```bash
export EXTRACTION_MODE=colab
export TEXT_TO_SQL_SERVICE_URL=https://<colab-tunnel>
export TEXT_TO_SQL_TIMEOUT_SECONDS=60

curl http://127.0.0.1:8100/api/runtime

curl -X POST http://127.0.0.1:8100/api/nl2chart \
  -H 'Content-Type: application/json' \
  -d '{"user_query":"Покажи динамику продаж по месяцам","data_source_id":"demo_sales"}'
```

## Acceptance criteria

- Server can call Colab `/extract`.
- `request_id` is same in server response and Colab response.
- If Colab is down, server returns safe failed response.
- Mock mode still works.
- Tests pass without real Colab.
- Manual smoke works with real Colab.

## Итоговый отчёт

Output:

1. Changed files.
2. Environment variables used.
3. Test outputs.
4. `/api/runtime` JSON in colab mode.
5. `/api/nl2chart` JSON in colab mode.
6. Server logs for request_id.
7. How Colab errors are mapped.
8. What to send to ChatGPT after this stage:
   - `/api/runtime` JSON;
   - `/api/nl2chart` JSON;
   - server logs;
   - Colab logs;
   - artifact JSON/spec;
   - failed tests if any.
