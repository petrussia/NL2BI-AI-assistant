"""baselines_b5_v6 — b4_v5 controller + Premium R2 retrieval and reranker.

Drop-in replacement for baselines_b4_v5 that:
  1. Uses retrieval lane R2 (BM25 + char-ngram + Qwen3-Embedding fused via RRF)
     in candidate generation (via the optional dense_retriever passed to
     schema_linker_bidirectional_v2.link).
  2. Passes a Qwen3-Reranker `score_pairs` callable to verifier_ranker_v2 so
     the composite score includes a cross-encoder estimate of P(SQL answers
     question). This is the Phase C BIRD discrimination gap fix.

Same call-shape as b4_v5 plus optional `dense_retriever` and `reranker_fn`
parameters.
"""
from __future__ import annotations

import textwrap

from candidate_generator_v2 import make_candidates
from verifier_ranker_v2 import rank_candidates
from repair_v2 import attempt_repair
from schema_ir_v2 import render_compact_schema


def run_b5v6_step(question: str, ir, *, gen, executor=None,
                   evidence_store=None, per_item_evidence: str = '',
                   plan_schema_path: str | None = None,
                   include_planner: bool = True,
                   include_evidence: bool = True,
                   non_harm_margin: float = 0.06,
                   max_repair_rounds: int = 1,
                   dense_retriever=None,
                   reranker_fn=None) -> dict:
    """One step of the B5_v6 (R2-augmented) pipeline."""
    candidates = make_candidates(question, ir, gen=gen,
                                  evidence_store=evidence_store,
                                  per_item_evidence=per_item_evidence,
                                  plan_schema_path=plan_schema_path,
                                  include_planner=include_planner,
                                  include_evidence=include_evidence)
    if not candidates:
        return {'sql':'','safe':False,'safe_reason':'no_candidates',
                'selected_candidate_source':'none','candidate_count':0,
                'verifier_top_score':0.0,'audit':{'rationale':['no_candidates']},
                'planner_used':False,'plan_valid':False,'fallback_used':True,
                'fallback_reason':'no_candidates','repair_used':False,
                'repair_rounds':0,'consensus_size':0,'reranker_used':bool(reranker_fn)}

    # Schema hint for reranker (compact, ~600 chars)
    schema_hint = render_compact_schema(ir, include_comments=False)

    ranked, consensus = rank_candidates(
        candidates, ir, executor=executor,
        question=question, non_harm_margin=non_harm_margin,
        reranker=reranker_fn, schema_hint=schema_hint,
    )
    top = ranked[0]
    chosen_sql = top['sql']
    chosen_safe = top['safe']
    chosen_safe_reason = top.get('safe_reason', '')

    repair_used = False; repair_rounds = 0
    if executor is not None and (not chosen_safe or top['verifier'].get('executable') is False):
        rep = attempt_repair(question, ir, top, executor, gen,
                              max_rounds=max_repair_rounds)
        repair_used = True; repair_rounds = rep['rounds']
        if rep['executable']:
            chosen_sql = rep['sql']; chosen_safe = rep['safe']
            chosen_safe_reason = 'repaired_ok'

    cand_sources = [{'source': c['source'],
                      'score': c['verifier']['score'],
                      'reranker': c['verifier'].get('reranker'),
                      'parses': c['verifier']['parses'],
                      'executable': c['verifier'].get('executable'),
                      'rows_count': c['verifier'].get('rows_count', 0),
                      'unknown_tables': c['verifier'].get('unknown_tables', []),
                      'unknown_columns_n': len(c['verifier'].get('unknown_columns', [])),
                      'intent_score': c['verifier']['intent']['intent']}
                     for c in ranked]
    consensus_size = consensus.get('top_count', 0)

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
        'verifier_top_score': top['verifier']['score'],
        'verifier_top2_margin': (ranked[0]['verifier']['score']
                                  - (ranked[1]['verifier']['score'] if len(ranked) > 1 else 0.0)),
        'reranker_used': bool(reranker_fn),
        'reranker_top_score': top['verifier'].get('reranker'),
        'planner_used': planner_used,
        'plan_valid': plan_valid,
        'compiler_status': top_audit.get('compiler_status',''),
        'fallback_used': fallback_used,
        'fallback_reason': fallback_reason,
        'repair_used': repair_used,
        'repair_rounds': repair_rounds,
        'audit': {
            'candidates': cand_sources,
            'difficulty': top.get('difficulty', {}),
            'consensus_top_count': consensus_size,
            'rationale': [
                f'n_candidates={len(candidates)}',
                f'top={top["source"]}',
                f'top_score={top["verifier"]["score"]:.3f}',
                f'reranker_top={top["verifier"].get("reranker")}',
                f'consensus={consensus_size}',
                f'r2={"yes" if (dense_retriever or reranker_fn) else "no"}',
            ],
        },
    }
