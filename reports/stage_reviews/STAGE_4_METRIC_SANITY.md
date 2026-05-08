# Stage 4 Metric Sanity Audit

Date: 2026-04-25

Status: **completed for review**.

Stage 5 was not started. No code changes were made.

## Scope

This audit checks whether the Stage 4 non-LLM baselines accidentally use gold visualization specs during prediction, and clarifies how to interpret the final aggregate metrics.

Final Drive run:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage4_cpu_sample200
```

## Gold Leakage Search

Command:

```powershell
Select-String -Path "src/t2v_eval/baselines/*.py","scripts/run_experiment.py" `
  -Pattern "gold_spec|gold_spec_normalized|normalized_exact_match|example\.gold" `
  -CaseSensitive
```

Result:

```text
no matches
```

Files checked:

```text
src/t2v_eval/baselines/__init__.py
src/t2v_eval/baselines/rule_based.py
src/t2v_eval/baselines/constraint_ranker.py
scripts/run_experiment.py
```

Conclusion: no gold leakage was found in B0, B1, or the experiment prediction path.

`B0_rule_based` predicts from `example.query`, metadata fields, and optional table schema inference only. `B1_constraint_ranker` uses the same inputs plus hard constraints and ranking over generated candidates. Neither baseline reads `gold_spec`, `gold_spec_normalized`, `normalized_exact_match`, or any `example.gold*` attribute.

`scripts/run_experiment.py` loads examples, runs predictors, writes `predictions/*.jsonl`, and only then calls the evaluator. The evaluator is allowed to use gold specs because it is not part of prediction.

## Metrics Read From Drive

Drive files read:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage4_cpu_sample200/metrics/B0_rule_based/aggregate_metrics.csv
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage4_cpu_sample200/metrics/B1_constraint_ranker/aggregate_metrics.csv
```

`B0_rule_based`:

```text
examples: 200
predictions: 200
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
failure_rate: 0.0
```

`B1_constraint_ranker`:

```text
examples: 200
predictions: 200
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
failure_rate: 0.0
```

## Metric Interpretation

`vega_lite_validity=1.0` is not semantic accuracy. It only means every produced spec passed the evaluator's Vega-Lite structural normalization/validity check. A valid Vega-Lite spec can still choose the wrong chart type, wrong fields, wrong encodings, or wrong aggregation.

`failure_rate=0.0` is not chart correctness. It only means the pipeline returned a prediction row with `status=ok` for every example. It does not prove that the predicted chart answers the natural-language query.

`rendered=20` is only a render smoke check. It confirms that the first 20 successful predictions per method could be rendered to image files. It is useful for detecting broken specs or renderer issues, but it is not a quality metric for semantic match against the gold visualization.

The real quality metrics for Stage 4 should be treated as:

```text
chart_type_accuracy
x_field_accuracy
y_field_accuracy
field_selection_f1
encoding_accuracy
aggregation_accuracy
normalized_exact_match
```

These metrics compare predicted chart structure against the gold spec and are the primary indicators of baseline quality. For the final sample200 run, B0 is stronger than B1 on most exact-match-oriented quality metrics, while B1 remains useful as a distinct constraint/ranking baseline.

## Audit Result

- Gold leakage found: **no**.
- Baseline code changed: **no**.
- Stage 5 started: **no**.

