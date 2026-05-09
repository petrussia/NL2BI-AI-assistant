# Step 11: B2 design decision + author the minimal plan_schema.json the
# implementation will validate against. Writes both to Drive.

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

# ---------- 1. plan_schema.json ----------
# Minimal but strict enough to catch nonsense. Strict-ish typing.
plan_schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "diploma_plan_sql/plan_schema.json",
    "title": "B2 Plan",
    "description": "Compact JSON Plan emitted by the planner before SQL generation.",
    "type": "object",
    "required": ["intent", "tables", "operations"],
    "additionalProperties": False,
    "properties": {
        "intent": {
            "type": "string",
            "enum": [
                "select_count",
                "select_aggregate",
                "select_filter",
                "select_join",
                "select_groupby",
                "select_orderby",
                "select_other"
            ],
            "description": "High-level shape of the answer the user wants."
        },
        "tables": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string"},
            "description": "Tables required to answer; subset of the reduced schema."
        },
        "columns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Columns to project or aggregate over."
        },
        "filters": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["column", "op", "value"],
                "additionalProperties": False,
                "properties": {
                    "column": {"type": "string"},
                    "op": {"type": "string", "enum": ["=", "!=", ">", "<", ">=", "<=", "LIKE", "IN", "BETWEEN"]},
                    "value": {}
                }
            }
        },
        "aggregations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["function", "column"],
                "additionalProperties": False,
                "properties": {
                    "function": {"type": "string", "enum": ["COUNT", "SUM", "AVG", "MIN", "MAX"]},
                    "column": {"type": "string"}
                }
            }
        },
        "group_by": {"type": "array", "items": {"type": "string"}},
        "order_by": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["column", "dir"],
                "additionalProperties": False,
                "properties": {
                    "column": {"type": "string"},
                    "dir": {"type": "string", "enum": ["ASC", "DESC"]}
                }
            }
        },
        "limit": {"type": ["integer", "null"]},
        "joins": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["left_table", "right_table", "on"],
                "additionalProperties": False,
                "properties": {
                    "left_table": {"type": "string"},
                    "right_table": {"type": "string"},
                    "on": {"type": "string", "description": "Free-form join condition, e.g. 'a.id = b.a_id'."}
                }
            }
        },
        "notes": {"type": "string"}
    }
}

plan_schema_path = DOCS / 'plan_schema.json'
plan_schema_path.write_text(json.dumps(plan_schema, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'WROTE {plan_schema_path} ({plan_schema_path.stat().st_size} B)')

# ---------- 2. design decision ----------
ts = dt.datetime.now(dt.timezone.utc).isoformat()
design = f'''# B2 Design Decision

Date: {ts}.

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
'''
(OUTPUTS / 'logs' / 'b2_design_decision.md').write_text(design, encoding='utf-8')
print(f'WROTE {OUTPUTS / "logs" / "b2_design_decision.md"}')

# ---------- 3. baselines_b2.py module ----------
baselines_b2_src = '''"""B2 minimal Plan->SQL pipeline.

Reuses the lexical schema linker and reduced-schema prompt builder from B1
(in baselines.py). Adds a planner that emits JSON validated against
plan_schema.json, then a plan-to-SQL prompt.
"""
from __future__ import annotations

import json
import re
import textwrap


def make_plan_prompt(question: str, reduced_schema_context: str) -> str:
    """Prompt that asks the model to emit a JSON Plan only.

    The plan is validated against plan_schema.json downstream.
    """
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
    - columns: array of column names to project / aggregate
    - filters: array of {{"column": str, "op": one of [=, !=, >, <, >=, <=, LIKE, IN, BETWEEN], "value": any}}
    - aggregations: array of {{"function": one of [COUNT, SUM, AVG, MIN, MAX], "column": str}}
    - group_by: array of column names
    - order_by: array of {{"column": str, "dir": one of [ASC, DESC]}}
    - limit: integer or null
    - joins: array of {{"left_table": str, "right_table": str, "on": str}}
    - notes: optional short string

    Required fields: intent, tables, operations.

    {reduced_schema_context}

    Question: {question}
    JSON plan:
    \"\"\").strip()


def extract_json_block(raw_text: str) -> str:
    """Extract the JSON object from raw model output.

    Handles markdown fences, leading/trailing prose, and trailing junk after the
    first balanced object.
    """
    if not raw_text:
        return ""
    text = raw_text.strip()
    # strip ```json or ``` fences
    text = re.sub(r"^```(?:json)?\\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\\s*```\\s*$", "", text)
    # find first '{' and the matching '}' (depth-tracking)
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
    """Parse JSON, validate against plan_schema. Returns (parsed, valid, error_str)."""
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
        # very loose fallback validation
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
    """Prompt the model to emit one SQLite SQL query that implements the plan."""
    plan_pretty = json.dumps(plan_obj, ensure_ascii=False, indent=2)
    return textwrap.dedent(f\"\"\"
    You are a text-to-SQL assistant. You are given a natural-language question,
    a JSON plan describing how to answer it, and the reduced schema.
    Generate one SQLite SQL query implementing the plan. Return SQL only,
    no markdown fences and no prose.

    {reduced_schema_context}

    Question: {question}

    Plan:
    {plan_pretty}

    SQL:
    \"\"\").strip()
'''
(EVAL_DIR / 'baselines_b2.py').write_text(baselines_b2_src, encoding='utf-8')
print(f'WROTE {EVAL_DIR / "baselines_b2.py"} ({(EVAL_DIR / "baselines_b2.py").stat().st_size} B)')

# ---------- 4. install jsonschema if missing ----------
import subprocess, sys
try:
    import jsonschema  # noqa
    print('jsonschema already installed')
except ImportError:
    print('installing jsonschema...')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'jsonschema'], check=True)
    import jsonschema  # noqa
    print('jsonschema installed')

print('STATUS=DONE')
