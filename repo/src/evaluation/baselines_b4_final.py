"""B4_final: B3_v1 base + SELECT-only guard + multi-candidate + bounded repair.

Honest naming: this is still NOT true grammar-constrained decoding (no XGrammar
or Outlines). The validation is post-hoc regex/AST. Nothing changed from B4-lite
in terms of "constrained decoding" approximation; the name "_final" is for
positioning relative to B4-lite, not a claim that the spec is fully closed.
"""
from __future__ import annotations
import re
import textwrap


_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|create|alter|truncate|replace|pragma|attach|detach|grant|revoke)\b",
    re.IGNORECASE,
)
_SELECT_HEAD = re.compile(r"^\s*(?:with\s+.+?\s+as\s+\(.+?\)\s*,?\s*)*\s*select\b",
                          re.IGNORECASE | re.DOTALL)


def is_safe_select(sql: str):
    s = (sql or "").strip().rstrip(";").strip()
    if not s: return False, "empty"
    m = _FORBIDDEN_KEYWORDS.search(s)
    if m: return False, f"forbidden_keyword:{m.group(0).lower()}"
    if not _SELECT_HEAD.match(s): return False, "does_not_start_with_select"
    return True, ""


def make_repair_prompt(question, plan_obj, ctx, prev_sql, error_msg):
    import json as _json
    plan_pretty = _json.dumps(plan_obj, ensure_ascii=False, indent=2)
    return textwrap.dedent(f"""
    Your previous SQL produced an error. Generate a fixed SQLite SQL query.
    Return SQL only, no markdown.

    {ctx}

    Question: {question}

    Plan:
    {plan_pretty}

    Previous SQL (FAILED):
    {prev_sql}

    Error:
    {error_msg[:300]}

    Fixed SQL:
    """).strip()


def consistency_pick(candidate_results):
    if not candidate_results: return None, "no_candidates"
    executable = [(sql, rows) for sql, ex, rows, _ in candidate_results if ex]
    if not executable: return candidate_results[0][0], "no_executable"
    from collections import Counter
    counts = Counter(tuple(sorted(r)) for _, r in executable)
    best, _ = counts.most_common(1)[0]
    for sql, rows in executable:
        if tuple(sorted(rows)) == best: return sql, "consistency_winner"
    return executable[0][0], "fallback"
