# Stage 4 Review: B0 rule-based and B1 constraint/ranking baselines

Date: 2026-04-25

Status: **completed**.

Stage 5 was not started.

Stage 4 code was first pushed as a code checkpoint so Colab could pull it into `/content/petukhov_t2v_repo`, then the final CPU baseline runs were executed through the notebook runner.

Checkpoint commit:

```text
fb801a9 feat: add Stage 4 baseline experiment runner
```

## Scope Boundary

Stage 4 implements non-LLM post-query Text-to-Visualization baselines. It does not implement Text-to-SQL and does not query a database. The inputs are already prepared `T2VExample` rows with table paths, NL queries, metadata, and gold visualization specs from Stage 2.

## Implemented Files

```text
src/t2v_eval/baselines/rule_based.py
src/t2v_eval/baselines/constraint_ranker.py
src/t2v_eval/baselines/__init__.py
scripts/run_experiment.py
scripts/render_charts.py
notebooks/02_run_baselines_cpu.ipynb
tests/test_rule_baseline.py
reports/stage_reviews/STAGE_4_REVIEW.md
```

## Baselines

`B0_rule_based` implements deterministic rules:

- intent extraction from query: `trend`, `comparison`, `distribution`, `correlation`, `top`, `table`, `dashboard`;
- field linking by exact lowercase name match and token overlap against query, field name, description, and unit;
- chart rules: time plus numeric to line, categorical plus numeric to bar, two numeric fields to scatter, numeric distribution to binned bar, top/ranking to sorted bar, table/detail to text fallback;
- top-k candidate output with normalized candidate specs.

`B1_constraint_ranker` implements a separate generate-filter-rank baseline:

- generates multiple bar, sorted bar, line, scatter, histogram, and table/text candidates;
- filters hard constraints before ranking:
  - field must exist in schema;
  - temporal encoding requires temporal field;
  - quantitative encoding requires numeric field;
  - non-count aggregation requires numeric field and allowed aggregation metadata;
- ranks with soft score for intent match, field mention rank, perceptual simplicity, parsimony, and metadata compatibility.

Neither baseline reads or uses the gold spec. Field linking uses only query, metadata, and table schema inference when metadata fields are absent.

## Experiment Runner

`scripts/run_experiment.py` now runs `B0_rule_based`, `B1_constraint_ranker`, or `all` and writes one reproducible run folder:

```text
<drive_root>/runs/<run_id>/
  examples_used.jsonl
  runtime_info.json
  pip_freeze.txt
  experiment_summary.json
  predictions/B0_rule_based.jsonl
  predictions/B1_constraint_ranker.jsonl
  metrics/<method>/aggregate_metrics.csv
  metrics/<method>/per_example_metrics.csv
  metrics/<method>/evaluation_summary.json
  rendered/<method>/*.png
  rendered/<method>/render_failures.json
```

`examples_used.jsonl` is written before evaluation so `sample_size=50` evaluates exactly 50 examples, not the full source JSONL.

The default Drive root remains canonical:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part
```

The deprecated non-diploma Drive root is not used.

## Notebook

Created `notebooks/02_run_baselines_cpu.ipynb` with these cells:

```text
stage4-title
stage4-setup
stage4-run-sample50
stage4-run-sample200
stage4-verify-artifacts
```

The notebook is a valid empty-output Colab runner skeleton. Its setup cell mounts Drive, clones or pulls `origin/experiments/peter` into `/content/petukhov_t2v_repo`, installs requirements, installs the repo editable, and verifies `t2v_eval.__version__`.

The run cells target the Stage 2 processed examples under:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/datasets/processed/nvbench_postquery/examples_sample200.jsonl
```

Expected Colab run IDs:

```text
stage4_cpu_sample50
stage4_cpu_sample200
```

Final Drive run ID:

```text
stage4_cpu_sample200
```

## Commands Run

Branch sync before work:

```powershell
git pull --ff-only origin experiments/peter
git status --short --branch
```

Result:

```text
Already up to date.
## experiments/peter...origin/experiments/peter
```

Focused Stage 4 tests:

```powershell
python -m pytest tests/test_rule_baseline.py -q
```

Result:

```text
4 passed
```

