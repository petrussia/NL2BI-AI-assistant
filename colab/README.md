# Colab Text-to-SQL `/extract` service

External GPU inference service for NL2BI. Boots a FastAPI app on Google Colab Pro+, exposes `GET /health`, `POST /extract`, `POST /reload_model`, and tunnels through ngrok so the main server can call it over HTTPS.

## Files

| Path | Purpose |
| --- | --- |
| `text_to_sql_colab_server.py` | FastAPI app (`uvicorn colab.text_to_sql_colab_server:app`) |
| `text_to_sql_colab_server.ipynb` | One-click runner (mount Drive → install → load → tunnel → smoke) |
| `config.py` | Env-driven config (model id, mock flag, Spider DB root, log dirs) |
| `gpu.py` | GPU/VRAM detection |
| `schema_loader.py` | SQLite schema introspection (Spider-compatible) |
| `prompt.py` | Chat prompt for Qwen2.5-Coder |
| `model.py` | Qwen2.5-Coder loader (4-bit bnb) + mock fallback |
| `sql_guard.py` | Markdown stripping, SELECT-only validation, row-limit injection |
| `sql_runner.py` | SQLite execution with timeout (`conn.interrupt`) and row cap |
| `metadata.py` | Field metadata inference (data_type, semantic_role, aggregations) |
| `plan.py` | `ExtractionPlan` reconstruction from generated SQL |
| `extract_pipeline.py` | Orchestrator (gen → guard → exec → metadata → response) |
| `errors.py` | Error code enum + safe user messages |
| `smoke_extract.py` | Smoke client for `/health` + `/extract` |
| `requirements-colab.txt` | Pip deps for Colab |

## Run on Colab (recommended)

1. Open `colab/text_to_sql_colab_server.ipynb` in Colab Pro+.
2. Choose a GPU runtime: **Runtime → Change runtime type → T4 / L4 / A100**.
3. **Runtime → Run all.** The notebook:
   - mounts Drive,
   - clones `integration/colab-text-to-sql`,
   - installs `requirements-colab.txt`,
   - loads `Qwen2.5-Coder-7B-Instruct` in 4-bit,
   - starts uvicorn on `:8000`,
   - opens an ngrok HTTPS tunnel,
   - prints the public URL,
   - runs the smoke client against the tunnel.
4. Hand the printed `PUBLIC_URL` to the main server (`COLAB_SERVICE_URL`).

`NGROK_AUTHTOKEN` is read from `/content/drive/MyDrive/nl2bi_colab/.env` — never paste it into a cell.

## Run locally in mock mode (no GPU)

For HTTP contract testing without downloading the model:

```bash
COLAB_MOCK_MODEL=true \
COLAB_SPIDER_DB_ROOT=/path/to/spider/database \
uvicorn colab.text_to_sql_colab_server:app --host 0.0.0.0 --port 8000
```

Then:

```bash
curl http://127.0.0.1:8000/health
python -m colab.smoke_extract --base-url http://127.0.0.1:8000
```

## Hard guarantees (matches `03_claude_colab_text_to_sql_endpoint.md`)

- No OpenAI calls.
- Tokens never printed; ngrok auth read from Drive `.env`.
- Server is independent of the main backend; nothing in `services/` is imported.
- `extract` never returns raw tracebacks — errors are mapped to a fixed enum (`colab/errors.py`).
- Generated SQL goes through `validate_select_only` (rejects multiple statements, `INSERT/UPDATE/DELETE/DROP/ATTACH/PRAGMA/...`).
- `timeout_ms` enforced via `sqlite3.Connection.interrupt`.
- `row_limit` enforced via SQL `LIMIT` injection + post-fetch cap.
- `COLAB_MOCK_MODEL=true` runs the full HTTP path with a deterministic SQL stub.

## Config knobs (env)

| Var | Default | Notes |
| --- | --- | --- |
| `COLAB_MODEL_ID` | `Qwen/Qwen2.5-Coder-7B-Instruct` | HF id |
| `COLAB_QUANTIZATION` | `4bit` | falls back to fp16 if bnb missing |
| `COLAB_MAX_NEW_TOKENS` | `512` | greedy decode |
| `COLAB_MOCK_MODEL` | `false` | `true` to skip model load |
| `COLAB_PORT` | `8000` | uvicorn port |
| `COLAB_SPIDER_DB_ROOT` | `/content/drive/MyDrive/diploma_plan_sql/data/spider/database` | Spider DBs |
| `COLAB_DATA_SOURCES_PATH` | `<repo>/demo_data/data_sources.json` | id → db mapping |
| `COLAB_DEFAULT_DATA_SOURCE_ID` | `demo_sales` | aliased to `concert_singer` in the bundled mapping |
| `COLAB_ARTIFACTS_DIR` / `COLAB_LOG_DIR` | `/content/drive/MyDrive/nl2bi_colab/{artifacts,logs}` | persisted on Drive |
| `NGROK_AUTHTOKEN` | (required for tunnel) | read from Drive `.env` |
