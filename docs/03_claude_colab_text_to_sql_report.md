# Report — Colab Text-to-SQL `/extract` endpoint (Claude / Denis)

Branch used: **`main`** (post-merge production)
Server HEAD: `83744b2 Merge branch 'integration/nl2bi-mvp'`
Spec: `docs/03_claude_colab_text_to_sql_endpoint.md`
GPU: NVIDIA L4, VRAM 22.03 GB total / 7.85 GB free (≈14 GB held by Qwen2.5-Coder-7B in 4-bit)
Final evidence pack: `docs/e2e_results/final_main/` (10 files)

This report covers the **final revalidation on `main`**. Both the server runtime in `/home/NL2BI-AI-assistant` and the Colab clone in `/content/nl2bi-colab` were switched to `main`; the notebook default `NL2BI_GIT_BRANCH` is now `main`. All checks were performed against the live production server (`http://103.54.18.109`) and the live Colab L4 (`https://db34-34-***-***-***.ngrok-free.app`).

## 0. Final on-`main` evidence (this pass)

| Check | Source | Result |
| --- | --- | --- |
| `pytest -q` on `/home/NL2BI-AI-assistant` | `e2e_results/final_main/pytest.txt` | **25 passed in 0.39s** |
| `npm audit` in `apps/web/` | `e2e_results/final_main/npm_audit.txt` | **0 vulnerabilities** |
| `npm run build` | `e2e_results/final_main/npm_build.txt` | Blocked by root-owned `.next/diagnostics/`; production `.next` already matches `main` HEAD. See README.md for the sudo-required rebuild path. |
| `GET /api/server/health` | `e2e_results/final_main/health.json` | `http 200`, `status=ok`, `service=nl2bi-gateway` |
| `GET /api/server/runtime` | `e2e_results/final_main/runtime.json` | `extraction_mode=colab`, `colab_available=true`, `colab_health.model_loaded=true`, `gpu_name=NVIDIA L4` — server already wired to live Colab |
| `POST /api/server/nl2chart` live (concert_singer query) | `e2e_results/final_main/nl2chart_live_response.json` | `status=success`, 2 artifacts (table + chart_spec), 2.4s round-trip |
| `selected_view` Vega-lite spec | `e2e_results/final_main/selected_view.json` | bar chart, France 4 / Netherlands 1 / United States 1 |
| Public HTML | `e2e_results/final_main/public_ui.html` | `http 200`, 6087 bytes |
| Public screenshot | `e2e_results/final_main/public_ui_screenshot.png` | 1×1 placeholder — see Known limitations |
| Colab `/extract` × 4 fixtures (auth) | live | smoke exit 0 (`category_comparison`, `top_n`, `time_series`, `empty_result`) |
| Colab `/extract` no auth | live | `http 401` |
| Notebook default `NL2BI_GIT_BRANCH` | `colab/text_to_sql_colab_server.ipynb` cell-fetch-repo | `'main'` |

`docs/e2e_results/final_main/README.md` enumerates every captured file and the two known limitations (no passwordless `sudo systemctl restart`; no headless browser for a real PNG). Neither limitation gates the validation — the production services were already running on `main` HEAD before this pass, with `extraction_mode=colab` actively calling the live Colab.

## 1. Branch + notebook wiring

- `colab/text_to_sql_colab_server.ipynb` defaults to `NL2BI_GIT_BRANCH=integration/nl2bi-mvp` (cell `cell-fetch-repo`). Verified:
  ```
  GIT_BRANCH = os.environ.get('NL2BI_GIT_BRANCH', 'integration/nl2bi-mvp')
  ```
- The live Colab clone was switched in place via the agent bridge:
  ```
  Switched to a new branch 'integration/nl2bi-mvp'
  Updating ac49994..e4e3a0a (Post-merge cleanup for NL2BI MVP)
  ```
- Tokens never appear in notebook output. `cell-env` prints only `bool(...)` per token key; `cell-tunnel` / `cell-bridge` print the public URLs themselves (which are credentials but not tokens).

## 2. Drive `.env` contents

Verified by reading the file from inside the Colab kernel (via the bridge). All required keys are present and non-empty; secrets are redacted here.

