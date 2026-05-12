"""Multi-candidate ranker for B4_v3.

Combines: executable, safe_select, schema/join coverage, repair penalty,
optional reranker_score from a retriever signal.
"""
from __future__ import annotations
import re


def _table_names_in_sql(sql: str, candidate_tables: list[str]) -> set[str]:
    s = (sql or "").lower()
    out = set()
    for t in candidate_tables:
        # Match as a whole word (with backticks/quotes optional)
        if re.search(rf"\b{re.escape(t.lower())}\b", s):
            out.add(t)
    return out


def _join_count(sql: str) -> int:
    return len(re.findall(r"\bjoin\b", (sql or "").lower()))


def score_candidate(sql: str,
                    is_executable: bool,
                    is_safe_select: bool,
                    schema_tables: list[str],
                    plan_tables: list[str] | None = None,
                    repair_count: int = 0,
                    reranker_score: float = 0.0,
                    rows_returned: int | None = None) -> dict:
    """Compute a composite score in [0, 1] plus per-feature breakdown."""
    if not is_safe_select:
        return {"score": 0.0, "exec": is_executable, "safe": False, "reason": "unsafe"}
    if not is_executable:
        return {"score": 0.05, "exec": False, "safe": True, "reason": "not_executable"}

    sql_l = (sql or "").lower()
    tables_used = _table_names_in_sql(sql, schema_tables)
    joins = _join_count(sql)
    plan_set = set(plan_tables or [])

    # Coverage features
    table_coverage = (len(tables_used & plan_set) / max(1, len(plan_set))) if plan_set else 1.0
    join_coverage = min(1.0, joins / max(1, len(plan_set) - 1)) if len(plan_set) > 1 else 1.0
    rows_signal = 0.5
    if rows_returned is not None:
        # We slightly prefer non-empty results (heuristic, capped)
        rows_signal = 1.0 if rows_returned > 0 else 0.3
    repair_penalty = 0.85 ** max(0, repair_count)

    score = (
        0.40 +
        0.20 * table_coverage +
        0.15 * join_coverage +
        0.10 * rows_signal +
        0.10 * min(1.0, max(0.0, reranker_score)) +
        0.05 * repair_penalty
    )
    return {
        "score": min(1.0, max(0.0, score)),
        "exec": True, "safe": True,
        "table_coverage": table_coverage,
        "join_coverage": join_coverage,
        "rows_signal": rows_signal,
        "repair_penalty": repair_penalty,
    }


def pick_best(candidates: list[dict], min_margin: float = 0.0) -> dict | None:
    """candidates: list of {"sql": str, "exec": bool, "safe_select": bool,
                            "rows": list, "repair_count": int, "score_dict": ...}
    Returns the chosen candidate dict or None if no executable candidate.
    """
    if not candidates: return None
    executable = [c for c in candidates if c.get("exec")]
    if not executable: return None
    # Use consistency-of-results vote AS SECONDARY KEY behind score.
    # Primary: composite score
    executable.sort(key=lambda c: -c.get("score", 0.0))
    if len(executable) >= 2 and (executable[0]["score"] - executable[1]["score"]) < min_margin:
        # Low margin → defer to consistency vote
        from collections import Counter
        cnt = Counter(tuple(sorted(c.get("rows", []))) for c in executable)
        best_rows, _ = cnt.most_common(1)[0]
        for c in executable:
            if tuple(sorted(c.get("rows", []))) == best_rows:
                return c
    return executable[0]
