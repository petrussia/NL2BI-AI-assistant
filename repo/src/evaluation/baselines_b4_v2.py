"""B4_v2: B3_v2 + multi-candidate + SELECT guard + bounded repair + B1 fallback.

Differences vs B4_final:
1. B1 single-shot SQL is the unconditional safety net at TWO points:
   - if the planner output cannot be parsed/validated as a plan, AND
   - if no candidate (after repair) executes successfully.
   This guarantees B4_v2 EX >= B1 EX in expectation: every item the planner
   fails on degrades to B1, not to a hard failure.
2. Multi-candidate sampling kept (k=3, T=0.7, top_p=0.95) but only used when
   the plan is valid — otherwise we go straight to B1.
3. Repair budget kept at 1.

Public API:
- is_safe_select(sql) -> (bool, reason)
- make_repair_prompt_v2(question, plan_obj, full_schema_text, prev_sql, error)
- consistency_pick_v2(candidate_results)
"""
from __future__ import annotations
import re
import textwrap

# Re-export the SELECT-only guard from b4_final to avoid duplication.
from baselines_b4_final import is_safe_select  # type: ignore

_TXT_LIMIT = 300


def make_repair_prompt_v2(question, plan_obj, full_schema_text, prev_sql, error_msg):
    import json as _json
    plan_pretty = _json.dumps(plan_obj, ensure_ascii=False, indent=2)
    return textwrap.dedent(f"""
    Your previous SQL was invalid or returned an error. Emit a corrected SQLite SQL query.
    Return SQL only, no markdown, no commentary.

    {full_schema_text}

    Question: {question}

    Plan:
    {plan_pretty}

    Previous SQL (FAILED):
    {prev_sql}

    Error:
    {(error_msg or "")[:_TXT_LIMIT]}

    Fixed SQL:
    """).strip()


def consistency_pick_v2(candidate_results):
    """candidate_results: list of (sql, executable, rows, err).
    Picks the SQL whose execution result occurs most often among executable
    candidates. If none execute, returns (None, "no_executable") so the caller
    can apply the B1 fallback."""
    if not candidate_results:
        return None, "no_candidates"
    executable = [(sql, rows) for sql, ex, rows, _ in candidate_results if ex]
    if not executable:
        return None, "no_executable"
    from collections import Counter
    counts = Counter(tuple(sorted(r)) for _, r in executable)
    best, _ = counts.most_common(1)[0]
    for sql, rows in executable:
        if tuple(sorted(rows)) == best:
            return sql, "consistency_winner"
    return executable[0][0], "fallback"
