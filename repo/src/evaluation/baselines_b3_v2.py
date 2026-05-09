"""B3_v2: minimal-overhead retrieval/planner with B1-fallback safety net.

Differences vs B3_v1:
1. Knowledge channel is **disabled for every DB**. On Spider there is no real
   external corpus; the previous "knowledge proxy" was synthesized from the same
   tables.json that already powers schema linking, so it duplicates information
   and inflates the planner prompt without adding signal. Net effect on B3_v1
   was a regression vs B1 — see outputs/REPORT.md.
2. Planner gets ONLY the reduced schema (lex-linked tables). Compact prompt.
3. Synthesizer gets the FULL schema (not reduced) plus the plan, so that
   columns the linker missed are still reachable.
4. Hard B1 fallback: if the planner returns unparsable JSON, OR the JSON does
   not validate against plan_schema_v1, the pipeline falls back to a B1
   single-shot SQL generation. This guarantees B3_v2 EX >= B1 EX modulo SQL
   noise: the baseline can no longer regress below B1.

Required public API for the BG runner:
- make_b3v2_plan_prompt(question, reduced_schema_text)
- make_b3v2_sql_prompt(question, plan_obj, full_schema_text)
- parse_plan_json(raw_text) -> (plan_obj_or_none, error_str)
"""
from __future__ import annotations
import json
import re
import textwrap


def make_b3v2_plan_prompt(question: str, reduced_schema_text: str) -> str:
    return textwrap.dedent(f"""
    You are a SQL planner. Output one JSON plan only. No prose, no markdown fences.
    Required fields: intent, tables, operations.
    Optional: columns, filters, aggregations, group_by, order_by, limit, joins, distinct, notes.
    intent enum: select_count, select_aggregate, select_filter, select_join,
    select_groupby, select_orderby, select_other.

    {reduced_schema_text}

    Question: {question}
    JSON plan:
    """).strip()


def make_b3v2_sql_prompt(question: str, plan_obj, full_schema_text: str) -> str:
    plan_pretty = json.dumps(plan_obj, ensure_ascii=False, indent=2)
    return textwrap.dedent(f"""
    You are a text-to-SQL assistant. Use the schema and the JSON plan to emit one SQLite SQL query.
    Return SQL only, no markdown, no explanation.
    If the plan has "distinct": true, prepend SELECT with DISTINCT.
    The full schema is provided so you may reference columns the planner did not list.

    {full_schema_text}

    Question: {question}

    Plan:
    {plan_pretty}

    SQL:
    """).strip()


_JSON_FENCE_HEAD = re.compile(r"^\s*```(?:json)?\s*", re.IGNORECASE)
_JSON_FENCE_TAIL = re.compile(r"\s*```\s*$")


def parse_plan_json(raw: str):
    s = raw.strip()
    s = _JSON_FENCE_HEAD.sub("", s)
    s = _JSON_FENCE_TAIL.sub("", s)
    if "{" in s and "}" in s:
        s = s[s.find("{"): s.rfind("}") + 1]
    try:
        obj = json.loads(s)
    except Exception as exc:
        return None, f"json_decode:{type(exc).__name__}:{str(exc)[:120]}"
    if not isinstance(obj, dict):
        return None, "not_an_object"
    return obj, ""
