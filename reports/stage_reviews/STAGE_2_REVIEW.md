# Stage 2 Review: nvBench post-query preparation

Date: 2026-04-25

Status: **completed for review**.

Stage 3 was not started. No final Stage 2 documentation commit was made after completion; the only pushed Stage 2 commit is the earlier code-only checkpoint that made the adapter code available to Colab.

Historical blocker: `reports/stage_reviews/STAGE_2_BLOCKED.md` was created and accepted when Colab could not see the local Windows worktree. The blocker is now resolved by the code-only checkpoint commit plus a Colab checkout of `origin/experiments/peter` at `/content/petukhov_t2v_repo`.

## Scope Boundary

Stage 2 remains limited to post-query Text-to-Visualization. The implemented adapter does not generate SQL. nvBench gold SQL is used only to materialize already-defined input tables when the SQLite database is available. If SQL materialization is unavailable, the adapter can use nvBench `vis_obj` values as a benchmark-provided table extraction fallback.

## Implemented Files

```text
scripts/prepare_nvbench.py
src/t2v_eval/data/nvbench_adapter.py
src/t2v_eval/data/schema.py
tests/test_nvbench_adapter.py
notebooks/01_prepare_benchmarks.ipynb
reports/stage_reviews/STAGE_2_REVIEW.md
reports/stage_reviews/STAGE_2_BLOCKED.md
reports/practice_report_materials.md
```

## Checkpoint Commit

Code-only checkpoint pushed before Colab execution:

```text
a51e264b9e6f9937243d4c0921951552d8dd18ac feat: implement nvBench post-query preparation adapter
```

This checkpoint was required only to make the Stage 2 code available to Colab. It did not mark Stage 2 complete.

## Adapter Behavior

Implemented `src/t2v_eval/data/nvbench_adapter.py`:

- searches nvBench under the canonical Drive root:
  - `/content/drive/MyDrive/diploma/petr_text_to_visualization_part/datasets/raw`;
  - `/content/drive/MyDrive/diploma/petr_text_to_visualization_part/benchmarks`;
  - `/content/drive/MyDrive/diploma/petr_text_to_visualization_part`.
- if missing, can attempt official download from `https://github.com/TsinghuaDatabaseGroup/nvBench`;
- reads `NVBench.json` objects with `vis_query`, `chart`, `db_id`, `vis_obj`, and `nl_queries`;
- extracts gold SQL from `vis_query.data_part.sql_part`;
- finds SQLite databases by `db_id` and materializes SQL to CSV;
- falls back to `vis_obj.x_data`, `vis_obj.y_data`, and optional `classify` data when SQL/database materialization is unavailable;
- creates one `T2VExample` per NL query;
- saves processed JSONL, materialized CSV tables, failures JSONL, `dataset_card.md`, `prepare_result.json`, and `runtime_info.json`.

The official nvBench GitHub page states that `NVBench.json` stores JSON `(NL, VIS)` pairs and that fields include `vis_query`, `chart`, `db_id`, `vis_obj`, and `nl_queries`: https://github.com/TsinghuaDatabaseGroup/nvBench

## Notebook

Updated `notebooks/01_prepare_benchmarks.ipynb` with cells:

1. `stage2-setup`;
2. `stage2-run-sample20`;
3. `stage2-run-sample200`;
4. `stage2-verify-artifacts`.

The notebook uses the approved canonical Drive root:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part
```

The setup cell uses:

```text
repo_root: /content/petukhov_t2v_repo
repo_url: https://github.com/petrussia/NL2BI-AI-assistant.git
branch: experiments/peter
```

If the checkout does not exist, it clones the branch. If it exists, it runs `git fetch origin experiments/peter`, `git checkout experiments/peter`, and `git pull --ff-only origin experiments/peter`. It then runs:

```text
python -m pip install -q -r /content/petukhov_t2v_repo/requirements.txt
python -m pip install -q -e /content/petukhov_t2v_repo
python -c "import t2v_eval; print(t2v_eval.__version__)"
```

For the VS Code + Colab runner path, `google.colab.userdata` did not expose the web Colab secret. The setup cell therefore also supports a token file outside the repository:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/secrets/github_token.txt
```

The token is not committed, not printed, and is removed from the checkout remote URL after Git operations.

## Commands Run

Local tests before checkpoint:

```powershell
python -m pytest -q
python -c "import t2v_eval; print(t2v_eval.__version__)"
```

Result:

```text
5 passed
0.1.0
```

Colab setup run:

