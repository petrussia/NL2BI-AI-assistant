# Stage 3 Review: evaluator and metrics

Date: 2026-04-25

Status: **completed for review**.

Stage 4 was not started. No Stage 3 commit or push was made.

## Scope Boundary

Stage 3 implements the evaluator and metrics for post-query Text-to-Visualization. It does not implement Text-to-SQL and does not run baselines. SQL remains only an upstream/source materialization concern from Stage 2.

## Implemented Files

```text
src/t2v_eval/normalization/vega_lite.py
src/t2v_eval/normalization/__init__.py
src/t2v_eval/metrics/spec_metrics.py
src/t2v_eval/metrics/ranking_metrics.py
src/t2v_eval/metrics/system_metrics.py
src/t2v_eval/metrics/__init__.py
src/t2v_eval/utils/io.py
scripts/evaluate_predictions.py
tests/test_normalization.py
tests/test_metrics.py
notebooks/04_evaluate_and_render.ipynb
reports/stage_reviews/STAGE_3_REVIEW.md
```

## Normalization

Implemented a dependency-light Vega-Lite-like normalizer:

- canonicalizes chart mark into `chart_type`;
- extracts `x`, `y`, `color`, `size`, `shape`, `text`, `tooltip`, `detail`, `opacity`, `row`, and `column` encodings;
- extracts field, type, aggregate, bin, timeUnit, and sort;
- canonicalizes transform blocks;
- computes deterministic `canonical_json`;
- returns invalid specs as structured `valid=false` results instead of throwing.

The normalizer compares normalized canonical structures, not raw JSON string order.

## Metrics

Implemented spec metrics:

```text
chart_type_accuracy
x_field_accuracy
y_field_accuracy
field_selection_precision
field_selection_recall
field_selection_f1
encoding_accuracy
aggregation_accuracy
transform_accuracy
normalized_exact_match
vega_lite_validity
```

Implemented ranking metrics:

```text
top1_success
oracle_success_at_k
precision_at_k
mrr
```

Ranking metrics return `None` when no ranked candidates are available, and aggregate as `0.0` only in the final CSV summary.

Implemented system metrics:

```text
latency_ms
memory_peak_mb
failure_rate
```

## Evaluator CLI

Implemented `scripts/evaluate_predictions.py`.

Input:

```text
--examples / --gold-jsonl
--predictions / --predictions-jsonl
--output-dir
--top-k
--json
```

Output:

```text
per_example_metrics.csv
aggregate_metrics.csv
evaluation_summary.json
```

Invalid predicted specs do not stop evaluation. They are counted with `vega_lite_validity=0`, `normalized_exact_match=0`, and `status=failed` in spec metrics.

## Notebook

Created `notebooks/04_evaluate_and_render.ipynb` skeleton with:

1. `stage3-setup`;
2. `stage3-evaluate`.

The skeleton uses the canonical Drive root:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part
```

It expects the Colab checkout at:

```text
/content/petukhov_t2v_repo
```

The notebook has no outputs. It was not executed in Colab in this review pass because Stage 3 code is not yet pushed to `origin/experiments/peter`. Per project workflow, Colab execution of new code should happen after review approval and a code-only checkpoint commit if needed.

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

Focused Stage 3 tests:

```powershell
python -m pytest tests/test_normalization.py tests/test_metrics.py -q
```

Result:

```text
8 passed in 0.26s
```

Notebook validation:

```powershell
python -c "import nbformat; nb=nbformat.read('notebooks/04_evaluate_and_render.ipynb', as_version=4); nbformat.validate(nb); print(len(nb.cells), [c.get('id') for c in nb.cells], [len(c.get('outputs', [])) for c in nb.cells if c.cell_type == 'code'])"
```

Result:

```text
3 ['stage3-title', 'stage3-setup', 'stage3-evaluate'] [0, 0]
```

Full local test suite:

```powershell
python -m pytest -q
```

Result:

```text
13 passed in 1.46s
```

Evaluator CLI smoke during review:

```powershell
python scripts\evaluate_predictions.py `
  --examples <temp>\examples.jsonl `
  --predictions <temp>\predictions.jsonl `
  --output-dir <temp>\metrics `
  --json
```

Result:

```text
status: ok
examples: 1
predictions: 1
aggregate_metrics.csv created
per_example_metrics.csv created
evaluation_summary.json created
normalized_exact_match: 1.0
vega_lite_validity: 1.0
failure_rate: 0.0
```

Post-review final check requested by reviewer:

```powershell
python -m pytest -q
```

Result:

```text
13 passed in 1.63s
```

Five fake predictions evaluator smoke:

```powershell
python scripts\evaluate_predictions.py `
  --examples <temp>\examples.jsonl `
  --predictions <temp>\predictions.jsonl `
  --output-dir <temp>\metrics `
  --json
```

Result:

```text
status: ok
examples: 5
predictions: 5
aggregate_metrics.csv created
per_example_metrics.csv created
evaluation_summary.json created
vega_lite_validity: 0.6
normalized_exact_match: 0.2
failure_rate: 0.2
```

## Criteria Check

- `pytest` passes: yes, `13 passed`.
- Evaluator accepts gold + predicted JSONL: yes.
- `aggregate_metrics.csv` and `per_example_metrics.csv` are created: yes.
- Invalid specs do not break evaluation: yes, covered by unit tests.
- Field metrics and chart metrics are separate: yes.
- Top-k metrics work only when candidates exist: yes, no-candidate path returns `None`.
- Normalizer uses canonicalization instead of raw JSON order: yes.
- Tests cover different chart types / invalid specs / ranking / evaluator smoke: yes.

## Artifacts

No Drive artifacts were created in this Stage 3 review pass. The evaluator smoke wrote only to a local temporary directory under `%TEMP%`.

Expected future Drive metrics path when used by later stages:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/<run_id>/metrics/
```

## Problems and Risks

- The normalizer is intentionally Vega-Lite-like rather than a full Vega-Lite schema validator. It is sufficient for Stage 3 metric comparison, but full schema validation can be added later if needed.
- Ranking success currently uses normalized exact match. Later baselines may want a softer "gold-like" success criterion; the exact criterion is conservative and reproducible.
- Stage 3 Colab notebook was created as a skeleton and not executed with new code before review approval.

## Next Steps

1. Review Stage 3 implementation and tests.
2. Commit code, tests, notebook, and review markdown.
3. Push to `origin experiments/peter`.
4. Do not proceed to Stage 4 until explicitly requested.
