# Stage 2 (a): B2_v1 design note + plan_schema_v1.json + baselines_b2_v1.py.
# Minimal patches per the triage:
#   (i)   prompt: distinguish "subquery filter" from "ORDER BY ... LIMIT 1"
#   (ii)  prompt: instruct to use distinct=True for "all distinct X" questions
#   (iii) schema: add top-level "distinct" boolean field
#   (iv)  plan->SQL prompt: honour the distinct flag

import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
REPO = PROJECT_ROOT / 'repo'
DOCS = REPO / 'docs'
EVAL_DIR = REPO / 'src' / 'evaluation'
DOCS.mkdir(parents=True, exist_ok=True)
EVAL_DIR.mkdir(parents=True, exist_ok=True)

ts = dt.datetime.now(dt.timezone.utc).isoformat()

# ---------- 1. plan_schema_v1.json ----------
v0 = json.loads((DOCS / 'plan_schema.json').read_text(encoding='utf-8'))
v1 = json.loads(json.dumps(v0))  # deep copy
v1['$id'] = 'diploma_plan_sql/plan_schema_v1.json'
v1['title'] = 'B2 Plan v1'
v1['description'] = 'Compact JSON Plan emitted by the v1 planner. v1 = v0 + top-level "distinct" boolean.'
v1['properties']['distinct'] = {
    'type': 'boolean',
    'description': 'Whether SQL must include DISTINCT in projection.'
}
(DOCS / 'plan_schema_v1.json').write_text(json.dumps(v1, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'WROTE {DOCS / "plan_schema_v1.json"} ({(DOCS / "plan_schema_v1.json").stat().st_size} B)')

# ---------- 2. design note ----------
design = f'''# B2 v1 Design Patch

Date: {ts}.

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
'''
(OUTPUTS / 'logs' / 'b2_v1_design_patch.md').write_text(design, encoding='utf-8')
print(f'WROTE {OUTPUTS / "logs" / "b2_v1_design_patch.md"}')

# ---------- 3. baselines_b2_v1.py module ----------
v1_src = '''"""B2 v1 minimal patched Plan->SQL pipeline.

Differences vs baselines_b2.py (v0):
  * Planner prompt distinguishes subquery-filter from LIMIT 1.
  * Planner prompt instructs to set distinct=True for DISTINCT questions.
  * Plan->SQL prompt honours the distinct flag and includes one in-context
    subquery-filter example.
  * Validates against plan_schema_v1.json (adds a top-level "distinct" bool).
"""
from __future__ import annotations

import json
import re
import textwrap


def make_plan_prompt(question: str, reduced_schema_context: str) -> str:
    return textwrap.dedent(f\"\"\"
    You are a SQL planner. Given a natural-language question and a database schema,
    output a single JSON object describing the plan to answer the question.
    Output JSON only. No prose, no markdown fences.

    Allowed fields (additional fields will be rejected):
    - intent: one of [select_count, select_aggregate, select_filter, select_join,
              select_groupby, select_orderby, select_other]
    - tables: array of table names from the schema
    - operations: array of short verbs describing what SQL will do
                  (e.g. ["select", "filter"], ["join", "groupby", "count"])
    - distinct: boolean. Set TRUE when the question asks for distinct/unique/different
                values (e.g. "all distinct countries", "what unique types ...").
    - columns: array of column names to project / aggregate
    - filters: array of {{"column": str, "op": one of [=, !=, >, <, >=, <=, LIKE, IN, BETWEEN], "value": any}}
    - aggregations: array of {{"function": one of [COUNT, SUM, AVG, MIN, MAX], "column": str}}
    - group_by: array of column names
    - order_by: array of {{"column": str, "dir": one of [ASC, DESC]}}
    - limit: integer or null
    - joins: array of {{"left_table": str, "right_table": str, "on": str}}
    - notes: optional short string

    Required fields: intent, tables, operations.

    IMPORTANT — picking the right pattern for "min / max / youngest / oldest" questions:

    * If the question asks for *the row with the min/max value of X*
      (e.g. "show name and age of the youngest singer"), use ORDER BY X LIMIT 1.
    * If the question asks for *all rows whose property MATCHES the min/max value*
      (e.g. "songs of the youngest singer", "all employees in the oldest department"),
      DO NOT use LIMIT 1. The "youngest singer" is one entity, but their songs may be many.
      Express this with a subquery filter, e.g. WHERE singer_id = (SELECT singer_id FROM singer ORDER BY Age ASC LIMIT 1)
      OR WHERE Age = (SELECT MIN(Age) FROM singer).
      In the plan, encode this with filters that reference the min/max condition,
      and operations should include "subquery_filter".

    Example of a subquery-filter plan (do NOT copy verbatim, adapt to the question):
    {{"intent": "select_filter", "tables": ["singer"], "operations": ["select", "subquery_filter"],
      "columns": ["Name", "Song_release_year"],
      "filters": [{{"column": "Age", "op": "=", "value": "(SELECT MIN(Age) FROM singer)"}}]}}

    {reduced_schema_context}

    Question: {question}
    JSON plan:
    \"\"\").strip()


def extract_json_block(raw_text: str) -> str:
    if not raw_text:
        return ""
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\\s*```\\s*$", "", text)
    start = text.find("{")
    if start < 0:
        return text
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False; continue
        if ch == "\\\\" and in_string:
            escape = True; continue
        if ch == '"':
            in_string = not in_string; continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:]


def parse_and_validate_plan(raw_text: str, plan_schema: dict):
    json_text = extract_json_block(raw_text)
    if not json_text:
        return None, False, "no_json_block"
    try:
        parsed = json.loads(json_text)
    except Exception as exc:
        return None, False, f"json_parse_error: {type(exc).__name__}: {exc}"
    try:
        import jsonschema
    except ImportError:
        if not isinstance(parsed, dict):
            return parsed, False, "not_object"
        for k in ("intent", "tables", "operations"):
            if k not in parsed:
                return parsed, False, f"missing_field:{k}"
        return parsed, True, ""
    try:
        jsonschema.validate(parsed, plan_schema)
        return parsed, True, ""
    except jsonschema.ValidationError as exc:
        return parsed, False, f"schema_violation: {exc.message[:200]}"
    except Exception as exc:
        return parsed, False, f"validation_error: {type(exc).__name__}: {exc}"


def make_plan_to_sql_prompt(question: str, plan_obj: dict, reduced_schema_context: str) -> str:
    plan_pretty = json.dumps(plan_obj, ensure_ascii=False, indent=2)
    return textwrap.dedent(f\"\"\"
    You are a text-to-SQL assistant. You are given a natural-language question,
    a JSON plan describing how to answer it, and the reduced schema.
    Generate one SQLite SQL query implementing the plan. Return SQL only,
    no markdown fences and no prose.

    Special handling rules:
    * If the plan has "distinct": true, the SELECT clause MUST start with SELECT DISTINCT.
    * If the plan's filters reference a subquery in their value (e.g. "(SELECT MIN(Age) FROM singer)"),
      keep that subquery exactly in the WHERE clause; DO NOT replace it with ORDER BY ... LIMIT 1.
      Example: filter [{{"column": "Age", "op": "=", "value": "(SELECT MIN(Age) FROM singer)"}}]
      must produce SQL ... WHERE Age = (SELECT MIN(Age) FROM singer).
    * Honour the plan's group_by and order_by exactly. If "limit" is null, do NOT add LIMIT.

    {reduced_schema_context}

    Question: {question}

    Plan:
    {plan_pretty}

    SQL:
    \"\"\").strip()
'''
(EVAL_DIR / 'baselines_b2_v1.py').write_text(v1_src, encoding='utf-8')
print(f'WROTE {EVAL_DIR / "baselines_b2_v1.py"} ({(EVAL_DIR / "baselines_b2_v1.py").stat().st_size} B)')
print('STATUS=DONE')
