"""Planner gate: decides whether to invoke planner, and validates the result.

Used by B2_v3 / B4_v3. Single source for the fallback policy:
    1. planner_used := True (default) unless link_confidence < gate_threshold
    2. if planner JSON unparsable / fails plan_schema_v2 → fallback to B1_v3
    3. if SQL execution fails after bounded repair → fallback to B1_v3
"""
from __future__ import annotations
import json
import re

_JSON_FENCE_HEAD = re.compile(r"^\s*```(?:json)?\s*", re.IGNORECASE)
_JSON_FENCE_TAIL = re.compile(r"\s*```\s*$")


def parse_plan_v2(raw: str):
    """Returns (plan_obj_or_None, error_str)."""
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


def should_invoke_planner(link_confidence: float, gate_threshold: float = 0.40) -> bool:
    """If link confidence is too low, the planner is likely to hallucinate.
    Better to skip planner and fall back directly to B1_v3."""
    return link_confidence >= gate_threshold


def make_compact_planner_prompt(question: str, shortlist_schema: str,
                                 fk_summary: str = "", evidence: str = "") -> str:
    import textwrap
    extra = ""
    if fk_summary:
        extra += f"\n\nForeign-key summary:\n{fk_summary}"
    if evidence:
        extra += f"\n\nDomain evidence (from benchmark, may be empty):\n{evidence}"
    return textwrap.dedent(f"""
    You are a SQL planner. Output one COMPACT JSON plan only. No prose, no markdown fences.
    Required: intent, tables, operations.
    Optional: columns, filters, aggregations, group_by, order_by, limit, joins,
    distinct, answer_shape, expected_card, evidence_used, notes.

    intent enum: select_count, select_aggregate, select_filter, select_join,
    select_groupby, select_orderby, select_other.
    answer_shape: scalar | row | table | unknown.
    expected_card: one | few | many | unknown.

    Use the simplest plan that satisfies the question. No over-engineering.

    {shortlist_schema}{extra}

    Question: {question}
    JSON plan:
    """).strip()


def make_compact_synth_prompt(question: str, plan_obj, full_or_reduced_schema: str) -> str:
    import textwrap
    plan_pretty = json.dumps(plan_obj, ensure_ascii=False, indent=2)
    return textwrap.dedent(f"""
    You are a text-to-SQL assistant. Use the schema and the JSON plan to emit one
    SQLite SQL query. Return SQL only, no markdown, no commentary.
    If the plan has "distinct": true, prepend SELECT with DISTINCT.

    {full_or_reduced_schema}

    Question: {question}

    Plan:
    {plan_pretty}

    SQL:
    """).strip()


def make_repair_prompt(question: str, plan_obj, schema: str, prev_sql: str, error_msg: str) -> str:
    import textwrap
    plan_pretty = json.dumps(plan_obj, ensure_ascii=False, indent=2)
    return textwrap.dedent(f"""
    Your previous SQL failed. Emit a corrected SQLite SQL query.
    Return SQL only, no markdown, no commentary.

    {schema}

    Question: {question}

    Plan:
    {plan_pretty}

    Previous SQL (FAILED):
    {prev_sql}

    Error:
    {(error_msg or "")[:300]}

    Fixed SQL:
    """).strip()


def build_fk_summary(tables_meta: dict) -> str:
    """One-line per FK: table_a.col_a -> table_b.col_b."""
    tn = tables_meta.get("table_names_original") or tables_meta.get("table_names") or []
    cn = tables_meta.get("column_names_original") or tables_meta.get("column_names") or []
    fks = tables_meta.get("foreign_keys") or []
    lines = []
    for a, b in fks:
        if a < 0 or b < 0 or a >= len(cn) or b >= len(cn): continue
        ta, ca = cn[a]; tb, cb = cn[b]
        if ta < 0 or tb < 0 or ta >= len(tn) or tb >= len(tn): continue
        lines.append(f"{tn[ta]}.{ca} -> {tn[tb]}.{cb}")
    return "\n".join(lines[:25])  # cap


def is_safe_select(sql: str):
    """Re-export of the SELECT-only AST guard."""
    s = (sql or "").strip().rstrip(";").strip()
    if not s: return False, "empty"
    if re.search(r"\b(insert|update|delete|drop|create|alter|truncate|replace|pragma|attach|detach|grant|revoke)\b", s, re.IGNORECASE):
        return False, "forbidden_keyword"
    if not re.match(r"^\s*(?:with\s+.+?\s+as\s+\(.+?\)\s*,?\s*)*\s*select\b", s, re.IGNORECASE | re.DOTALL):
        return False, "does_not_start_with_select"
    return True, ""
