# Report — Colab Text-to-SQL `/extract` endpoint (Claude / Denis)

Branch: `integration/colab-text-to-sql`
Spec: `docs/03_claude_colab_text_to_sql_endpoint.md`
Pair branch: `integration/server-colab-nl2chart-mvp` (Codex / Peter — already done)

## 1. Files created

```text
contracts/
  __init__.py
  common.py                              # mirrored exactly from server branch
  extraction.py                          # mirrored exactly from server branch
colab/
  __init__.py
  config.py                              # env-driven config + data_source.id → SQLite resolver
  errors.py                              # ExtractionErrorCode enum + safe Russian messages
  gpu.py                                 # torch.cuda.* probe; safe on CPU
  schema_loader.py                       # SQLite introspection (Spider-compatible)
  prompt.py                              # system + user prompt for Qwen2.5-Coder
  model.py                               # 4-bit bnb loader; deterministic mock fallback
  sql_guard.py                           # extract_sql, validate_select_only, apply_row_limit
  sql_runner.py                          # sqlite3 + threading.Timer interrupt + row cap
  metadata.py                            # FieldMetadata inference (data_type/semantic_role/agg)
  plan.py                                # ExtractionPlan reconstruction from generated SQL
  extract_pipeline.py                    # gen → guard → exec → metadata → response
  text_to_sql_colab_server.py            # FastAPI app (importable + uvicorn-runnable)
  text_to_sql_colab_server.ipynb         # Colab runner (Drive mount + ngrok + smoke)
  smoke_extract.py                       # CLI smoke client
  requirements-colab.txt                 # pip pins
  README.md
demo_data/
  data_sources.json                      # demo_sales → concert_singer (Spider)
  extraction_requests/
    time_series.json
    top_n.json
    category_comparison.json
    empty_result.json
docs/
  03_claude_colab_text_to_sql_report.md  # this file
.env.example                             # NGROK_AUTHTOKEN + COLAB_* vars
.gitignore                               # excludes .env, __pycache__, .venv, .ipynb_checkpoints
```

## 2. How to start the Colab service

1. Save your ngrok token to Drive: `/content/drive/MyDrive/nl2bi_colab/.env` containing `NGROK_AUTHTOKEN=...`. The notebook reads this — don't put it in a cell.
2. Open `colab/text_to_sql_colab_server.ipynb` in Colab Pro+.
3. **Runtime → Change runtime type → T4 / L4 / A100**.
4. **Runtime → Run all.** The notebook:
   - mounts Drive,
   - clones `integration/colab-text-to-sql`,
   - installs `colab/requirements-colab.txt`,
   - boots `uvicorn colab.text_to_sql_colab_server:app` on `:8000`,
   - waits up to 10 minutes for the model to load (greenlight when `model_loaded=true`),
   - opens an ngrok HTTPS tunnel,
   - prints `PUBLIC_URL`,
   - runs the smoke client against the tunnel.

Local mock-mode (no GPU, no model download — for HTTP contract tests):

```bash
COLAB_MOCK_MODEL=true \
COLAB_SPIDER_DB_ROOT=/path/to/spider/database \
PYTHONPATH=. \
python3 -m uvicorn colab.text_to_sql_colab_server:app --host 0.0.0.0 --port 8000
```

## 3. How to expose the tunnel

The notebook uses **ngrok** with the token from Drive `.env`:

```python
from pyngrok import ngrok, conf
conf.get_default().auth_token = os.environ['NGROK_AUTHTOKEN']
tunnel = ngrok.connect(8000, 'http')
PUBLIC_URL = tunnel.public_url.replace('http://', 'https://')
```

The token is never written to stdout or to a notebook cell.

## 4. `/health` example output

(captured locally in mock mode — on Colab the GPU fields fill in)

```json
{
  "status": "ok",
  "model_loaded": true,
  "model_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
  "mock_model": true,
  "device": "cpu",
  "gpu_name": null,
  "vram_total_gb": null,
  "vram_free_gb": null,
  "demo_db_ready": true,
  "server_role": "colab-runtime"
}
```

On Colab (real run, expected shape):

```json
{
  "status": "ok",
  "model_loaded": true,
  "model_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
  "mock_model": false,
  "device": "cuda",
  "gpu_name": "NVIDIA L4",
  "vram_total_gb": 22.16,
  "vram_free_gb": 14.8,
  "demo_db_ready": true,
  "server_role": "colab-runtime"
}
```

