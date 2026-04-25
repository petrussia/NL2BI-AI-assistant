# Stage 6 Review: local LLM Vega-Lite baseline

Date: 2026-04-25

Status: **completed and pushed-ready**.

Stage 7 was not started.

## Scope Boundary

Stage 6 implements a local LLM baseline for post-query Text-to-Visualization. It does not implement Text-to-SQL and does not call any closed hosted API. The input remains a prepared `T2VExample` with a materialized table, NL query, metadata, and gold spec for evaluation only.

## Implemented Files

```text
src/t2v_eval/baselines/llm_vegalite.py
src/t2v_eval/baselines/__init__.py
scripts/run_llm_experiment.py
configs/colab_llm_8b.yaml
notebooks/03_run_local_llm.ipynb
tests/test_llm_vegalite.py
reports/stage_reviews/STAGE_6_REVIEW.md
```

## Baseline

Implemented:

```text
B3_local_llm_qwen3_8b
```

Model:

```text
Qwen/Qwen3-8B
```

The config rejects `Qwen2.5` model IDs. The implementation uses Hugging Face Transformers locally in Colab with 4-bit quantization.

## Speed Fix

The first Qwen3 run was too slow because generation used the default chat behavior and `max_new_tokens=1024`.

Changes applied:

- disabled Qwen3 thinking mode through `enable_thinking=False`;
- added `/no_think` to system/user prompt text;
- reduced default `max_new_tokens` to `384`;
- added `stop_after_json`;
- changed stop logic to stop only after the first complete top-level JSON object;
- stripped `<think>...</think>` blocks before JSON extraction;
- added a 2-example latency probe cell.

Observed latency improvement:

```text
old sample20 latency_ms: 96371.9068
fast latency2 latency_ms: 13554.3165
fast sample20 latency_ms: 10381.32785
fast sample50 latency_ms: 10187.22126
```

This reduced average latency from about 96 seconds/example to about 10 seconds/example, roughly a 9x speed-up on the final sample50 run.

## Prompt

`build_prompt()` includes:

- user query;
- compact schema metadata;
- first `N` table rows, default `N=5`;
- allowed chart mark types;
- strict JSON-only instruction;
- instruction not to use markdown, explanations, code fences, or `<think>` blocks;
- field legality and dtype/aggregation guidance.

## JSON Extraction And Repair-Lite

Implemented:

- markdown fence stripping;
- `<think>` block stripping;
- first complete top-level JSON object extraction;
- JSON parsing;
- simple repair-lite:
  - `chart_type` to `mark`;
  - top-level `x`/`y`/`color`/`tooltip`/`text` moved into `encoding`;
  - missing encoding `type` filled from metadata where possible;
- Vega-Lite-like validation through the existing normalizer.

Invalid output becomes a structured failed `T2VPrediction` instead of stopping the whole run.

## Colab Runs

Runtime: Colab GPU L4, High RAM.

Canonical Drive root:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part
```

Initial code checkpoint:

```text
f31c320 feat: add Stage 6 local LLM baseline
```

Speed checkpoints:

```text
bbe7c89 perf: speed up Stage 6 Qwen3 generation
b66bc53 fix: stop Stage 6 generation on complete JSON spec
```

Final selected run:

```text
/content/drive/MyDrive/diploma/petr_text_to_visualization_part/runs/stage6_qwen3_8b_fast_sample50
```

Final run metrics:

```text
run_id: stage6_qwen3_8b_fast_sample50
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
transform_accuracy: 0.86
normalized_exact_match: 0.36
top1_success: 0.4186046511627907
latency_ms: 10187.22126
memory_peak_mb: 1983.812
rendered_png: 20
render_failures: 10
```

Verified final artifacts:

```text
examples_used.jsonl
runtime_info.json
llm_config.json
gpu_runtime_before.json
gpu_runtime_after.json
pip_freeze.txt
experiment_summary.json
predictions/B3_local_llm_qwen3_8b.jsonl
metrics/B3_local_llm_qwen3_8b/aggregate_metrics.csv
metrics/B3_local_llm_qwen3_8b/per_example_metrics.csv
metrics/B3_local_llm_qwen3_8b/evaluation_summary.json
rendered/B3_local_llm_qwen3_8b/*.png
rendered/B3_local_llm_qwen3_8b/render_failures.json
```

Artifact verification result:

```text
missing: []
rendered: 20
STAGE6_ARTIFACTS_OK
```

## Commands Run

Local tests before code checkpoint:

```powershell
python -m pytest -q
```

Result:

```text
26 passed
```

After speed fixes:

```powershell
python -m pytest -q
```

Result:

```text
28 passed
```

Colab runner commands:

```powershell
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\03_run_local_llm.ipynb -Action cell -CellId stage6-setup -WaitSeconds 45 -ReloadFromDisk:$false -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\03_run_local_llm.ipynb -Action cell -CellId stage6-latency2 -WaitSeconds 120 -ReloadFromDisk:$false -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\03_run_local_llm.ipynb -Action cell -CellId stage6-run20 -WaitSeconds 120 -ReloadFromDisk:$false -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\03_run_local_llm.ipynb -Action cell -CellId stage6-run50 -WaitSeconds 180 -ReloadFromDisk:$false -Json
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\03_run_local_llm.ipynb -Action cell -CellId stage6-verify-artifacts -WaitSeconds 30 -ReloadFromDisk:$false -Json
```

Markers:

```text
STAGE6_SETUP_OK
STAGE6_LATENCY2_OK
STAGE6_SAMPLE20_OK
STAGE6_SAMPLE50_OK
STAGE6_ARTIFACTS_OK
```

## Checklist

- No closed API: yes.
- Model is not Qwen2.5: yes.
- Prompt requires JSON without markdown: yes.
- JSON extraction and validation implemented: yes.
- VRAM/latency logs written: yes.
- Run sample not too small: yes, final run uses 50 examples.
- Model cache in git: no.
- Stage 7 not started: yes.

## Problems And Risks

- Even after the speed fix, Qwen3-8B is still much slower than deterministic baselines: about 10 seconds/example on this Colab L4 run.
- Render smoke produced 20 PNG files but 10 render failures; metrics/predictions are present, and render failures are saved under the run folder.
- Quality is much better after disabling thinking, but not perfect: `failure_rate=0.14`, `normalized_exact_match=0.36`.

## Next Steps

- Commit the final cleared notebook and this review markdown.
- Push `origin experiments/peter`.
- Do not start Stage 7 until explicitly requested.
