# Stage 7 Review: LLM validator/reranker

Date: 2026-04-26

Status: **finalized after review acceptance**.

Stage 8 was not started.

## Scope Boundary

Stage 7 improves the post-query Text-to-Visualization LLM baseline only. It does not implement Text-to-SQL and does not use closed hosted APIs.

## Implemented Files

```text
configs/colab_llm_reranker.yaml
notebooks/03_run_local_llm.ipynb
scripts/run_llm_rerank_experiment.py
src/t2v_eval/baselines/__init__.py
src/t2v_eval/baselines/llm_vegalite.py
src/t2v_eval/baselines/llm_validator_reranker.py
tests/test_llm_validator_reranker.py
reports/stage_reviews/STAGE_7_REVIEW.md
```

Code checkpoint pushed so Colab could pull the implementation:

```text
33bd7e2 feat: add Stage 7 LLM validator reranker
```

## Baseline

Implemented:

```text
B4_llm_validator_reranker
```

Model:

```text
Qwen/Qwen3-8B
```

Generation settings:

```text
candidate_count: 3
candidate_temperatures: [0.0, 0.2, 0.3]
max_new_tokens: 384
top_p: 0.9
enable_thinking: false
stop_after_json: true
quantization: 4bit
```

The first candidate is deterministic and preserves the strong B3-style path. The other candidates use small temperature and prompt variants.

## Validator/Reranker

Each candidate is validated and scored without using the gold spec.

Validator checks:

- JSON extraction and parse success;
- Vega-Lite-like validity;
- field legality against input metadata;
- dtype compatibility;
- aggregation legality;
- parsimony/readability proxy.

The reranker chooses the highest-scoring valid candidate as the top prediction. All candidates are preserved in `predictions/*.jsonl`.

## Latency Tuning

The requested small-sample latency probes were run before the final B4 run.

```text
stage7_b4_latency2_tokens256:
  examples: 2
  candidates: 6
  failure_rate: 0.0
  vega_lite_validity: 1.0
  normalized_exact_match: 1.0
  latency_ms: 46669.4215

stage7_b4_latency2_tokens384:
  examples: 2
  candidates: 6
  failure_rate: 0.0
  vega_lite_validity: 1.0
  normalized_exact_match: 1.0
  latency_ms: 41201.849
```

`max_new_tokens=384` was selected because it was faster on the 2-example probe and had the same quality.

## Final Run

Final Drive run:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage7_b4_sample20_tokens384
```

After review acceptance, this already completed and verified run was kept as the final Stage 7 run. It was not rerun, to avoid repeating the same expensive B4 generation.

Final B4 metrics:

```text
predictions: 20
candidate_rows: 60
failures: 1
failure_rate: 0.05
vega_lite_validity: 0.95
chart_type_accuracy: 0.5
x_field_accuracy: 0.5
y_field_accuracy: 0.5
field_selection_f1: 0.8
encoding_accuracy: 0.5
aggregation_accuracy: 0.85
transform_accuracy: 0.95
normalized_exact_match: 0.5
top1_success: 0.5
oracle_success_at_k: 0.5
precision_at_k: 0.36666666666666664
mrr: 0.5
latency_ms: 34898.125199999995
memory_peak_mb: 2153.457
rendered_png: 19
render_failures: 0
```

Artifact verification:

```text
missing: []
rendered: 19
STAGE7_ARTIFACTS_OK
```

## B3 Comparison

Comparable B3 fast sample20 from Stage 6:

```text
run_id: stage6_qwen3_8b_fast_sample20
failure_rate: 0.15
vega_lite_validity: 0.85
field_selection_f1: 0.7333333333333333
normalized_exact_match: 0.35
top1_success: 0.4117647058823529
latency_ms: 10381.32785
```

B4 sample20:

```text
failure_rate: 0.05
vega_lite_validity: 0.95
field_selection_f1: 0.8
normalized_exact_match: 0.5
top1_success: 0.5
oracle_success_at_k: 0.5
latency_ms: 34898.125199999995
```

Conclusion: B4 improves quality and failure rate on the sample20 comparison, but it is about 3.4x slower because it generates three candidates per example.

## Commands Run

Local tests:

```powershell
python -m pytest -q
```

Result:

```text
32 passed
```

Colab runner commands:

```powershell
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\03_run_local_llm.ipynb -Action cell -CellId stage6-setup -WaitSeconds 45 -ReloadFromDisk:$false -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\03_run_local_llm.ipynb -Action cell -CellId stage7-latency2-256 -WaitSeconds 120 -ReloadFromDisk:$false -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\03_run_local_llm.ipynb -Action cell -CellId stage7-latency2-384 -WaitSeconds 150 -ReloadFromDisk:$false -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\03_run_local_llm.ipynb -Action cell -CellId stage7-run20 -WaitSeconds 240 -ReloadFromDisk:$false -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\03_run_local_llm.ipynb -Action cell -CellId stage7-verify-artifacts -WaitSeconds 30 -ReloadFromDisk:$false -Json
```

Markers:

```text
STAGE6_SETUP_OK
STAGE7_LATENCY2_256_OK
STAGE7_LATENCY2_384_OK
STAGE7_RUN20_OK
STAGE7_ARTIFACTS_OK
```

## Checklist

- All candidates saved: yes, `candidate_rows=60` for 20 examples.
- Reranker does not use gold spec: yes.
- Validator checks legality against the input table metadata: yes.
- Oracle@3 computed: yes, evaluator uses `top_k=3`.
- B4 compared against B3: yes.
- Stage 8 not started: yes.

## Problems And Risks

- B4 latency is materially higher than B3 because it performs three generations per example.
- The reranker score is heuristic and does not use learned relevance; it mainly filters invalid/illegal/over-complex specs.
- The final sample is 20 examples to keep Colab time bounded after latency tuning.

## Next Steps

- Do not start Stage 8 until explicitly requested.
