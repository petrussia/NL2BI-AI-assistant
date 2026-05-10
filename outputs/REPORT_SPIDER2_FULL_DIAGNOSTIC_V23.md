# Spider2 FULL diagnostic — Phase 23 (V23) report

_Generated: 2026-05-10 | branch: `experiments/denis` | parent commit: `1ba0b8f` (Phase 22)_

> **Scope.** Diagnostic FULL runs across all three Spider2 benchmarks
> (Lite 547, Snow 547, DBT 68), strictly separated. **Honest reading:
> session ran into a structural GPU-memory blocker on the bridge that
> degraded BQ FULL to 14/205 and forced cancellation of all Snow runs.
> DBT FULL was blocked by the same GPU pressure. This report documents
> the partial / cancelled outcomes, the root cause, and the exact
> remaining blockers — it is NOT an official benchmark headline.**

---

## 1. Hard status

| component | value |
|---|---|
| Branch | `experiments/denis` |
| Parent commit | `1ba0b8f` |
| Phase 23 commit | `<assigned at STAGE 6>` |
| Bridge | `https://corpus-vatican-technical-pennsylvania.trycloudflare.com` |
| GPU | A100 80 GB |
| Models loaded | Qwen3-Coder-30B-A3B-Instruct (planner) + Qwen2.5-Coder-7B-Instruct (emitter), 79.5 GB used |
| BQ auth | OK (`project-0e0fc8a5-27b1-4e00-912`) |
| Snow auth | **BLOCKED** — env vars unset on bridge kernel |
| DBT remote | OK at `denis@103.54.18.91` (`/home/denis/dbt/.venv/bin/dbt`) |
| Push | NOT executed |

## 2. What was run

| run_id | benchmark / lane | n_target | n_processed | status |
|---|---|---:|---:|---|
| `lite_full_diagnostic_v23_bq` | Spider2-Lite / BQ lane | 205 | **14** | **PARTIAL** — runner stuck on OOM-retry |
| `lite_full_diagnostic_v23_snow` | Spider2-Lite / Snow lane | 207 | 70 | **CANCELLED** — OOM under concurrency, then stub-abort |
| `snow_full_diagnostic_v23` | Spider2-Snow benchmark | 547 | 32 | **CANCELLED** — OOM, all-fail |
| `dbt_full_diagnostic_v23` | Spider2-DBT benchmark | 68 | 0 | **BLOCKED** — bridge GPU exhausted; CUBLAS_STATUS_ALLOC_FAILED on inference |

SQLite lane in Lite (135 tasks) is documented in
[`outputs/logs/spider2_lite_full_diagnostic_lane_breakdown_v23.md`](logs/spider2_lite_full_diagnostic_lane_breakdown_v23.md)
as **non-comparable** per benchmark policy (not run).

## 3. Lite FULL diagnostic result

### 3.1 Lane breakdown (Spider2-Lite 547)

| lane | n | run | metric headline |
|---|---:|---|---|
| BigQuery | 205 | `lite_full_diagnostic_v23_bq` | partial 14/205 — see §3.2 |
| Snowflake | 207 | `lite_full_diagnostic_v23_snow` | cancelled |
| SQLite | 135 | not run (non-comparable) | — |

### 3.2 Lite-BQ partial numbers (n_processed = 14 / 205)

| metric | count | rate vs n=14 | rate vs n=205 |
|---|---:|---:|---:|
| plan_validation_ok | 4 | 28.6% | 2.0% |
| chosen_schema_valid | 4 | 28.6% | 2.0% |
| parse_ok | 6 | 42.9% | 2.9% |
| execute_ok (BQ dry_run) | 2 | 14.3% | 1.0% |
| OutOfMemoryError (mid-task) | 8 | 57.1% | — |

**Sub-restricted to non-OOM cases (n=6):** schema_valid 67%, exec_ok 33%
— directionally consistent with v22 pilot50 (54% / 44%) within sample
noise, but sample is too small to claim.

### 3.3 Top blockers (Lite-BQ)

1. **OutOfMemoryError (8/14)** — concurrent inference contention; not a
   model/pipeline failure
2. **`bq_dry_run_failed` (3/14)** — engine-compat issues (STAGE A4 from
   Phase 22 still unaddressed)
3. **`schema_invalid` (2/14)** — pack-thinness validator FP, expected

### 3.4 Lite Snow / SQLite

- Snow lane: cancelled before producing any usable predictions.
  Re-launch deferred to next session, sequentially.
- SQLite lane: declared non-comparable; not run.

## 4. Snow FULL diagnostic result

