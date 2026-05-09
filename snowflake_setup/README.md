# Snowflake setup for Spider2-Lite SF subset

_Parallel onboarding track. Does not touch the v7/v8 BigQuery experiments
or the production B6_v7 controller. All artifacts here live under
`snowflake_setup/` (this folder), `configs/snowflake/`, and
`outputs/spider2_lite_snowflake_smoke/`._

This folder prepares the repo to run the Snowflake portion of Spider2-Lite
(~198–207 items, depending on benchmark version) once a friend grants us
Snowflake access. Nothing here issues benchmark queries against SF — the
smoke test caps at `SELECT CURRENT_VERSION()`. The actual SF agent runner
is the next iteration; this PR just wires the credentials path, task
selection, and connection sanity.

## Files

| Path | Purpose |
|---|---|
| `snowflake_setup/.env.template` | Env-var template for SF creds. Copy to `.env` and fill from friend. |
| `snowflake_setup/.gitignore` | Prevents `.env` / `*.pem` / `secrets/` from being committed. |
| `snowflake_setup/test_snowflake_connection.py` | Standalone smoke: SELECT CURRENT_VERSION, ROLE, WAREHOUSE, DATABASE, SCHEMA, SHOW WAREHOUSES. Masks all secrets in stdout. |
| `snowflake_setup/run_spider2_lite_snowflake_smoke.py` | CLI runner: filters Spider2-Lite to SF subset, writes selection JSONL, optional connection probe. Refuses to invoke the agent until the next PR lands. |
| `snowflake_setup/friend_provisioning.sql` | SQL the friend runs in their SF account to create `SPIDER2_RW` role, `SPIDER2_WH` warehouse, `SPIDER2_BENCH` user, and grant Spider2 dataset access. |
| `snowflake_setup/spider2_sf_compat_notes.md` | Compatibility + risk briefing: 2025-11-06 MFA change, BQ→SF dialect deltas, billing/MFA/dialect risks. |
| `configs/snowflake/default.yaml` | Defaults for the future SF agent runner. Reserved knobs only — not consumed by the smoke pipeline. |

## What you need to ask the friend for

Send the friend `snowflake_setup/friend_provisioning.sql`. Ask them to:

1. Replace `REPLACE_ME_STRONG_PASSWORD` with a real password (don't share it
   in chat — use a password manager). If their org enforces MFA on new
   users, replace step 3 Option A with step 3 Option B (key-pair auth) and
   send us the public key path instead.