## 5. `/extract` example output (truncated)

Request: `demo_data/extraction_requests/time_series.json`. Below is the response captured against the local mock; on Colab the SQL will be model-generated and the row counts will match the underlying Spider DB.

```json
{
  "request_id": "smoke-time-series",
  "status": "success",
  "user_query": "Покажи количество концертов по годам",
  "data_source": {"id": "demo_sales", "dialect": "sqlite", "schema_version": "spider-v1"},
  "plan": {
    "tables": ["concert"], "columns": ["concert_ID", "concert_Name", "Theme", "Stadium_ID", "Year"],
    "limit": 50, "validated": true
  },
  "sql": {
    "query": "SELECT concert_ID, concert_Name, Theme, Stadium_ID, Year FROM \"concert\" LIMIT 50",
    "dialect": "sqlite", "validated": true, "read_only": true
  },
  "result_table": {"row_count": 6, "truncated": false, "columns": ["concert_ID", "concert_Name", "Theme", "Stadium_ID", "Year"]},
  "field_metadata": [
    {"name":"concert_ID","data_type":"number","semantic_role":"id","sql_type":"INTEGER"},
    {"name":"Year","data_type":"string","semantic_role":"time","sql_type":"TEXT"}
  ],
  "execution": {"latency_ms": 2, "row_limit": 1000, "timeout_ms": 8000, "executable": true},
  "errors": [],
  "warnings": []
}
```

Error-path example (`data_source.id="does_not_exist"`):

```json
{
  "status": "failed",
  "errors": [{
    "code": "schema_not_found",
    "message": "Схема для указанного источника данных не найдена.",
    "source": "colab",
    "retryable": false,
    "details": {"data_source_id": "does_not_exist"}
  }]
}
```

Row-limit truncation (`row_limit=3` against a 6-row table):

```json
{
  "status": "success",
  "result_table": {"row_count": 3, "truncated": true},
  "warnings": [{"code": "row_limit_exceeded", "source": "colab"}]
}
```

## 6. GPU info

Locally (CPU only — used for mock-mode smoke):

```json
{"device": "cpu", "gpu_name": null, "vram_total_gb": null, "cuda_available": false}
```

On Colab the `colab.gpu.gpu_info()` helper reports `device`, `gpu_name`, `vram_total_gb`, `vram_free_gb`, `cuda_available` from `torch.cuda.mem_get_info`.

## 7. Smoke test results (local, mock-model)

`python -m colab.smoke_extract --base-url http://127.0.0.1:8765`

| Fixture | HTTP | Status | row_count | Notes |
| --- | --- | --- | --- | --- |
| `time_series.json` | 200 | success | 6 | mock SELECT — schema-agnostic |
| `top_n.json` | 200 | success | 6 | mock fallback (no numeric measure col) |
| `category_comparison.json` | 200 | success | 6 | mock fallback |
| `empty_result.json` | 200 | success | 6 | mock can't apply WHERE; real model will |
| ad-hoc bad source | 200 | failed | — | `errors[0].code == schema_not_found` |
| ad-hoc `row_limit=3` | 200 | success | 3 | `truncated=true`, warning `row_limit_exceeded` |