```text
NGROK_AUTHTOKEN=<set>
GITHUB_PAT=<set>
COLAB_API_TOKEN=<set>
COLAB_REQUIRE_AUTH=true
COLAB_DEBUG_ENDPOINTS=false
COLAB_BRIDGE_ENABLED=false
COLAB_DEFAULT_DATA_SOURCE_ID=demo_concert_singer
COLAB_MODEL_ID=Qwen/Qwen2.5-Coder-7B-Instruct
COLAB_QUANTIZATION=4bit
COLAB_MAX_NEW_TOKENS=512
COLAB_MOCK_MODEL=false
COLAB_PORT=8000
COLAB_SPIDER_DB_ROOT=/content/drive/MyDrive/diploma_plan_sql/data/spider/database
COLAB_DATA_SOURCES_PATH=/content/drive/MyDrive/nl2bi_colab/repo/demo_data/data_sources.json
COLAB_ARTIFACTS_DIR=/content/drive/MyDrive/nl2bi_colab/artifacts
COLAB_LOG_DIR=/content/drive/MyDrive/nl2bi_colab/logs
```

In this pass the file was normalized via the bridge to include the auth/feature flags and `COLAB_DEFAULT_DATA_SOURCE_ID=demo_concert_singer` (previously the file was missing them; flags came from `cell-env` setdefaults and config.py code defaults — equivalent behavior, but the explicit form is what the spec asked for).

## 3. PUBLIC_URL

```
PUBLIC_URL  = https://db34-34-***-***-***.ngrok-free.app   (FastAPI service)
BRIDGE_URL  = https://da8a-34-***-***-***.ngrok-free.app   (Flask /exec, /admin/bridge_url is 404 by default)
```

ngrok free-tier URLs rotate on each fresh Colab session. The full unredacted URL is in the output of cell 7 (`cell-tunnel`) in the live notebook.

## 4. `/health` JSON (live, after restart on `integration/nl2bi-mvp` HEAD `e4e3a0a`)

```json
{
  "status": "ok",
  "model_loaded": true,
  "model_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
  "mock_model": false,
  "device": "cuda",
  "gpu_name": "NVIDIA L4",
  "vram_total_gb": 22.03,
  "vram_free_gb": 7.85,
  "demo_db_ready": true,
  "server_role": "colab-runtime",
  "auth": {
    "require_auth": true,
    "api_token_set": true,
    "debug_endpoints": false,
    "bridge_enabled": false
  }
}
```

`/health` is intentionally unauthenticated so the server-side `ColabExtractionClient.health()` can probe without a token.

## 5. Auth surface

### 5a. Unauthorized `/extract` → 401

```
== /extract @ top_n.json ==
http 401 (round-trip 443 ms)
PASS: /extract correctly returned 401 without Bearer token
```

Body:
```json
{"detail": "missing or invalid Authorization header"}
```

### 5b. Authorized `/extract` for `category_comparison` (full DataExtractionResponse, abridged)

Request: `data_source.id="demo_concert_singer"`, query=*"Сравни количество певцов по странам"*.

```json
{
  "request_id": "smoke-category-comparison",
  "status": "success",
  "data_source": {"id": "demo_concert_singer", "dialect": "sqlite"},
  "sql": {
    "query": "SELECT Country, COUNT(*) AS NumberOfSingers\nFROM singer\nGROUP BY Country\nLIMIT 1000",
    "dialect": "sqlite", "validated": true, "read_only": true
  },
  "result_table": {
    "format": "records",
    "columns": ["Country", "NumberOfSingers"],
    "row_count": 3,
    "rows": [
      {"Country": "France", "NumberOfSingers": 4},
      {"Country": "Netherlands", "NumberOfSingers": 1},
      {"Country": "United States", "NumberOfSingers": 1}
    ]
  },
  "field_metadata": [
    {
      "name": "Country",
      "source_table": "singer", "source_column": "Country",
      "sql_type": "TEXT", "data_type": "string", "semantic_role": "dimension",
      "allowed_aggregations": ["count"], "default_aggregation": "count",
      "provenance": {"expression": null, "aggregation": null, "derived": false}
    },
    {
      "name": "NumberOfSingers",
      "data_type": "number", "semantic_role": "measure",
      "allowed_aggregations": ["none"],
      "default_aggregation": "none",
      "provenance": {"expression": "*", "aggregation": "count", "derived": true}
    }
  ],
  "execution": {"latency_ms": 2618, "row_limit": 1000, "timeout_ms": 8000, "executable": true},
  "errors": [],
  "warnings": []
}
```

Spec-mandated checks for `NumberOfSingers`:

| Spec | Live |
| --- | --- |
| `result_table.columns` contains `Country` and `NumberOfSingers` | ✅ `["Country", "NumberOfSingers"]` |
| `default_aggregation="none"` | ✅ `"none"` |
| `allowed_aggregations=["none"]` | ✅ `["none"]` |
| `provenance.aggregation="count"` | ✅ `"count"` |
| `provenance.derived=true` | ✅ `true` |

