# Spider2 FULL diagnostic — STAGE 0 state audit

_Generated: 2026-05-10 | branch: `experiments/denis` | HEAD `1ba0b8f` (Phase 22)_

> Pre-flight check before launching FULL 547 / 547 / 68 diagnostic runs across
> Spider2-Lite, Spider2-Snow, Spider2-DBT. Strict policy: **no benchmark mixing,
> no FULL claim on diagnostic runs, no oracle in official scores, no push.**

---

## 1. Git

| field | value |
|---|---|
| Branch | `experiments/denis` |
| HEAD | `1ba0b8f` (Phase 22 STAGE A1+A2+A3 — pack-thinness fix + Family C) |
| User-pushed | confirmed by user; matches local |
| Working-tree dirty | yes — Phase 22 left modified files (not relevant to Phase 23 runs) |

## 2. Bridge / Colab kernel

| field | value |
|---|---|
| URL file | `tools/.bridge_url` |
| URL | `https://corpus-vatican-technical-pennsylvania.trycloudflare.com` |
| `/health` | OK; pid 3960 |
| Tunnel type | Cloudflare quick-tunnel (free, no SLA — may rotate if kernel restarts) |

## 3. GPU / models

| field | value |
|---|---|
| GPU | NVIDIA A100-SXM4-80GB |
| VRAM in use | 79.5 / 80 GB (alloc 71.1 GB; reserved 77.2 GB) |
| Planner | `Qwen/Qwen3-Coder-30B-A3B-Instruct` (loaded) |
| Direct emitter | `Qwen/Qwen2.5-Coder-7B-Instruct` (loaded) |
| `_V18_MODELS_READY` | `True` |

## 4. Datasets

| dataset | path | rows |
|---|---|---:|
| Spider2-Lite | `external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl` | **547** |
| Spider2-Snow | `external_benchmarks/spider2_snow/raw/Spider2/spider2-snow/spider2-snow.jsonl` | **547** |
| Spider2-DBT | local `data/spider2_dbt/tasks/` | **68** (all task dirs present) |

## 5. Live catalogs

| catalog | path | rows | size |
|---|---|---:|---:|
| BigQuery | `outputs/cache/spider2_bq_live_catalog_v18.jsonl` | 428,424 | 130 MB |
| Snowflake | `outputs/cache/spider2_snow_live_catalog_v18.jsonl` | 586,472 | 156 MB |

## 6. Engine auth

| engine | status | detail |
|---|---|---|
| BigQuery | ✅ OK | project `project-0e0fc8a5-27b1-4e00-912`, dry_run probe returned `total_bytes_processed=0` |
| Snowflake | ❌ **BLOCKED** | `SNOWFLAKE_USER` / `SNOWFLAKE_ACCOUNT` not set on bridge kernel; connector raises `AttributeError: 'NoneType' object has no attribute 'find'` |

**Implication for Snow FULL.** Without Snow connector creds, `execute_ok` and
`explain_ok` cannot be measured engine-side. The diagnostic still produces
`schema_valid` (AST-checked against live catalog of 586,472 columns) and
`parse_ok` (sqlglot Snowflake dialect). This is recorded as STAGE 2 partial.

## 7. DBT remote server

| field | value |
|---|---|
| Host | `denis@103.54.18.91` (`petrthefirst24.fvds.ru`, Ubuntu 6.8) |
| dbt binary | `/home/denis/dbt/.venv/bin/dbt` |
| Disk free | OK |
| Tasks on remote | absent — DBT tasks dir lives **locally** under `data/spider2_dbt/tasks/` (68 task dirs all present) |
| Existing inference helper | `tools/remote_scripts/_run_dbt_inference.py` (per-task; uses bridge for Coder-30B planner) |

## 8. v18 evaluation modules (current harness)

```
candidate_selector_v18.py
schema_linking_v18.py
schema_pack_builder_v18.py
spider2_candidate_factory_v18.py
sql_renderer_v18.py
structured_plan_v18.py
```

All present on Drive at `repo/src/evaluation/`.

## 9. Existing run inventory (sanity)

Latest runs on Drive `outputs/spider2_lite/runs/`:

```
lite_bq_v17_qwen3coder30b_bf16_pilot10
lite_bq_v18_1_pilot10
lite_bq_v18_1b_pilot10
lite_bq_v18_1b_pilot50
lite_bq_v18_pilot10
lite_bq_v20_pilot10
lite_bq_v20a_pilot10
lite_bq_v20a_pilot50_b
lite_bq_v21_pilot10
lite_bq_v21_pilot50
lite_bq_v22_pilot10
lite_bq_v22_pilot50
```

Latest Snow runs: `snow_v10..v17_*_pilot10`. **No FULL Snow run exists.**

## 10. Disk / cost / risk

| field | value |
|---|---|
| Drive free | 121 GB |
| BQ cost risk | dry_run (`use_query_cache=False`) — 0 bytes scanned per task; cost ~$0 |
| Snow cost risk | not applicable until auth resolved |
| DBT cost risk | local container builds; no cloud spend |
| Wall-time est. | Lite/BQ FULL 547 ≈ 10–12 h (pilot50 ran ~60 min); DBT 68 ≈ 2–4 h |

---

## 11. Decision matrix for Phase 23 launches

| stage | run | launch decision |
|---|---|---|
| 1a | Lite/BQ FULL 547 BG | **GO** — full v22 stack, BQ dry_run on |
| 1b | Lite/Snow FULL 547 BG | **GO partial** — `no_execute=True`; produces schema_valid + parse_ok (no engine-side execute_ok) |
| 1c | Lite/SQLite | **breakdown only** — declared non-comparable per benchmark policy; no run |
| 2 | Spider2-Snow FULL 547 | same as 1b but on snow-547 task list (Spider2-Snow benchmark is a distinct list from Lite-Snow lane); same partial limitation |
| 3 | DBT FULL 68 BG | **GO** — remote server reachable, dbt installed, tasks present locally |
| 4–6 | reporting / matrix / commit | post-runs |

**No FULL claim** will be made on Lite-Snow or Spider2-Snow until engine-side
execute_ok / explain_ok is measurable (requires Snow creds on bridge kernel).

## 12. Critical blockers

1. **Snow connector creds missing on bridge.** Without these the Snow FULL
   diagnostic is `schema_valid`/`parse_ok` only — not directly comparable to
   the Spider2-Snow official metric (which is execution-based). User can fix
   by running `os.environ['SNOWFLAKE_USER']=...` etc. in the Colab kernel.
2. **Cloudflare tunnel uptime.** Free quick-tunnel has no SLA; an 11-hour
   FULL run risks tunnel rotation. Mitigation: BG runner writes per-task
   to Drive (`predictions.jsonl` flushed every task); we can resume from
   Drive even if the tunnel rotates.
