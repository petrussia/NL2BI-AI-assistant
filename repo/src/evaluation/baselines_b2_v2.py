"""B2_v2: targeted patches over B2_v1.

Patches (informed by outputs/logs/b2_targeted_error_triage.md):
1. Stronger DISTINCT cue.
2. Stronger superlative subquery cue.
3. Anti-overengineering instruction ("simplest plan that satisfies").
4. Hard B1 fallback when plan is unparsable / fails schema validation.

API:
- make_b2v2_plan_prompt(question, full_schema_text)
- make_b2v2_sql_prompt(question, plan_obj, full_schema_text)
- parse_plan_json(raw_text) — re-exported from b3_v2 for parser parity.
"""
from __future__ import annotations
import json
import textwrap

# Re-use the stable JSON parser from b3_v2 to avoid duplication.
from baselines_b3_v2 import parse_plan_json  # type: ignore


def make_b2v2_plan_prompt(question: str, full_schema_text: str) -> str:
    return textwrap.dedent(f"""
    You are a SQL planner. Output one JSON plan only. No prose, no markdown fences.
    Required fields: intent, tables, operations.
    Optional: columns, filters, aggregations, group_by, order_by, limit, joins, distinct, notes.
    intent enum: select_count, select_aggregate, select_filter, select_join,
    select_groupby, select_orderby, select_other.

    Use the simplest plan that satisfies the question. Do not add operations
    not requested by the question (no spurious GROUP BY, ORDER BY, LIMIT,
    or DISTINCT).

    DISTINCT cue: when the question asks for "different", "distinct", "unique",
    "all the X" (set semantics), set "distinct": true. Otherwise leave it false.

    Superlative cue: when the question contains "the youngest/oldest/largest/
    smallest/highest/lowest X", emit a filter whose value is a subquery, e.g.
    {{"column":"Age","op":"=","value":"(SELECT MIN(Age) FROM singer)"}}.

    {full_schema_text}

    Question: {question}
    JSON plan:
    """).strip()


def make_b2v2_sql_prompt(question: str, plan_obj, full_schema_text: str) -> str:
    plan_pretty = json.dumps(plan_obj, ensure_ascii=False, indent=2)
    return textwrap.dedent(f"""
    You are a text-to-SQL assistant. Use the schema and the JSON plan to emit
    one SQLite SQL query. Return SQL only, no markdown, no commentary.
    If the plan has "distinct": true, prepend SELECT with DISTINCT.
    If a filter value starts with "(SELECT", keep it verbatim in WHERE.
    Do NOT add ORDER BY, GROUP BY, or LIMIT unless the plan asks for them.

    {full_schema_text}

    Question: {question}

    Plan:
    {plan_pretty}

    SQL:
    """).strip()
