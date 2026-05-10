# Spider2 Phase 24 — stable sequential Lite-BQ retry with engine-compat rewrites

_Generated: 2026-05-10 | branch: `experiments/denis` | parent commit: `5f6a39b` (Phase 23)_

> **Scope.** Phase 24 ships (a) a Drive-file GPU lock that enforces ONE
> inference run at a time; (b) a STAGE A4 BigQuery engine-compat
> rewrite library; (c) a fresh Lite-BQ pilot50 measured against the
> Phase 22 baseline; (d) Lite-BQ FULL 205 — **NOT launched**, pilot50
> gate not cleared.
>
> **Outcome:** orchestration is fixed (no OOM, no concurrency), but
> the v22 metrics did NOT improve. v22's `sv 54% / exec 44%` is
> reproduced exactly: `sv 54% / exec 44%`. The 6 pp gate gap remains.
> Snow and DBT remain DEFERRED — not run in this session.

---

## 1. Hard status

| field | value |
|---|---|
| Branch | `experiments/denis` |
| Phase 23 parent | `5f6a39b` |
| Phase 24 commit | `<assigned at STAGE 7>` |
| Bridge | `corpus-vatican-...trycloudflare.com` (alive) |
| GPU | A100 80 GB; 73–76 GB allocated to planner+emitter; 3–6 GB free during forward passes |
| BQ auth | OK (`project-0e0fc8a5-27b1-4e00-912`) |
| Snow auth | unset (NOT used in Phase 24) |
| DBT remote | reachable (NOT used in Phase 24) |
| Push | NOT executed |

## 2. Why Phase 23 was an orchestration failure (not a model failure)

Phase 23 launched three BG runners concurrently. Models already used
79.5 GB of the A100's 80 GB → ~6 GB headroom. A single 30B-MoE forward
pass spikes activation memory to 30–40 GB. Three concurrent calls →
cascading CUDA OOM that:

1. Failed every Snow task (47 real OOMs across two Snow runs).
2. Poisoned the BQ FULL runner's memory state, which froze in slow
   OOM-retry (stuck at 14 / 205, no further progress).
3. Blocked DBT inference (`CUBLAS_STATUS_ALLOC_FAILED`).
4. The leftover Phase 23 BG threads were not killable from `/exec` —
   one held `_PHASE23_GEN_LOCK` permanently and had to be terminated
   by injecting `SystemExit` via `ctypes.PyThreadState_SetAsyncExc`.

The v22 SQL stack itself was untouched. Phase 24's pilot50 confirmed
this: with all concurrency removed, the v22 stack reproduces exactly
its known metrics.

## 3. GPU lock + sequential runner — what was built

Three components.

### 3.1 `repo/src/evaluation/gpu_lock_v24.py`

Drive-file exclusive lock at `<DRIVE>/outputs/runtime/gpu_inference.lock`:

- Atomic `O_CREAT | O_EXCL`; payload JSON `{run_id, host, pid, ts_start}`.
- Acquire fails if a live PID on the same host already holds the lock.
- Stale locks (foreign host or dead PID) force-broken with prior
  content recorded in `_FORCE_BROKEN`.
- Release idempotent; orchestrator releases on completion AND on
  exception (try/finally).

### 3.2 `tools/run_spider2_sequential_v24.py`

Sequential single-benchmark orchestrator. Refuses:
- Lock held by different live PID.
- `--full` if pilot50 metrics file does NOT show
  `chosen_schema_valid >= 0.60 AND execute_ok >= 0.50`.

Internally uses a `threading.Lock` around all `model.generate` calls
to serialize even within the runner thread.

### 3.3 v23 cleanup

`tools/remote_scripts/_phase24_cleanup_v23_threads.py`:
- Stubbed `_v18_plan*`, `_gen*`, `_gen_planner*`, `_gen_emitter*` with
  `RuntimeError('PHASE24_V23_THREAD_ABORTED')`.
- Force-released `_PHASE23_GEN_LOCK` (was held by stuck thread).
- `torch.cuda.empty_cache()` + `gc.collect()`.
- Marked all v23 run dirs that aren't `_DONE` with `_CANCELLED_OOM`.
- One stuck thread had to be terminated via `PyThreadState_SetAsyncExc`
  (mid-CUDA-call thread did not respond to stub-abort).
- `model.generate` instance-level wrappers from Phase 23 were removed
  (`del m.generate`) so subsequent calls use the unwrapped class
  method — eliminates the leftover Phase 23 lock dependency.

## 4. STAGE A4 engine-compat rewrite library

`repo/src/evaluation/bigquery_engine_compat_v24.py` ships 6 rules.
v22 trace analysis showed 14 `bq_dry_run_failed` cases distributed as:
`unrecog_name 12, AND_int 4, nested_agg 2, ARRAY_CONTAINS 1, other 9`.

