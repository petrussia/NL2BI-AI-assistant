# Stage 2 Blocked: Colab repository checkout missing

Date: 2026-04-25

Resolution: **resolved on 2026-04-25**.

This file is retained as an audit record of the earlier Stage 2 blocker. The current Stage 2 status is recorded in `reports/stage_reviews/STAGE_2_REVIEW.md`: the blocker was resolved by a code-only checkpoint commit plus a Colab checkout of `origin/experiments/peter` at `/content/petukhov_t2v_repo`; Colab then ran sample20/sample200 and verified Drive artifacts.

## What Failed

Stage 2 could not complete the required Colab benchmark preparation run.

The Stage 2 setup notebook successfully reached the active Colab runtime and Drive was already mounted, but the Colab filesystem did not contain a repository checkout with `pyproject.toml` and the current Stage 2 code. `pyproject.toml` is only a root marker for an installable repository checkout; the real blocker is that the local Windows worktree is not automatically available inside Colab. Because `scripts/prepare_nvbench.py` and `src/t2v_eval/data/nvbench_adapter.py` are local uncommitted Stage 2 changes, the Colab runtime cannot import or execute them unless a checkout/copy of the current code is available inside Colab.

The blocking cell was `notebooks/01_prepare_benchmarks.ipynb`, cell id `stage2-setup`.

## Failed Command

Runner command:

```powershell
.\scripts\colab\run_colab_notebook.ps1 `
  -NotebookPath .\notebooks\01_prepare_benchmarks.ipynb `
  -Action cell `
  -CellIndex 1 `
  -WaitSeconds 15 `
  -ReloadFromDisk:$false `
  -Json
```

Runner result:

```text
ok: true
selectedCell.Id: stage2-setup
target window: 01_prepare_benchmarks.ipynb - Visual Studio Code
```

Notebook output:

```text
Drive already mounted at /content/drive; to attempt to forcibly remount, call drive.mount("/content/drive", force_remount=True).
STAGE2_SETUP_BLOCKED
{
  "reason": "repository root with pyproject.toml was not found in Colab filesystem",
  "checked": [
    "/content/drive/MyDrive/diploma/petr_text_to_visualization_part/repo",
    "/content/drive/MyDrive/diploma/petr_text_to_visualization_part/NL2BI-AI-assistant",
    "/content/NL2BI-AI-assistant",
    "/content/petukhov_t2v_repo"
  ],
  "hint": "Set T2V_REPO_ROOT to a Drive or /content checkout containing the current Stage 2 code before running benchmark preparation."
}
```

Traceback:

```text
RuntimeError: T2V_REPO_ROOT is required for Stage 2 Colab run
```

## Checked Hypotheses

- Active notebook preflight: passed.
- Colab Drive mount: passed; Drive was already mounted at `/content/drive`.
- Canonical Drive root policy: notebook uses `/content/drive/MyDrive/diploma/petr_text_to_visualization_part`.
- `pyproject.toml` check: used only to identify a Colab-visible repo root; it failed because the current local worktree was not present in Colab.
- Repository candidates checked in Colab:
  - `/content/drive/MyDrive/diploma/petr_text_to_visualization_part/repo`;
  - `/content/drive/MyDrive/diploma/petr_text_to_visualization_part/NL2BI-AI-assistant`;
  - `/content/NL2BI-AI-assistant`;
  - `/content/petukhov_t2v_repo`.
- Local Stage 2 code tests: passed, see `STAGE_2_REVIEW.md`.

## Proposed Fix Options

Option 1, preferred for review-safe execution:

1. Put a checkout/copy of the current working repository, including the uncommitted Stage 2 files, into one of these Colab-visible paths:
   - `/content/drive/MyDrive/diploma/petr_text_to_visualization_part/repo`;
   - `/content/drive/MyDrive/diploma/petr_text_to_visualization_part/NL2BI-AI-assistant`;
   - `/content/petukhov_t2v_repo`.
2. Reopen or verify `notebooks/01_prepare_benchmarks.ipynb` in VS Code.
3. Rerun cell `stage2-setup`.
4. If setup succeeds, continue sequentially to sample20, sample200, and artifact verification cells through the runner.

Option 2:

After code review approval, commit and push Stage 2 code first, then let the Colab notebook clone `origin/experiments/peter` into `/content/petukhov_t2v_repo` before running. This changes the review/execute order and needs explicit user approval because the current project rule says not to commit before review.

Option 3:

Embed a temporary patch or code payload into the notebook to recreate the uncommitted Stage 2 code in Colab. This is not recommended because it duplicates source code in the notebook and makes review harder.

## Can Work Continue Without This?

No for full Stage 2 completion.

The adapter, script, notebook, and tests are implemented locally, but the main benchmark preparation cannot be considered complete until Colab runs produce:

- `datasets/processed/nvbench_postquery/examples_sample20.jsonl`;
- `datasets/processed/nvbench_postquery/examples_sample200.jsonl`;
- materialized `tables/*.csv`;
- `dataset_card.md`;
- at least 50 successful examples for the main sample.

Do not proceed to Stage 3 until this blocker is resolved and Stage 2 preparation completes in Colab.
