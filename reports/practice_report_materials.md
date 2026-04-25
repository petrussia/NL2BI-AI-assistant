# Practice Report Materials

## Stage 2: nvBench post-query benchmark preparation

Stage 2 implements the benchmark preparation layer for post-query Text-to-Visualization. The scope explicitly excludes Text-to-SQL evaluation: nvBench SQL is used only as gold materialization logic for producing ready input tables, and the downstream examples contain a materialized table path, NL query, metadata, and a gold visualization target.

Implemented components:

- `src/t2v_eval/data/nvbench_adapter.py`: nvBench discovery, loading, SQL/table materialization, fallback table extraction from `vis_obj`, example generation, and dataset card output.
- `scripts/prepare_nvbench.py`: CLI wrapper for reproducible Colab/Drive preparation runs.
- `notebooks/01_prepare_benchmarks.ipynb`: Colab runner notebook for setup, sample20, sample200, and artifact verification.
- `tests/test_nvbench_adapter.py`: smoke fixture tests and missing-source blocker behavior.

Canonical Drive root:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part
```

Processed Stage 2 artifacts:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/datasets/processed/nvbench_postquery
```

Final Colab results:

```text
sample20 successful_examples: 20
sample200 successful_examples: 200
failed_visualizations: 0
materialized table CSV files: 50
minimum successful examples threshold: passed (>= 50)
```

Verified files:

```text
examples.jsonl
examples_sample20.jsonl
examples_sample200.jsonl
dataset_card.md
prepare_result.json
runtime_info.json
tables/*.csv
failures/*.jsonl if failures exist
```

Resolution of the Colab blocker: a code-only checkpoint commit was pushed so the Colab setup cell could clone/pull `experiments/peter` into `/content/petukhov_t2v_repo`. The setup cell mounts Drive, syncs the repository, installs `requirements.txt`, installs the package editable, and verifies `t2v_eval.__version__ == 0.1.0`.

Main limitation: in the local VS Code + Colab runner path, the web Colab secret was not exposed through `google.colab.userdata`, so the setup cell supports a Drive token file outside the repository. The token itself is not committed and should be rotated because it was briefly tested in a manual notebook cell during debugging.

## Stage 4: non-LLM baseline experiments

Stage 4 implements and runs two deterministic post-query Text-to-Visualization baselines:

- `B0_rule_based`: direct intent extraction, field linking, and simple chart rules.
- `B1_constraint_ranker`: candidate generation, hard constraint filtering, and soft ranking.

Implemented components:

- `src/t2v_eval/baselines/rule_based.py`
- `src/t2v_eval/baselines/constraint_ranker.py`
- `scripts/run_experiment.py`
- `scripts/render_charts.py`
- `notebooks/02_run_baselines_cpu.ipynb`
- `tests/test_rule_baseline.py`

Final Drive run:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage4_cpu_sample200
```

Final sample200 results:

```text
B0_rule_based:
  predictions: 200
  failure_rate: 0.0
  vega_lite_validity: 1.0
  normalized_exact_match: 0.085
  field_selection_f1: 0.857
  rendered charts: 20

B1_constraint_ranker:
  predictions: 200
  failure_rate: 0.0
  vega_lite_validity: 1.0
  normalized_exact_match: 0.06
  field_selection_f1: 0.847
  rendered charts: 20
```

B1 is not better than B0 on exact-match-oriented metrics for this sample, but it is not worse on validity/failure/transform metrics and remains a distinct constraint-based ranking baseline.

## Stage 5: existing / partial tool baseline

Stage 5 attempted to add an existing open-source Text-to-Visualization comparison tool. NL4DV was checked first, but it was not installed because its dry-run dependency plan included `pytest~=3.10.1` plus a large stack (`spacy`, `litellm`, `openai`, `vega`, and others), which is risky for the current project environment. This is documented as an incompatibility rather than hidden.

Implemented fallback:

```text
B2_partial_recommender
```

This is a partial fit: it uses the query for field filtering/ranking, while chart recommendation comes from table/schema profiling heuristics. It uses the same prediction format and evaluator as B0/B1.

Final Drive run:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage5_partial_sample200
```

Final sample200 results:

```text
B2_partial_recommender:
  predictions: 200
  failure_rate: 0.0
  vega_lite_validity: 1.0
  chart_type_accuracy: 0.62
  field_selection_f1: 0.8703333333333333
  encoding_accuracy: 0.11
  aggregation_accuracy: 0.11
  normalized_exact_match: 0.11
  rendered charts: 20
```

## Stage 6: local LLM baseline

Stage 6 implements a local Hugging Face Transformers baseline:

```text
B3_local_llm_qwen3_8b
```

Model:

```text
Qwen/Qwen3-8B
```

The run uses local Colab inference with 4-bit quantization. No closed hosted API is used, and Qwen2.5 is explicitly rejected by config validation.

The initial Qwen3 run was too slow because the model spent too much time in long generation/reasoning mode. The implementation was updated to disable Qwen3 thinking mode, add `/no_think`, reduce `max_new_tokens` to 384, and stop generation after the first complete top-level JSON spec.

Final Drive run:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage6_qwen3_8b_fast_sample50
```

Final sample50 results:

```text
B3_local_llm_qwen3_8b:
  predictions: 50
  failures: 7
  failure_rate: 0.14
  vega_lite_validity: 0.86
  chart_type_accuracy: 0.5
  x_field_accuracy: 0.72
  y_field_accuracy: 0.6
  field_selection_f1: 0.7533333333333333
  encoding_accuracy: 0.59
  aggregation_accuracy: 0.84
  normalized_exact_match: 0.36
  latency_ms: 10187.22126
  memory_peak_mb: 1983.812
  rendered charts: 20
```

The speed fix reduced observed average latency from about 96 seconds/example on the first sample20 run to about 10 seconds/example on the final sample50 run.

## Stage 7: LLM validator/reranker

Stage 7 implements a multi-candidate local LLM baseline:

```text
B4_llm_validator_reranker
```

The method generates three candidates per example with `Qwen/Qwen3-8B`, validates each candidate without using gold specs, and reranks by JSON/Vega-Lite validity, field legality, dtype compatibility, aggregation legality, and parsimony.

Small latency probes were run before the final run:

```text
stage7_b4_latency2_tokens256: latency_ms 46669.4215
stage7_b4_latency2_tokens384: latency_ms 41201.849
```

`max_new_tokens=384` was selected.

Final Drive run:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage7_b4_sample20_tokens384
```

Final sample20 results:

```text
B4_llm_validator_reranker:
  predictions: 20
  candidates saved: 60
  failure_rate: 0.05
  vega_lite_validity: 0.95
  field_selection_f1: 0.8
  encoding_accuracy: 0.5
  aggregation_accuracy: 0.85
  normalized_exact_match: 0.5
  top1_success: 0.5
  oracle_success_at_k: 0.5
  latency_ms: 34898.125199999995
  rendered charts: 19
```

Compared with the Stage 6 B3 fast sample20 run, B4 improves failure rate, validity, field F1, normalized exact match, and top1 success, but it is about 3.4x slower because it performs three LLM generations per example.