| # | rewrite | active | smoke-test | pilot50 emit count | helpful |
|---|---|---|---|---:|---:|
| 1 | `ARRAY_CONTAINS(arr, x)` → `EXISTS UNNEST` | YES | passes | 1 | 0 |
| 2 | `NTH(arr, n)` → `arr[OFFSET(n-1)]` | YES | passes | 0 | — |
| 3 | `UNNEST(a.b.c) AS x` (≤3-seg) → chained | YES | passes | 0 | — |
| 4 | `SUM(SUM(x))` etc. | flagged-only (CTE rewrite needs GROUP-BY scope analysis; semantically risky) | passes | 0 | — |
| 5 | window + GROUP BY coexist | flagged-only | passes | 0 | — |
| 6 | `AND <bare_int_id>` → `AND (<id> != 0)` | YES (with `KW_BLOCK` guard) | passes | 0 | — |

Rewrites are applied as a parallel candidate variant: for each base
candidate (Family A / B / C), an `<X>_v24` candidate is added if the
rewrite changes the SQL. The selector tie-break prefers original
families on equal-score ties, so `_v24` only wins when it produces a
**strictly better dry_run outcome**.

## 5. Lite-BQ pilot50 result vs Phase 22

`outputs/spider2_lite/runs/lite_bq_v24_pilot50/`

| metric | Phase 22 v22 pilot50 | Phase 24 v24 pilot50 | delta | gate |
|---|---:|---:|---:|---|
| n | 50 | 50 | — | — |
| plan_validation_ok | 27 (54%) | 27 (54%) | 0 | — |
| chosen_schema_valid | 27 (54%) | 27 (54%) | 0 | ≥ 60% |
| parse_ok | 49 (98%) | 49 (98%) | 0 | — |
| execute_ok (BQ dry_run) | 22 (44%) | 22 (44%) | 0 | ≥ 50% |
| chosen_family A | 43 | 43 | 0 | — |
| chosen_family B | 7 | 7 | 0 | — |
| chosen_family A_v24 / B_v24 | — | 0 / 0 | — | — |
| Engine rewrite emitted | — | 1 (`array_contains`) | new | — |
| Engine rewrite **helpful** (won dry_run vs original) | — | **0** | new | — |
| Wall time | 60 min | 108 min | +80% | — |

Phase 24 reproduced v22 metrics **exactly** — the orchestration fix
restored the stack's expected behaviour, but the engine-compat
rewrites had **zero net impact**.

### 5.1 Why rewrites had zero impact

Drilling into the 14 `bq_dry_run_failed` cases on this pilot50:

| category | count | rewrite would fire | rewrite would help | reason rewrite didn't help |
|---|---:|---|---|---|
| `unrecog_name` (column without JOIN) | 5 | NO — STAGE A3 territory, not A4 | — | requires JOIN-aware fix (Family C with real FK signal); deferred to Phase 25+ |
| `nested_agg` (`SUM(SUM(x))`) | 2 | NO — flagged-only | — | requires GROUP-BY scope analysis to safely rewrite to CTE; intentionally not auto-rewritten |
| `AND_int` | 3 | NO | — | error is **BOOL AND BOOL AND INT** caused by **unquoted date literals** like `AND (2023-10-01)` parsed as `2023-10-1 = 2012`, not by bare integer columns. My regex targeted `\bAND\s+<bare_id>` which doesn't match parenthesized arithmetic. Different root cause than the v22 trace sample suggested. |
| `ARRAY_CONTAINS` | 1 | YES — A_v24 emitted | NO — A_v24 dry_run still failed because the SQL had **other** errors beyond ARRAY_CONTAINS (additional invalid `STRUCT` access). Fixing one error doesn't unlock dry_run when a candidate has multiple. |
| `other` | 3 | NO | — | heterogeneous (e.g., STRUCT field type mismatch, RPC errors) — case-by-case |

**Honest read.** The Phase 24 rewrite library targeted the wrong
root causes. v22 trace analysis suggested AND-on-int was a bare-int
issue; the Phase 24 traces show it's actually a **date-literal
quoting issue** at the model-output layer. Real fixes needed:

1. JOIN-aware Family C with FK signal (5 cases) — biggest leverage.
2. Date-literal post-render fix (3 cases) — unquoted `2023-10-01` →
   `DATE '2023-10-01'`.
3. CTE wrap for nested aggregates (2 cases) — needs scope analysis.
4. Multi-error candidate handling — current selector evaluates
   candidates as binary pass/fail per dry_run; chained rewrites
   could fix one issue at a time.

## 6. Gate decision

| gate condition | required | observed | passed |
|---|---|---|---|
| `chosen_schema_valid >= 0.60` | 60% | **54%** | **NO** (-6 pp) |
| `execute_ok >= 0.50` | 50% | **44%** | **NO** (-6 pp) |

**Gate FAILED. Lite-BQ FULL 205 NOT launched** per Phase 24 strict
policy ("Если pilot50 не прошёл gate: FULL НЕ запускать").