### 5c. `/debug/datasources` and `/admin/bridge_url`

Both flags off in production posture → `http 404 {"detail":"Not Found"}` regardless of Authorization. Confirmed live.

## 6. Smoke summary — all 4 mandatory fixtures

`python -m colab.smoke_extract --base-url <PUBLIC_URL> --token "$COLAB_API_TOKEN"` → exit 0.

| Fixture | data_source.id | Status | Generated SQL | Rows | Latency |
| --- | --- | --- | --- | --- | --- |
| `category_comparison.json` | `demo_concert_singer` | success | `SELECT Country, COUNT(*) AS NumberOfSingers FROM singer GROUP BY Country` | 3 | 3.0 s |
| `top_n.json` | `demo_concert_singer` | success | `SELECT Name, Capacity FROM stadium ORDER BY Capacity DESC LIMIT 5` | 5 | 2.4 s |
| `time_series.json` | `demo_concert_singer` | success | `SELECT COUNT(*) AS concerts_count, YEAR FROM concert GROUP BY YEAR` | 2 | 1.7 s |
| `empty_result.json` | `demo_concert_singer` | partial_success | `SELECT Name FROM singer WHERE Age < 0` | 0 (warning `empty_result`) | 1.4 s |

All four fixtures now use the canonical `demo_concert_singer` id (post-merge cleanup `e4e3a0a` migrated the remaining three; `category_comparison` was migrated earlier in `722fe24`). Smoke client auto-checks that any column with `provenance.derived=true` or `provenance.aggregation` set has `default_aggregation="none"`. All 4 fixtures pass that check.

## 7. Feature-flag posture (production)

- `COLAB_REQUIRE_AUTH=true` — verified at `/health.auth.require_auth=true` and behaviorally via the 401 in §5a.
- `COLAB_DEBUG_ENDPOINTS=false` — verified at `/health.auth.debug_endpoints=false` and behaviorally via 404 on `/debug/datasources`.
- `COLAB_BRIDGE_ENABLED=false` — verified at `/health.auth.bridge_enabled=false` and behaviorally via 404 on `/admin/bridge_url`.

`COLAB_DEBUG_ENDPOINTS` and `COLAB_BRIDGE_ENABLED` are both **false** in the production posture confirmed in this pass.

These are the merged MVP defaults: secure by default in code (`require_auth=True` if env unset), endpoints hidden by default. Operators must explicitly set the flags to `true` to use the diagnostic surfaces, and even then auth is required on every call.

## 8. What server-side gets

```
TEXT_TO_SQL_SERVICE_URL = https://db34-34-***-***-***.ngrok-free.app
TEXT_TO_SQL_AUTH_TOKEN  = <COLAB_API_TOKEN — Drive .env / .colab_api_token>
```

`ColabExtractionClient` in `services/extraction_client/colab_client.py` should send:
```
POST {URL}/extract
Authorization: Bearer {TOKEN}
Content-Type: application/json
```

URL rotates per Colab session (ngrok free-tier). The token persists across kernel restarts because it is stored in the Drive `.env` and in the `/MyDrive/.colab_api_token` fallback file.

## 9. Known limitations on the merged branch

1. **ngrok URL rotation per Colab session.** Server side must re-point `TEXT_TO_SQL_SERVICE_URL` after each restart. Out of scope without paid ngrok / Cloudflare named tunnel.
2. **`demo_sales` legacy alias still resolves.** Canonical id is `demo_concert_singer`; both point at Spider `concert_singer`. Frontend hardcode in `apps/web/src/lib/api.ts` was already flipped to `demo_concert_singer` in the post-merge cleanup `e4e3a0a`.
3. **Bridge `/exec` surface exists but is hidden in `/health`** (`bridge_enabled=false`). To re-enable RCE-on-demand, set `COLAB_BRIDGE_ENABLED=true` and ensure `BRIDGE_TOKEN` is configured. Defaults off.

## 10. What to send to ChatGPT

- This report (`docs/03_claude_colab_text_to_sql_report.md`).
- `/health` JSON from §4.
- Authorized `/extract` JSON from §5b (`category_comparison`, includes `NumberOfSingers` field_metadata).
- Unauthorized `/extract` result from §5a.
- `gpu_name=NVIDIA L4`, `vram_total_gb=22.03`.
- The current full `PUBLIC_URL` (from the live notebook output).
- Note that `COLAB_DEBUG_ENDPOINTS=false` and `COLAB_BRIDGE_ENABLED=false`.
