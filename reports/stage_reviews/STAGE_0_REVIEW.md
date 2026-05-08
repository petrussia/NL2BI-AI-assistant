# Stage 0 Review: repository, branch, and Google Drive audit

Date: 2026-04-25

Status: **completed, awaiting user/ChatGPT review**.

No Stage 1 work was started. No commit or push was made.

## Scope Boundary

This project stage remains limited to post-query Text-to-Visualization:

- input: already materialized table, natural-language request, table metadata;
- output: Vega-Lite spec, table output, chart recommendation, or mini-dashboard spec;
- Text-to-SQL and database query generation are upstream and are not implemented or evaluated here.

## Commands Run

Git and repository audit:

```powershell
git rev-parse --show-toplevel
git branch --show-current
git status --short --branch
git remote -v
git branch -a --list "*experiments/peter*"
git log -1 --oneline --decorate
```

Repository indexing:

```powershell
Get-ChildItem -Recurse -Force -File |
  Where-Object { $_.FullName -notmatch '\\.git\\' } |
  Select-Object FullName,Length,LastWriteTime |
  Sort-Object FullName |
  Select-Object -First 500
```

Colab runner preflight:

```powershell
.\scripts\colab\run_colab_notebook.ps1 `
  -NotebookPath .\notebooks\00_setup_and_drive.ipynb `
  -Action cell `
  -CellIndex 1 `
  -DryRun `
  -Json
```

Colab Drive audit run:

```powershell
.\scripts\colab\run_colab_notebook.ps1 `
  -NotebookPath .\notebooks\00_setup_and_drive.ipynb `
  -Action cell `
  -CellIndex 1 `
  -WaitSeconds 15 `
  -ReloadFromDisk:$false `
  -Json
```

Notebook output check:

```powershell
$nb = Get-Content -Raw -Encoding UTF8 -Path "notebooks/00_setup_and_drive.ipynb" | ConvertFrom-Json
$cell = $nb.cells[1]
$cell.execution_count
$cell.outputs
```

## Git State

- Repository root: `C:/Users/user/Учёба/4 курс/Диплом/Практика`
- Current branch: `experiments/peter`
- Remote:
  - `origin git@github.com:petrussia/NL2BI-AI-assistant.git (fetch)`
  - `origin git@github.com:petrussia/NL2BI-AI-assistant.git (push)`
- Branch availability:
  - local `experiments/peter` exists;
  - remote `origin/experiments/peter` exists.
- Last commit:
  - `4b8231d (HEAD -> experiments/peter, origin/experiments/peter) Ignore Petukhov practice execution plan`

## Worktree State Observed Before Stage 0 Report

The branch was already dirty before this Stage 0 review was created. These pre-existing changes were not reverted.

```text
## experiments/peter...origin/experiments/peter
 M docs/README.en.md
 M docs/README.ru.md
 D notebooks/example.ipynb
 D notebooks/upload.ipynb
 D scripts/run_colab_notebook.ps1
?? configs/
?? notebooks/00_setup_and_drive.ipynb
?? notebooks/01_prepare_benchmarks.ipynb
?? notebooks/02_run_baselines_cpu.ipynb
?? notebooks/03_run_local_llm.ipynb
?? notebooks/04_evaluate_and_render.ipynb
?? notebooks/05_make_report_materials.ipynb
?? notebooks/legacy/
?? pyproject.toml
?? reports/
?? requirements.txt
?? scripts/colab/
?? scripts/evaluate_predictions.py
?? scripts/prepare_nvbench.py
?? scripts/render_charts.py
?? scripts/run_experiment.py
?? scripts/summarize_results.py
?? src/
?? tests/
```

Tracked diff observed before this Stage 0 report:

```text
 docs/README.en.md              |   24 +-
 docs/README.ru.md              |   24 +-
 notebooks/example.ipynb        |  230 --------
 notebooks/upload.ipynb         |  592 ---------------------
 scripts/run_colab_notebook.ps1 | 1154 ----------------------------------------
 5 files changed, 24 insertions(+), 2000 deletions(-)
