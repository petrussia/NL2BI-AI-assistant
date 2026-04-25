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