Notebook validation:

```powershell
python -c "import nbformat; nb=nbformat.read('notebooks/02_run_baselines_cpu.ipynb', as_version=4); nbformat.validate(nb); print(len(nb.cells), [c.get('id') for c in nb.cells], [len(c.get('outputs', [])) for c in nb.cells if c.cell_type == 'code'])"
```

Result:

```text
5 ['stage4-title', 'stage4-setup', 'stage4-run-sample50', 'stage4-run-sample200', 'stage4-verify-artifacts'] [0, 0, 0, 0]
```

Full local test suite:

```powershell
python -m pytest -q
```

Result:

```text
17 passed
```

Local five-example smoke run with synthetic post-query examples and real temporary CSV tables:

```powershell
python scripts/run_experiment.py `
  --examples <temp>\examples.jsonl `
  --method all `
  --drive-root <temp>\drive_after_b1_table `
  --run-id stage4_local_smoke `
  --sample-size 5 `
  --render-limit 2 `
  --json
```

Result:

```text
B0_rule_based:
  examples: 5
  predictions: 5
  failure_rate: 0.0
  vega_lite_validity: 1.0
  field_selection_f1: 1.0
  normalized_exact_match: 1.0
  aggregation_accuracy: 1.0
  rendered_png: 2

B1_constraint_ranker:
  examples: 5
  predictions: 5
  failure_rate: 0.0
  vega_lite_validity: 1.0
  field_selection_f1: 1.0
  normalized_exact_match: 1.0
  aggregation_accuracy: 1.0
  rendered_png: 2
```

The smoke artifacts were written only to `%TEMP%`, not to the repository and not to Google Drive.

Code checkpoint for Colab:

```powershell
git add -- notebooks/02_run_baselines_cpu.ipynb scripts/render_charts.py scripts/run_experiment.py src/t2v_eval/baselines/__init__.py src/t2v_eval/baselines/constraint_ranker.py src/t2v_eval/baselines/rule_based.py tests/test_rule_baseline.py
git commit -m "feat: add Stage 4 baseline experiment runner"
git push origin experiments/peter
```

Result:

```text
fb801a9 feat: add Stage 4 baseline experiment runner
```

Colab cells were run sequentially through the runner:

```powershell
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\02_run_baselines_cpu.ipynb -Action cell -CellId stage4-setup -ReloadFromDisk:$false -WaitSeconds 20 -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\02_run_baselines_cpu.ipynb -Action cell -CellId stage4-run-sample50 -ReloadFromDisk:$false -WaitSeconds 30 -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\02_run_baselines_cpu.ipynb -Action cell -CellId stage4-run-sample200 -ReloadFromDisk:$false -WaitSeconds 45 -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\02_run_baselines_cpu.ipynb -Action cell -CellId stage4-verify-artifacts -ReloadFromDisk:$false -WaitSeconds 15 -Json
```

Markers observed:

```text
STAGE4_SETUP_OK
STAGE4_SAMPLE50_OK
STAGE4_SAMPLE200_OK
STAGE4_ARTIFACTS_OK
```

## Drive Artifacts

Canonical Drive root:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part
```