2. Run the SQL as `ACCOUNTADMIN`.
3. Confirm which Spider2 SF databases their account can see — they may
   need to fill out the
   [Spider2 Snowflake Access form](https://docs.google.com/forms/d/e/1FAIpQLScbVIYcBkADVr-NcYm9fLMhlxR7zBAzg-jaew1VNRj6B8yD3Q/viewform)
   first if the Marketplace shares aren't already attached.
4. Hand back, via private channel:

| Field | Example |
|---|---|
| `SNOWFLAKE_ACCOUNT` | `abc12345.us-east-1` (read off the Snowflake URL) |
| `SNOWFLAKE_USER` | `SPIDER2_BENCH` |
| `SNOWFLAKE_PASSWORD` | (whatever they set — never paste into chat) |
| or `SNOWFLAKE_PRIVATE_KEY_PATH` | path to the encrypted/unencrypted PEM private key |
| `SNOWFLAKE_ROLE` | `SPIDER2_RW` |
| `SNOWFLAKE_WAREHOUSE` | `SPIDER2_WH` |
| `SNOWFLAKE_DATABASE` | one of the granted SF databases (default context) |
| `SNOWFLAKE_SCHEMA` | usually `PUBLIC` |

## Setup commands

```
# one-time
pip install --upgrade snowflake-connector-python cryptography
cp snowflake_setup/.env.template snowflake_setup/.env
# ...edit snowflake_setup/.env...

# 1. connection sanity
python snowflake_setup/test_snowflake_connection.py
```

## Smoke runs (progressive)

```
# 1. select 1 SF item, save selection JSONL only — no SF queries
python snowflake_setup/run_spider2_lite_snowflake_smoke.py \
    --benchmark spider2-lite --engine snowflake --subset snowflake \
    --limit 1

# 2. add the connection probe (SELECT CURRENT_VERSION)
python snowflake_setup/run_spider2_lite_snowflake_smoke.py \
    --benchmark spider2-lite --engine snowflake --subset snowflake \
    --limit 1 --probe-connection

# 3. ramp up
python snowflake_setup/run_spider2_lite_snowflake_smoke.py \
    --benchmark spider2-lite --engine snowflake --subset snowflake \
    --limit 3 --probe-connection

python snowflake_setup/run_spider2_lite_snowflake_smoke.py \
    --benchmark spider2-lite --engine snowflake --subset snowflake \
    --limit 10 --probe-connection
```

Outputs (relative to repo root):
- `outputs/spider2_lite_snowflake_smoke/tasks_selected.jsonl`
- `outputs/spider2_lite_snowflake_smoke/connection_probe.json` (if `--probe-connection`)
- `outputs/spider2_lite_snowflake_smoke/run_metadata.json`

## Where the current evaluator picks the backend

`repo/src/evaluation/spider2_router_v7.route_item` is the single dispatch
point — it inspects `instance_id` prefix and returns one of `A_bq | A_sf |
B_sqlite | C_struct`. Today the agent (`spider2_agent_v7`/`v8`) skips
`A_sf` items with `mode='blocked_snowflake'`, no SQL generated.

What needs to change to enable the SF lane (next PR, NOT this one):

1. New executor: `spider2_tools_v7` already has BigQuery + in-memory SQLite
   builders. Add `build_sf_executor(creds_dict, *, warehouse, role, ...)`
   that mirrors `build_bq_executor`'s contract:
   `(sql, *, dry_run, max_rows, dialect) -> {ok, rows, bytes_billed,
   bytes_processed, error_type, error_message, mode}`. Snowflake doesn't
   bill by bytes scanned, so `bytes_billed` becomes a credits proxy
   (parsed from query history) or zero.
2. New schema index: `spider2_sf_schema_index_v8.py` reading
   `resource/databases/snowflake/<DB>/<SCHEMA>/<table>.json` (the per-table
   sample-rows JSON has the same shape as the BQ stubs — same parser
   structure as `build_index_from_db_dir`).
3. New prompting: `spider2_sf_prompting_v8.py` with SF dialect rules
   (DATEDIFF arg order, FLATTEN vs UNNEST, no `_TABLE_SUFFIX`, etc.)
   The compat notes document spells out the deltas.
4. Selector / repair / verifier: 80% of `spider2_bq_*_v8.py` ports cleanly;
   only the `dialect_check` step needs `parse(read='snowflake')` and the
   error-bucket vocabulary swaps a few entries.
5. Router: `spider2_router_v7` already routes SF correctly; no change.

Predicted-SQL format stays JSONL identical to A_bq (one row per item with
`generated_sql`, `executable`, `execution_match`, etc.) so the existing
consolidation script `128_phase_nine_*` ingests it without modification.

## Risks (full breakdown in `spider2_sf_compat_notes.md`)

- **MFA / SSO** breaks headless runs. Service user with password or
  key-pair is mandatory. Don't accept the friend's personal SSO account.
- **Marketplace shares not attached** → `IMPORTED PRIVILEGES` grant fails.
  Fix: fill the Spider2 access form OR self-host the data.
- **Credit burn** on accidental cross-joins. `RESOURCE_MONITOR` capped at
  5 credits/day in the provisioning SQL; XSMALL warehouse with 60s
  auto-suspend.
- **Dialect drift**: BQ prompt rules don't transfer 1:1 to SF (DATEDIFF
  arg order is the easiest trap). SF-specific prompting required before
  any real generation.
- **Auto-suspend cold start** adds 3-5s on the first query of a session;
  not a defect but the runner shouldn't treat it as a timeout.
- **Account locator format**: old `XYZ12345` vs new `xyz.region.cloud`.
  Use exactly what's in the Snowflake URL.
- **Spider2-Lite vs Spider2-Snow**: this folder targets `spider2-lite.jsonl`
  ONLY. `spider2-snow.jsonl` is a separate benchmark (547 SF-only items)
  and is out of scope here.

## What's blocked until SF access lands

- `--probe-connection` will report `reason=missing_env` on the smoke runner
  until `.env` is filled.
- `--allow-generate` is a no-op flag right now; the agent invocation is
  intentionally not wired so we can't accidentally hit SF before it's
  vetted. Once `spider2_sf_*_v8` modules ship, the flag enables the
  generation step.
- `outputs/logs/spider2_sf_blocker_status.md` (path reserved in the
  config) gets generated by the smoke runner each time `--probe-connection`
  fails, with the exact missing piece — same pattern as the existing
  `spider2_execution_blockers_v7.md` for documentation.
