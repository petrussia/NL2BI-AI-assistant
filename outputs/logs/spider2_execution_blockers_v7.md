# Spider2-Lite execution blockers — honest map (v7)

_Generated: 2026-05-05. Branch `experiments/denis`._

This is the explicit blocker map for the Spider2-Lite agent_v7 run.
It is the "mode D" deliverable from the brief: every item that cannot
produce an official EX number is accounted for here, with the exact
missing piece named.

## What we have

- BigQuery service account (test key) at
  `/content/drive/MyDrive/diploma_plan_sql/secrets/spider2_bq_sa.json`.
  Project: `project-0e0fc8a5-27b1-4e00-912`.
- Probe of credentials confirms:
  - `SELECT 1` → 0 bytes_billed, OK.
  - `SELECT COUNT(*) FROM bigquery-public-data.samples.shakespeare` →
    OK, 0 bytes_billed (cached). `bigquery-public-data.*` is reachable
    by any project with billing enabled, so this transitively covers
    the majority of Spider2 BQ items.
  - `client.list_datasets()` → 0 own datasets in the project (the test
    project owns nothing; it relies on `bigquery-public-data` for
    cross-tenant reads).
- Spider2-Lite raw resources at
  `/content/drive/.../external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/`
  including 547-item `spider2-lite.jsonl`, `evaluation_suite/gold/`
  (256 SQL files, 1544 multi-variant `exec_result/*.csv`), and per-db
  resource dirs:
    - `resource/databases/bigquery/` — 74 BQ db directories
    - `resource/databases/snowflake/` — 58 SF db directories
    - `resource/databases/sqlite/` — 30 SQLite stub directories
      (each contains `DDL.csv` + `<table>.json` sample-rows files).
- An L4 22 GB GPU running Qwen2.5-Coder-7B-Instruct in BF16.

## What we DON'T have

| Missing piece | Effect | Items affected | Required to fix |
|---|---|---:|---|
| Snowflake credentials | Can't run any SF item | 207 items (`sf*` prefix) | Snowflake account + warehouse + user/key auth + (optionally) Spider2 datasets uploaded; or paid SF service-account JSON |
| Read access to private BQ datasets (`isb-cgc-bq.*`, `isb-cgc.*`, `spider2-public-data.*`, etc. depending on item) | A subset of A_bq items will fail at exec time with `permission_denied` or `dataset_not_found` | unknown until run; logged per-item in `error_type` field | Authorized dataset access in the test project, or alternative project with explicit dataset grants |
| BQ billing budget for large scans | The runner caps per-query scan at 1 GB. Items whose query needs > 1 GB scan will fail with `bytesBilledExceeded` | unknown; expected small subset of A_bq | Either (a) raise the cap to 10 GB / 100 GB if the friend agrees to pay, or (b) accept the item as a partial / `executable=False` row |
| Per-item BQ dataset hint | The `external_knowledge` field points to a documentation file but doesn't tell us at routing time which dataset family the gold SQL targets | informational only — execution finds out | Could be precomputed offline by parsing each gold SQL once, but the current run handles this at exec time |
| Doc-text retrieval over `resource/documents/` | Docs are read raw and truncated at 1500 chars; no structured parse of the markdown table sections | quality-of-evidence loss across all A_bq items | Future work: chunk docs at heading boundaries; route relevant sections by question similarity |

## How items distribute

Routed via `spider2_router_v7.summarize_routes()` over the actual 547
items with our test BQ creds present:

| Lane | n | Why | What we report |
|---|---:|---|---|
| A_bq  | 205 | dialect = bigquery, BQ creds present | execution_match against gold rows (any-of-variant CSV match), structural metrics |
| A_sf  | 207 | dialect = snowflake, no SF creds | `mode='blocked_snowflake'`, no SQL generated |
| B_sqlite | 135 | dialect = sqlite, stub dir present, materialized in-memory | exec_ok against materialized stub; explicit `oracle-on-sample-data, non-comparable to official EX` annotation |
| C_struct | 0 | (none with current creds) | parse + dialect-valid + schema-valid + structural features only |
| **Total** | **547** | | |

## What "official EX" means in this run

We claim official EX **only** on lane A_bq. The number is computed at
consolidation time as:

> For each A_bq item: re-execute the predicted SQL via BigQuery (capped
> at 1 GB billed). Compare result rows against any of the gold
> `exec_result/<instance_id>_{a,b,c,...}.csv` variants using a loose
> set comparator (case-insensitive cell-wise, optional ordering). Mark
> `execution_match=True` iff at least one variant matches.

If the predicted query times out, exceeds 1 GB, or fails authorization,
we record `executable=False` and `execution_match=False` with the
specific reason in `exec_match_reason`. We do not impute success.

Lane B_sqlite has full `executable` numbers but **no
execution_match** — gold rows came from the full warehouse (BQ or SF),
not the small SQLite sample, so they would not match by construction.
B_sqlite numbers prove the pipeline produces SQL that runs against
the stub schema with sample data; they don't prove correctness.

Lane A_sf produces no SQL and no metrics. The 207 items are explicitly
not assessed.

## Reproducibility / honesty checklist

- [x] No SQL generated for A_sf items (no fake structural-only numbers).
- [x] BQ key never committed (lives in Drive `secrets/`).
- [x] All execution numbers come from real engines, never imputed.
- [x] B_sqlite numbers labeled non-comparable in the matrix.
- [x] Per-item route reason is in the prediction record.
- [x] Per-item BQ failure modes captured in `error_type` /
      `exec_match_reason` (consolidation step).
- [x] No mixed-engine averages reported as a single "Spider2 EX"
      number; each lane is a separate column.

## Future work to lift blockers

1. **Get Snowflake creds** → unblocks 207 items. Highest value.
2. **Larger BQ billing budget** → covers items whose gold queries
   need wildcard `_TABLE_SUFFIX` scans across ga_sessions_2017*.
3. **Authorized access to `isb-cgc.*` and similar private BQ datasets**
   → covers ~10–30 items in the medical / genomics subset.
4. **Parse gold SQL → extract referenced dataset → precompute the
   whitelist** → routes items more precisely so we don't waste
   compute on items the creds can never access. (At present the
   runner discovers this at exec time and logs per-item.)
