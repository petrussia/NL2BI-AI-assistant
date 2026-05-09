# Spider2-Lite Snowflake compatibility notes

_Status: as of 2026-05-05. Source: official Spider2 README (xlang-ai/Spider2)
+ inspection of `external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/`._

This is the minimum-knowledge briefing for hooking up our pipeline to the
Snowflake half of Spider2-Lite. It covers what the benchmark expects, the
recent (2025-11-06) auth changes, and the failure modes most likely to bite
us before the first row matches.

## 1. What's in Spider2-Lite that needs Snowflake

- `spider2-lite.jsonl` has 547 items. Items prefixed `sf*` (e.g. `sf001`,
  `sf_bq091`) are routed to Snowflake. By our routing on the current file,
  this is **207 items**; the upstream README states **198** for the latest
  v2 release — small drift between releases, not a defect. Either count is
  the SF subset.
- `evaluation_suite/snowflake_credential.json` is a 99-byte template:
  `{user, password, account}` only. No role/warehouse/db fields — Spider2
  expects these to be defaults on the account. We will pass them explicitly
  in our wrapper.
- `evaluation_suite/evaluate_utils.py:124-131` calls
  `snowflake.connector.connect(**snowflake_credential)` and runs the
  predicted SQL, comparing rows with the gold CSV multi-variants under
  `gold/exec_result/<instance_id>_*.csv` (same pattern as BigQuery).
- `resource/databases/snowflake/<DB>/<SCHEMA>/<table>.json` ships sample
  rows + column metadata for 58 SF databases, mirroring the BigQuery layout.
  This is what our `spider2_bq_schema_index_v8` consumes for BQ — we'll
  reuse the same JSON shape for SF in a future SF-specific index.
- The official path for getting SF access is the **Spider2 Snowflake Access
  form** linked in the upstream README; or self-host the data via
  `assets/Spider2_Data_Host.md`. Either way, the credentials we receive
  end up in the same `.env` we already documented.

## 2. The 2025-11-06 auth change

Spider2 added a banner to its README on 2025-11-06:

> "We apologize for the recent Snowflake login and credential issues caused by
> Snowflake's password & MFA policy upgrade. Both Web UI login and Python
> credential access behaviors have changed. Please carefully review the
> updated Snowflake guideline before continuing."

The practical impact is:

1. **Password-only auth is being phased out** for personal/SSO accounts.
   `snowflake_credential.json` with `{user, password, account}` will work
   only on a service-account user that explicitly bypasses the org-level
   MFA policy. If the friend creates such a user on their own account
   (`SPIDER2_BENCH`, see `friend_provisioning.sql`), password works.
2. **For shared accounts** managed by xlang-ai, key-pair auth or SSO is
   often required. A Spider2 runner cannot use SSO (`externalbrowser`
   authenticator) because it pops a browser; we have to use either:
   - a service user the friend creates with no MFA → password OK; or
   - key-pair auth (`authenticator='snowflake_jwt'` + RSA public key
     registered on the Snowflake user via
     `ALTER USER ... SET RSA_PUBLIC_KEY = '...'`).
3. **Headless runs are the constraint.** Anything interactive (MFA push,
   browser SSO) breaks the long-running batch agent.

Our `.env.template` exposes both paths:
```
SNOWFLAKE_PASSWORD=               # path A
SNOWFLAKE_PRIVATE_KEY_PATH=       # path B (preferred when MFA is enforced)
SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=
SNOWFLAKE_AUTHENTICATOR=          # leave blank for password; "snowflake_jwt" for key-pair
```

## 3. Compatibility / dialect notes for our agent

When we wire the SF lane (next step), the agent must emit Snowflake SQL,
not BigQuery SQL. Differences that matter most:

| Concept | BigQuery | Snowflake |
|---|---|---|
| Fully qualified names | `` `project.dataset.table` `` | `database.schema.table` (no backticks; double-quote case-sensitive identifiers) |
| Date math | `DATE_DIFF(d2,d1,DAY)` | `DATEDIFF(DAY,d1,d2)` (note: arg order flipped!) |
| Date parse | `PARSE_DATE('%Y%m%d', s)` | `TO_DATE(s,'YYYYMMDD')` |
| Date trunc | `DATE_TRUNC(d, MONTH)` | `DATE_TRUNC('MONTH', d)` |
| Year extract | `EXTRACT(YEAR FROM d)` | `EXTRACT(YEAR FROM d)` (same — but `YEAR(d)` also works) |
| Repeated → rows | `UNNEST(arr) AS x` | `LATERAL FLATTEN(input => arr) f` (use `f.value`) |
| Wildcard tables | `_TABLE_SUFFIX` | NOT supported — no daily-suffix wildcards in SF |
| Cast | `SAFE_CAST(x AS T)` | `TRY_CAST(x AS T)` |
| String concat | `CONCAT(a,b)` or `\|\|` | `\|\|` or `CONCAT(a,b)` |
| Approx distinct | `APPROX_COUNT_DISTINCT(x)` | `APPROX_COUNT_DISTINCT(x)` (same) |
| Quoted identifier | `` `Foo Bar` `` | `"Foo Bar"` (case-sensitive!) |

