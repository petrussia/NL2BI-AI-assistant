# Stage 5 Review: existing / partial tool baseline

Date: 2026-04-25

Status: **completed for final review**.

Stage 6 was not started. The final Stage 5 documentation commit has not been made.

Stage 5 code was pushed as a code-only checkpoint so Colab could pull it into `/content/petukhov_t2v_repo`, then sample50 and sample200 were executed through the notebook runner.

Checkpoint commit:

```text
2f4fdff996d0b1ccc5aa71e62fba0c5bb288c54b
```

## Scope Boundary

Stage 5 adds a comparison baseline based on an existing-tool attempt. It remains post-query Text-to-Visualization: the input is a ready `T2VExample` table, query, and metadata. No Text-to-SQL logic is implemented.

## NL4DV Attempt

Primary external tool attempt: NL4DV.

Commands:

```powershell
python --version
python -m pip show nl4dv
python -m pip install --dry-run nl4dv
```

Result:

```text
Python 3.11.1
WARNING: Package(s) not found: nl4dv
```

The dry-run resolved `nl4dv==4.1.0` but would install a large dependency stack including `pytest~=3.10.1`, `spacy`, `litellm`, `openai`, and `vega`. This is treated as incompatible/risky for the current project environment because it can downgrade or destabilize the test stack. The details are documented in:

```text
reports/stage_reviews/STAGE_5_NL4DV_FAILURE.md
```

No NL4DV package was installed into the project environment. NL4DV full-fit was not used.

## Implemented Baseline

Implemented:

```text
B2_partial_recommender
```

Files:

```text
src/t2v_eval/baselines/nl4dv_adapter.py
src/t2v_eval/baselines/__init__.py
scripts/run_experiment.py
notebooks/02_run_existing_tools_cpu.ipynb
tests/test_nl4dv_adapter.py
reports/stage_reviews/STAGE_5_NL4DV_FAILURE.md
reports/stage_reviews/STAGE_5_REVIEW.md
```

`B2_partial_recommender` is a **partial fit**:

- query is used to filter and rank fields;
- chart recommendation is generated from table/schema profiling heuristics;
- generated candidates are Vega-Lite-like specs in the same prediction format as B0/B1;
- the same Stage 3 evaluator is used.

The adapter module also contains a best-effort `predict_nl4dv` path and `convert_nl4dv_output` converter for common NL4DV-like output shapes, but the production Stage 5 method is the partial fallback because NL4DV was not installed.

## Experiment Runner

`scripts/run_experiment.py` now accepts:

```text
--method B2_partial_recommender
```

Output format is the same as B0/B1:

```text
<drive_root>/runs/<run_id>/
  examples_used.jsonl
  runtime_info.json
  pip_freeze.txt
  experiment_summary.json
  predictions/B2_partial_recommender.jsonl
  metrics/B2_partial_recommender/aggregate_metrics.csv
  metrics/B2_partial_recommender/per_example_metrics.csv
  metrics/B2_partial_recommender/evaluation_summary.json
  rendered/B2_partial_recommender/*.png
  rendered/B2_partial_recommender/render_failures.json
```

## Notebook

Created `notebooks/02_run_existing_tools_cpu.ipynb` with these cells:

```text
stage5-title
stage5-setup
stage5-run-sample50
stage5-run-sample200
stage5-verify-artifacts
```

The notebook uses the canonical Drive root:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part
```

Run IDs:

```text
stage5_partial_sample50
stage5_partial_sample200
```

The notebook was run through the Colab runner, then outputs were cleared. The committed notebook has no outputs.

## Commands Run

Branch status after Stage 4 sanity commit:

```powershell
git status --short --branch
```

Result:

```text
## experiments/peter...origin/experiments/peter
```

NL4DV compatibility check:

```powershell
python --version
python -m pip show nl4dv
python -m pip install --dry-run nl4dv
```

Result summary:

```text
Python 3.11.1
nl4dv not installed
dry-run resolved nl4dv-4.1.0 but included pytest-3.10.1 and a large dependency stack
```

Focused Stage 5 tests:

```powershell
python -m pytest tests/test_nl4dv_adapter.py -q
```

Result:

```text
4 passed
```

Notebook validation:

```powershell
python -c "import nbformat; nb=nbformat.read('notebooks/02_run_existing_tools_cpu.ipynb', as_version=4); nbformat.validate(nb); print(len(nb.cells), [c.get('id') for c in nb.cells], [len(c.get('outputs', [])) for c in nb.cells if c.cell_type == 'code'])"
```

Result:

```text
5 ['stage5-title', 'stage5-setup', 'stage5-run-sample50', 'stage5-run-sample200', 'stage5-verify-artifacts'] [0, 0, 0, 0]
```

Full local test suite:

```powershell
python -m pytest -q
```

Result:

```text
21 passed
```

Local five-example smoke run with synthetic post-query examples and temporary CSV tables:

```powershell
python scripts/run_experiment.py `
  --examples <temp>\examples.jsonl `
  --method B2_partial_recommender `
  --drive-root <temp>\drive `
  --run-id stage5_local_smoke `
  --sample-size 5 `
  --render-limit 2 `
  --json
```