```

## Repository Tree Snapshot

Top-level:

```text
.
├── .git/
├── .gitignore
├── README.md
├── configs/
├── docs/
├── notebooks/
├── pyproject.toml
├── reports/
├── requirements.txt
├── scripts/
├── src/
└── tests/
```

Important files and directories:

```text
configs/
├── colab_cpu.yaml                         empty scaffold
├── colab_llm_14b.yaml                     empty scaffold
├── colab_llm_8b.yaml                      empty scaffold
└── default.yaml                           empty scaffold

docs/
├── README.en.md                           modified before Stage 0
├── README.ru.md                           modified before Stage 0
└── petukhov_practice_execution_plan/      ignored by .gitignore
    ├── README.md
    ├── 00_MASTER_PLAN.md
    ├── 01_COLAB_RESOURCES.md
    ├── 02_STAGE_PROMPTS_FOR_CODEX.md
    ├── 03_VALIDATION_CHECKLISTS.md
    ├── 04_METRICS_AND_ARTIFACTS_SPEC.md
    ├── 05_LLM_SELECTION.md
    └── 06_REPORT_ALIGNMENT.md

notebooks/
├── 00_setup_and_drive.ipynb               valid Stage 0 Drive audit notebook
├── 01_prepare_benchmarks.ipynb            empty scaffold, cannot be run
├── 02_run_baselines_cpu.ipynb             empty scaffold, cannot be run
├── 03_run_local_llm.ipynb                 empty scaffold, cannot be run
├── 04_evaluate_and_render.ipynb           empty scaffold, cannot be run
├── 05_make_report_materials.ipynb         empty scaffold, cannot be run
└── legacy/
    └── upload.ipynb                       valid legacy benchmark upload notebook

reports/
├── practice_report_materials.md           empty scaffold
└── stage_reviews/
    └── STAGE_0_REVIEW.md

scripts/
├── colab/
│   └── run_colab_notebook.ps1             valid Colab/VS Code runner
├── evaluate_predictions.py                empty scaffold
├── prepare_nvbench.py                     empty scaffold
├── render_charts.py                       empty scaffold
├── run_experiment.py                      empty scaffold
└── summarize_results.py                   empty scaffold

src/t2v_eval/
├── __init__.py                            empty scaffold
├── baselines/                             empty scaffold modules
├── data/                                  empty scaffold modules
├── metrics/                               empty scaffold modules
├── normalization/                         empty scaffold modules
├── rendering/                             empty scaffold modules
└── utils/                                 empty scaffold modules

tests/
├── test_metrics.py                        empty scaffold
├── test_normalization.py                  empty scaffold
├── test_nvbench_adapter.py                empty scaffold
├── test_rule_baseline.py                  empty scaffold
├── test_schema.py                         empty scaffold
└── test_smoke_pipeline.py                 empty scaffold
```

## Google Drive Audit

Required Drive path:

```text
/content/drive/MyDrive/petr_text_to_visualization_part
```

The audit was executed inside the active Colab notebook through the required runner. The notebook cell completed successfully.

Important correction: the populated folder visible in the user's VS Code/Colab file explorer is:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part
```

This is different from the root path required by the execution plan. The Stage 0 cell checked and created the plan root without `diploma`; the screenshot shows that the older/legacy diploma root already contains project materials. No files were moved between these Drive locations during Stage 0.

Execution check:

```text
execution_count: 3
output_type: stream
success marker: STAGE0_DRIVE_AUDIT_OK
```

Key output:

```json
{
  "status": "ok",
  "created_or_exists": true,
  "mount_error": null,
  "drive_root": "/content/drive/MyDrive/petr_text_to_visualization_part",
  "timestamp_utc": "2026-04-25T14:56:21.671207+00:00",
  "python": "3.12.13",
  "platform": "Linux-6.6.113+-x86_64-with-glibc2.35",
  "cwd": "/content",
  "tree": [
    {
      "path": ".",
      "kind": "dir",
      "size_bytes": null
    }
  ]
}
```

Drive tree for the required plan root, 2-3 levels:

```text
/content/drive/MyDrive/petr_text_to_visualization_part/
└── .
```

The required plan root exists and was empty at the time of the Colab audit output.

