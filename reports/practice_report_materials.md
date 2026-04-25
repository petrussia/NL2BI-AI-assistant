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
