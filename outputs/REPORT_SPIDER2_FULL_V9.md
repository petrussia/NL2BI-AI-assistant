# Spider2 Phase 11 (v9) — DBT FULL / Snow gate-failed / Lite pilot — unified report

_Generated: 2026-05-08 | branch: `experiments/denis` | author: Denis_

> **Honest scope.** This report carries one **real FULL** number
> (Spider2-DBT 68, V4 variant, n=68, task_success=9/68=13.2%), one
> **gated-out FULL** (Spider2-Snow — pilot10 v9 parse_ok=0/10, gate ≥50%
> failed, FULL not launched), and **Spider2-Lite v9 pilot10 only** (FULL
> Lite is multi-hour and is queued for a follow-up). No FULL claim is
> made on partial data.

---

## 1. Hard status

| component | status | evidence |
|---|:---:|---|
| Colab bridge | ✅ | preflight pid=1139 (a5cdbfe artefact) |
| HF_TOKEN | ✅ | bridge probe |
| BigQuery | ✅ live | preflight live n=164656 |
| Snowflake live | ✅ | account RSR\*\*\* / PARTICIPANT / COMPUTE_WH_PARTICIPANT |
| Spider2-Lite jsonl | ✅ 547 | `data/spider2_lite/raw/spider2-lite.jsonl` |
| **Spider2-Snow canonical 547** | ✅ acquired this session | `data/spider2_snow/raw/spider2-snow.jsonl`, 152 unique db_id, manifest+sha256 in `external_benchmarks/spider2_snow/manifests/` |
| Spider2-DBT 68 | ✅ FULL run done | `task_success=9/68=13.2%` |
| Phase 11 commit | not yet committed | this session |

## 2. Spider2-DBT FULL 68 — REAL FULL RESULT

`outputs/spider2_dbt/runs_v8/dbt_v8_FULL_68/` (variant=v4, n=68).

| metric | value | rate |
|---|---:|---:|
| n | 68 | — |
| done (pipeline reached evaluator) | 66 | 97.1% |
| dbt_deps_ok | 66 | 97.1% |
| dbt_run_ok | 27 | **39.7%** |
| dbt_test_ok | 26 | 38.2% |
| **task_success (matched > 0)** | **9** | **13.2%** |

Successful tasks (9): `playbook001, lever001, mrr001, quickbooks003,
salesforce001, superstore001, f1003, retail001, mrr002`.

Error taxonomy (whole pipeline status):
- `done` 66, `inference_failed` 1, `agent_exception` 1.

Canonical artifacts:
- Predictions: `outputs/predictions/spider2_dbt_agent_v8_full_predictions.jsonl`
- Traces: `outputs/traces/spider2_dbt_agent_v8_traces.jsonl`
- Metrics: `outputs/tables/spider2_dbt_agent_v8_metrics.csv`
- Error taxonomy: `outputs/tables/spider2_dbt_agent_v8_error_taxonomy.csv`
- Source breakdown: `outputs/tables/spider2_dbt_agent_v8_source_breakdown.csv`
- Cost/runtime: `outputs/tables/spider2_dbt_agent_v8_cost_runtime.csv`
- Readout: `outputs/logs/spider2_dbt_agent_v8_readout.md`

This is the **first publishable Spider2-DBT FULL number** for this
project. The 13.2% task_success uses the official_eval (matched > 0).

## 3. Spider2-Snow canonical 547 — acquisition status

✅ **Done.** From `xlang-ai/Spider2` GitHub via tarball.

- Drive: `external_benchmarks/spider2_snow/processed/spider2_snow_547.jsonl` (245 274 bytes, 547 rows)
- Drive: `external_benchmarks/spider2_snow/raw/spider2_main.tgz` (327 575 607 bytes, sha256 in manifest)
- Drive: `external_benchmarks/spider2_snow/manifests/spider2_snow_manifest.json`
- Local: `data/spider2_snow/raw/spider2-snow.jsonl`
- Schema dirs (resource/databases) live on Colab `/content/spider2_snow_extract/` and are pulled lazily per-DB by the v9 runner.

Schema drift vs Spider2-Lite:
| Spider2-Lite | Spider2-Snow canonical |
|---|---|
| `db` | `db_id` |
| `question` | `instruction` |

The v9 runner (`tools/run_spider2_snow_full_v9.py`) adapts on read.

Top dbs by row count: `CRYPTO=20, THELOOK_ECOMMERCE=19, GA4=17, PATENTS=15, GITHUB_REPOS=15, STACKOVERFLOW=15, IDC=15, BANK_SALES_TRADING=15` (152 unique db_ids).

