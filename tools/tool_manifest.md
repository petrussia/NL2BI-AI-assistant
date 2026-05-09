# Tool Manifest

Single index of every tool the agent uses to drive the Colab-attached notebook on Drive.

| Name | Path | Status | Purpose | Keep? |
|---|---|---|---|---|
| `run_cell.py` | `tools/run_cell.py` | active | Dispatch one notebook cell, force-focus the notebook tab via `code -r`, wait for completion via `execution_count` polling, dump output, write `.log` + `.json` sidecar to `tools/logs/`. v3. | yes |
| `notebook_status.py` | `tools/notebook_status.py` | active | Quick view of all/selected cells (id, exec_count, outputs, last lines, error flag). Supports `--full <id>`, `--json`, `--save-json PATH`. | yes |
| `exec_remote.py` | `tools/exec_remote.py` | active | Talks to the Colab kernel directly over HTTP via the cloudflared tunnel that `AGENT_BRIDGE_SETUP` cell starts. Bypasses SendKeys completely — no VS Code focus required. Supports `--health`, `--code`, `--code-file`, `--ls`, `--download`. URL read from `tools/.bridge_url` or `--url` flag. | yes |
| `.bridge_url` | `tools/.bridge_url` | runtime artifact | Persisted bridge URL written by the agent after reading it from the notebook cell output. Shared between `exec_remote.py` invocations. | yes (gitignore) |
| `bridge_status.md` | `tools/bridge_status.md` | active | Local mirror of `outputs/logs/bridge_status_drive.md` — endpoint, probes, globals access, limits. | yes |
| `artifact_recheck.md` | `tools/artifact_recheck.md` | active | Local mirror of `outputs/logs/artifact_recheck_drive.md` — required-artifact checklist with sizes. | yes |
| `remote_scripts/01_bridge_globals_import.py` | `tools/remote_scripts/01_bridge_globals_import.py` | active | One-shot per session: copies `model`, `tokenizer`, helpers from notebook `__main__` into bridge exec scope. |
| `remote_scripts/02_recheck.py` | `tools/remote_scripts/02_recheck.py` | active | Bridge write test + 25-artifact recheck on Drive; writes `outputs/logs/{artifact_recheck_drive,bridge_status_drive}.md`. |
| `remote_scripts/03_smoke25_subset_audit.py` | `tools/remote_scripts/03_smoke25_subset_audit.py` | active | Audits `data/spider/subsets/smoke_25.json`; writes `outputs/logs/smoke25_subset_audit.md`. |
| `remote_scripts/04b_smoke25_b0_and_b1_bg.py` | `tools/remote_scripts/04b_smoke25_b0_and_b1_bg.py` | active | Inference dispatcher: starts a daemon thread that runs B0 then B1 on smoke25, saves predictions incrementally, writes per-step entries to `outputs/logs/smoke25_bg_task_log.txt`. Returns immediately so Cloudflare quick-tunnel timeout (~100 s) is never hit. |
| `remote_scripts/05_smoke25_comparison_and_aggregate.py` | `tools/remote_scripts/05_smoke25_comparison_and_aggregate.py` | active | After 04b finishes: writes B0 vs B1 smoke25 comparison (csv/md/png/case_diff), aggregate progression smoke10→smoke25 (csv/md/png), error taxonomy + failure buckets. |
| `remote_scripts/06_evidence_packs.py` | `tools/remote_scripts/06_evidence_packs.py` | active | Writes practice evidence pack (worklog/checklist/mapping/figure_index/table_index) and thesis evidence pack (experiment_inventory/figure_index/table_index/methods_notes). |
| `remote_scripts/07_b2_readiness_and_plan.py` | `tools/remote_scripts/07_b2_readiness_and_plan.py` | active | Writes `outputs/logs/b2_readiness_after_smoke25.md` and `outputs/logs/b2_implementation_plan.md`. Does not run B2. |
| `remote_scripts/08_export_tarball.py` | `tools/remote_scripts/08_export_tarball.py` | active | Builds a fresh `diploma_smoke25_results_<UTC>.tar.gz` from `outputs/`, `practice/`, and `data/spider/SOURCE_AND_AUDIT.md`. Saves to Drive `exports/` and `exports/latest_smoke25.tar.gz`. Agent then downloads via `exec_remote.py --download`. |
| `backups/_set_export_cell.py` | `tools/backups/_set_export_cell.py` | one-shot | Inserted catbox-upload code into notebook cell `e40d182b`. |
| `backups/_add_bridge_cell.py` | `tools/backups/_add_bridge_cell.py` | one-shot | Inserted `AGENT_BRIDGE_SETUP` cell `7f6bca53` into notebook. |
| `_audit_nb.py` | `tools/_audit_nb.py` | legacy | Single-purpose first-version cell lister; superseded by `notebook_status.py`. Kept for reproducibility of the early audit. | review later |
| `tooling_readme.md` | `tools/tooling_readme.md` | active | High-level docs of how the tooling fits together. | yes |
| `notebook_tooling_audit.md` | `tools/notebook_tooling_audit.md` | active | Full audit of dispatch+detection loop and known failure modes (focus race, autosave lag, mid-write JSON race, kernel restart). Referenced from `tooling_readme.md`. | yes |
| `run_cell_changelog.md` | `tools/run_cell_changelog.md` | active | What changed v1 → v2 → v2.1 → v3. | yes |
| `tooling_stability_report.md` | `tools/tooling_stability_report.md` | written by stability test | Smoke-test verdict on whether the loop is stable enough for B1. | yes |
| `run_cell.py.v1.bak` | `tools/backups/run_cell.py.v1.bak` | backup | First version (no focus fix, no log file). Kept as historical reference. | yes |
| `_add_cell_f.py` | `tools/backups/_add_cell_f.py` | backup | One-shot script that inserted `B1_FINAL_INDEX` cell `d99a1573` into the notebook by direct JSON edit (bypassed NotebookEdit when render exceeded 25k tokens). | yes (provenance) |
| `_add_cell_g.py` | `tools/backups/_add_cell_g.py` | backup | One-shot script that inserted `B1_EXPORT_TARBALL` cell `d41975cb`. | yes (provenance) |
| `tools/logs/` | dir | active | Per-invocation `run_cell` transcripts (`.log`) and structured status sidecars (`.json`). Append-only; rotate manually. | yes |
| `tools/backups/` | dir | active | Backups and one-shot scripts; nothing here is invoked at runtime. | yes |

