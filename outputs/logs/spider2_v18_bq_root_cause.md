# Spider2 v18 — BQ pilot10 root-cause read

_Generated: 2026-05-09 | run: `lite_bq_v18_pilot10`_

## Headline

| metric | value |
|---|---:|
| n | 10 |
| **parse_ok** | **10/10** ✅ |
| **execute_ok (BQ dry_run)** | **1/10** ✅ first non-zero |
| chosen_schema_valid (closed-set, conservative) | 0/10 |
| plan_validation_ok | 0/10 |
| chosen Family A (deterministic) | 9/10 |
| chosen Family B (Coder-7B direct) | 1/10 |

The architectural pivot delivered the engine-acceptance signal Spider2
work has been chasing for 7 phases. The 9 remaining failures decompose
cleanly into three small bugs.

## bq011 — the dry_run_ok candidate

```sql
SELECT COUNT(DISTINCT e1.user_pseudo_id) AS distinct_users_with_positive_engagement
FROM bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_20210109 e1
LEFT JOIN bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_20201107 e2
ON e1.user_pseudo_id = e2.user_pseudo_id
WHERE e1.event_timestamp >= UNIX_SECONDS('2021-01-01 00:00:00')
AND   e1.event_timestamp < UNIX_SECONDS('2021-01-08 00:00:00')
```
- **Family**: B (Coder-7B direct emit on the closed schema pack)
- **Why it passed**: clean unbacktick-but-FQN pattern, real GA4 dataset,
  real `event_timestamp` field, real `UNIX_SECONDS` builtin. BQ accepts.

## The 9 fails — three repeating patterns

### Pattern P1 — renderer prefix-duplication
`bq010`, `bq003`:
```
FROM `bigquery-public-data.google_analytics_sample.ga_sessions.bigquery-public-data.google_analytics_sample.ga_sessions_20170710`
```
The planner returned `selected_database = "bigquery-public-data.google_analytics_sample"`
(a fully-qualified path) and `selected_tables = ["bigquery-public-data.google_analytics_sample.ga_sessions_20170710"]`.
The renderer concatenated `db + schema + tables[0]` naively and produced
the duplicated path. **Bug in `sql_renderer_v18._qualify_table`.**

### Pattern P2 — `selected_database = "bq"` ghost
`bq008`, `bq269`, `bq268`, `bq011 (planner)`:
The planner returned a phantom `"bq"` for `selected_database` despite
`bigquery-public-data` being the only database in the pack. This is a
generation artifact of Qwen3-Coder-30B confusing "BQ lane" with
"BQ database name". **Fix: the prompt should explicitly forbid using
abbreviations and pin `selected_database` to a literal pack value.**

### Pattern P3 — date shards not recognized as wildcards
`bq001`:
```
selected_tables = ["ga_sessions_20170201","ga_sessions_20170202",
                   "ga_sessions_20170203", ...]
```
The planner enumerated specific GA4 date shards. Some are in the pack,
some are not. The deterministic renderer falls back to picking
`selected_tables[0]` and concatenating, missing the actual SQL pattern
(`FROM \`...ga_sessions_*\` WHERE _TABLE_SUFFIX BETWEEN ...`). **Renderer
bug + planner doesn't know about wildcard sharding semantics.**

## What this DOES tell us

1. **The closed-set retrieval works**: the schema linker found the
   correct dataset (`google_analytics_sample` / `ga4_obfuscated_sample_ecommerce`)
   for every GA-related question. The pack was small (≤8 tables, ≤22
   cols/table, ~600 tokens) and the right answer was reliably in it.

2. **The planner produces well-typed JSON**: 10/10 plans parsed as JSON
   without retry. The structural-output approach works; the strictness
   problem is in *what counts as a valid identifier*, not in the model
   producing JSON.

3. **The renderer's deterministic skeleton is sound**: 9/10 chosen
   candidates parsed as legal BQ SQL via sqlglot. The remaining engine
   rejections are 3 patterns that are bug-fixes rather than research.

4. **Coder-7B remains the strongest emitter** when the planner
   over-qualifies; the 1 dry_run_ok was Coder-7B beating Qwen3-Coder-30B
   on bq011.

## What this does NOT tell us

- Whether the engine-acceptance lift generalizes to non-GA tasks. The
  v17 BQ pilot10 happens to start with 10 GA-heavy tasks (`bq001..bq011`).
  v18.1 should re-pilot a non-GA-heavy slice (`bq30..bq40`) for
  signal that's not artifically narrow.
- Whether Snow shows the same lift. STEP 1 already harvested the Snow
  live catalog; v18.1 should run Snow pilot10 immediately after the
  three v18.1 patches land.