Most failure modes from the v7/v8 BigQuery audit will reappear here
(wrong identifier names, wrong functions). The retrieval layer port to SF
is the main work; the prompt rules table flips for half a dozen entries.

## 4. Risks on this side

| Risk | Why | Mitigation |
|---|---|---|
| **MFA on friend's account** | If the friend's SF org enforces MFA at the account level, even our service user will be challenged. | Ask the friend explicitly for an exemption for `SPIDER2_BENCH`, or use key-pair auth (mfa-bypass). |
| **Marketplace share missing** | Spider2 datasets are exposed as Marketplace shares; the friend's account may not have them attached. | Either fill out the Spider2 access form OR self-host (`Spider2_Data_Host.md`). The provisioning SQL has both branches. |
| **Warehouse credit burn** | A negligent query (e.g. cross-join on a 100GB table) can chew $$ in seconds. | Use XSMALL warehouse, AUTO_SUSPEND=60, attach a `RESOURCE_MONITOR` capping credits/day. SQL provided. |
| **Dialect drift in our agent** | Same prompt that worked on BQ will fail SF (DATEDIFF arg order, no _TABLE_SUFFIX, FLATTEN vs UNNEST). | Build `spider2_sf_prompting_vN` with SF-specific rules; do not reuse the BQ rules block. |
| **Gold SQL/result mismatch** | Some `sf*` items may have no `<iid>_*.csv` in `gold/exec_result/` — exec_match would be N/A. | Mirror the BQ consolidation: only count EX where gold rows exist; report n_compared explicitly. |
| **Auto-suspend latency on first query** | First query after a long pause needs ~3-5 sec to wake the warehouse. | Acceptable — the runner should treat warehouse-resume as part of latency; don't fail on it. |
| **MFA push on personal account** | If the friend mistakenly hands us their personal user, every connect attempt fires an MFA push to their phone. | Refuse personal accounts; insist on `SPIDER2_BENCH` or equivalent service user. |
| **Account locator format** | Old format `XYZ12345`, new format `xyz12345.region.cloud` — the wrong one fails with confusing errors. | Always copy the value directly from the Snowflake URL; document the format in `.env.template`. |
| **Spider2-Lite vs Spider2-Snow confusion** | Spider2-Snow is the Snowflake-only benchmark (547 items). We want Spider2-**Lite** SF subset (~198-207 items). | The runner is hard-coded to `--benchmark spider2-lite` and reads `spider2-lite.jsonl`. Do not point it at `spider2-snow.jsonl`. |
| **Bridge URL rotation during long runs** | Our Colab bridge tunnel rotates ~6h. SF runs over hours will outlast a single tunnel. | Already handled: runner is detached (`nohup`), resumable JSONL. |

## 5. Path forward — order of operations

1. Friend runs `friend_provisioning.sql` (with placeholders replaced).
   Sends back: account, user, password (or public_key), role, warehouse,
   database, schema. They share via password manager, NOT chat.
2. We fill `snowflake_setup/.env` and run
   `python snowflake_setup/test_snowflake_connection.py` — that confirms
   `CURRENT_VERSION` returns + we have a warehouse + role we can see.
3. Smoke selection:
   ```
   python snowflake_setup/run_spider2_lite_snowflake_smoke.py \
     --benchmark spider2-lite --engine snowflake --subset snowflake \
     --limit 1 --probe-connection
   ```
   Then `--limit 3` and `--limit 10`. The runner emits a selection JSONL
   plus a `connection_probe.json` for audit.
4. Once SF access is confirmed, the next iteration adds:
   - `repo/src/evaluation/spider2_sf_executor_vN.py` (snowflake.connector
     wrapper analogous to `build_bq_executor`)
   - `repo/src/evaluation/spider2_sf_schema_index_vN.py` (mirrors
     `spider2_bq_schema_index_v8` but reads `resource/databases/snowflake/`)
   - `repo/src/evaluation/spider2_sf_prompting_vN.py` (SF dialect rules)
   - `repo/src/evaluation/spider2_agent_vN.py` (lane-aware agent extending
     v8 to A_sf)
5. Re-route, re-run on the SF subset only, label artifacts as
   `spider2_sf_agent_vN_*` to keep them separated from BQ.

## 6. Things explicitly NOT done in this PR

- No SF queries are issued by anything in `snowflake_setup/`. The smoke
  test stops at `SELECT CURRENT_VERSION()`. The Spider2 dataset queries
  only run after a future PR adds the SF executor.
- No changes to v7/v8 modules. Existing BG runs are untouched.
- No real secrets in any file in the repo. `.env` is in `.gitignore`
  inside the folder; the template uses placeholders only.
- No fake EX numbers for SF lane — the existing master matrix already
  marks A_sf as "blocked, no SF creds"; that stays until SF execution
  is wired and a real run completes.
