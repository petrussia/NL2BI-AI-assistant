"""baselines_b6_v7 — calibrated LLM-as-judge selector wrapped over B4_v5.

Adds a SQL-aware semantic selector layer on top of the Phase C heuristic
verifier. Designed to close the BIRD discrimination gap between
B4_v5 (34.00%) and B2_v5 (37.60%) without regressing Spider B4_v5 (76.69%).

Calibration triggers (judge invoked only when ALL of):
  - benchmark profile says "needs_judge" (configured per-call)
  - candidate set has >=2 distinct candidates
  - heuristic margin between top-2 < `judge_close_margin` (default 0.06)
  - at least one candidate is C2_retrieval_evidence AND it is executable
  - evidence_text is non-empty (per-item or db-level evidence available)
  - top-2 do NOT share consensus (consensus_top_count < n_candidates)

If judge is invoked AND its confidence >= `judge_override_min_conf`
(default 0.65) AND the chosen candidate id is valid AND not equal to the
heuristic top, the controller OVERRIDES the heuristic pick.

If any check fails, B6_v7 behaves identically to B4_v5 (safe baseline).
"""
from __future__ import annotations

from typing import Callable

from candidate_generator_v2 import make_candidates
from verifier_ranker_v2 import rank_candidates, SOURCE_RISK
from repair_v2 import attempt_repair
from schema_ir_v2 import render_compact_schema
from llm_judge_v7 import judge_candidates


# Default selector policy. Caller can override per-step via kwargs.
DEFAULT_POLICY = {
    'needs_judge': True,
    'judge_close_margin': 0.10,           # heuristic margin below which judge fires
    'judge_override_min_conf': 0.65,
    'judge_max_candidates': 4,
    'allow_anchor_override': True,        # True = judge can pick non-anchor
    'spider_safe_mode': False,            # True = even tighter triggers on Spider
}


def _candidate_meta_from_ranked(c: dict) -> dict:
    """Pull executor/parse metadata into the judge-payload meta dict."""
    v = c.get('verifier', {}) or {}
    return {
        'executable': v.get('executable'),
        'rows_count': v.get('rows_count', 0),
        'error_type': '' if v.get('executable') else 'not_executable',
        'parses': v.get('parses'),
        'unknown_columns_n': len(v.get('unknown_columns', [])),
    }


