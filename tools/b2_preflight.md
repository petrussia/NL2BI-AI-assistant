# B2 Preflight (local mirror)

## Pass/Fail
**PASS** after authoring `repo/docs/plan_schema.json`. Drive copy: `outputs/logs/b2_preflight_drive.md`.

## What was checked
- Bridge `/health`: ok (pid 2218).
- B0 + B1 predictions/metrics on both smoke10 and smoke25: present.
- Practice evidence pack (worklog/checklist/mapping): present.
- Thesis evidence pack (experiment_inventory): present.
- B2 readiness + B2 implementation plan from previous step: present.
- Spider data (smoke10/25 subsets, tables.json, SOURCE_AND_AUDIT.md): present.
- `repo/src/evaluation/baselines.py` (B1 helpers): present.

## What was missing → fixed
- `repo/docs/plan_schema.json`: not present. Authored a minimal one in `tools/remote_scripts/11_b2_design_and_schema.py` (3384 B).
- `output_contract.json`: not present, not strictly required for B2 since B2 outputs use the same shape as B0/B1 + extra `plan_*` columns. Not authoring a placeholder.

## What was added in design step
- `repo/docs/plan_schema.json` (Drive)
- `repo/src/evaluation/baselines_b2.py` (Drive) — `make_plan_prompt`, `extract_json_block`, `parse_and_validate_plan`, `make_plan_to_sql_prompt`. Reuses `lexical_schema_linking`, `build_reduced_schema_context`, `extract_sql`, `execute_sql` from B0/B1 helpers.
- `outputs/logs/b2_design_decision.md` (Drive) — rationale.
- Pip-installed `jsonschema` (4.26.0) on the Colab kernel for plan validation.

## Next step
Component sanity test on smoke10 item 0 → one full round-trip through the B2 pipeline → if green, run B2 smoke10 in BG thread.
