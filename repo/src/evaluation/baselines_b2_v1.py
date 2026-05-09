"""B2 v1 minimal patched Plan->SQL pipeline.

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
    """).strip()


def extract_json_block(raw_text: str) -> str:
    if not raw_text:
        return ""
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
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
    return textwrap.dedent(f"""
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
    """).strip()