Drive tree visible in the user's screenshot for the existing legacy/diploma root:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/
├── additional docs/
├── benchmarks/
├── notebooks/
└── reports/
```

Before Stage 1/2, the team should decide whether to:

- keep using the execution-plan root `/content/drive/MyDrive/petr_text_to_visualization_part` and migrate/copy only needed artifacts later; or
- update configs/notebooks to consistently use `/content/drive/MyDrive/diploma/petr_text_to_visualization_part`.

Until that decision is made, code should not silently mix both roots.

## Existing Text-to-Visualization Coverage

Already partially present:

- execution plan for Petukhov Text-to-Visualization work under `docs/petukhov_practice_execution_plan/`;
- expected repository skeleton is already present as empty files/directories;
- Colab runner exists at `scripts/colab/run_colab_notebook.ps1`;
- `notebooks/00_setup_and_drive.ipynb` now contains a minimal valid Drive audit cell and was updated to report both the execution-plan root and the legacy/diploma root on the next run;
- legacy benchmark upload notebook exists at `notebooks/legacy/upload.ipynb`;
- the existing legacy/diploma Drive root appears to contain `additional docs/`, `benchmarks/`, `notebooks/`, and `reports/`;
- `reports/stage_reviews/` exists.

Not implemented yet:

- `T2VExample`, `T2VPrediction`, `FieldMetadata` schema;
- reproducibility utilities;
- nvBench post-query adapter;
- Vega-Lite normalization;
- metrics/evaluator;
- B0/B1/B2/B3/B4 baselines;
- rendering pipeline;
- runnable Stage 1+ notebooks;
- tests with assertions.

## Files Better Not To Touch Yet

- `docs/README.en.md` and `docs/README.ru.md`: already modified before Stage 0; preserve until the owner confirms intent.
- Deleted tracked files `notebooks/example.ipynb`, `notebooks/upload.ipynb`, and `scripts/run_colab_notebook.ps1`: these look like a migration to `notebooks/legacy/` and `scripts/colab/`; do not restore or remove without explicit review.
- `notebooks/legacy/upload.ipynb`: valid legacy benchmark downloader, but it uses `/content/drive/MyDrive/diploma/petr_text_to_visualization_part`, not the Stage plan root; do not run it or migrate data until the canonical Drive root is confirmed.
- Empty scaffold notebooks under `notebooks/01_*.ipynb` through `notebooks/05_*.ipynb`: do not run until populated with valid notebook JSON.
- Empty scaffold source/test/config files: treat as placeholders for later stages; do not fill during Stage 0.

## Recommended Next Stages

1. Stage 1: create the minimal reproducible project scaffold:
   - `requirements.txt`;
   - package metadata if useful;
   - `src/t2v_eval` utilities;
   - schema dataclasses;
   - smoke tests;
   - valid `00_setup_and_drive.ipynb` without heavy outputs.
2. Stage 2: implement nvBench post-query preparation:
   - use gold SQL only to materialize tables;
   - save datasets under Drive;
   - create `dataset_card.md`.
3. Stage 3: implement Vega-Lite normalization and evaluator metrics.
4. Stage 4-5: implement CPU baselines and existing/partial tool baseline.
5. Stage 6+: run local open-source LLM baselines only after CPU pipeline is stable.

Do not start Stage 1 until this Stage 0 bundle is reviewed and explicitly approved.

## Risks

- Existing dirty worktree is large and predates this Stage 0 work; commits must be carefully scoped.
- Many files are empty scaffolds, which can be mistaken for implemented functionality.
- Legacy Drive path differs from the required project path; this must be resolved explicitly before data-heavy Stage 2 work.
- `rg` exists but failed with `Access is denied`; PowerShell fallback was used for repository indexing.
- Colab Drive auth initially failed once with a credentials propagation `MessageError`; the later rerun succeeded after the active Colab session had Drive mounted.

## Self-Check

- Current branch is `experiments/peter`: yes.
- `origin/experiments/peter` exists: yes.
- Required Drive root exists in Colab: yes.
- Drive tree captured: yes for the required plan root; user screenshot also documents a populated legacy/diploma root.
- Repository tree captured: yes.
- No Stage 1 implementation started: yes.
- No commit/push performed: yes.
