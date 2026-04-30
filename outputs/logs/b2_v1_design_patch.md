# B2 v1 Design Patch

Date: 2026-04-29T14:33:21.758306+00:00.

## Scope
Minimum-viable patches addressing the three failures of B2_v0 on smoke10
(idx 6, 7 = `result_mismatch`; idx 8 = `plan_invalid`). No retrieval, no
repair, no multi-candidate.

## Changes vs B2_v0

### a. Planner prompt
- Add explicit instruction distinguishing "find the entity whose property
  is min/max, then list its rows" (use a SUBQUERY filter, e.g.
  `WHERE x = (SELECT MIN(...))`) from "the first row sorted by X" (LIMIT 1).
- Add one short in-context example for the subquery pattern (~6 lines).
- Add explicit instruction for DISTINCT questions: emit `"distinct": true`
  in the plan when the question contains "all distinct ...", "unique ...",
  "different ..." etc.

### b. Plan schema (`plan_schema_v1.json`)
- Add a top-level optional boolean field `distinct`.
- Otherwise identical to `plan_schema.json` (v0). Required fields and
  `additionalProperties: false` semantics unchanged.

### c. Plan->SQL prompt
- Add one sentence: "If the plan has `distinct: true`, prepend SELECT with DISTINCT".
- Add same one in-context example (subquery filter for "songs of the youngest")
  but in the SQL form, so the model sees both ends of the patch.

## Risks
- More text in the prompt may slow inference and could distract on simpler questions.
- Adding `"distinct"` to the schema increases the surface for the model to emit
  unrelated boolean fields; mitigated by `additionalProperties: false`.
- The subquery-vs-LIMIT instruction may push the model toward subqueries even
  when LIMIT is correct (e.g., "the top-3 stadiums by capacity"). We do not
  have such a case in smoke10, but worth watching on smoke25.

## Out of v1 scope
- Retrieval (cross-DB) — belongs to B1R / B2R.
- Repair / retry loop on SQL execution failure.
- Multi-candidate sampling, self-consistency.
- Domain-doc retrieval, fine-tuning.

## Acceptance criteria
- B2_v1 EX on smoke10 ≥ B2_v0 EX (0.7) — preferably ≥ 0.9.
- Plan_valid_count ≥ 9/10 (do not regress on planner reliability).
- No new error_types appear (no `gen_failed`, no `plan_parse_failures`).

## Code layout
- `repo/src/evaluation/baselines_b2_v1.py` — v1 module. Original
  `baselines_b2.py` (v0) is left untouched.
- `repo/docs/plan_schema_v1.json` — v1 schema. Original `plan_schema.json`
  (v0) is left untouched.
