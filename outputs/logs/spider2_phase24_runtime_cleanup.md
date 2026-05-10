# Phase 24 — STAGE 2 runtime cleanup log

## Pre-cleanup state (post-Phase 23)

- GPU free: 6.13 / 79.25 GB
- Alive `_runner` threads: 2
  - `Thread-632 (_runner)` — Lite-BQ FULL (Phase 23) — stuck mid-OOM-retry
  - `Thread-640 (_runner)` — Snow / Spider2-Snow runner — slow stub-abort iteration
- v23 lock `_PHASE23_GEN_LOCK` was **held** by a stuck thread.

## Cleanup actions

| step | action | result |
|---|---|---|
| 1 | Replace v23 generator helpers (`_v18_plan`, `_v18_plan_local`, `_gen`, `_gen_planner`, `_gen_planner_local`, `_gen_emitter`, `_gen_emitter_local`) with `RuntimeError('PHASE24_V23_THREAD_ABORTED')` stubs in shared globals | done |
| 2 | Force-release `_PHASE23_GEN_LOCK` (was held) | done |
| 3 | `torch.cuda.empty_cache()` + `gc.collect()` (twice) | GPU free 6.13 → 6.02 GB (no significant difference, model weights still loaded) |
| 4 | Mark all v23 run dirs that aren't `_DONE` with `_CANCELLED_OOM` | done |
| 5 | Upload `gpu_lock_v24.py` + `bigquery_engine_compat_v24.py` to bridge eval dir | done |

## Post-cleanup state

- GPU free: ~6 GB (model weights still pinned to VRAM; sufficient for ONE
  forward pass at a time — confirmed by v22 pilot50 baseline)
- v23 threads still listed as alive but iterate via stubs only — no new
  GPU allocations from them
- v23 GEN_LOCK released; new v24 threads can acquire fresh `_PHASE24_GEN_LOCK`
- Drive lock dir `outputs/runtime/` not yet created (will be created on
  first Phase 24 lock acquire)

## What we did NOT do

- Did NOT restart bridge kernel (per session policy: "Не перезапускать
  kernel без необходимости")
- Did NOT unload model weights (saves ~30 minutes of reload time at the
  start of pilot50)
- Did NOT kill v23 BG threads (Python doesn't permit thread.kill())

## Verdict

Runtime is in a clean-enough state to launch a SEQUENTIAL Phase 24
pilot50 — the v23 threads are no-ops at runtime cost (stub-abort) and
won't compete for GPU. Pre-launch GPU budget: 6 GB headroom is the same
as v22 pilot50, which ran successfully.

Next: STAGE 3 module already shipped (`bigquery_engine_compat_v24.py`).
STAGE 4: launch `lite_bq_v24_pilot50` via
`tools/run_spider2_sequential_v24.py --benchmark lite_bq --pilot50`.