```powershell
.\scripts\colab\run_colab_notebook.ps1 `
  -NotebookPath .\notebooks\01_prepare_benchmarks.ipynb `
  -Action cell `
  -CellId stage2-setup `
  -WaitSeconds 60 `
  -ReloadFromDisk:$false `
  -Json
```

Result:

```text
STAGE2_SETUP_OK
repo_root: /content/petukhov_t2v_repo
branch: experiments/peter
sync_status: pulled_existing_checkout
commit: a51e264b9e6f9937243d4c0921951552d8dd18ac
t2v_eval_version: 0.1.0
```

Colab sample20 run:

```powershell
.\scripts\colab\run_colab_notebook.ps1 `
  -NotebookPath .\notebooks\01_prepare_benchmarks.ipynb `
  -Action cell `
  -CellId stage2-run-sample20 `
  -WaitSeconds 45 `
  -ReloadFromDisk:$false `
  -Json
```

Result:

```text
STAGE2_SAMPLE20_OK
requested_sample_size: 20
successful_examples: 20
failed_visualizations: 0
elapsed_seconds: 8.476
```

Colab sample200 run:

```powershell
.\scripts\colab\run_colab_notebook.ps1 `
  -NotebookPath .\notebooks\01_prepare_benchmarks.ipynb `
  -Action cell `
  -CellId stage2-run-sample200 `
  -WaitSeconds 60 `
  -ReloadFromDisk:$false `
  -Json
```

Result:

```text
STAGE2_SAMPLE200_OK
requested_sample_size: 200
successful_examples: 200
failed_visualizations: 0
elapsed_seconds: 12.903
```

Colab artifact verification:

```powershell
.\scripts\colab\run_colab_notebook.ps1 `
  -NotebookPath .\notebooks\01_prepare_benchmarks.ipynb `
  -Action cell `
  -CellId stage2-verify-artifacts `
  -WaitSeconds 20 `
  -ReloadFromDisk:$false `
  -Json
```

Result:

```text
STAGE2_ARTIFACTS_OK
missing: []
successful_examples: 200
failed_visualizations: 0
table_count: 50
```

## Artifacts

Drive processed root:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/datasets/processed/nvbench_postquery
```

Verified artifact tree:

```text
nvbench_postquery/
|-- examples.jsonl
|-- examples_sample20.jsonl
|-- examples_sample200.jsonl
|-- dataset_card.md
|-- prepare_result.json
|-- runtime_info.json
|-- tables/                 # 50 CSV files
`-- failures/               # JSONL failure logs if any failures exist
```

Colab summary for `prepare_result.json`:

```text
status: ok
requested_sample_size: 200
total_visualizations_seen: 7247
total_nl_pairs_seen: 200
successful_examples: 200
failed_visualizations: 0
source_root: /content/drive/MyDrive/diploma/petr_text_to_visualization_part/benchmarks/NVBench/repo/nvBench-main
official_download_attempted: false
failure_reasons: {}
```

## Criteria Check

- Benchmark is not replaced by synthetic data: yes, official nvBench source under Drive was used.
- Gold SQL is used only for table materialization, not Text-to-SQL evaluation: yes.
- Processed JSONL exists: yes.
- Materialized tables exist: yes, 50 CSV tables verified.
- Metadata exists for fields: yes, generated by adapter from materialized/fallback tables.
- Gold visualization/spec is normalized into a Vega-Lite-like target: yes.
- Minimum 50 successful examples: yes, 200 successful examples.
- `dataset_card.md` describes source and failures: yes.
- Notebook is valid JSON: yes.
- Stage 3 was not started: yes.

## Problems and Risks

- The local VS Code + Colab runner did not receive the web Colab `GITHUB_TOKEN` secret through `google.colab.userdata`; the practical fallback is a Drive token file outside git.
- A token was briefly tested manually in a notebook cell before the fallback was added. That cell and all outputs were removed from the local notebook; the token should still be rotated as a credential hygiene step.
- Official nvBench local inspection via `git clone --depth 1` timed out on Windows after 2 minutes; Colab used an existing Drive nvBench source instead.
- The adapter intentionally writes CSV tables instead of Parquet to avoid adding `pyarrow` as a Stage 2 dependency.
- There are fewer materialized tables than examples because multiple NL queries can share the same table/visualization.

## Next Steps

1. Review Stage 2 code, notebook setup, and Drive artifact summary.
2. Rotate the GitHub token that was briefly pasted into a manual notebook cell.
3. After approval, rerun final checks.
4. Commit the Stage 2 notebook/doc changes without datasets, model weights, rendered charts, or run outputs.
5. Push to `origin experiments/peter`.
6. Do not proceed to Stage 3 until Stage 2 review is accepted.
