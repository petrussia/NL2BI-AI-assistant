"""spider2_bq_selector_v8 — pick the winning candidate after verification.

Rules (strict order, first match wins):
  1. Among candidates whose dry_run passed, prefer those with
     `bytes_processed <= soft_cap`. If multiple, go to step 2.
  2. Prefer candidates whose `all_known` is True (sqlglot-side; advisory).
  3. Prefer candidates whose `table_refs_n` matches the question's
     intent — answer-shape heuristics:
       count -> COUNT(*) present
       list -> projection only, no aggregate
       top/best -> ORDER BY + LIMIT
       average/sum -> AVG/SUM
       distinct -> DISTINCT
  4. Prefer non-anchor (C1_retrieval / C2_cte) over C0 when scores tie,
     since retrieval-aware candidates use docs/aliases.
  5. If still tied AND >= 2 candidates have valid dry_run, optionally
     invoke the existing `llm_judge_v7` with BQ-aware payload.

Returns (chosen, audit) where audit is a dict explaining the pick.
"""
from __future__ import annotations

import re
from typing import Callable

from llm_judge_v7 import judge_candidates


SOURCE_RANK = {'C0_direct': 0, 'C1_retrieval_docs': 1, 'C2_cte_decomp': 2,
                'C3_repaired': 1.5}


def _intent_match(question: str, sql: str) -> float:
    q = (question or '').lower()
    s = (sql or '').lower()
    score = 0.0
    if 'how many' in q or 'count of' in q or 'number of' in q:
        if 'count(' in s: score += 1.0
    if 'list' in q or 'which' in q or 'show' in q:
        if 'count(' not in s and 'sum(' not in s: score += 0.5
    if 'top' in q or 'most' in q or 'best' in q or 'highest' in q or 'lowest' in q:
        if 'order by' in s and 'limit' in s: score += 1.0
    if 'average' in q or 'avg' in q:
        if 'avg(' in s: score += 1.0
    if 'distinct' in q or 'different' in q or 'unique' in q:
        if 'distinct' in s: score += 0.5
    if 'per ' in q or 'by ' in q or 'for each' in q:
        if 'group by' in s: score += 0.5
    return score


def _candidate_score(cand: dict, question: str, *,
                       max_bytes_soft: int = 5 * 10**9) -> float:
    v = cand.get('verifier') or {}
    score = 0.0
    if v.get('parses'): score += 3.0
    if v.get('safe_select'): score += 0.5
    if v.get('all_known') is True: score += 1.0
    if v.get('table_refs_n', 0) >= 1: score += 0.3
    score += _intent_match(question, cand.get('sql', '')) * 1.0
    # Penalize over-cap dry_run results
    if v.get('over_soft_cap'): score -= 0.5
    # Tiny bonus for non-anchor sources to break ties
    score += 0.05 * SOURCE_RANK.get(cand.get('source', ''), 0)
    return score


def select_candidate(cands: list[dict], question: str, *,
                       judge_gen: Callable | None = None,
                       judge_close_margin: float = 0.4,
                       judge_min_conf: float = 0.65,
                       schema_summary: str = '',
                       evidence_text: str = '') -> tuple[dict, dict]:
    """Return (chosen_candidate, audit_dict)."""
    if not cands:
        return None, {'reason': 'no_candidates'}
    scored = [(c, _candidate_score(c, question)) for c in cands]
    scored.sort(key=lambda x: -x[1])

    top, top_score = scored[0]
    audit = {
        'scores': [(c['source'], round(s, 3)) for c, s in scored],
        'judge_invoked': False, 'judge_overrode': False,
        'judge_chose': '', 'judge_confidence': 0.0,
        'judge_reason': '',
    }

    # Optional judge fire if top-2 close AND both have parses
    if (judge_gen is not None and len(scored) >= 2
            and (scored[0][1] - scored[1][1]) < judge_close_margin
            and (scored[0][0].get('verifier') or {}).get('parses')
            and (scored[1][0].get('verifier') or {}).get('parses')):
        audit['judge_invoked'] = True
        cand_meta = []
        for i, (c, _) in enumerate(scored[:4]):
            v = c.get('verifier') or {}
            cand_meta.append({
                'id': str(i), 'source': c['source'],
                'sql': c.get('sql', ''),
                'meta': {'executable': v.get('parses'),
                          'rows_count': 0,
                          'error_type': v.get('error_type', ''),
                          'parses': v.get('parses')}
            })
        try:
            verdict = judge_candidates(question, None, cand_meta,
                                        gen=judge_gen,
                                        evidence_text=evidence_text,
                                        schema_summary=schema_summary[:1200])
            audit['judge_confidence'] = float(verdict.get('confidence', 0.0))
            audit['judge_reason'] = (verdict.get('reason') or '')[:200]
            bid = verdict.get('best_candidate_id')
            if bid is not None:
                try:
                    j_idx = int(bid)
                    if 0 <= j_idx < len(scored):
                        jchose = scored[j_idx][0]
                        audit['judge_chose'] = jchose['source']
                        if (audit['judge_confidence'] >= judge_min_conf
                                and jchose['source'] != top['source']):
                            top = jchose
                            audit['judge_overrode'] = True
                except (ValueError, IndexError):
                    pass
        except Exception as exc:
            audit['judge_error'] = f'{type(exc).__name__}'

    audit['chosen'] = top['source']
    return top, audit
