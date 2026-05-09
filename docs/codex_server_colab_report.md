# Codex Report — Server + Colab NL2BI MVP

## Scope Completed

- Created the server-runtime repository structure requested by `00_README_START_HERE.md`.
- Implemented FastAPI backend without Superset, MCP, OpenAI, or GPU imports.
- Implemented Pydantic contracts for extraction, visualization, and `/api/nl2chart`.
- Implemented mock extraction fixtures, adapter, CPU visualization rules, artifact storage, Colab HTTP client, auth/chat persistence, and a Next.js chat UI.
- Added a Colab service contract template, smoke scripts, docs, and tests.

## Donor Reuse

The donor `/home/superset_ai` was used as an architectural reference for:

- FastAPI router shape.
- Cookie-based auth/register/login flow.
- SQLite-backed chat sessions and message persistence.
- Message artifacts attached to assistant responses.

No Superset runtime, MCP clients, OpenAI/LangChain agent, or Superset pages were copied into the default server path.

## Disabled/Removed From Server Runtime

- Superset routes/pages: preview, recommend, share, scan.
- Superset API/runtime assumptions and `SUPERSET_*` env requirements.
- MCP runtime and `mcp-use`.
- OpenAI/LangChain runtime and `OPENAI_API_KEY` requirements.
- GPU/LLM packages: `torch`, `transformers`, `bitsandbytes`, `accelerate`.

## Verification

```text
python3 -m pytest -q
19 passed in 0.39s
```

```text
cd apps/web && npm run build
Next.js 14.2.35 build compiled successfully.
```

```json
{"status":"ok","service":"nl2bi-gateway"}
```

```json
{
  "server_runtime": true,
  "gpu_in_backend": false,
  "extraction_mode": "mock",
  "visualization_mode": "local_cpu",
  "artifact_storage": "local",
  "colab_service_url_configured": false,
  "server_allows_llm_imports": false,
  "debug_sql_visible": false
}
```

## Evidence Files

- Mock runtime: `docs/e2e_results/runtime_mock.json`
- Mock time series: `docs/e2e_results/01_time_series_mock.json`
- Mock category comparison: `docs/e2e_results/02_category_comparison_mock.json`
- Mock top-N: `docs/e2e_results/03_top_n_mock.json`
- Mock empty result: `docs/e2e_results/04_empty_result_mock.json`
- Colab unavailable: `docs/e2e_results/05_colab_unavailable.json`
- Metadata incomplete: `docs/e2e_results/06_metadata_incomplete_mock.json`
- Chat artifact smoke: `docs/e2e_results/09_chat_message_artifacts.json`
- UI screenshot: `docs/e2e_results/frontend_chat_artifact.png`

## Known Issues

- Real Colab GPU endpoint was not available on this server, so real Colab `/health` and `/extract` remain external/manual.
- `npm audit --omit=dev` reports current Next/PostCSS advisories. The suggested automatic fix installs Next 16.2.6, which requires Node >=20.9.0; this server has Node 18.19.1. Functional build is green on Next 14.2.35.

