# run_cell.py changelog

## v3 — 2026-04-25 (tools/ migration + status sidecar + focus diagnostics)

### Moved
- Script and logs migrated from `.claude/` to `tools/` per project layout decision: `tools/run_cell.py`, logs to `tools/logs/run_cell_<cellid>_<UTC>.log`.

### Added
- **Status sidecar** `.json` next to every `.log`. Schema: `cell_id`, `status` (`ok` / `cell_error` / `invocation_failed` / `timeout` / `focus_suspect`), `exit_code`, `started_at`, `ended_at`, `elapsed_seconds`, `pre_exec`, `new_exec`, `helper_rc`, `output_tail`. Lets a caller scan many runs by reading just the JSON files, no transcript parsing needed.
- **`focus_suspect` status**: when `execution_count` never changes AND helper exited rc=0, the script logs an explicit "SUSPECT FOCUS FAILURE" diagnostic and finalises with `status="focus_suspect"`. Distinguishes *the keystroke went somewhere wrong* from *the cell legitimately took longer than `--max-wait`* (the latter is plain `timeout`). Exit code stays 3 in both cases.
- **Helper rc surfaced** in sidecar so the caller can correlate.

### Unchanged
- v2.1 focus fix (`focus_notebook` via `code -r`) is retained.
- v2 features: stability re-read, partial-output dumps every ~30 s, dump-on-timeout, helper-timeout differentiation.

## v2.1 — 2026-04-25 (focus fix)

Critical fix discovered during smoke test.

### Root cause
The agent's PowerShell tool opens its stdout/stderr as readonly tabs in VS Code (e.g. `\temp\readonly\PowerShell tool output (cmcxl6)`). These tabs become the focused editor, displacing the notebook tab. The helper script's strict-single-notebook check still passes (only one *notebook* editor open), but its mouse-click-on-editor-surface step targets the wrong editor's bounding rect — manifesting in the trace as `mouse click editor surface at 1028,-999` (off-screen Y coordinate). SendKeys then types into nothing useful, the cell never runs, `execution_count` doesn't change, and v2 times out.

### Fix
Added `focus_notebook(log)` step that runs `code -r <notebook_path>` immediately before each helper invocation. `code -r` reuses the existing VS Code window and brings the target file's tab to the foreground. A 1.5 s sleep follows to let VS Code finish the tab switch.

`code` CLI is searched in: explicit path `D:\Programs\Microsoft VS Code\bin\code.cmd` (matches helper's discovery), `code.cmd`, then `code`. If none found, logs a warning and continues — the loop will then likely time out, but at least the failure is visible.

### Effect
With this fix, every `run_cell.py` invocation explicitly re-focuses the notebook tab before sending keys, so PowerShell-tool-opened readonly tabs no longer break the loop.

## v2 — 2026-04-25

Backup of v1: `run_cell.py.v1.bak`

### Added
- **Persistent transcript log** at `.claude/logs/run_cell_<cellid>_<UTC>.log`. Every invocation writes a timestamped log of helper invocation, polling events, partial-output dumps, and final outcome. Lets the agent reconstruct what happened on any past cell run.
- **Stability re-read after detection**: when `execution_count` changes, sleep up to 2 s and re-read the notebook; if exec_count flipped again or JSON failed to parse, continue polling. Absorbs the race where VS Code is mid-write while we're polling.
- **Periodic partial-output dumps**: every ~30 s of waiting, log the tail (last 600 chars) of the cell's current output. Lets long-running cells (B1 inference) be observed without blocking the agent on stale output.
- **Dump partial output on timeout** (exit 3): even if `execution_count` never changed, the agent gets to see whatever the cell printed before timing out.
- **Helper-timeout differentiation**: if the helper itself hangs >180 s (very rare), exits with `helper_timeout` status rather than blocking forever.
- **Helper-failure logging**: on non-zero helper rc, logs first 500 chars of stdout+stderr so the agent can diagnose.
- **`--log-file` override** for callers that want to direct the transcript elsewhere.

### Changed
- Polling loop catches `json.JSONDecodeError` when the notebook is mid-write and skips that cycle (was previously raising).
- Default `--initial-wait` lowered from 12 to 8 s; the loop polls afterwards anyway, so the buffer doesn't need to cover full cell duration.
- Cell output reading now also flattens `error` traceback lines (was only ename:evalue), giving full stack trace in the transcript.

### Unchanged
- Exit-code contract: 0 success / 1 cell-error / 2 invocation-failure / 3 timeout.
- Detection method: `execution_count` change is the single source of truth (no marker flag, intentionally — see audit doc for rationale).
- Helper invocation params: `cell` action with `-CellId X -WaitSeconds N`.
- Stdout still prints full cell output between `--- CELL OUTPUT ---` / `--- END ---` markers for unattended-mode parsing.

## v1 — 2026-04-25 (initial)

- Basic exec_count polling, helper invocation, output dump.
- No persistent log; output only to stdout.
- No stability check; no partial-output dumps; no timeout dump.
