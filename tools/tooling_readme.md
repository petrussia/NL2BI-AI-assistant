# Agent ↔ Colab Notebook Tooling

Local-side wrappers around `scripts/run_colab_notebook.ps1` so the agent can drive the Colab-attached notebook in a continuous loop: dispatch a cell → wait for completion → read output → make a decision.

## Files in this directory (`tools/`)

| File | Purpose |
|---|---|
| `run_cell.py` | Dispatch one cell, wait for completion, dump output. v3: focus-fix + status JSON sidecar + focus-failure suspicion. Logs to `logs/`. |
| `notebook_status.py` | Quick view of all cells: id / type / exec_count / outputs count / last lines. Supports `--full <id>`, `--json`, `--save-json PATH`. |
| `notebook_tooling_audit.md` | Full audit of the dispatch+detection loop and its failure modes. |
| `run_cell_changelog.md` | What changed v1 → v2 → v2.1 → v3 and why. |
| `tooling_readme.md` | This file. |
| `tool_manifest.md` | Single index of every tool with status (active/backup/legacy). |
| `tooling_stability_report.md` | Smoke-test verdict. |
| `_audit_nb.py` | Legacy single-purpose cell lister (superseded by `notebook_status.py`). |
| `logs/` | Per-invocation transcripts (`.log`) and structured status sidecars (`.json`). |
| `backups/run_cell.py.v1.bak` | First version (no focus fix). |
| `backups/_add_cell_*.py` | One-shot helpers used to insert specific cells via direct JSON edit (used when NotebookEdit hits the 25k-token render cap). Kept for provenance. |

Claude Code config remains in `.claude/`: `settings.json` and `settings.local.json` (gitignored personal allowlist).

## Two parallel mechanisms

There are two ways to drive the kernel from the agent. They have very different reliability profiles — pick by use case.

### A. SendKeys (`run_cell.py` → helper PowerShell)

Drives VS Code via `WScript.SendKeys`. **Fragile in agent context**: every Claude tool call opens its stdout/stderr as a readonly editor tab in VS Code, which steals focus from the notebook tab. The helper then mis-routes its keystrokes and the cell never runs (status `focus_suspect` in the run sidecar). Works fine when *you* manually click cells in VS Code, but unreliable when the agent triggers it.

Use SendKeys only when the bridge is unavailable.

### B. Bridge tunnel (`AGENT_BRIDGE_SETUP` cell + `exec_remote.py`) — preferred

You run the `AGENT_BRIDGE_SETUP` cell once per Colab session (one Shift+Enter). It starts a Flask server inside the kernel and exposes it via a free Cloudflare tunnel; the cell prints `BRIDGE_URL: https://...trycloudflare.com`. The agent saves this URL to `tools/.bridge_url`, then uses `exec_remote.py` to send Python code, list files, or download artifacts directly over HTTPS. No SendKeys, no focus dependency.

```bash
# After running the bridge cell once and saving the URL:
python tools/exec_remote.py --health
python tools/exec_remote.py --code "import os; print(os.listdir('/content/drive/MyDrive/diploma_plan_sql/outputs'))"
python tools/exec_remote.py --ls /content/drive/MyDrive/diploma_plan_sql/outputs/predictions
python tools/exec_remote.py --download /content/drive/MyDrive/diploma_plan_sql/exports/diploma_b1_results_20260425T150459Z.tar.gz --to ./outputs.tar.gz
```

## Common workflows

### Dispatch a cell and wait for it (legacy SendKeys)
```bash
python tools/run_cell.py ad703bcf --max-wait 60 --poll 4 --initial-wait 6
```
Exit codes: 0 ok / 1 cell error / 2 invocation failure / 3 timeout (`focus_suspect` if helper rc=0 + no exec change).
Transcript goes to `tools/logs/run_cell_ad703bcf_<UTC>.log`.
Status sidecar JSON: `tools/logs/run_cell_ad703bcf_<UTC>.json`.

### See what's in the notebook right now
```bash
python tools/notebook_status.py
python tools/notebook_status.py --cell-id ad703bcf --cell-id bd82d61f
python tools/notebook_status.py --full bd82d61f                       # full output of one cell
python tools/notebook_status.py --json                                # JSON to stdout
python tools/notebook_status.py --save-json tools/logs/snapshot.json  # JSON to file
```

### Insert a new cell via direct JSON edit
Use one of the `_add_cell_*.py` patterns; they bypass NotebookEdit when the rendered notebook exceeds the tool's 25k-token cap. Each script reads the JSON, appends a cell with a fresh `uuid.uuid4().hex[:8]` id, and writes back with `indent=1`.

## Loop semantics

- **Single source of truth for completion** is the cell's `execution_count` flipping from its pre-run value to a new non-None integer. v2 adds a 2 s stability re-read to absorb the race where VS Code is mid-write while we poll.
- **Stdout streams** in `outputs[]` are consumed cumulatively; the last `--last-lines` are shown in terse status.
- **Error detection** is `any(o.output_type == "error" for o in outputs)`; that flips the exit code to 1 and dumps the traceback.
- **Timeouts** dump whatever output exists — useful when the kernel disconnects mid-run.

## Conventions for cells in `notebooks/example.ipynb`

- Each cell starts with a unique `MARKER = '<NAME>'` constant and `print(MARKER)` near the start, so the transcript log makes it obvious which cell ran.
- Each cell ends with `print('WROTE', path)` lines for every Drive write, so the transcript shows side effects.
- Cells are *defensive*: re-mount Drive if missing, re-install pip packages if missing, re-load model if globals lost. Safe to re-run individually after a kernel restart.
- Heavy artifacts go to `/content/drive/MyDrive/diploma_plan_sql/` (Drive). The local `.ipynb` is only a control channel; don't store project artifacts there.