def run_b6v7_step(question: str, ir, *,
                   gen, executor=None,
                   evidence_store=None, per_item_evidence: str = '',
                   plan_schema_path: str | None = None,
                   include_planner: bool = True,
                   include_evidence: bool = True,
                   non_harm_margin: float = 0.06,
                   max_repair_rounds: int = 1,
                   planner_gen=None,
                   judge_gen: Callable | None = None,
                   judge_policy: dict | None = None,
                   benchmark: str = 'unknown') -> dict:
    """Run one B6_v7 step.

    `judge_gen` defaults to the synth `gen` (Coder-7B). Pass a separate
    callable if you want a different judge model.
    """
    pol = dict(DEFAULT_POLICY)
    if judge_policy: pol.update(judge_policy)
    judge_call = judge_gen if judge_gen is not None else gen

    # ---------- 1. Candidate pool ----------
    candidates = make_candidates(question, ir, gen=gen,
                                  planner_gen=planner_gen,
                                  evidence_store=evidence_store,
                                  per_item_evidence=per_item_evidence,
                                  plan_schema_path=plan_schema_path,
                                  include_planner=include_planner,
                                  include_evidence=include_evidence)
    if not candidates:
        return _empty_response(reason='no_candidates')

    # ---------- 2. Heuristic ranker (Phase C) ----------
    ranked, consensus = rank_candidates(candidates, ir, executor=executor,
                                         question=question,
                                         non_harm_margin=non_harm_margin,
                                         reranker=None)
    heuristic_top = ranked[0]
    top_score = heuristic_top['verifier']['score']
    top2_score = ranked[1]['verifier']['score'] if len(ranked) > 1 else 0.0
    margin = top_score - top2_score

    # ---------- 3. Judge gating ----------
    judge_invoked = False
    judge_verdict = None
    judge_chose = None
    judge_reason = ''
    judge_overrode = False

    has_c2_executable = any(c['source'] == 'C2_retrieval_evidence'
                              and c['verifier'].get('executable')
                              for c in ranked)
    has_evidence = bool((per_item_evidence or '').strip()) or evidence_store is not None
    consensus_top = consensus.get('top_count', 0) if consensus else 0
    n_cands = len(ranked)
    not_unanimous = consensus_top < n_cands

    triggers = {
        'needs_judge': pol['needs_judge'],
        'has_c2_executable': has_c2_executable,
        'has_evidence': has_evidence,
        'not_unanimous': not_unanimous,
        'margin_close': margin < pol['judge_close_margin'],
        'multi_candidate': n_cands >= 2,
    }
    # Spider safe mode = tighter triggers (require strict close call)
    if pol.get('spider_safe_mode'):
        triggers['margin_close'] = margin < 0.04

    should_judge = all(triggers.values())

    if should_judge:
        judge_invoked = True
        # Build judge payload
        ev_text = (per_item_evidence or '').strip()
        schema_text = render_compact_schema(ir, include_comments=True)
        cand_meta = []
        for i, c in enumerate(ranked[:pol['judge_max_candidates']]):
            cand_meta.append({
                'id': str(i),
                'source': c['source'],
                'sql': c.get('sql', ''),
                'meta': _candidate_meta_from_ranked(c),
            })
        judge_verdict = judge_candidates(question, ir, cand_meta,
                                          gen=judge_call,
                                          evidence_text=ev_text,
                                          schema_summary=schema_text)
        judge_reason = judge_verdict.get('reason', '')
        chosen_id = judge_verdict.get('best_candidate_id')
        if chosen_id is not None:
            try:
                judge_chose = ranked[int(chosen_id)]
            except (ValueError, IndexError):
                judge_chose = None
        # Override decision
        if (judge_chose is not None
            and judge_verdict.get('confidence', 0.0) >= pol['judge_override_min_conf']
            and judge_chose.get('source') != heuristic_top.get('source')):
            if not pol['allow_anchor_override'] and heuristic_top['source'] == 'C0_anchor':
                judge_overrode = False
            else:
                judge_overrode = True

    if judge_overrode:
        top = judge_chose
        # Re-derive top2 margin against actual heuristic top for audit
        top_score = top['verifier']['score']
    else:
        top = heuristic_top

    chosen_sql = top['sql']
    chosen_safe = top['safe']
    chosen_safe_reason = top.get('safe_reason', '')

    # ---------- 4. Bounded repair on chosen ----------
    repair_used = False; repair_rounds = 0
    if executor is not None and (not chosen_safe or top['verifier'].get('executable') is False):
        rep = attempt_repair(question, ir, top, executor, gen,
                              max_rounds=max_repair_rounds)
        repair_used = True; repair_rounds = rep['rounds']
        if rep['executable']:
            chosen_sql = rep['sql']; chosen_safe = rep['safe']
            chosen_safe_reason = 'repaired_ok'

    # ---------- 5. Audit ----------
    cand_sources = [{'source': c['source'],
                      'score': c['verifier']['score'],
                      'parses': c['verifier']['parses'],
                      'executable': c['verifier'].get('executable'),
                      'rows_count': c['verifier'].get('rows_count', 0),
                      'unknown_tables': c['verifier'].get('unknown_tables', []),
                      'unknown_columns_n': len(c['verifier'].get('unknown_columns', [])),
                      'intent_score': c['verifier']['intent']['intent']}
                     for c in ranked]
    fallback_used = (top['source'] == 'C0_anchor' and len(candidates) > 1)
    fallback_reason = ('verifier_chose_anchor' if fallback_used else '')

    return {
        'sql': chosen_sql, 'safe': chosen_safe, 'safe_reason': chosen_safe_reason,
        'selected_candidate_source': top['source'],
        'heuristic_top_source': heuristic_top['source'],
        'judge_invoked': judge_invoked,
        'judge_overrode': judge_overrode,
        'judge_chose_source': judge_chose['source'] if judge_chose else '',
        'judge_confidence': (judge_verdict or {}).get('confidence', 0.0),
        'judge_reason': judge_reason,
        'judge_risk_flags': (judge_verdict or {}).get('risk_flags', []),
        'judge_parse_status': (judge_verdict or {}).get('parse_status', ''),
        'triggers': triggers,
        'candidate_count': len(candidates),
        'consensus_size': consensus_top,
        'verifier_top_score': top_score,
        'verifier_top2_margin': margin,
        'planner_used': (top['source'] == 'C3_planner_compiled'),
        'plan_valid': bool(top.get('audit', {}).get('plan_valid', False)),
        'compiler_status': top.get('audit', {}).get('compiler_status', ''),
        'fallback_used': fallback_used,
        'fallback_reason': fallback_reason,
        'repair_used': repair_used,
        'repair_rounds': repair_rounds,
        'audit': {
            'candidates': cand_sources,
            'difficulty': top.get('difficulty', {}),
            'consensus_top_count': consensus_top,
            'rationale': [
                f'n_candidates={len(candidates)}',
                f'heuristic_top={heuristic_top["source"]}',
                f'judge_invoked={judge_invoked}',
                f'judge_overrode={judge_overrode}',
                f'final_top={top["source"]}',
                f'margin={margin:.3f}',
            ],
        },
    }


def _empty_response(reason: str) -> dict:
    return {'sql': '', 'safe': False, 'safe_reason': reason,
             'selected_candidate_source': 'none',
             'heuristic_top_source': '',
             'judge_invoked': False, 'judge_overrode': False,
             'judge_chose_source': '', 'judge_confidence': 0.0,
             'judge_reason': '', 'judge_risk_flags': [], 'judge_parse_status': '',
             'triggers': {},
             'candidate_count': 0, 'consensus_size': 0,
             'verifier_top_score': 0.0, 'verifier_top2_margin': 0.0,
             'planner_used': False, 'plan_valid': False,
             'compiler_status': '', 'fallback_used': True,
             'fallback_reason': reason, 'repair_used': False,
             'repair_rounds': 0, 'audit': {'rationale': [reason]}}
