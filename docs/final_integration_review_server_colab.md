# Final Integration Review — Server + Colab NL2BI MVP

## 1. Snapshot

- Branch: `integration/server-colab-nl2chart-mvp`
- Commit: this implementation commit (`git rev-parse --short HEAD`)
- Server runtime: FastAPI + Next.js, CPU-only
- Colab runtime: live external HTTP API via ngrok URL `https://db34-34-124-208-160.ngrok-free.app` (token redacted)
- Env summary: `EXTRACTION_MODE=colab` for live smoke, `VISUALIZATION_MODE=local_cpu`, `ARTIFACT_STORAGE=local`, `TEXT_TO_SQL_AUTH_TOKEN` configured and redacted

## 2. Runtime Split Compliance

| Rule | Pass/Fail | Evidence | Notes |
|---|---|---|---|
| Server without GPU | Pass | `/api/runtime gpu_in_backend=false` | No GPU packages in server requirements. |
| No `torch`/`transformers`/`bitsandbytes` default imports | Pass | `rg` scan over `requirements.txt`, `services`, `contracts`, `apps/web` | No matches. |
| Server does not use OpenAI API | Pass | `rg` scan and requirements | No `openai` dependency or env requirement. |
| Server does not require Superset/MCP | Pass | `rg` scan and new structure | Donor used only as reference. |
| Colab is external HTTP API | Pass | `services/extraction_client/colab_client.py` | Frontend never calls Colab directly. |
| Supports `mock|colab|disabled` | Pass | extraction client factory | Disabled returns structured error. |
| Colab outage handled safely | Pass | `docs/e2e_results/05_colab_unavailable.json` | Error code `colab_unavailable`. |
| Colab Bearer auth | Pass | `tests/unit/test_colab_extraction_client.py` + live smoke | Server sends `Authorization: Bearer <redacted>` when configured. |
| Contracts are Pydantic validated | Pass | `contracts/*`, `tests/unit/test_contracts.py` | Colab response validates as `DataExtractionResponse`. |
| SQL generation only in extraction layer | Pass | Adapter/visualization read SQL context only | Visualization does not generate SQL. |
| Visualization does not generate SQL | Pass | `services/visualization/*` | Rule-based chart/table selection only. |
| No double aggregation of derived SQL outputs | Pass | `docs/e2e_results/live_colab/selected_view.json` | `NumberOfSingers` has no Vega `aggregate`. |

## 3. Endpoint Matrix

| Endpoint | Runtime | Pass/Fail | Evidence |
|---|---|---|---|
| `GET /api/health` | server | Pass | `{"status":"ok","service":"nl2bi-gateway"}` |
| `GET /api/ready` | server | Pass | `{"status":"ready","server_runtime":true,"gpu_in_backend":false}` |
| `GET /api/runtime` | server | Pass | `docs/e2e_results/runtime_mock.json`, `docs/e2e_results/live_colab/runtime.json` |
| `POST /api/nl2chart` | server | Pass | `docs/e2e_results/01_time_series_mock.json` |
| `GET /api/artifacts/{artifact_id}` | server | Pass | Artifacts returned in `/api/nl2chart` response with local URIs. |
| `GET /health` | Colab | Pass | `docs/e2e_results/live_colab/runtime.json` | Health reached through server runtime check. |
| `POST /extract` | Colab | Pass | `docs/e2e_results/live_colab/nl2chart_response.json` | Server→Colab live smoke succeeded. |
| `POST /reload_model` | Colab | Partial | Template no-op endpoint exists | Real reload is Colab-side. |

## 4. Contract Validation

| Contract | Pass/Fail | Notes |
|---|---|---|
| `ErrorItem`, `WarningItem`, `ArtifactRef` | Pass | Pydantic models in `contracts/common.py`. |
| `DataExtractionRequest/Response` | Pass | Used by mock and Colab clients. |
| `VisualizationRequest/Response` | Pass | Adapter creates request; CPU service returns response. |
| `Nl2ChartRequest/Response` | Pass | FastAPI response model validates API output. |

## 5. E2E Scenarios

| Scenario | Mode | Expected | Actual | Pass/Fail | Response file |
|---|---|---|---|---|---|
| Time series | mock | line chart | `success`, `line` | Pass | `docs/e2e_results/01_time_series_mock.json` |
| Category comparison | mock | bar chart | `success`, `bar` | Pass | `docs/e2e_results/02_category_comparison_mock.json` |
| Top-N | mock | table or bar | `success`, `bar` | Pass | `docs/e2e_results/03_top_n_mock.json` |
| Empty result | mock | safe empty result | `failed`, `empty_result` | Pass | `docs/e2e_results/04_empty_result_mock.json` |
| Colab unavailable | colab/broken URL | safe error | `failed`, `colab_unavailable` | Pass | `docs/e2e_results/05_colab_unavailable.json` |
| Live Colab COUNT alias | colab/live URL | bar chart, table artifact, no double aggregation | `success`, `bar`, y.field=`NumberOfSingers`, no y.aggregate | Pass | `docs/e2e_results/live_colab/nl2chart_response.json` |
| Metadata incomplete | mock | fallback + warning | `partial_success`, `metadata_incomplete` warnings | Pass | `docs/e2e_results/06_metadata_incomplete_mock.json` |
| Business mode hides SQL | chat mock | no SQL visible | assistant artifacts `table`, `chart_spec`; no `debug_sql` | Pass | `docs/e2e_results/09_chat_message_artifacts.json` |
| Technical mode can show SQL | server env gated | `DEBUG_SQL_VISIBLE=true` required | Not run in current server env | Partial | By design, disabled in default env. |

