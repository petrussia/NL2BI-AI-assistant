# Bridge Status (local mirror)

Checked at: 2026-04-25 (post-B1 session, smoke10 results captured)

## Endpoint

- URL: `https://participation-writings-organization-papua.trycloudflare.com`
- Persisted at: `tools/.bridge_url`
- Tunnel: cloudflared quick-tunnel (`trycloudflare.com`), free, no auth, no uptime SLA
- Backing server: Flask in Colab kernel main process, started by notebook cell `7f6bca53` (`AGENT_BRIDGE_SETUP`)

## Probes (all passed)

| Probe | Result |
|---|---|
| `GET /health` | `{"ok": true, "pid": 2218}` |
| `POST /exec` (Python) | works; runs in shared globals dict |
| `GET /file?path=…` | works; used to download `diploma_b1_results_*.tar.gz` (32 KB) |
| `GET /ls?path=…` | works; listed Drive `outputs/`, `practice/`, `exports/` |
| Drive write via exec | works; wrote `outputs/logs/_bridge_write_test.txt` |

## Notebook globals access

`tools/remote_scripts/01_bridge_globals_import.py` copies these from `__main__.__dict__` into the bridge exec scope, so we don't reload:

- `model`, `tokenizer` (Qwen2.5-Coder-7B-Instruct on `cuda:0`, 8.2 GB VRAM)
- `PROJECT_ROOT`, `SPIDER_DIR`, `OUTPUTS_DIR`, `PRACTICE_DIR`
- `tables_map`, `db_paths`, `dev`, `smoke10`
- `build_full_schema_prompt_context`, `extract_sql`, `execute_sql`
- `lexical_schema_linking`, `build_reduced_schema_context`, `make_b1_prompt`, `make_prompt`
- `func_timeout`, `FunctionTimedOut`
- `load_spider_dev`, `load_spider_tables`, `load_spider_db_paths`

Run this script once at the start of every session (or whenever state of `_SHARED_GLOBALS` is uncertain). Cost: <1 s.

## Limits

- Tunnel URL changes when the cell is re-run. If the kernel restarts, re-run cell `7f6bca53` and update `tools/.bridge_url`.
- Cloudflare quick-tunnels are best-effort; for long-running pipelines prefer a named tunnel (one-time auth setup).
- Long `/exec` calls block other requests in this single-process Flask. We don't currently parallelise.
