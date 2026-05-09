"""B4-lite: B3 base + SELECT-only guard + bounded repair + multi-candidate selection.

Honest naming: this is B4-lite, NOT full grammar-constrained decoding (XGrammar/Outlines).
We approximate constrained decoding via post-hoc AST/regex validation gates.

Pipeline per item:
  1. Run B3 planner stage to get a JSON plan (validated).
  2. Generate K candidate SQLs (sampling temperature 0.7, num_return_sequences=K).
  3. AST/regex guard each candidate: SELECT-only (no INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/REPLACE/PRAGMA).
  4. Execute each surviving candidate against the gold DB with 8s timeout.
  5. Pick the candidate by consistency (most candidates agreeing on a row-multiset).
     Tie-break: first executable.
  6. Bounded repair: if NO candidate executable, retry SQL gen once with the error message
     appended to the prompt. Single retry, bounded to 1.
"""
from __future__ import annotations
import re
import textwrap


# Regex-based SQL safety guard (post-hoc constrained decoding approximation)
_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|create|alter|truncate|replace|pragma|attach|detach|grant|revoke)\b",
    re.IGNORECASE,
)
_SELECT_HEAD = re.compile(r"^\s*(?:with\s+.+?\s+as\s+\(.+?\)\s*,?\s*)*\s*select\b", re.IGNORECASE | re.DOTALL)


def is_safe_select(sql: str) -> tuple[bool, str]:
    """Return (ok, reason). ok=False means SQL is rejected."""
    s = (sql or "").strip().rstrip(";").strip()
    if not s:
        return False, "empty"
    if _FORBIDDEN_KEYWORDS.search(s):
        m = _FORBIDDEN_KEYWORDS.search(s)
        return False, f"forbidden_keyword:{m.group(0).lower()}"
    if not _SELECT_HEAD.match(s):
        return False, "does_not_start_with_select"
    return True, ""


def make_repair_prompt(question: str, plan_obj, b3_context: str, prev_sql: str, error_msg: str) -> str:
    import json as _json
    plan_pretty = _json.dumps(plan_obj, ensure_ascii=False, indent=2)
    return textwrap.dedent(f"""
    Your previous SQL produced an error. Generate a fixed SQLite SQL query.
    Return SQL only, no markdown, no prose.

    {b3_context}

    Question: {question}

    Plan:
    {plan_pretty}

    Previous SQL (FAILED):
    {prev_sql}

    Error message:
    {error_msg[:300]}

    Fixed SQL:
    """).strip()


def consistency_pick(candidate_results):
    """candidate_results = list of (sql, executable, rows_or_None, error).

    Group executable candidates by their result (sorted row tuple).
    Return the SQL whose result group is largest (consistency); tie-break: first.
    If no executable, return the first candidate (signals failure to caller).
    """
    if not candidate_results:
        return None, "no_candidates"
    executable = [(sql, rows) for sql, ex, rows, _ in candidate_results if ex]
    if not executable:
        return candidate_results[0][0], "no_executable"
    from collections import Counter
    counts = Counter(tuple(sorted(r)) for _, r in executable)
    best_result, _ = counts.most_common(1)[0]
    for sql, rows in executable:
        if tuple(sorted(rows)) == best_result:
            return sql, "consistency_winner"
    return executable[0][0], "fallback"
