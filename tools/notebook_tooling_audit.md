# Notebook Tooling Audit

Audit of the agent ↔ Colab notebook interaction loop, performed before running B1.

## Components

### 1. `scripts/run_colab_notebook.ps1` (helper)

PowerShell driver that automates VS Code's notebook UI on Windows via `WScript.SendKeys`.

- **Strict single-notebook mode**: refuses to run unless exactly one matching notebook editor is active (non-notebook tabs are fine).
- **Cell selection**: by `-CellIndex` (0-based), `-CellId` (Jupyter cell id), or `-CellText` (substring).
- **Actions**: `cell`, `current-cell`, `current-cell-and-advance`, `run-all`, `restart-and-run-all`, `run-above`, `run-current-and-below`, `interrupt-kernel`, `restart-kernel`.
- **Dispatch**: focuses the cell via VS Code keyboard navigation then sends `Shift+Enter` for run, or invokes the localized Jupyter command via the command palette for kernel actions.
- **Save**: triggers `Ctrl+S` after `WaitSeconds` if `-SaveAfterRun` (default true).
- **Output**: plain text or JSON via `-Json`.

**Limitations**:
- `WaitSeconds` is just a buffer between SendKeys and shell return — the cell may still be running after the script exits. Long-running cells need a separate completion-detection loop.
- Notebook output reflects on disk only when VS Code saves; with autosave enabled, lag is usually <2 s, but there is no guarantee.
- Cannot edit notebook cells; only focus/run them.

### 2. `.claude/run_cell.py` (agent-side cell runner)

Python wrapper around the helper that knows how to wait and read the result.

**Detection method**: polls notebook JSON every `--poll` seconds and detects completion when the cell's `execution_count` changes from its pre-run value to a non-`None` integer. v2 adds:
- A *stability check*: after detecting a change, re-reads after a short pause to confirm VS Code has finished writing.
- Periodic partial-output dumps every ~30 s for long-running cells.
- Full transcript saved to `.claude/logs/run_cell_<cellid>_<ts>.log`.
- Even on timeout, dumps whatever output is already in the cell.

**Output reading**: walks `cell.outputs[]`, concatenating `stream` text, `execute_result` text/plain, and any `error` traceback. Distinguishes:
- success (exit 0)
- cell error (exit 1, traceback present in `outputs[].output_type == "error"`)
- helper failure / cell not found (exit 2)
- timeout (exit 3)

### 3. Notebook (`notebooks/example.ipynb`)

Author-managed `.ipynb` JSON file. VS Code holds an in-memory editor model; on every change it autosaves to disk after the configured delay (default ~1 s after typing pause). External edits to the JSON file are auto-detected and the editor reloads as long as the in-memory copy is unmodified.

The ipynb uses standard nbformat 4: each cell has `id`, `cell_type`, `source`, `outputs`, `execution_count`, `metadata`. Only `code` cells get `execution_count`; on a fresh cell or after a kernel reset, `execution_count = None`.

### 4. Added cells (B1 pipeline)

| id | role | side effects on Drive |
|---|---|---|
| `ad703bcf` | B0 physical recheck | writes `outputs/logs/b0_physical_recheck.md` |
| `bd82d61f` | B1 inference + linking + EX | writes B1 predictions/metrics/summary/runlog/errors/examples + linking audit + examples |
| `05ffd516` | B0 vs B1 comparison | writes comparison CSV/MD, plot PNG, case_diff MD |
| `23bafcd6` | practice artifacts update | writes practice/{worklog,checklist,mapping}.md |
| `3ef99fef` | next-step readiness | writes `outputs/logs/next_step_readiness.md` |
| `d99a1573` | B1 final index | reads metrics, prints Drive tree + final status |
| `d41975cb` | B1 export tarball | builds `/content/diploma_b1_results_<ts>.tar.gz`, copies to `<root>/exports/`, uploads to 0x0.st (fallback file.io) |

All cells are *defensive*: each re-mounts Drive if needed, re-establishes paths in fresh kernels, and re-installs `func_timeout` / `bitsandbytes` / `transformers` if globals are missing. So they can be re-run individually after a kernel restart without re-running B0.

## Failure modes and how the loop handles them

### a) Cell completes normally
- VS Code writes the new notebook JSON within ~1 s of completion (autosave) or immediately on `Ctrl+S` from the helper.
- `run_cell.py` sees `execution_count` change, does a stability re-read, dumps outputs, exits 0.

### b) Cell raises a Python error
- VS Code writes the cell with an `outputs[].output_type == "error"` block and a fresh `execution_count`.
- `run_cell.py` detects the exec_count change *and* the error block, dumps the traceback, exits 1.

### c) Kernel was restarted (cold start)
- Defensive cells re-init: re-mount Drive (auth flow may pop in VS Code if token expired), re-install pip packages, re-load model. Total cold start for `bd82d61f` (B1 inference) ≈ 2–3 min including model reload.
- Cell A (`ad703bcf`) is the cheapest probe — completes in seconds even cold; if it succeeds, kernel + Drive are healthy.

### d) Notebook autosave is delayed
- VS Code may delay save up to its `files.autoSave` delay (default 1 s after change with `afterDelay`, or "never" if disabled).
- Detection: `run_cell.py` polls every `--poll` seconds. If VS Code hasn't saved yet, `execution_count` looks unchanged for one extra poll cycle, then catches up.
- Worst-case: if `files.autoSave` is `off`, the helper's `Ctrl+S` after `WaitSeconds` is the only save trigger; for cells longer than `WaitSeconds`, that save catches a still-running cell. Mitigation: set `WaitSeconds` ≥ expected duration *or* rely on autosave being enabled.

### e) `execution_count` never changes (cell stuck or kernel disconnected)
- `run_cell.py` reaches `--max-wait`, dumps any partial output captured so far, exits 3.
- Operator (the agent) should then check the Colab kernel state in VS Code (interrupt or restart).

### f) Notebook JSON is mid-write when polled
- Reading mid-write may yield invalid JSON.
- `run_cell.py` catches `json.JSONDecodeError` and skips that poll cycle; effective poll resolution is preserved on the next iteration.

### g) Multiple notebook windows / wrong focus
- Helper `WScript.SendKeys` requires the target VS Code window to be foreground. Helper does its own foregrounding via Windows API; in strict-single-notebook mode it refuses to act if any other notebook editor is open.
- If the agent triggers the helper while the user is interacting with another app, focus competition may misroute the keystroke. Mitigation: do not run other GUI activity during cell dispatch.

## Best practices (used in this project)

1. **One detection method, well-implemented**: trust `execution_count` change; do not race-detect with output markers. Stability check (re-read after short pause) absorbs save-lag races.
2. **Defensive cells**: each cell can run cold or warm. No hidden inter-cell state required.
3. **Drive is single source of truth** for project artifacts; local notebook file is the inter-process channel between agent and Colab kernel.
4. **Logging**: every `run_cell.py` invocation writes a timestamped log to `.claude/logs/`, so the loop is auditable after the fact.
5. **Smoke tests before heavy runs**: run `print(0)` cell first to confirm kernel is alive; then a cheap Drive-write cell to confirm Drive is mounted; only then trigger inference.

## Open issues (not blocking)

- 0x0.st export depends on a third-party host. If it's down, fallback is file.io; if both fail, the tarball still exists in Drive at `<root>/exports/`. A direct-from-Drive download would require rclone or Drive API auth, which is not currently set up locally.
- `--marker` flag intentionally not added: trusting `execution_count` is simpler and avoids false-positive detection (a cell could print the marker, then fail downstream).
