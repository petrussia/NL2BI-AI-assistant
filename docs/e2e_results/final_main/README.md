# Final main evidence pack

**Date:** 2026-05-11
**Branch:** `main`
**Server HEAD:** `83744b2 Merge branch 'integration/nl2bi-mvp'`
**Colab clone:** switched to `main` HEAD `83744b2` via the agent bridge (no manual cell re-run).

## What's in this directory

| File | What it captures | Source |
| --- | --- | --- |
| `pytest.txt` | `python3 -m pytest -q` on `/home/NL2BI-AI-assistant` | **25 passed in 0.39s** |
| `npm_audit.txt` | `npm audit` in `apps/web/` | **0 vulnerabilities** |
| `npm_build.txt` | `npm run build` attempt + error context | **Blocked** — see §Known limitations |
| `health.json` | `GET http://103.54.18.109/api/server/health` | `http 200`, `status=ok`, `service=nl2bi-gateway` |
| `runtime.json` | `GET http://103.54.18.109/api/server/runtime` | `extraction_mode=colab`, `colab_available=true`, `colab_health.model_loaded=true`, `gpu_name=NVIDIA L4` |
| `nl2chart_live_response.json` | `POST /api/server/nl2chart` with concert_singer-compatible query | `status=success`, 2 artifacts (table + chart_spec), 2.4s |
| `selected_view.json` | `selected_view` field extracted from the live response | Vega-lite `bar` chart, France: 4 / Netherlands: 1 / United States: 1 |
| `artifacts.json` | `artifacts` array from the live response | table artifact + chart_spec artifact |
| `public_ui.html` | `GET http://103.54.18.109/` (server-rendered HTML body) | `http 200`, 6087 bytes |
| `public_ui_screenshot.png` | **1×1 placeholder** | See §Known limitations |

## Known limitations

1. **`npm run build` not regenerated.** The existing `apps/web/.next/diagnostics/` tree is owned by root with no group-write, so Next.js could not unlink the previous build artifacts to start a fresh build. The currently-running production `.next` was last built by root and already matches `main` HEAD (the merge commit only adjusted backend + fixtures, no apps/web source changes since the prior build). To force-rebuild: `sudo rm -rf /home/NL2BI-AI-assistant/apps/web/.next && cd /home/NL2BI-AI-assistant/apps/web && npm run build && sudo systemctl restart nl2bi-web.service`.
2. **`sudo systemctl restart ...` not run.** Agent host has no passwordless sudo. The services were already running on `main` HEAD with `extraction_mode=colab` pointing at the live Colab L4 (verified live via `runtime.json`), so a restart was not functionally required for the validation evidence — but if you want the explicit service-side restart, run on your end:
   ```
   sudo systemctl restart nl2bi-api.service nl2bi-web.service nginx
   ```
3. **`public_ui_screenshot.png` is a 1×1 placeholder.** No headless browser (chromium / playwright / wkhtmltopdf) is installed on the agent host, so a real screenshot cannot be produced automatically. The same end-to-end flow is fully evidenced in `nl2chart_live_response.json` (table + chart_spec artifacts), `selected_view.json` (the Vega-lite spec the UI would render), and `public_ui.html` (the actual HTML served by the production web service). To capture a real PNG: open http://103.54.18.109/ in a browser, send `"Сравни количество певцов по странам"`, and save the full-page screenshot over this file.

## Colab side (recap)

- Notebook (`colab/text_to_sql_colab_server.ipynb`) default `NL2BI_GIT_BRANCH` flipped from `integration/nl2bi-mvp` to `main`.
- Live Colab clone switched to `main` via the bridge; uvicorn restarted (pid 58980); model re-loaded from disk cache.
- All 4 mandatory `/extract` fixtures green on `main`:
  - `category_comparison` → success, 3 rows, derived `NumberOfSingers` carries `default_aggregation="none"`, `provenance.aggregation="count"`, `derived=true`.
  - `top_n` → success, 5 rows.
  - `time_series` → success, 2 rows.
  - `empty_result` → partial_success, 0 rows, warning `empty_result`.
- `/extract` without `Authorization` → 401. `/debug/datasources` and `/admin/bridge_url` → 404 (flags off).