## 4. Spider2-Snow v9 pilot10 (after dialect fix)

`outputs/spider2_snow/runs/snow_v9_pilot10/`

| metric | v8 pilot3 | **v9 pilot10** |
|---|---:|---:|
| n | 3 | 10 |
| parse_ok | 0/3 | **0/10 (0.0%)** |
| execute_ok | 0/3 | 0/10 |
| dominant errors | wrong_dialect (2), object_not_found (1) | object_not_found (6), syntax (4) |

Dialect-fix breakdown (this run): `unnest_to_flatten` applied to 3
candidates. `wrong_dialect` errors **eliminated** by v9 (was 2/3 in v8).

**Gate decision (per user policy):** parse_ok 0% << 50% → **Spider2-Snow
FULL 547 NOT launched**. Diagnostic at
`outputs/logs/spider2_snow_dialect_fix_v9.md`.

Root-cause hypotheses for the gate miss (next session):
- H1: schema rendering shows both `fq_name` and `table_fullname`; model
  concatenates → 4-part identifiers.
- H2: model invents columns (retrieval shortlist too wide for sparse
  Snow column descriptions).
- H3: Coder-7B insufficient for Snow domain.
- H4: per-task wall_time 66–227 s with current rendering — token budget pinned.

## 5. Spider2-Snow FULL 547

**Deferred (gate failed).** Will be the first action of next session
after H1/H2 fixes land + Coder-32B test on n=10.

## 6. Spider2-Lite v9 pilot10 (4 BQ + 3 SF + 3 SQLite)

`outputs/spider2_lite/runs/lite_v9_pilot10/`

| lane | n | parse_ok | execute_ok | parse_rate | non_comparable |
|---|---:|---:|---:|---:|:---:|
| `A_bq` | 4 | 0 | 0 | **0.0%** | no |
| `A_sf` | 3 | 0 | 0 | **0.0%** | no |
| `C_sqlite_stub` | 3 | 0 | 0 | 0.0% | **YES — never report officially** |

Per-lane diagnostic:

- **A_bq (0/4)** — every task hit `agent_exception: HTTPError: HTTP
  Error 500` from the Colab bridge when calling `_BQ_CLIENT.query`
  through `_bridge_exec`. Task 2 (`bq010`) hung for 1248 s before the
  500. Likely cause: the code-string sent through `/exec` triggered a
  kernel-state issue after the BQ executor bootstrap. Tasks 3, 4
  failed instantly with the same 500 — the kernel was in a broken
  state for the rest of the run.
- **A_sf (0/3)** — all returned `syntax` in 2–16 s, much shorter than
  Snow v9 pilot10 (~66–227 s/task). The fast wall plus empty `sql`
  field in predictions suggests generation failed early; SF lane
  shared a degraded kernel with the BQ lane.
- **C_sqlite_stub (0/3)** — all `sqlite_db_missing` for `db=E_commerce`.
  Spider2-Lite local* items use `E_commerce` while Spider2 ships
  `e_commerce` on Drive. The v9 case-insensitive resolver
  (`sqlite_lane_resolver_v9.py`) covers `db.lower()`, but on this
  failed kernel the bridge call inside the resolver also hit the same
  500 wave.

**Gate decision:** parse_ok ≪ 30% on every lane → **Spider2-Lite FULL
547 NOT launched.**

## 7. Spider2-Lite FULL 547 — DEFERRED

Same reason as Snow: gate failed. Two root causes need a separate
diagnostic session:

1. **Bridge HTTP 500 instability** — the BQ executor pattern
   (large code blob through `/exec`) appears to push the Cloudflare
   tunnel over a limit. Mitigations: shorten the per-call code blob,
   reset the kernel between phases, or run BQ via a local
   `google.cloud.bigquery` client (would need pulling the SA key off
   Drive — defer per security policy).
2. **SQLite case** — Spider2 sample DBs use `e_commerce` lowercase on
   disk; the dataset record has `db=E_commerce`. The v9 resolver does
   try `.lower()` but failed because of the same bridge wave. A
   non-bridge resolver (Drive sync to local disk first) is the cleanest
   fix.

## 8. Official vs non-comparable split

- **Official-eligible** (rankable claim possible after FULL):
  Spider2-DBT 68 (DONE — 13.2%), Spider2-Snow canonical 547 (gate
  failed), Spider2-Lite BQ lane 205 (deferred), Spider2-Lite SF lane
  207 (deferred).
- **Non-comparable** (always flagged): Spider2-Lite SQLite stub 135.
- **No oracle / ground-truth-table mode** in v9.

