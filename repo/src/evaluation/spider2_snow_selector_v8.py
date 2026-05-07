"""spider2_snow_selector_v8 — pick the best Snowflake candidate.

Selection rules (in priority order):
  1. Executable (passed live execute) > parses-only > non-parses
  2. Schema-valid (no unknown_tables/columns from verifier) > unknown
  3. Answer-shape proxy: prefer candidates with rows_count > 0
  4. Lower cost: prefer shorter SQL when above are tied
  5. Source preference: C3_repaired > C1 > C0 > C2 > C4 (small bias)

Returns (chosen, audit) where audit logs all per-candidate scores.
"""
from __future__ import annotations


_SOURCE_BIAS = {
    'C0_direct': 0.0,
    'C1_retrieval_docs': 0.05,
    'C2_cte_decomp': 0.02,
    'C3_repaired': 0.10,
    'C4_tool_loop': 0.04,
}


def candidate_score(c: dict) -> tuple[float, dict]:
    v = c.get('verifier') or {}
    s = 0.0
    parts: dict[str, float] = {}
    if v.get('executable'):
        s += 5.0; parts['executable'] = 5.0
    if v.get('parses'):
        s += 3.0; parts['parses'] = 3.0
    if v.get('safe_select'):
        s += 0.5; parts['safe_select'] = 0.5
    if v.get('rows_count', 0) > 0:
        s += 0.4; parts['has_rows'] = 0.4
    if not v.get('unknown_tables') and not v.get('unknown_columns'):
        s += 0.3; parts['schema_valid'] = 0.3
    bias = _SOURCE_BIAS.get(c.get('source', ''), 0.0)
    s += bias; parts['source_bias'] = bias
    sql_len = len(c.get('sql') or '')
    if sql_len > 0:
        # Mild prior toward shorter, well-formed SQL when scores tie
        len_bonus = max(0.0, 0.3 - (sql_len / 4000.0))
        s += len_bonus; parts['len_bonus'] = round(len_bonus, 3)
    return s, parts


def select_candidate(cands: list[dict], question: str,
                       *, judge_gen=None, judge_close_margin: float = 0.4,
                       schema_summary: str = '') -> tuple[dict | None, dict]:
    """Pick the best candidate. Returns (chosen, audit).

    LLM-judge is invoked only if the top-2 are within `judge_close_margin`
    AND `judge_gen` is supplied. Otherwise pure heuristic.
    """
    audit = {'n_candidates': len(cands), 'scores': [], 'judge_used': False}
    if not cands:
        return None, audit

    scored = []
    for c in cands:
        s, parts = candidate_score(c)
        scored.append({'source': c.get('source', '?'),
                        'score': round(s, 3), 'parts': parts,
                        'sql_chars': len(c.get('sql') or '')})
        c['_score'] = s

    scored.sort(key=lambda r: -r['score'])
    audit['scores'] = scored
    cands_sorted = sorted(cands, key=lambda c: -c.get('_score', 0))
    top1 = cands_sorted[0]

    if (judge_gen is not None and len(cands_sorted) >= 2
            and (top1.get('_score', 0) - cands_sorted[1].get('_score', 0))
            < judge_close_margin):
        try:
            verdict = _call_judge(judge_gen, question, top1, cands_sorted[1],
                                     schema_summary)
            audit['judge_used'] = True
            audit['judge_verdict'] = verdict
            if verdict == 'B':
                top1 = cands_sorted[1]
        except Exception as exc:
            audit['judge_error'] = f'{type(exc).__name__}: {exc}'

    return top1, audit


def _call_judge(judge_gen, question: str, A: dict, B: dict,
                  schema_summary: str) -> str:
    prompt = (
        "You are a strict SQL judge. Pick the better Snowflake answer.\n\n"
        f"QUESTION: {question}\n\n"
        f"SCHEMA SUMMARY:\n{schema_summary[:1500]}\n\n"
        f"CANDIDATE A (source={A.get('source','?')}, "
        f"parses={(A.get('verifier') or {}).get('parses')}):\n"
        f"```sql\n{(A.get('sql') or '')[:1500]}\n```\n\n"
        f"CANDIDATE B (source={B.get('source','?')}, "
        f"parses={(B.get('verifier') or {}).get('parses')}):\n"
        f"```sql\n{(B.get('sql') or '')[:1500]}\n```\n\n"
        "Reply with exactly one line: A or B."
    )
    raw = judge_gen(prompt, max_new=8)
    txt = (raw or '').strip().upper()
    return 'B' if txt.startswith('B') else 'A'
