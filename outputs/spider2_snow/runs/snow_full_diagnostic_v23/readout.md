# Spider2-Snow FULL diagnostic — `snow_full_diagnostic_v23` (CANCELLED)

> **STATUS: CANCELLED.** 32 of 547 tasks attempted, all failed with CUDA
> OOM under concurrent inference with the Lite-BQ FULL runner.
>
> Stub-abort was installed but did not propagate before the kernel
> stalled.

| metric | value | rate |
|---|---:|---:|
| n_processed | 32 / 547 | — (incomplete) |
| OutOfMemoryError | 32 | 100.0% |
| chosen_schema_valid | 0 | 0% |
| parse_ok | 0 | 0% |
| executed engine-side | NA — Snow connector not authenticated on bridge kernel |

Same root cause as `lite_full_diagnostic_v23_snow` — concurrent
inference exceeded GPU memory budget. **Cancelled.** Relaunch as
`snow_full_diagnostic_v23_v2` sequentially after BQ FULL completes
(estimated 547 × ~30 s ≈ 4.6 h).

**Important policy note.** Even after sequential relaunch, the Snow
diagnostic still produces only `schema_valid` (AST-checked against
live catalog of 586,472 columns) and `parse_ok` (sqlglot Snowflake
dialect). Engine-side `execute_ok` / `explain_ok` requires Snow
connector creds (`SNOWFLAKE_USER`, `SNOWFLAKE_ACCOUNT`,
`SNOWFLAKE_PRIVATE_KEY_PATH` or `SNOWFLAKE_PASSWORD`) on the bridge
kernel. Phase 23 STAGE 0 audit confirmed those env vars are unset;
without user action, this run can never produce execution metrics
comparable to the official Spider2-Snow benchmark.