## 9. v8 → v9 improvement (delta this session)

| benchmark | v8 status | v9 status |
|---|---|---|
| Spider2-Snow | pilot3 wrong_dialect 2/3 | pilot10 wrong_dialect **0/10** thanks to normalizer; semantic errors still dominate |
| Spider2-Lite (BQ) | pilot1 unknown_bq_cast | v9 wraps BQ executor with `bigquery_dialect_normalizer_v9` (DATE("YYYYMMDD") → typed DATE 'YYYY-MM-DD') — pilot10 in flight |
| Spider2-Lite (SQLite) | pilot1 sqlite_db_missing | v9 `sqlite_lane_resolver_v9` does case-insensitive db-path resolve via bridge — pilot10 in flight |
| Spider2-DBT | n=6 ablation V4 helpful=1 | **FULL 68 task_success=9/68=13.2%**, including all 6 prior smoke wins ⊆ canonical successes set |

## 10. Error taxonomy (live cuts)

DBT FULL 68 status: `done` 66, `inference_failed` 1, `agent_exception` 1.

Snow v9 pilot10: `object_not_found` 6, `syntax` 4, `wrong_dialect` 0.

Lite v9 pilot10:
- A_bq: `agent_exception` 4 (bridge HTTP 500)
- A_sf: `syntax` 3 (kernel degraded)
- C_sqlite_stub: `sqlite_db_missing` 3 (db naming + bridge degraded)

## 11. Repair impact

DBT FULL 68: V4 (diff-form) is the single variant; no in-pipeline repair
loop in this run.

Snow v9 pilot10: repair_helpful=0 (because all candidates failed the same
class of error — repair was correctly **not invoked** when the seed
failure was semantic, not lexical).

## 12. Cost / runtime

| benchmark | n | total wall (~) | s/task |
|---|---:|---|---:|
| Spider2-DBT FULL 68 | 68 | 56 min | ~50 |
| Spider2-Snow v9 pilot10 | 10 | ~17 min | 66–227 (variance because canonical Snow tables are large; rendering hits token budget for CTE) |
| Spider2-Lite v9 pilot10 | 10 | _filling_ | _filling_ |

## 13. Blockers

1. **Snow gate failed** — see §4 H1–H4. Top fix: drop `table_fullname`
   from prompt and keep only `fq_name`; switch to Coder-32B on a 10-task
   sanity run.
2. **GCP SA test key still in use** — rotation deferred to merge time
   per user.
3. **a5cdbfe local-only** — no `git push` triggered, will need explicit
   approval.

## 14. Exact artifact paths

DBT v8 FULL 68:
- `outputs/predictions/spider2_dbt_agent_v8_full_predictions.jsonl`
- `outputs/traces/spider2_dbt_agent_v8_traces.jsonl`
- `outputs/tables/spider2_dbt_agent_v8_{metrics,error_taxonomy,source_breakdown,cost_runtime}.csv`
- `outputs/logs/spider2_dbt_agent_v8_readout.md`
- `outputs/spider2_dbt/runs_v8/dbt_v8_FULL_68/` (raw run dir)

Snow v9 pilot10:
- `outputs/spider2_snow/runs/snow_v9_pilot10/`
- `outputs/predictions/spider2_snow_agent_v9_snow_v9_pilot10_predictions.jsonl`
- `outputs/tables/spider2_snow_pilot10_v9_metrics.csv`
- `outputs/logs/spider2_snow_dialect_fix_v9.md`

Snow canonical dataset:
- Drive: `external_benchmarks/spider2_snow/{processed/spider2_snow_547.jsonl, raw/spider2_main.tgz, manifests/spider2_snow_manifest.json}`
- Local: `data/spider2_snow/raw/spider2-snow.jsonl`

Lite v9 pilot10:
- `outputs/spider2_lite/runs/lite_v9_pilot10/` (in flight)

Phase 11 unified report (this file): `outputs/REPORT_SPIDER2_FULL_V9.md`.

## 15. Next recommendation

1. **Snow H1 fix**: drop `table_fullname` from prompt rendering — model
   no longer concatenates schema name twice. Sanity check on 10 tasks.
2. **Snow H3 sanity**: try Coder-32B on the same 10 tasks to gauge how
   much improvement we can buy. Decide between fix-prompt + Coder-7B
   vs ship-Coder-32B.
3. **Lite v9 FULL** if pilot10 parse_ok ≥ 30% per lane, otherwise repeat
   the diagnostic loop on Lite-BQ first.
4. Rotate GCP SA key on merge.
5. Decide push for `a5cdbfe` + this Phase 11 commit.