## 6. Live Colab Evidence

Live URL: `https://db34-34-124-208-160.ngrok-free.app` (Bearer token redacted).

Smoke command shape:

```bash
SERVER_URL=http://127.0.0.1:8101 \
SMOKE_DATA_SOURCE_ID=demo_concert_singer \
SMOKE_QUERY='Сравни количество певцов по странам' \
python3 scripts/smoke_server_colab.py
```

`/api/runtime` JSON:

```json
{
  "server_runtime": true,
  "gpu_in_backend": false,
  "extraction_mode": "colab",
  "visualization_mode": "local_cpu",
  "artifact_storage": "local",
  "colab_service_url_configured": true,
  "colab_auth_token_configured": true,
  "colab_available": true,
  "colab_health": {
    "model_loaded": true,
    "gpu_name": "NVIDIA L4",
    "mock_model": false
  },
  "server_allows_llm_imports": false,
  "debug_sql_visible": false
}
```

`/api/nl2chart` live response summary:

```json
{
  "request_id": "334784a9633942bab638128d1db20772",
  "status": "success",
  "message": "Построил график по вашему запросу.",
  "selected_view": {
    "type": "chart",
    "chart_type": "bar",
    "spec": {
      "mark": "bar",
      "encoding": {
        "x": {"field": "Country", "type": "nominal", "title": "Country"},
        "y": {"field": "NumberOfSingers", "type": "quantitative", "title": "NumberOfSingers"}
      }
    }
  },
  "artifacts": [
    {"artifact_type": "table", "title": "Таблица результата"},
    {"artifact_type": "chart_spec", "title": "Сравнение по категориям"}
  ],
  "warnings": [],
  "errors": []
}
```

Full files:

- `docs/e2e_results/live_colab/runtime.json`
- `docs/e2e_results/live_colab/nl2chart_response.json`
- `docs/e2e_results/live_colab/selected_view.json`
- `docs/e2e_results/live_colab/artifacts.json`
- `docs/e2e_results/live_colab/summary.json`

COUNT alias check: `selected_view.spec.encoding.y.field == "NumberOfSingers"` and there is no `selected_view.spec.encoding.y.aggregate`. The already aggregated SQL output is not re-aggregated in Vega.

## 7. Interservice Logs by Request ID

- Live Colab smoke request id: `334784a9633942bab638128d1db20772`.
- Live response artifacts: see `docs/e2e_results/live_colab/`.
- Broken Colab smoke request id: see `docs/e2e_results/05_colab_unavailable.json`.
- Server mapped the failed HTTP connection to `colab_unavailable` without stack traces.

## 8. Fallback Behavior

- Mock mode: deterministic fixtures under `demo_data/extraction_fixtures`.
- Disabled mode: `DisabledExtractionClient` returns `extraction_disabled`.
- Colab unavailable: `ColabExtractionClient` returns `colab_unavailable`, retryable.
- Invalid Colab response: tests cover invalid JSON/schema mapping to `invalid_extraction_response`.

## 9. Test Coverage

- Unit/integration: `python3 -m pytest -q` -> `25 passed`.
- Frontend build: `npm run build` -> passed.
- UI smoke: Playwright Chromium register/send/artifact render -> passed.
- Screenshot: `docs/e2e_results/frontend_next16_chat_artifact.png`.
- Audit: `npm audit --omit=dev` -> `found 0 vulnerabilities`.
- Frontend runtime: `next@16.2.6`, `react@19.2.6`, system `node@24.15.0`.
- Server CPU-only scan: `rg '\b(torch|transformers|bitsandbytes)\b' requirements.txt services contracts tests scripts .env.example` -> no matches.
- Live Colab smoke: `python3 scripts/smoke_server_colab.py` against `SERVER_URL=http://127.0.0.1:8101` -> pass.

## 10. Remaining Risks

| Risk | Impact | Owner | Fix |
|---|---|---|---|
| ngrok free-tier URL changes on Colab restart | Server env must be updated for the next live smoke/session | Denis/Colab + server operator | Refresh `TEXT_TO_SQL_SERVICE_URL`; keep token redacted. |
| Node 24 installed under `/usr/local` via `n` | Services launched with a restricted PATH could still find older `/usr/bin/node` | Peter/server | Ensure production service PATH prefers `/usr/local/bin` or install Node 24 through the OS package workflow. |
| Rule-based visualization only | Limited chart selection quality | Peter | Replace/extend B0/B1/B2 rules while keeping CPU-only path. |
| Local artifact storage | Not production durable across hosts | Peter | Add S3/Blob/Postgres-backed artifact store when deployment target is fixed. |

## 11. What To Send To ChatGPT

- This review: `docs/final_integration_review_server_colab.md`.
- Runtime JSON: `docs/e2e_results/runtime_mock.json`, `docs/e2e_results/live_colab/runtime.json`.
- Five `/api/nl2chart` responses: `docs/e2e_results/01_time_series_mock.json`, `02_category_comparison_mock.json`, `03_top_n_mock.json`, `04_empty_result_mock.json`, `05_colab_unavailable.json`.
- Live Colab `/api/nl2chart` response: `docs/e2e_results/live_colab/nl2chart_response.json`.
- Live Colab selected view/artifacts/summary: `docs/e2e_results/live_colab/selected_view.json`, `docs/e2e_results/live_colab/artifacts.json`, `docs/e2e_results/live_colab/summary.json`.
- UI screenshot: `docs/e2e_results/frontend_next16_chat_artifact.png`.
- Test/build output: `pytest 25 passed`; `npm run build` passed; `npm audit --omit=dev` found 0 vulnerabilities.
