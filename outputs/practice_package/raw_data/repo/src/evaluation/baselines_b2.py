"""B2 minimal Plan->SQL pipeline.

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
    return textwrap.dedent(f"""
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
    """).strip()


def extract_json_block(raw_text: str) -> str:
    """Extract the JSON object from raw model output.

    Handles markdown fences, leading/trailing prose, and trailing junk after the
    first balanced object.
    """
    if not raw_text:
        return ""
    text = raw_text.strip()
    # strip ```json or ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
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
        if ch == "\\" and in_string:
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
    return textwrap.dedent(f"""
    You are a text-to-SQL assistant. You are given a natural-language question,
    a JSON plan describing how to answer it, and the reduced schema.
    Generate one SQLite SQL query implementing the plan. Return SQL only,
    no markdown fences and no prose.

    {reduced_schema_context}

    Question: {question}

    Plan:
    {plan_pretty}

    SQL:
    """).strip()
