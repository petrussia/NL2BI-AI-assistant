# B2 Design Decision

Date: 2026-04-25T17:21:14.653161+00:00.

## Where new B2 code goes
- New file `repo/src/evaluation/baselines_b2.py`. Keeps `baselines.py` (B1 lexical schema linking + helpers) untouched. B2-specific names live in their own module so a future refactor can replace either side independently.
- B2 prompt builders, parser, validator, and per-item runner all live in `baselines_b2.py`.
- The bridge-side script that drives the run is `tools/remote_scripts/12_b2_smoke10_components.py` (component test) and `tools/remote_scripts/13_b2_smoke10_bg.py` (background inference dispatcher analogous to `04b_smoke25_b0_and_b1_bg.py`).

## What the planner is allowed to produce
- Strict JSON. No markdown fences in the final answer; the parser strips fences if present.
- Validated against `repo/docs/plan_schema.json` (we authored it in this step — it did not exist on Drive before).
- Required fields: `intent`, `tables`, `operations`. Optional: `columns`, `filters`, `aggregations`, `group_by`, `order_by`, `limit`, `joins`, `notes`. `additionalProperties: false` everywhere to refuse hallucinated fields.
- `intent` is an enum of seven shapes that cover Spider question types ("select_count", "select_aggregate", "select_filter", "select_join", "select_groupby", "select_orderby", "select_other").
- Validation uses the `jsonschema` Python library (installed if missing).

## Pipeline shape (B2 minimal)
```
question
   |---> lexical_schema_linking (reused from B1)
   |---> reduced_schema_context  (reused from B1)
   v
make_plan_prompt --(model.generate, max_new=256, greedy)--> plan_raw
   |---> extract_json_block
   v
parse_and_validate_plan --(jsonschema validate)--> plan_parsed, plan_valid, plan_error
   |---> if invalid: record error_type='plan_invalid', skip SQL generation
   v
make_plan_to_sql_prompt(question, plan_parsed, reduced_schema)
   |---> model.generate, max_new=192, greedy --> sql_raw
   |---> extract_sql
   v
execute_sql, evaluate against gold --> executable, execution_match, error_type
```

## Out of B2 scope (deferred to B2.5+)
- Repair / retry loop on SQL execution failure.
- Multi-candidate generation + execution-guided selection.
- Cross-DB schema retrieval (still uses lexical linking on the question's own DB).
- Domain-doc retrieval (Spider has no glossary worth retrieving).
- Fine-tuning of any kind.

## Why we author plan_schema.json now
The original project notes listed `plan_schema.json` as already created, but the preflight (`outputs/logs/b2_preflight_drive.md`) found it missing on Drive (`MISSING: plan_schema.json (searched repo/docs/, docs/, contracts/, repo/, root)`). To unblock B2 we author the minimal version above. If a richer pre-existing schema turns up later it can replace this file; the parser only depends on the field names listed in `make_plan_prompt`.