`snow_full_diagnostic_v23`: 32/547 tasks attempted, **all OutOfMemory**.
Run cancelled. **No metrics produced.** Re-launch is required and
should happen sequentially (after BQ FULL completes) with a
serializing GPU lock and Snow connector creds set on the bridge
kernel before launch.

Without Snow auth, the diagnostic only produces `schema_valid` /
`parse_ok` — not engine-side `execute_ok` / `explain_ok`. This is a
known constraint, documented separately in the run-dir readout.

## 5. DBT FULL diagnostic result

**BLOCKED.** No tasks completed. Inference test (`asana001`, v4) failed
with `CUDA error: CUBLAS_STATUS_ALLOC_FAILED when calling cublasCreate`
because the GPU was already saturated by the Snow OOM threads.

Re-launch path: same — wait for bridge GPU to recover (Snow stubs to
fully drain), then launch `run_dbt_ablation.py --variants v4` over all
68 tasks. Estimated wall: ~7 hours sequentially.

DBT baseline of record: **9/68 = 13.2% task_success** from Phase 11.
Phase 23 did NOT replace this number.

## 6. Comparable / diagnostic-only status

| run_id | status | comparable to official? |
|---|---|---|
| `lite_full_diagnostic_v23_bq` | partial 14/205 | **NO** — too few samples; **diagnostic only** |
| `lite_full_diagnostic_v23_snow` | cancelled | **NO** — diagnostic only, no metrics |
| `snow_full_diagnostic_v23` | cancelled | **NO** — diagnostic only, no metrics |
| `dbt_full_diagnostic_v23` | blocked | **NO** — not run |

**Phase 23 produces ZERO official-comparable benchmark numbers.**
The single Spider2 number that remains publishable is the **DBT FULL
13.2% baseline from Phase 11**. v22 pilot50 (BQ schema_valid 54%,
exec 44%) remains the most current Lite-BQ datapoint but is a
pilot, not a FULL.

## 7. Top-10 blockers across all three benchmarks

1. **Concurrent inference vs single A100 80 GB.** Two HF models (~67 GB)
   pre-loaded leaves only ~13 GB headroom. Three concurrent
   model.generate() calls exceed it. **Fix: serialize at launch with a
   global threading.Lock before any BG runner starts; do not start
   second/third runner until first releases.**
2. **No bridge-kernel restart available from CLI.** When a thread is
   stuck in OOM-retry, only kernel restart can free it; we cannot do
   that programmatically. **Fix: lift the BG runner pattern to a
   subprocess/separate-process model so we can SIGTERM and recover.**
3. **Snow connector creds unset on bridge.** Spider2-Snow / Lite-Snow
   `execute_ok` / `explain_ok` cannot be measured. **Fix: user sets
   `SNOWFLAKE_USER`, `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_PRIVATE_KEY_PATH`
   in the bridge kernel before launch.**
4. **DBT inference template loads a separate model copy.** Patched in
   Phase 23 (`tools/remote_scripts/_dbt_inference_one.py`) to reuse
   `_MDL_EMIT` / `_TOK_EMIT`. Validated locally; not yet run end-to-end
   due to (1).
5. **Cloudflare quick-tunnel 100-second timeout.** Long inferences
   (>100 s) hit HTTP 524. **Fix:** chunk requests; or use a named
   tunnel for >100 s calls.
6. **v22 engine-compat ceiling (Phase 22 finding).** STAGE A4
   (ARRAY_CONTAINS → EXISTS UNNEST, NTH → array offset, multi-CTE
   nested aggregate, no_signature type fix) is still not implemented;
   v22 pilot50 was 6 pp short on dry_run_ok gate.
7. **Family C never chosen (Phase 22).** Shared-column-name FK
   heuristic is too weak. **Fix:** real FK signal from
   `INFORMATION_SCHEMA.KEY_COLUMN_USAGE` (BQ supports for some
   datasets) or co-occurrence-trained FK scoring on prior successful
   queries.
8. **No FULL Snow run has ever completed in this project.** Snow
   v10–v17 ran only pilot10 each. The v18+v22 stack has not been
   exercised on Spider2-Snow at all.
9. **DBT v2 governed agent (Phase 22 brief STAGE C) not built.**
   Project-map / read-before-write / dbt error parser / verifier /
   quick-fix loop are absent. The 13.2% baseline likely reflects this
   gap rather than the model's intrinsic capability.
10. **No CSV-format alignment with official evaluator (Phase 22 brief
    STAGE E).** Predictions in our run-dirs are JSONL; the official
    Spider2 evaluator may expect a different shape. Not validated.

## 8. Exact artifact paths

