# Stage 1 Review: minimal reproducible scaffold

Date: 2026-04-25

Status: **completed, awaiting user/ChatGPT review**.

No Stage 2 work was started. No commit or push was made.

## Scope Boundary

Stage 1 only creates the reproducible code scaffold for post-query Text-to-Visualization. Text-to-SQL remains out of scope. No benchmark preparation, baseline execution, model inference, or heavy Drive artifact generation was performed.

## Implemented

### Environment and Packaging

- Updated `.gitignore` with Python-generated artifact rules for `__pycache__/`, `*.py[cod]`, `*.egg-info/`, and `.pytest_cache/`.
- Added `requirements.txt` with lightweight CPU-stage dependencies:
  - `pandas`, `numpy>=1.23`, `pyyaml`, `tqdm`, `jsonschema`, `altair`, `vl-convert-python`, `psutil`, `scikit-learn`, `matplotlib`, `pytest`, `nbformat`, `jupyter`.
- Added `pyproject.toml` for editable install from `src/`.
- Added pytest config with `pythonpath = ["src"]`.

### Configs

- Added `configs/default.yaml`.
- Added Colab-oriented config placeholders:
  - `configs/colab_cpu.yaml`;
  - `configs/colab_llm_8b.yaml`;
  - `configs/colab_llm_14b.yaml`.
- Drive root is not hardcoded across code. Config records:
  - env variable: `T2V_DRIVE_ROOT`;
  - approved canonical root: `/content/drive/MyDrive/diploma/petr_text_to_visualization_part`;
  - deprecated non-diploma root: `/content/drive/MyDrive/petr_text_to_visualization_part`, not used for artifacts.

### Package Structure

Created package initializers and minimal modules:

```text
src/t2v_eval/
├── __init__.py
├── baselines/__init__.py
├── data/
│   ├── __init__.py
│   └── schema.py
├── metrics/__init__.py
├── normalization/__init__.py
├── rendering/__init__.py
└── utils/
    ├── __init__.py
    ├── io.py
    └── reproducibility.py
```

Implemented:

- `src/t2v_eval/utils/io.py`
  - `read_json`, `write_json`;
  - `read_jsonl`, `write_jsonl`;
  - `read_yaml`, `write_yaml`;
  - `read_csv`, `write_csv`.
- `src/t2v_eval/utils/reproducibility.py`
  - `set_seed`;
  - `git_sha`;
  - `git_status_short`;
  - `pip_freeze`;
  - `runtime_info`.
- `src/t2v_eval/data/schema.py`
  - `FieldMetadata`;
  - `T2VSpec`;
  - `T2VExample`;
  - `T2VPrediction`.

### Notebook

Updated `notebooks/00_setup_and_drive.ipynb` into a valid Stage 1 setup notebook with four cells:

1. title/description;
2. mount Drive and verify/create `T2V_DRIVE_ROOT`, defaulting to `/content/drive/MyDrive/diploma/petr_text_to_visualization_part`;
3. install requirements and editable package when `T2V_REPO_ROOT` points to the repo;
4. verify `import t2v_eval`, create standard Drive subfolders, and build a smoke `T2VExample`.

The notebook is valid JSON and has no saved outputs.

### Tests

Added:

- `tests/conftest.py`;
- `tests/test_schema.py`;
- `tests/test_smoke_pipeline.py`.

The smoke test verifies package import and JSONL write/read roundtrip.

## Commands Run

Editable install:

```powershell
python -m pip install -e .
```

Result:

```text
Successfully built t2v-eval
Successfully installed t2v-eval-0.1.0
```

Dependency install attempt:

```powershell
python -m pip install -r requirements.txt
```

Result:

```text
command timed out after 304056 milliseconds
```

Follow-up checks showed required Stage 1 packages were installed or already available, including `pytest`, `jupyter`, and `vl-convert-python`. The timeout is recorded as an environment issue, not a code failure.

Package import smoke:

```powershell
python -c "import t2v_eval; print(t2v_eval.__version__)"
```

Result:

```text
0.1.0
```

JSONL smoke:

```powershell
python -c "import t2v_eval, numpy; from t2v_eval.utils.io import write_jsonl, read_jsonl; print('t2v_eval', t2v_eval.__version__); print('numpy', numpy.__version__); print(read_jsonl(write_jsonl('reports/stage_reviews/stage1_smoke_tmp.jsonl', [{'ok': True}])))"
```

Result:

```text
t2v_eval 0.1.0
numpy 1.26.4
[{'ok': True}]
```

Temporary smoke file `reports/stage_reviews/stage1_smoke_tmp.jsonl` was removed after the check.

Notebook validation:

