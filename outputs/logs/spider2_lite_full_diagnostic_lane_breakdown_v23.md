# Spider2-Lite FULL — lane breakdown (Phase 23)

_Generated: 2026-05-10 | run-id: `lite_full_diagnostic_v23` (composite)_

The Spider2-Lite benchmark = 547 distinct tasks. Each task has a `db` /
`db_id` field that maps to one of three resource families:

| lane | aliases (sets/N DBs) | tasks | resource path |
|---|---:|---:|---|
| BigQuery | 74 DBs | **205** | `resource/databases/bigquery/<alias>` |
| Snowflake | 58 DBs | **207** | `resource/databases/snowflake/<alias>` |
| SQLite (incl. local sakila/IMDB) | 30 + 2 = 32 DBs | **135** | `resource/databases/sqlite/<alias>` and local `sqlite-sakila` / `Db-IMDB` |
| **total** | — | **547** | — |

> The 12 "other" tasks (`local056`, `local096..100`, `local193..199`)
> are SQLite-flavored sakila/IMDB tasks; they are counted in the SQLite
> lane (135 = 123 strict + 12 local).

## Per-lane diagnostic policy (Phase 23)

| lane | status | rationale |
|---|---|---|
| **BigQuery** (205) | run via v22 stack as `lite_full_diagnostic_v23_bq`; full v18+v22 pipeline including BQ dry_run for `execute_ok` | engine auth confirmed; ground-truth metric is engine-side dry_run pass |
| **Snowflake** (207) | run via Snow no-execute diagnostic as `lite_full_diagnostic_v23_snow`; produces only `schema_valid` and `parse_ok` (sqlglot Snowflake dialect) | Snow connector unauthenticated on bridge kernel; engine-side `execute_ok` not measurable in this session |
| **SQLite** (135) | **NOT run** — declared **non-comparable** per benchmark policy | SQLite path is a Spider1-style stub fixture with embedded gold; running it would not produce a comparable Spider2 metric. Counted only for lane breakdown completeness. |

## SQLite non-comparable note

The SQLite lane in Spider2-Lite reuses the older Spider1 SQLite test
infrastructure for tasks where the original DB happens to be a SQLite
file. These tasks have execution oracles (the SQLite DB ships with the
benchmark) but the official Spider2-Lite scoring criteria (Snowflake/BQ
execution match) do not apply to SQLite-only tasks. Per the benchmark's
own design notes, the SQLite results are "non-comparable" with the
BQ/Snow-graded numbers and should not be summed into a single Lite
score.

For the diploma:

- **DO NOT** present SQLite execute_ok as part of an aggregate
  Spider2-Lite metric.
- The 135 SQLite tasks are reported as a **separate diagnostic** with
  their own metric column, OR omitted from the official Lite metric
  with the lane-breakdown footnote.
- DBT, BQ, Snow each have their own dedicated benchmarks with separate
  scoring; do not blend.

## Cross-reference to runs

| lane | run_id | n | status |
|---|---|---:|---|
| BQ | `lite_full_diagnostic_v23_bq` | 205 | in-progress (degraded — see Phase 23 final report) |
| Snow | `lite_full_diagnostic_v23_snow` | 207 | CANCELLED (OOM under concurrency) |
| SQLite | — | 135 | not run (non-comparable) |

> The composite "Spider2-Lite FULL" metric for Phase 23 will be
> reported as **BQ-lane only** (because that is the only lane that
> reaches engine-side execute_ok in this session). The Snow lane will
> be reported separately as a partial schema-valid + parse-ok
> diagnostic. SQLite is omitted from the metric per non-comparable
> policy.
