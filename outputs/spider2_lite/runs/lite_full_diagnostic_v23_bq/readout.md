# Spider2-Lite-BQ FULL diagnostic — `lite_full_diagnostic_v23_bq` (PARTIAL)

> **STATUS: PARTIAL.** 14 of 205 BQ tasks completed before the BG runner
> got stuck in deep OOM-retry on its current generate() call after
> concurrent Snow runners exhausted the GPU's free headroom.

| metric | value | rate |
|---|---:|---:|
| n_processed | 14 / 205 | — |
| plan_validation_ok | 4 | 28.6% |
| chosen_schema_valid | 4 | 28.6% |
| parse_ok | 6 | 42.9% |
| execute_ok (BQ dry_run) | 2 | 14.3% |
| chosen_family_A | 5 | 35.7% |
| chosen_family_B | 1 | 7.1% |
| **OutOfMemoryError** (failed mid-task) | **8** | **57.1%** |

## Non-OOM subset (6 tasks)

| task | family | schema_valid | parse_ok | dry_run_ok |
|---|---|---|---|---|
| bq001 | A | False | True | False |
| bq002 | A | True | True | False |
| bq009 | A | False | True | True |
| bq010 | A | True | True | False |
| bq011 | B | True | True | True |
| bq019 | A | True | True | False |

On the 6 non-OOM tasks: **4/6 schema_valid (67%)**, **2/6 dry_run_ok (33%)**.
Sample is too small to draw a reliable comparison to v22 pilot50
(`schema_valid 54% / dry_run_ok 44%`). The non-OOM subset rate is
broadly consistent with pilot50 within the noise floor.

## Why partial — root cause

The run launched concurrently with two Snow BG runners that were
designed for **no_execute=True** (no engine-side execute_ok needed).
With 79.5 / 80 GB GPU memory pre-allocated to the planner+emitter
weights, only ~6 GB headroom remained. Each model.generate() forward
pass needed ~10–40 GB of activation memory; concurrent calls from
three threads triggered cascading OOMs that consumed (and never
released) memory, leaving the BQ runner stuck in a slow OOM-retry
loop.

Root cause is the **lack of a serializing GPU lock at launch time**.
A lock was installed mid-run via `_phase23_serialize_generate.py` —
but by then the BQ runner had already poisoned its own memory state
with allocations from failed forward passes.

## Next actions

1. Restart bridge kernel (or wait for it to recover after empty_cache).
2. Re-launch BQ FULL `lite_full_diagnostic_v23_bq_v2` in **isolation**
   (no concurrent Snow / DBT inference threads).
3. Estimated wall: pilot50 was 60 min for 50 tasks → 205 tasks ≈ 4.1 h.
4. Then sequentially run Snow (Spider2-547 + Lite-Snow-207) with the
   serializing lock pre-installed.
