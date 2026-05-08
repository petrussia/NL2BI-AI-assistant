# Stage 5 NL4DV Compatibility Note

Date: 2026-04-25

Status: **NL4DV full-fit baseline not used**.

## Attempt

The project environment was checked with:

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

The dry-run completed within the Stage 5 time budget and resolved `nl4dv==4.1.0`, but the dependency plan is not safe for the current project environment.

## Compatibility Issue

The dry-run would install or change a large dependency stack, including:

```text
nl4dv-4.1.0
pytest-3.10.1
pytest-cov-2.6.1
spacy-3.8.14
litellm-1.71.3
openai-2.32.0
vega-4.1.0
pandas-2.2.3
```

The critical blocker is `pytest~=3.10.1`. The local project test suite currently runs on a modern pytest version, and installing NL4DV directly into the working environment could downgrade or destabilize the test/runtime stack. The package also pulls LLM/API-related dependencies that are not needed for this non-LLM existing-tool baseline.

## Decision

NL4DV was not installed into the project environment, and no repository requirements were changed for NL4DV.

Per Stage 5 instructions, the fallback implementation is:

```text
B2_partial_recommender
```

This is marked as a **partial fit**:

- it uses the NL query for field filtering/ranking;
- chart recommendations are generated from table/schema profiling heuristics;
- it does not claim to be a full NL4DV replacement.