## External (not in tools/)

| Name | Path | Status | Purpose | Keep? |
|---|---|---|---|---|
| `run_colab_notebook.ps1` | `scripts/run_colab_notebook.ps1` | active | PowerShell helper that drives VS Code Jupyter via `WScript.SendKeys` (focus → keyboard nav → Shift+Enter → Ctrl+S). The thing `run_cell.py` wraps. | yes |
| `notebooks/example.ipynb` | local | active | The notebook attached to the Colab runtime. Inter-process channel between the agent and the kernel. | yes |
| `.claude/settings.json` | local | active | Project-level Claude Code settings. | yes |
| `.claude/settings.local.json` | local | active (gitignored) | Personal allowlist for Bash/PowerShell/Edit/Write/Read/Glob/Grep/NotebookEdit so the agent runs without per-call prompts. | yes |
| `outputs/` (local) | local | populated by export tarball + extract | Local mirror of Drive outputs (predictions/metrics/tables/logs/plots, practice/). | yes |

## Where things live

- **Tooling**: `tools/`
- **Tooling backups**: `tools/backups/`
- **Tooling logs**: `tools/logs/`
- **Project artifacts (canonical)**: Google Drive at `/content/drive/MyDrive/diploma_plan_sql/`
- **Project artifacts (local mirror)**: `outputs/` (after export step)
- **Notebook**: `notebooks/example.ipynb`
- **Helper script**: `scripts/run_colab_notebook.ps1`
- **Claude Code config**: `.claude/`

## Conventions

- Cell ids in `notebooks/example.ipynb` are 8-char hex generated when inserted.
- Each new pipeline cell defines a `MARKER = '<NAME>'` constant and prints it near the start.
- Each cell that writes to Drive prints `WROTE <path>` for every write, so the transcript shows side effects.
- Status sidecars at `tools/logs/<run>.json` carry `status`, `exit_code`, `pre_exec`, `new_exec`, `helper_rc`, `output_tail` — enough to reconstruct what happened without re-reading the full log.