Result:

```text
examples: 5
predictions: 5
failure_rate: 0.0
vega_lite_validity: 1.0
field_selection_f1: 0.6
normalized_exact_match: 0.0
rendered_png: 2
```

The smoke artifacts were written only to `%TEMP%`, not to the repository and not to Google Drive.

Code checkpoint for Colab:

```powershell
python -m pytest -q
git add -- scripts/run_experiment.py src/t2v_eval/baselines/__init__.py src/t2v_eval/baselines/nl4dv_adapter.py tests/test_nl4dv_adapter.py notebooks/02_run_existing_tools_cpu.ipynb
git commit -m "feat: add Stage 5 partial existing-tool baseline"
git push origin experiments/peter
```

Result:

```text
2f4fdff996d0b1ccc5aa71e62fba0c5bb288c54b
```

Colab cells were run sequentially through the runner:

```powershell
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\02_run_existing_tools_cpu.ipynb -Action cell -CellId stage5-setup -ReloadFromDisk:$false -WaitSeconds 20 -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\02_run_existing_tools_cpu.ipynb -Action cell -CellId stage5-run-sample50 -ReloadFromDisk:$false -WaitSeconds 35 -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\02_run_existing_tools_cpu.ipynb -Action cell -CellId stage5-run-sample200 -ReloadFromDisk:$false -WaitSeconds 60 -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\02_run_existing_tools_cpu.ipynb -Action cell -CellId stage5-verify-artifacts -ReloadFromDisk:$false -WaitSeconds 15 -Json
```

Markers observed:

```text
STAGE5_SETUP_OK
STAGE5_SAMPLE50_OK
STAGE5_SAMPLE200_OK
STAGE5_ARTIFACTS_OK
```

## Drive Artifacts

Canonical Drive root:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part
```

Final run folder:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage5_partial_sample200
```

Verified files:

```text
examples_used.jsonl
runtime_info.json
pip_freeze.txt
experiment_summary.json
predictions/B2_partial_recommender.jsonl
metrics/B2_partial_recommender/aggregate_metrics.csv
metrics/B2_partial_recommender/per_example_metrics.csv
metrics/B2_partial_recommender/evaluation_summary.json
rendered/B2_partial_recommender/*.png
rendered/B2_partial_recommender/render_failures.json
```

Artifact verification result:

```text
missing: []
rendered/B2_partial_recommender PNG files: 20
```

## Final Metrics

Sample50:

```text
predictions: 50
failure_rate: 0.0
vega_lite_validity: 1.0
chart_type_accuracy: 0.62
field_selection_f1: 0.8613333333333333
encoding_accuracy: 0.1
aggregation_accuracy: 0.1
normalized_exact_match: 0.1
rendered_png: 20
```

Sample200:

```text
predictions: 200
failure_rate: 0.0
vega_lite_validity: 1.0
chart_type_accuracy: 0.62
field_selection_f1: 0.8703333333333333
encoding_accuracy: 0.11
aggregation_accuracy: 0.11
normalized_exact_match: 0.11
rendered_png: 20
```

## Checklist

- Existing tool attempt was honest: yes, NL4DV compatibility was checked and documented.
- NL4DV failure/incompatibility documented: yes, `STAGE_5_NL4DV_FAILURE.md`.
- Partial baseline marked as partial fit: yes.
- Predictions use the common prediction format: yes, verified by local tests, smoke run, and Drive predictions.
- Evaluator is the same as previous methods: yes, `scripts/run_experiment.py` calls the same `evaluate_predictions`.
- Drive predictions and metrics exist: yes.
- Rendered examples exist: yes, 20 PNG files in the final Drive run.

## Problems And Risks

- NL4DV was not installed because its dependency plan can destabilize the current environment.
- `B2_partial_recommender` is intentionally weaker than a full NL-to-Vis tool: it uses query-aware field ranking, but chart recommendation is table/profile based.

## Next Steps

Stage 5 is ready for final documentation commit after review. Do not start Stage 6 until the user explicitly requests it.