```
outputs/logs/spider2_full_diagnostic_state_audit.md          STAGE 0 audit
outputs/tables/spider2_full_diagnostic_infra_check.csv       STAGE 0 component check
outputs/logs/spider2_lite_full_diagnostic_lane_breakdown_v23.md   STAGE 1c
outputs/spider2_lite/runs/lite_full_diagnostic_v23_bq/
    _STARTED, predictions.jsonl (14), traces.jsonl, progress.json,
    schema_linking_recall.csv, readout.md
outputs/spider2_lite/runs/lite_full_diagnostic_v23_snow/
    _STARTED, _CANCELLED_OOM, predictions.jsonl (70), traces.jsonl,
    progress.json, readout.md
outputs/spider2_snow/runs/snow_full_diagnostic_v23/
    _STARTED, _CANCELLED_OOM, predictions.jsonl (32), traces.jsonl,
    progress.json, readout.md
outputs/REPORT_SPIDER2_FULL_DIAGNOSTIC_V23.md                this report
outputs/tables/spider2_full_diagnostic_master_matrix_v23.csv master matrix
outputs/tables/spider2_full_diagnostic_master_matrix_v23.md  master matrix
tools/remote_scripts/_phase23_infra_check.py                STAGE 0 prober
tools/remote_scripts/_phase23_launch_lite_bq_full.py         BQ FULL launcher
tools/remote_scripts/_phase23_launch_snow_full.py            Snow FULL launcher
tools/remote_scripts/_phase23_serialize_generate.py          GPU lock installer
tools/remote_scripts/_phase23_kill_snow_runs.py              Snow cancellation marker
tools/remote_scripts/_phase23_pull_artifacts.py              artifact extractor
tools/remote_scripts/_dbt_inference_one.py                   patched to reuse _MDL_EMIT
spider2_dbt_bridge/config.yaml                               local DBT config (not committed if sensitive)
```

## 9. Recommended next fixes, ranked by expected metric lift

1. **Pre-launch GPU lock + sequential runner orchestration.** Without
   this, no Phase 23 retry will succeed. Highest ROI: unblocks all 4
   benchmarks. **No metric lift directly**, but **enables every other
   metric to be measured.**
2. **STAGE A4 engine-compat library** (Phase 22 next-step lever).
   Targets the 14 dry_run_failed cases on v22 pilot50. Expected
   ceiling lift: **+6 pp on Lite-BQ dry_run_ok** to clear 50% gate.
3. **Snow connector creds → run Spider2-Snow FULL.** Establishes the
   first-ever Snow execute_ok number. Expected: any positive value
   (was always NaN until this). Ballpark from Phase 17 Snow pilot10:
   `chosen_schema_valid` was 0% with v17, but v18+ stack has not been
   tried on Snow at all — could be 30–50 % schema_valid on FULL based
   on BQ-lane analogues.
4. **DBT v2 governed agent** (Phase 22 brief STAGE C). Targeted lift
   from 9/68 → ~20–25/68 task_success on the same model, just by
   adding read-before-write + dbt-error-parser + quick-fix loop.
5. **Family C with real FK signal** (Phase 22 leftover). Should bump
   chosen rate of Family C from 0/50 → ~5–8/50 on multi-table joins,
   net Lite-BQ schema_valid +3–5 pp.
6. **Premium-overlay (closed) for failed BQ tasks** — when the v22
   stack rejects a task, fall back to a single GPT-5 / Claude Opus
   call on the same pack. This is "fair" because Spider2 allows any
   model and we still use the same closed-set pack. Net: probably
   +5–8 pp on Lite-BQ exec_ok.

## 10. ВКР-safe summary

**Can be honestly written:**
- Phase 23 piloted a multi-benchmark FULL diagnostic and identified
  GPU-memory contention as the dominant blocker for concurrent
  v18+v22 stack inference on a single A100 80 GB.
- The v22 stack was exercised against 14 of 205 Spider2-Lite-BQ tasks;
  on the OOM-clean subset (6 tasks) it produced 67 % schema_valid and
  33 % execute_ok, directionally consistent with the v22 pilot50
  baseline of 54 % / 44 %.
- The DBT-FULL `13.2%` task_success baseline (Phase 11) remains the
  only Spider2 metric publishable in this thesis until a successful
  full-pass diagnostic re-run is achieved.

**Must NOT be claimed:**
- No Spider2-Lite FULL number (203 of 205 BQ tasks were not measured).
- No Spider2-Snow FULL number (0 of 547 produced metrics).
- No new Spider2-DBT number (0 of 68 ran).
- No combined Spider2 metric across the three benchmarks.
- No improvement over the v22 pilot50 / DBT 13.2% baselines.