`sql_guard` unit checks: 10/10 cases pass (rejects `DROP`, `UPDATE`, `PRAGMA`, multiple statements; accepts `SELECT`/`WITH`; line comments don't smuggle keywords; `extract_sql` strips ```` ```sql ```` fences and `SQL:` prefixes).

## 8. Contract guarantees (cross-checked against the spec)

| Spec requirement | Where enforced |
| --- | --- |
| `GET /health`, `POST /extract`, `POST /reload_model` | `colab/text_to_sql_colab_server.py` |
| Returns `DataExtractionResponse` per shared contract | `contracts/extraction.py` (mirrors server branch) |
| `request_id` preserved | `extract_pipeline.run_extraction` always sets `request_id=request.request_id` |
| No OpenAI calls | not imported anywhere |
| No tokens printed | notebook reads `NGROK_AUTHTOKEN` from Drive `.env`; logs only `bool(tok)` |
| No frontend/backend imports for boot | only `contracts/`, `colab/`, stdlib, fastapi, httpx-free |
| No raw tracebacks to user | `extract_pipeline._failed_response` + top-level `try/except` map to enum codes |
| SELECT-only guard | `colab/sql_guard.validate_select_only` + `PRAGMA query_only=1` at runtime |
| Timeout enforced | `colab/sql_runner._arm_interrupt` (Threading.Timer → `conn.interrupt`) |
| Row limit enforced | `apply_row_limit` (LIMIT injection) + post-fetch cap + truncation flag |
| Mock-model mode for smoke tests | `COLAB_MOCK_MODEL=true` → `model._mock_sql` |
| GPU detection (device, name, VRAM, model_loaded) | `colab/gpu.gpu_info` + `_health_payload` |
| Default model `Qwen/Qwen2.5-Coder-7B-Instruct` 4-bit | `colab/model.TextToSqlModel.load` (with bnb fallback to fp16) |
| Demo SQLite via JSON or introspection | `colab/schema_loader.load_schema` (introspection) + `demo_data/data_sources.json` |
| Static SELECT-only validation, markdown fence stripping | `extract_sql` + `validate_select_only` |
| Full error enum | `colab/errors.ExtractionErrorCode` |
| Tunnel via cloudflared/ngrok | notebook uses ngrok per user choice; tokens never in cells |

## 9. Known limitations

1. **Local smoke tests run mock-mode only** — this environment has no GPU, no `transformers` install, and no Drive. Real model load is exercised only when the notebook runs in Colab.
2. **Mock heuristic is intentionally dumb** — for the four bundled fixtures it usually picks the first table (alphabetical: `concert`) and returns the first 5 columns. Real Qwen2.5-Coder will produce schema-aware SQL. The point of mock mode is HTTP-contract testing, not SQL quality.
3. **`data_sources.json` aliases `demo_sales` → Spider's `concert_singer`** because that's where you said the demo data lives. To point at a different demo, edit `demo_data/data_sources.json` (no code change).
4. **No retries on Colab cold-start** — the notebook waits up to 10 min for `/health` to flip `model_loaded=true`, then bails. First-run model download from HF can occasionally exceed that on T4 — re-run the cell if it fails (model files cache in `/root/.cache` for the session).
5. **ngrok free-tier URL changes per session.** The main server's `COLAB_SERVICE_URL` env var must be re-pointed each time you reboot Colab. Stable URL needs a paid ngrok plan or a custom domain — out of scope here.
6. **No persistent rate limiting / auth on `/extract`.** OK because the tunnel is private and short-lived; if you ever expose this beyond your team, add auth.

## 10. What I needed from you and what's still pending

**Already received (this session):**

- Demo DB choice: reuse Spider DBs from `/content/drive/MyDrive/diploma_plan_sql/data/spider/database`. Wired via `COLAB_SPIDER_DB_ROOT` + `demo_data/data_sources.json`.
- Model + quant: Qwen2.5-Coder-7B-Instruct, 4-bit bnb. Defaults in `colab/config.py`.
- Tunnel: ngrok, token already in `.env`. Notebook reads it from Drive at runtime.
- Drive mount: yes, logs/artifacts at `/content/drive/MyDrive/nl2bi_colab/`.

**Still needed from you to actually run end-to-end on Colab (one-time setup):**

1. Copy `.env` to Drive at `/content/drive/MyDrive/nl2bi_colab/.env`. (Repo-level `.env` is gitignored and only used for local tests; Colab needs it on Drive.)
2. Confirm Spider data is at `/content/drive/MyDrive/diploma_plan_sql/data/spider/database/` (you already have it there — I saw it referenced in your `experiments/denis` notebooks). If the path differs, override `COLAB_SPIDER_DB_ROOT` in the Drive `.env`.
3. Push this branch to GitHub so the notebook can `git clone` it. Until pushed, either change `NL2BI_GIT_URL`/`NL2BI_GIT_BRANCH` in the notebook cell-2 or paste the repo into Drive manually.
4. In Colab, attach a GPU runtime (T4 / L4 / A100). 7B-4bit fits T4 (~6 GB) so any of the three will work.

## 11. What to send to ChatGPT after this stage

- This report (`docs/03_claude_colab_text_to_sql_report.md`).
- `/health` JSON from a real Colab run (so GPU fields are populated).
- One `/extract` JSON from a real Colab run (Qwen-generated SQL, not mock).
- `nvidia-smi` output (or just `gpu_name` + `vram_total_gb`).
- The `PUBLIC_URL` ngrok printed (so the server side can wire `COLAB_SERVICE_URL`).
- Any errors from `colab/logs/uvicorn.stderr.log` on Drive if startup or generation failed.