## 7. Lite-BQ FULL 205 result

**NOT EXECUTED.** Per gate policy, no FULL run was launched. The
FULL launcher refuses unless the pilot50 metrics file shows the
gate cleared; this is enforced both at the local CLI (gate-check
before bridge call) and at the bridge runtime (lock acquisition).

## 8. Exact artifact paths

```
outputs/REPORT_SPIDER2_PHASE24_LITE_BQ.md                    this report
outputs/logs/spider2_phase24_state_audit.md                  STAGE 0
outputs/logs/spider2_phase24_orchestration_design.md         STAGE 1
outputs/logs/spider2_phase24_runtime_cleanup.md              STAGE 2
repo/src/evaluation/gpu_lock_v24.py                          STAGE 1 module
repo/src/evaluation/bigquery_engine_compat_v24.py            STAGE 3 module
tools/run_spider2_sequential_v24.py                          STAGE 1 orchestrator
tools/remote_scripts/_phase24_state_probe.py                 STAGE 0 prober
tools/remote_scripts/_phase24_cleanup_v23_threads.py         STAGE 2 cleanup
tools/_phase24_decode_pull.py                                artifact pull decoder
outputs/spider2_lite/runs/lite_bq_v24_pilot50/
    _STARTED, _DONE, predictions.jsonl (50), traces.jsonl,
    progress.json, metrics.csv, error_taxonomy.csv,
    engine_rewrite_stats.csv, family_breakdown.csv,
    schema_linking_recall.csv, readout.md
```

## 9. Top remaining blockers (after Phase 24)

1. **6 pp dry_run gate gap** — STAGE A4 rewrites missed the actual
   failure modes. Real top-3 fixers needed:
   - JOIN-aware Family C with FK signal (`unrecog_name` × 5)
   - Date-literal post-render (`unquoted YYYY-MM-DD` × 3)
   - CTE wrap for nested aggregates (`SUM(SUM(x))` × 2)
2. **GPU memory budget** — A100 80 GB with planner 30B + emitter 7B
   leaves only 3–6 GB headroom; this is enough for ONE forward pass
   at a time but slow (5–6 min/task in pilot50 vs 72 s/task baseline
   when memory was less crowded). Throughput improvement requires
   either model-swap-based unloading or a larger GPU.
3. **Snow connector creds still unset** — Snow benchmarks remain
   blocked from `execute_ok` measurement. User action required.
4. **DBT v2 governed agent** still unbuilt; 13.2% baseline unchanged.
5. **Multi-error candidate handling** — the `_v24` parallel-candidate
   pattern only helps when ONE rewrite unlocks dry_run. For SQL with
   multiple errors, one fix isn't enough.
6. **No FULL Snow run** has ever completed in this project.

## 10. Next recommendation for Snow / DBT

- **Spider2-Snow.** Reuse the Phase 24 lock + sequential orchestrator.
  Once user sets `SNOWFLAKE_USER` / `SNOWFLAKE_ACCOUNT` /
  `SNOWFLAKE_PRIVATE_KEY_PATH` on the bridge kernel, Phase 25 can
  launch sequentially (lock-protected). Estimated wall:
  547 + 207 ≈ 754 tasks × ~30 s = 6.3 h.
- **Spider2-DBT.** Phase 23 patched
  `tools/remote_scripts/_dbt_inference_one.py` to reuse `_MDL_EMIT`.
  Once the lock is free, run sequentially. Real lift comes from the
  v2 governed-agent (read-before-write + dbt error parser + verifier
  + quick-fix loop) — expected 9/68 → 20–25/68.
- **Lite-BQ retry strategy.** STAGE A4 needs to be redesigned around
  the actual failure-mode breakdown. Priority order for Phase 25:
  1. JOIN-aware Family C with FK signal (biggest leverage; 5 cases).
  2. Date-literal post-render fix (3 cases).
  3. CTE wrap for nested aggregates (2 cases).
- **Sequential lock policy from Phase 24 must NOT be relaxed** as
  long as both planner and emitter remain pinned to VRAM. To
  parallelize, one model must be unloaded first.

---

## Honest summary for ВКР

- **Phase 24 GPU-orchestration fix: SUCCESS.** No OOM, no concurrency
  contention, lock works.
- **Phase 24 STAGE A4 rewrites: METRIC-NEUTRAL.** Rewrites compile
  correctly and are emitted as parallel candidates, but they did not
  unlock any failed dry_run. Root cause: trace-driven category
  analysis from Phase 22 misidentified the actual failure modes.
- **v22 metric reproduced exactly:** sv 54% / exec 44% on the same
  Lite-BQ pilot50 task list — confirms the v22 stack itself is
  reproducible and the Phase 23 OOM was purely a runtime issue.
- **DBT 13.2% baseline (Phase 11) remains the only publishable
  Spider2 number.** Phase 24 changes do not affect this.
