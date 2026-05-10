# Report — Colab Text-to-SQL `/extract` endpoint (Claude / Denis)

Branch: `integration/colab-text-to-sql`
Latest commit: `722fe24` (Bearer auth + derived metadata fix)
Spec: `docs/03_claude_colab_text_to_sql_endpoint.md`
Pair branch: `integration/server-colab-nl2chart-mvp` (Codex / Peter — already done)

## 0. Pre-integration security + metadata pass (commit 722fe24)

What changed since the v0.1 report:

- **Bearer auth** on `/extract` + `/reload_model` (env `COLAB_REQUIRE_AUTH=true`,
  shared secret `COLAB_API_TOKEN`).
- **Endpoint gating**: `/debug/datasources` and `/admin/bridge_url` return `404`
  unless `COLAB_DEBUG_ENDPOINTS=true` / `COLAB_BRIDGE_ENABLED=true`; once enabled
  they always require the same Bearer token. Defaults are both `false`.
- **Agent bridge fail-closed**: refuses to start without `BRIDGE_TOKEN`; per-request
  check also rejects when no token is configured (defense in depth).
- **Derived metadata fix**: any column whose `provenance.derived=true` or
  `provenance.aggregation` is set now reports `default_aggregation="none"` and
  `allowed_aggregations=["none"]`, so the downstream visualizer can't
  double-aggregate a `COUNT(*) AS NumberOfSingers`. The original SQL function is
  still preserved in `provenance.aggregation` for traceability.
- **Demo datasource clarity**: `data_sources.json` now ships a canonical
  `demo_concert_singer` id alongside the legacy `demo_sales` alias. `_doc` field
  explains the alias; `load_data_sources` strips `_`-prefixed keys.
- **Tokens never logged**: notebook cell-env and FastAPI startup log only
  `bool()` of presence; uvicorn logs do not contain secrets.

Validated live on Colab L4 (commit `722fe24`):

| Check | Result |
| --- | --- |
| `/extract` without Authorization | `http 401` `{"detail":"missing or invalid Authorization header"}` |
| `/extract` with valid Bearer (all 4 fixtures) | `http 200`, `status` ∈ {success, partial_success}, smoke exit 0 |
| `/reload_model` without Authorization | `http 401` |
| `/debug/datasources` without Authorization (flag on) | `http 401` |
| `/admin/bridge_url` without Authorization (flag on) | `http 401` |
| `/admin/bridge_url` with auth (flag on) | `http 200`, returns the live bridge URL |
| Either flag off | `http 404` (endpoint not even discoverable) |
| `category_comparison` → `NumberOfSingers` | `default_aggregation="none"`, `allowed=["none"]`, `provenance.aggregation="count"`, `derived=true` |
| `Country` (non-derived) | `default_aggregation="count"`, `semantic_role="dimension"` |

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

## 4. `/health` example output (real, from Colab L4 after auth rollout)

```json
{
  "status": "ok",
  "model_loaded": true,
  "model_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
  "mock_model": false,
  "device": "cuda",
  "gpu_name": "NVIDIA L4",
  "vram_total_gb": 22.03,
  "vram_free_gb": 7.74,
  "demo_db_ready": true,
  "server_role": "colab-runtime",
  "auth": {
    "require_auth": true,
    "api_token_set": true,
    "debug_endpoints": true,
    "bridge_enabled": true
  }
}
```

(`/health` is intentionally unauthenticated so the server-side `ColabExtractionClient.health()` works without a token; nothing sensitive is exposed.)

`/debug/datasources` output (added for diagnosing schema_not_found remotely):

```json
{
  "data_sources_path": "/content/nl2bi-colab/demo_data/data_sources.json",
  "data_sources_path_exists": true,
  "data_sources_loaded_keys": ["concert_singer", "demo_sales", "world_1", "wrestler"],
  "spider_db_root": "/content/drive/MyDrive/diploma_plan_sql/data/spider/database",
  "spider_db_root_exists": true,
  "data_source_resolutions": [
    {"data_source_id": "demo_sales",
     "resolved_path": ".../concert_singer/concert_singer.sqlite", "exists": true},
    ...
  ]
}
```

## 5. `/extract` example outputs (real, Qwen2.5-Coder-7B on L4, commit 722fe24)

