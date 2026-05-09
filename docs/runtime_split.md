# Runtime Split — Server + Colab

## Server Runtime

Server runs the production-like application on CPU only:

- `apps/web`: Next.js chat UI.
- `services/gateway`: FastAPI API, auth, chat persistence, runtime endpoints.
- `services/orchestrator`: `/api/nl2chart` orchestration.
- `services/extraction_client`: mock, disabled, and Colab HTTP clients.
- `services/adapter`: extraction-to-visualization contract adapter.
- `services/visualization`: deterministic CPU visualization rules.
- `services/artifacts`: local JSON artifact storage.
- `contracts`: Pydantic contracts shared by server and Colab template.

Server default mode is:

```env
EXTRACTION_MODE=mock
VISUALIZATION_MODE=local_cpu
ARTIFACT_STORAGE=local
```

The server requirements intentionally do not include GPU or LLM runtime
packages such as `torch`, `transformers`, `bitsandbytes`, `openai`,
`langchain-openai`, or `mcp-use`.

## Colab Runtime

Colab is an external HTTP inference API. The server talks to Colab only through:

```text
GET  /health
POST /extract
POST /reload_model
```

The frontend never calls the Colab tunnel directly. In `EXTRACTION_MODE=colab`,
the server `ColabExtractionClient` posts a `DataExtractionRequest` to
`TEXT_TO_SQL_SERVICE_URL/extract` and validates the response as
`DataExtractionResponse`.

## Fallback Modes

| Mode | Behavior |
|---|---|
| `mock` | Reads deterministic demo fixtures from `demo_data/extraction_fixtures`. |
| `colab` | Calls external Colab `/extract` over HTTP and maps network/schema errors to safe errors. |
| `disabled` | Returns a structured `extraction_disabled` error. |