```powershell
python -c "import nbformat; nb=nbformat.read('notebooks/00_setup_and_drive.ipynb', as_version=4); nbformat.validate(nb); print(len(nb.cells), [c.get('id') for c in nb.cells])"
```

Result:

```text
4 ['stage1-setup-title', 'mount-drive', 'install-dependencies', 'verify-package-and-paths']
```

Pytest:

```powershell
python -m pytest -q
```

Result:

```text
...                                                                      [100%]
3 passed in 0.11s
```

Pip check:

```powershell
python -m pip check
```

Result:

```text
opencv-python 4.12.0.88 has requirement numpy<2.3.0,>=2; python_version >= "3.9", but you have numpy 1.26.4.
```

This is a conflict in the shared local Python environment between unrelated preinstalled packages. The Stage 1 package does not depend on OpenCV or TensorFlow, and project tests pass. A clean virtual environment or Colab runtime should be used for later reproducible runs.

## Runtime Info

```json
{
  "python": "3.11.1",
  "python_executable": "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
  "platform": "Windows-10-10.0.26200-SP0",
  "git_sha": "1e00a3cef6b83ed8792a3e13056d8e66cef43f6c",
  "seed": 42,
  "t2v_drive_root_env": "T2V_DRIVE_ROOT"
}
```

## Files Created or Updated for Stage 1

```text
requirements.txt
pyproject.toml
.gitignore
configs/default.yaml
configs/colab_cpu.yaml
configs/colab_llm_8b.yaml
configs/colab_llm_14b.yaml
notebooks/00_setup_and_drive.ipynb
src/t2v_eval/__init__.py
src/t2v_eval/baselines/__init__.py
src/t2v_eval/data/__init__.py
src/t2v_eval/data/schema.py
src/t2v_eval/metrics/__init__.py
src/t2v_eval/normalization/__init__.py
src/t2v_eval/rendering/__init__.py
src/t2v_eval/utils/__init__.py
src/t2v_eval/utils/io.py
src/t2v_eval/utils/reproducibility.py
tests/conftest.py
tests/test_schema.py
tests/test_smoke_pipeline.py
reports/stage_reviews/STAGE_1_REVIEW.md
```

## Existing Dirty Worktree Not Owned by Stage 1

These files were already modified/deleted/untracked before Stage 1 and were not reverted:

```text
 M docs/README.en.md
 M docs/README.ru.md
 D notebooks/example.ipynb
 M notebooks/upload.ipynb
 D scripts/run_colab_notebook.ps1
?? notebooks/01_prepare_benchmarks.ipynb
?? notebooks/02_run_baselines_cpu.ipynb
?? notebooks/03_run_local_llm.ipynb
?? notebooks/04_evaluate_and_render.ipynb
?? notebooks/05_make_report_materials.ipynb
?? notebooks/legacy/
?? reports/practice_report_materials.md
?? scripts/colab/
?? scripts/evaluate_predictions.py
?? scripts/prepare_nvbench.py
?? scripts/render_charts.py
?? scripts/run_experiment.py
?? scripts/summarize_results.py
?? tests/test_metrics.py
?? tests/test_normalization.py
?? tests/test_nvbench_adapter.py
?? tests/test_rule_baseline.py
```

Some scaffold files listed above will likely become Stage 2+ work. They were intentionally not implemented during Stage 1.

## Criteria Check

- `pytest` passes: yes, `3 passed`.
- `import t2v_eval` works after editable install: yes.
- JSONL write/read works: yes.
- `T2VExample` contains query, table path, metadata, and gold spec: yes.
- Drive path is configurable through `T2V_DRIVE_ROOT` and config YAML, with canonical default `/content/drive/MyDrive/diploma/petr_text_to_visualization_part`: yes.
- No large datasets, model weights, rendered charts, or runs were added: yes.
- Notebook is valid JSON and has no heavy saved outputs: yes.

## Problems and Risks

- `python -m pip install -r requirements.txt` exceeded the 5-minute tool timeout once. Required packages were available afterward, and tests passed.
- `python -m pip check` reports a local environment conflict involving `opencv-python` and NumPy. This is outside the Stage 1 package surface but should be avoided in final reproducibility by using a clean Colab runtime or virtual environment.
- The canonical Drive root was approved as `/content/drive/MyDrive/diploma/petr_text_to_visualization_part`.
- The non-diploma root `/content/drive/MyDrive/petr_text_to_visualization_part` is deprecated and must not be used for artifacts.
- Several empty scaffold files for later stages already exist and should not be mistaken for completed implementations.

## Next Steps

After review approval only:

1. Run final `python -m pytest -q`.
2. Check `git status`.
3. Commit only Stage 1 code/config/notebook/test/review files.
4. Push to `origin experiments/peter`.
5. Do not start Stage 2 until the Stage 1 review is approved.
