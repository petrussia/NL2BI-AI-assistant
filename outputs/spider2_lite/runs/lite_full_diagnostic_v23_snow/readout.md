# Spider2-Lite-Snow FULL diagnostic — `lite_full_diagnostic_v23_snow` (CANCELLED)

> **STATUS: CANCELLED.** 70 of 207 tasks "processed" but every prediction
> is an error — first 15 from CUDA OOM under concurrency, the next 55+
> from a deliberate stub-abort installed to free the BG thread to drain
> its task list quickly.
>
> No useful schema_valid / parse_ok numbers were obtained.

## Final state

| metric | value | rate |
|---|---:|---:|
| n_processed | 70 / 207 | — (incomplete) |
| chosen_schema_valid | 0 | 0% |
| parse_ok | 0 | 0% |
| OutOfMemoryError (real engine fail) | 15 | 21.4% |
| RuntimeError (stub-aborted, not real failure) | 55 | 78.6% |
| executed engine-side | NA — Snow connector not authenticated on bridge kernel |

## Why cancelled

The Snow runners were launched concurrently with the Lite-BQ FULL
runner. With both Qwen3-Coder-30B (planner) and Qwen2.5-Coder-7B
(emitter) already loaded (~67 GB VRAM), only ~13 GB remained for
activation memory. Concurrent forward passes from three BG threads
exceeded available memory; every Snow task OOM'd at `_v18_plan_local`
during planner generate.

A serializing lock was added mid-run (`_phase23_serialize_generate.py`)
and the planner / emitter generators were stub-aborted to let the
thread drain its task list quickly without further wasting GPU. The
remaining task slots fast-failed with `RuntimeError: PHASE23_SNOW_ABORTED`.

## Next actions

1. Wait for bridge to be in clean state (no concurrent BG runners).
2. Restore real `_v18_plan_local` / `_gen_emitter_local` from the snow
   runner module (in-globals stub overwrite is non-persistent if kernel
   restarts).
3. Relaunch as `lite_full_diagnostic_v23_snow_v2` **sequentially**
   AFTER BQ FULL completes.
4. Expected wall: 207 tasks × ~30 s (Family B only, no planner retry
   loop in some configs) ≈ 1.7 h.