Final run folder:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage4_cpu_sample200
```

Verified files:

```text
examples_used.jsonl
runtime_info.json
pip_freeze.txt
experiment_summary.json
predictions/B0_rule_based.jsonl
predictions/B1_constraint_ranker.jsonl
metrics/B0_rule_based/aggregate_metrics.csv
metrics/B0_rule_based/per_example_metrics.csv
metrics/B0_rule_based/evaluation_summary.json
metrics/B1_constraint_ranker/aggregate_metrics.csv
metrics/B1_constraint_ranker/per_example_metrics.csv
metrics/B1_constraint_ranker/evaluation_summary.json
rendered/B0_rule_based/*.png
rendered/B0_rule_based/render_failures.json
rendered/B1_constraint_ranker/*.png
rendered/B1_constraint_ranker/render_failures.json
```

Artifact verification result:

```text
missing: []
rendered/B0_rule_based PNG files: 20
rendered/B1_constraint_ranker PNG files: 20
```

## Final Metrics

Sample50:

```text
B0_rule_based:
  examples: 50
  predictions: 50
  failures: 0
  failure_rate: 0.0
  chart_type_accuracy: 0.46
  x_field_accuracy: 0.52
  y_field_accuracy: 0.52
  field_selection_f1: 0.8613333333333333
  aggregation_accuracy: 0.42
  normalized_exact_match: 0.0
  vega_lite_validity: 1.0
  rendered_png: 20

B1_constraint_ranker:
  examples: 50
  predictions: 50
  failures: 0
  failure_rate: 0.0
  chart_type_accuracy: 0.44
  x_field_accuracy: 0.52
  y_field_accuracy: 0.52
  field_selection_f1: 0.8546666666666667
  aggregation_accuracy: 0.4
  normalized_exact_match: 0.0
  vega_lite_validity: 1.0
  rendered_png: 20
```

Sample200:

```text
B0_rule_based:
  examples: 200
  predictions: 200
  failures: 0
  failure_rate: 0.0
  chart_type_accuracy: 0.54
  x_field_accuracy: 0.575
  y_field_accuracy: 0.585
  field_selection_precision: 0.84
  field_selection_recall: 0.94
  field_selection_f1: 0.857
  encoding_accuracy: 0.2525
  aggregation_accuracy: 0.26
  transform_accuracy: 1.0
  normalized_exact_match: 0.085
  vega_lite_validity: 1.0
  top1_success: 0.085
  oracle_success_at_k: 0.085
  precision_at_k: 0.0425
  mrr: 0.085
  latency_ms: 0.18079
  memory_peak_mb: 106.309

B1_constraint_ranker:
  examples: 200
  predictions: 200
  failures: 0
  failure_rate: 0.0
  chart_type_accuracy: 0.51
  x_field_accuracy: 0.575
  y_field_accuracy: 0.56
  field_selection_precision: 0.84
  field_selection_recall: 0.925
  field_selection_f1: 0.847
  encoding_accuracy: 0.2275
  aggregation_accuracy: 0.23
  transform_accuracy: 1.0
  normalized_exact_match: 0.06
  vega_lite_validity: 1.0
  top1_success: 0.06
  oracle_success_at_k: 0.085
  precision_at_k: 0.028333333333333332
  mrr: 0.06833333333333333
  latency_ms: 0.32999
  memory_peak_mb: 210.348
```

B1 is not better than B0 on exact-match-oriented metrics for this sample. It is not worse on several hard-validity and structural metrics: `failure_rate`, `vega_lite_validity`, `transform_accuracy`, `x_field_accuracy`, `field_selection_precision`, and `oracle_success_at_k`. The likely reason is that B0's direct rules already match many nvBench gold conventions, while B1's extra candidate generation sometimes ranks a valid but different chart above the simple B0 choice. This is acceptable for Stage 4 because both baselines are reproducible, valid, non-LLM baselines and B1's distinct constraint/ranking behavior is visible in the candidate lists and ranking metrics.

## Checklist

- B0 and B1 are different: yes. B0 is direct rule selection; B1 is generate-filter-rank with hard constraints and soft scoring.
- Baselines do not use gold spec: yes.
- Field linking uses only query, metadata, and table schema inference: yes.
- B1 uses hard constraints: yes.
- Predictions contain `raw_spec`, `normalized_spec`, `status`, `latency_ms`, and `candidates`: yes, verified by unit tests, smoke run, and Drive predictions.
- Failure rate acceptable: yes, 0.0 for both methods on sample50 and sample200.
- Rendered examples exist: yes, 20 PNG files per method in the final Drive run.
- Drive predictions and metrics exist: yes.
- Drive rendered examples exist: yes.

## Problems And Risks

- `rg` was unavailable in the local shell with `Access is denied`; PowerShell `Select-String` was used for plan/checklist lookup.
- The first local smoke command used bash heredoc syntax and failed before executing Python. The smoke was rerun with PowerShell here-strings and passed.
- B1 did not improve over B0 on exact-match metrics for sample200. It remains a distinct constraint/ranking baseline and matches B0 on validity/failure/transform and some field/ranking metrics.

## Next Steps

Stage 4 is ready for final commit and push. Do not start Stage 5 until the user explicitly requests it.
