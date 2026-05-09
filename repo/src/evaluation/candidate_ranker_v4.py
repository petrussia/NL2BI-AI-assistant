"""Candidate ranker v4 for B4_v4 (multi-source candidate pool).

Sources combined per query:
  - candidate_b0  : direct full schema
  - candidate_b1v3: bidirectional linker direct
  - candidate_b3v4: hybrid retrieval direct (with evidence on BIRD)
  - candidate_b2v4: planner v4 (only if planner_gate passes)

Ranker applies multi-feature scoring AND a *non-harm* rule:
  if margin between top-1 and top-2 is small, prefer the candidate from a
  cheaper / less-risky source (B0 > B1_v3 > B3_v4 > B2_v4 priority).
"""
from __future__ import annotations
import re
from collections import Counter


SOURCE_RISK = {  # lower = safer
    "candidate_b0": 0,
    "candidate_b1v3": 1,
    "candidate_b3v4": 2,
    "candidate_b2v4": 3,
    "candidate_b2v4_repair": 4,
}


def _table_names_in_sql(sql: str, candidate_tables: list[str]) -> set[str]:
    s = (sql or "").lower()
    out = set()
    for t in candidate_tables:
        if re.search(rf"\b{re.escape(t.lower())}\b", s):
            out.add(t)
    return out


def _join_count(sql: str) -> int:
    return len(re.findall(r"\bjoin\b", (sql or "").lower()))


def score_candidate_v4(sql: str, source: str, *,
                        is_executable: bool, is_safe_select: bool,
                        rows: list | None,
                        schema_tables: list[str],
                        plan_tables: list[str] | None = None,
                        link_confidence: float = 0.5,
                        repair_count: int = 0,
                        prompt_chars: int = 0) -> dict:
    if not is_safe_select: return {"score": 0.0, "reason": "unsafe", "exec": is_executable, "safe": False}
    if not is_executable: return {"score": 0.05, "reason": "not_executable", "exec": False, "safe": True}
    sql_l = (sql or "").lower()
    plan_set = set(plan_tables or [])
    tables_used = _table_names_in_sql(sql, schema_tables)
    table_coverage = (len(tables_used & plan_set) / max(1, len(plan_set))) if plan_set else 1.0
    joins = _join_count(sql)
    join_coverage = min(1.0, joins / max(1, len(plan_set) - 1)) if len(plan_set) > 1 else 1.0
    rows_signal = 0.5
    if rows is not None:
        rows_signal = 1.0 if len(rows) > 0 else 0.3
    repair_penalty = 0.85 ** max(0, repair_count)
    prompt_penalty = max(0.5, 1.0 - max(0, prompt_chars - 4000) / 8000)
    risk_factor = 1.0 - 0.02 * SOURCE_RISK.get(source, 0)
    score = (
        0.35 +
        0.18 * table_coverage +
        0.13 * join_coverage +
        0.10 * rows_signal +
        0.08 * link_confidence +
        0.05 * repair_penalty +
        0.05 * prompt_penalty +
        0.06 * risk_factor
    )
    return {"score": min(1.0, max(0.0, score)),
            "exec": True, "safe": True,
            "table_coverage": table_coverage, "join_coverage": join_coverage,
            "rows_signal": rows_signal, "link_confidence": link_confidence,
            "risk_factor": risk_factor}


def pick_best_v4(candidates: list[dict], min_margin: float = 0.04) -> dict | None:
    """candidates: list of {"sql","source","exec","safe","rows","score","score_dict"}.

    1. Filter executable & safe.
    2. Sort by score desc.
    3. If margin between top-1 and top-2 < min_margin, apply consensus vote
       (most-common rows-set) and prefer lower-risk source on tie."""
    if not candidates: return None
    executable = [c for c in candidates if c.get("exec") and c.get("safe")]
    if not executable: return None
    executable.sort(key=lambda c: -c.get("score", 0.0))
    if len(executable) >= 2 and (executable[0]["score"] - executable[1]["score"]) < min_margin:
        cnt = Counter(tuple(sorted(c.get("rows", []))) for c in executable)
        winning_rows, _ = cnt.most_common(1)[0]
        winners = [c for c in executable if tuple(sorted(c.get("rows", []))) == winning_rows]
        winners.sort(key=lambda c: SOURCE_RISK.get(c.get("source",""), 99))
        return winners[0]
    return executable[0]
