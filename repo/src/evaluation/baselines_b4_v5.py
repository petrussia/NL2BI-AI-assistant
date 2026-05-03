"""baselines_b4_v5 — full controller: candidate_generator → verifier_ranker → bounded repair.

Architecture: produce 2-4 candidates per question (from candidate_generator_v2),
score them with verifier_ranker_v2 (using a no-gold executor probe), pick the
top, attempt repair if the top fails parse / executes empty / fails. The
verifier's non-harm tie-break ensures we never regress below the anchor by
more than the verifier margin.

Returns the chosen SQL plus a thick audit suitable for the runner JSONL.
"""
from __future__ import annotations

from candidate_generator_v2 import make_candidates
from verifier_ranker_v2 import rank_candidates, SOURCE_RISK
from repair_v2 import attempt_repair
from dialect_utils_v2 import is_safe_select


def run_b4v5_step(question: str, ir, *, gen, executor=None,
                   evidence_store=None, per_item_evidence: str = '',
                   plan_schema_path: str | None = None,
                   include_planner: bool = True,
                   include_evidence: bool = True,
                   non_harm_margin: float = 0.06,
                   max_repair_rounds: int = 1) -> dict:
    """Returns dict ready to merge into JSONL row."""
    candidates = make_candidates(question, ir, gen=gen,
                                  evidence_store=evidence_store,
                                  per_item_evidence=per_item_evidence,
                                  plan_schema_path=plan_schema_path,
                                  include_planner=include_planner,
                                  include_evidence=include_evidence)
    if not candidates:
        return {'sql': '', 'safe': False, 'safe_reason': 'no_candidates',
                 'selected_candidate_source': 'none', 'candidate_count': 0,
                 'verifier_top_score': 0.0, 'audit': {'rationale': ['no_candidates']},
                 'planner_used': False, 'plan_valid': False, 'fallback_used': True,
                 'fallback_reason': 'no_candidates', 'repair_used': False,
                 'repair_rounds': 0, 'consensus_size': 0}

    ranked, consensus = rank_candidates(candidates, ir, executor=executor,
                                         question=question,
                                         non_harm_margin=non_harm_margin)
    top = ranked[0]
    top_score = top['verifier']['score']
    chosen_sql = top['sql']
    chosen_safe = top['safe']
    chosen_safe_reason = top.get('safe_reason', '')

    # Repair if top is unsafe / not executable
    repair_used = False; repair_rounds = 0; repair_history = []
    if executor is not None and (not chosen_safe or top['verifier'].get('executable') is False):
        rep = attempt_repair(question, ir, top, executor, gen,
                              max_rounds=max_repair_rounds)
        repair_used = True; repair_rounds = rep['rounds']
        repair_history = rep['history']
        if rep['executable']:
            chosen_sql = rep['sql']; chosen_safe = rep['safe']
            chosen_safe_reason = 'repaired_ok'

    # Audit
    cand_sources = [{'source': c['source'],
                      'score': c['verifier']['score'],
                      'parses': c['verifier']['parses'],
                      'executable': c['verifier'].get('executable'),
                      'rows_count': c['verifier'].get('rows_count', 0),
                      'unknown_tables': c['verifier'].get('unknown_tables', []),
                      'unknown_columns_n': len(c['verifier'].get('unknown_columns', [])),
                      'intent_score': c['verifier']['intent']['intent']}
                     for c in ranked]
    consensus_size = consensus.get('top_count', 0)

    # Provenance (was the top a planner or anchor? etc.)
    top_audit = top.get('audit', {})
    planner_used = (top['source'] == 'C3_planner_compiled')
    plan_valid = bool(top_audit.get('plan_valid', False))

    fallback_used = (top['source'] == 'C0_anchor' and len(candidates) > 1)
    fallback_reason = ('verifier_chose_anchor' if fallback_used else '')

    return {
        'sql': chosen_sql, 'safe': chosen_safe, 'safe_reason': chosen_safe_reason,
        'selected_candidate_source': top['source'],
        'candidate_count': len(candidates),
        'consensus_size': consensus_size,
        'verifier_top_score': top_score,
        'verifier_top2_margin': (ranked[0]['verifier']['score']
                                  - (ranked[1]['verifier']['score'] if len(ranked) > 1 else 0.0)),
        'planner_used': planner_used,
        'plan_valid': plan_valid,
        'compiler_status': top_audit.get('compiler_status',''),
        'fallback_used': fallback_used,
        'fallback_reason': fallback_reason,
        'repair_used': repair_used,
        'repair_rounds': repair_rounds,
        'repair_history': repair_history,
        'audit': {
            'candidates': cand_sources,
            'difficulty': top.get('difficulty', {}),
            'consensus_top_count': consensus_size,
            'rationale': [
                f'n_candidates={len(candidates)}',
                f'top={top["source"]}',
                f'top_score={top_score:.3f}',
                f'consensus={consensus_size}',
                f'repair={repair_used}',
            ],
        },
    }