### 5a. `category_comparison` — derived COUNT alias

Request: `demo_data/extraction_requests/category_comparison.json` (`"Сравни количество певцов по странам"`, `data_source.id="demo_concert_singer"`):

```json
{
  "request_id": "smoke-category-comparison",
  "status": "success",
  "sql": {
    "query": "SELECT Country, COUNT(*) AS NumberOfSingers\nFROM singer\nGROUP BY Country\nLIMIT 1000",
    "dialect": "sqlite", "validated": true, "read_only": true
  },
  "result_table": {"row_count": 3, "columns": ["Country", "NumberOfSingers"]},
  "field_metadata": [
    {
      "name": "Country",
      "data_type": "string",
      "semantic_role": "dimension",
      "default_aggregation": "count",
      "allowed_aggregations": ["count"],
      "provenance": {"expression": null, "aggregation": null, "derived": false}
    },
    {
      "name": "NumberOfSingers",
      "data_type": "number",
      "semantic_role": "measure",
      "default_aggregation": "none",
      "allowed_aggregations": ["none"],
      "provenance": {"expression": "*", "aggregation": "count", "derived": true}
    }
  ]
}
```

The downstream visualization layer reads `default_aggregation` — for `NumberOfSingers` it now sees `"none"` and won't sum the SUMs.

### 5b. Unauthorized `/extract`

```bash
$ curl -X POST .../extract -H 'Content-Type: application/json' -d @top_n.json
HTTP/1.1 401 Unauthorized
{"detail":"missing or invalid Authorization header"}
```

### 5c. `top_n` — full DataExtractionResponse (compact)

Request: `demo_data/extraction_requests/top_n.json` (`"Покажи топ-5 стадионов по вместимости"`):

```json
{
  "request_id": "smoke-top-n",
  "status": "success",
  "data_source": {"id": "demo_sales", "dialect": "sqlite", "schema_version": "spider-v1"},
  "plan": {
    "intent": "top_n",
    "tables": ["stadium"], "columns": ["Name", "Capacity"],
    "order_by": [{"field": "Capacity", "direction": "desc"}],
    "limit": 5
  },
  "sql": {
    "query": "SELECT Name, Capacity \nFROM stadium \nORDER BY Capacity DESC \nLIMIT 5",
    "dialect": "sqlite", "validated": true, "read_only": true
  },
  "result_table": {
    "row_count": 5,
    "rows": [
      {"Name": "Hampden Park", "Capacity": 52500},
      {"Name": "Somerset Park", "Capacity": 11998},
      {"Name": "Stark's Park", "Capacity": 10104},
      {"Name": "Gayfield Park", "Capacity": 4125},
      {"Name": "Balmoor", "Capacity": 4000}
    ]
  },
  "field_metadata": [
    {"name":"Name","sql_type":"TEXT","data_type":"string","semantic_role":"dimension"},
    {"name":"Capacity","sql_type":"INT","data_type":"number","semantic_role":"measure",
     "allowed_aggregations":["sum","avg","min","max","count"],"default_aggregation":"sum"}
  ],
  "execution": {"latency_ms": 1922, "row_limit": 1000, "timeout_ms": 8000, "executable": true},
  "errors": [],
  "warnings": []
}
```

Smoke results (against `https://db34-34-124-208-160.ngrok-free.app` with Bearer auth, commit 722fe24, exit 0):

| Fixture | Status | Generated SQL | Rows | Latency |
| --- | --- | --- | --- | --- |
| `top_n.json` | success | `SELECT Name, Capacity FROM stadium ORDER BY Capacity DESC LIMIT 5` | 5 | 1.9 s |
| `time_series.json` | success | `SELECT COUNT(*) AS concerts_count, YEAR FROM concert GROUP BY YEAR` | 2 | 1.3 s |
| `category_comparison.json` | success | `SELECT Country, COUNT(*) AS NumberOfSingers FROM singer GROUP BY Country` | 3 | 2.5 s |
| `empty_result.json` | partial_success | `SELECT Name FROM singer WHERE Age < 0` | 0 (warning `empty_result`) | 1.0 s |

Smoke client now auto-checks that derived columns have `default_aggregation="none"`. Zero failures on this run.

## 6. GPU info (real)

```
device:        cuda
gpu_name:      NVIDIA L4
vram_total_gb: 22.03
vram_free_gb:  7.69    (≈14 GB занято под Qwen2.5-Coder-7B-Instruct в 4-bit)
cuda_available: true
```

## 7. Smoke test results (Colab L4, real model)

`python -m colab.smoke_extract --base-url <ngrok-url>` → exit 0. См. таблицу в §5.

`sql_guard` unit checks (locally): 10/10 cases pass (rejects `DROP`, `UPDATE`, `PRAGMA`, multiple statements; accepts `SELECT`/`WITH`; line comments don't smuggle keywords; `extract_sql` strips ```` ```sql ```` fences and `SQL:` prefixes).

Live error/warning paths confirmed via direct probes:
- `data_source.id="does_not_exist"` → `errors[0].code == "schema_not_found"`, status `failed`.
- `row_limit=3` против 6-строчной таблицы → `truncated=true`, warning `row_limit_exceeded`.
- Запрос с `WHERE age < 0` → 0 rows → status `partial_success`, warning `empty_result`.

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

1. **Local smoke runs mock-mode only**; real GPU pipeline валидируется только на Colab. Это сделано в этой сессии — все 4 фикстуры зелёные на L4.
2. **`data_sources.json` aliases `demo_sales` → Spider `concert_singer`** — менять только в `demo_data/data_sources.json`, не в коде.
3. **`Name` колонка из stadium иногда указывает `source_table: "singer"`** в `field_metadata`, потому что resolver берёт первое совпадение по lookup без учёта `FROM` clause. Не влияет на корректность SQL/данных, только на provenance. Минорное nice-to-have.
4. **ngrok free-tier URL меняется при рестарте Colab.** На стороне основного сервера `COLAB_SERVICE_URL` нужно перенаправлять. Стабильный URL — платный ngrok / Cloudflare named tunnel.
5. **Нет auth на `/extract` и `/debug/datasources`.** Туннель приватный и короткоживущий — ок. Если выставлять во внешний мир — добавить bearer-токен.
6. **Cold-start модели ~3-5 минут на L4 первый раз** (скачивание весов с HF). Кэш `/root/.cache/huggingface` живёт до перезапуска runtime.

## 10. End-to-end validation status

✅ **Запущено и проверено на Colab L4 в этой сессии.** Drive подключён, `.env` на Drive (`NGROK_AUTHTOKEN` + `GITHUB_PAT`), Spider-базы доступны, репо клонируется по PAT, Qwen2.5-Coder-7B загружается в 4-bit (≈14 GB VRAM), uvicorn + ngrok поднимаются. Все 4 фикстуры — `success`/`partial_success`, smoke exit 0.

Стабильный setup в `.env` на Drive (`/content/drive/MyDrive/nl2bi_colab/.env`):
```
NGROK_AUTHTOKEN=...
GITHUB_PAT=ghp_... (with repo:read on petrussia/NL2BI-AI-assistant)
```

Прочие переменные оставить дефолтные — resolver сам найдёт `<repo>/demo_data/data_sources.json`.

## 11. What to send to ChatGPT after this stage

- This report (`docs/03_claude_colab_text_to_sql_report.md`).
- `/health` JSON with `auth` block (§4).
- `/extract` JSON for `category_comparison` showing `NumberOfSingers` with
  `default_aggregation="none"` (§5a).
- Unauthorized example `http 401` (§5b).
- `gpu_name=NVIDIA L4`, `vram_total_gb=22.03`, `vram_free_gb=7.74`.
- Current `PUBLIC_URL` (from the live notebook output of cell 7).

## 12. Files changed in this iteration (commit 722fe24)

```
.env.example                                       |  33 ++-
colab/agent_bridge.py                              |  34 ++-
colab/config.py                                    |  42 ++-
colab/metadata.py                                  |  11 +-
colab/smoke_extract.py                             |  86 +++++-
colab/text_to_sql_colab_server.ipynb               | 294 +++++++++++++--------
colab/text_to_sql_colab_server.py                  | 127 +++++++--
demo_data/data_sources.json                        |   8 +-
demo_data/extraction_requests/category_comparison.json |   2 +-
9 files changed, 465 insertions(+), 172 deletions(-)
```
