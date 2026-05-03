"""verifier_ranker_v2 — composite scoring + risk-aware non-harm rule.

Inputs (per candidate):
  - sql, source, safe (already computed by candidate)
  - executor: function (sql) -> (executable: bool, rows: list|None,
                                   error_type: str, error_message: str)
  - schema_ir (for AST/schema validity checks via sqlglot_checks_v2)
Output: ordered list of candidates with score and feature breakdown.
The first candidate is the chosen winner. b4_v5 should still apply
non-harm: if scores are within margin, prefer the lower-risk source
(C0 anchor < C1 retrieval < C2 retrieval+evidence < C3 planner_compiled).

Verifier signals (no gold leak):
  - parses_safe (binary, AST-level)
  - schema_validity (table/column existence)
  - executable + rows count
  - structural plausibility (for the question intent: aggregate keywords →
    candidate should have aggregate; "list" keywords → no aggregate)
  - similarity to peer candidates (rows-set Jaccard) — high agreement
    among candidates is a strong vote of confidence
"""
from __future__ import annotations

import re
from collections import Counter

from sqlglot_checks_v2 import (
    ast_validity, schema_validity, structural_features,
)
from error_taxonomy_v2 import classify_outcome


SOURCE_RISK = {
    'C0_anchor': 0,
    'C1_retrieval_direct': 1,
    'C2_retrieval_evidence': 2,
    'C3_planner_compiled': 3,
}


def _wants_aggregate(question: str) -> bool:
    q = (question or '').lower()
    kws = ('how many','count','total','sum','average','avg','max','min',
            'highest','lowest','most','fewest','top ','number of','percentage','ratio')
    return any(kw in q for kw in kws)


def _wants_distinct(question: str) -> bool:
    q = (question or '').lower()
    return 'distinct' in q or 'different' in q or 'unique' in q


def _wants_order_limit(question: str) -> bool:
    q = (question or '').lower()
    kws = ('top ','first ','last ','largest','smallest','highest','lowest',
            'most ','fewest ','best ','worst ','sort','order')
    return any(kw in q for kw in kws)


def intent_score(question: str, sql: str, struct: dict) -> dict:
    """Cheap intent-vs-shape match — punishes obvious mismatches."""
    score = 1.0
    notes: list[str] = []
    if _wants_aggregate(question) and not (struct.get('aggregate_count') or 0) > 0:
        score -= 0.25; notes.append('missing_aggregate')
    if _wants_distinct(question) and not struct.get('has_distinct') and \
       not (struct.get('aggregate_count') or 0) > 0:
        # acceptable to use COUNT DISTINCT instead of DISTINCT
        score -= 0.15; notes.append('missing_distinct')
    if _wants_order_limit(question) and not (struct.get('has_order_by') or struct.get('has_limit')):
        score -= 0.10; notes.append('missing_order_or_limit')
    return {'intent': max(0.0, score), 'notes': notes}


def _rows_signature(rows) -> tuple:
    if not isinstance(rows, list): return ()
    out = []
    for r in rows[:200]:
        if isinstance(r, (list, tuple)):
            out.append(tuple(repr(x)[:80] for x in r))
        else:
            out.append((repr(r)[:80],))
    return tuple(sorted(out))


def consensus_signal(rows_sigs: list[tuple]) -> dict:
    """Vote among non-empty distinct row-signatures."""
    cnt = Counter(s for s in rows_sigs if s)
    if not cnt: return {'votes': {}, 'top_count': 0}
    top_sig, top_n = cnt.most_common(1)[0]
    return {'votes': dict(cnt), 'top_signature': top_sig, 'top_count': top_n}


def score_candidate(c: dict, ir, *, executor=None, question: str = '',
                     consensus: dict | None = None,
                     reranker_score: float | None = None) -> dict:
    """Returns dict with 'score' (0..1) and feature breakdown.

    `reranker_score` (optional, [0,1]) is a cross-encoder estimate of
    P(SQL faithfully answers the question). When provided, the composite
    score adds a 0.20 weight to it; the non-harm tie-break bias toward
    the lower-risk source still applies.
    """
    sql = c.get('sql', '')
    src = c.get('source', '')
    safe = bool(c.get('safe', False))
    feats: dict = {'source': src, 'safe': safe}

    # AST + schema validity (no gold)
    av = ast_validity(sql, ir.dialect)
    sv = schema_validity(sql, ir, ir.dialect)
    sf = structural_features(sql, ir.dialect)
    feats['parses'] = av['parses']
    feats['safe_select'] = av['safe_select']
    feats['unknown_tables'] = sv['unknown_tables']
    feats['unknown_columns'] = sv['unknown_columns']
    feats['ambiguous_columns'] = sv['ambiguous_columns']
    feats['structural'] = sf

    # Executor signals (still no gold — just exec ok / rows count)
    executable = None; rows = None; et = ''; em = ''
    if executor is not None and safe and av['parses']:
        try:
            executable, rows, et, em = executor(sql)
        except Exception as exc:
            executable, rows, et, em = False, None, type(exc).__name__, str(exc)
    feats['executable'] = executable
    feats['rows_count'] = (len(rows) if isinstance(rows, list) else 0)
    feats['rows_signature'] = _rows_signature(rows)

    # Intent vs shape
    intent = intent_score(question, sql, sf)
    feats['intent'] = intent

    # Consensus boost (rows-set agreement)
    cons_boost = 0.0
    if consensus and feats['rows_signature']:
        if feats['rows_signature'] == consensus.get('top_signature'):
            cons_boost = min(0.15, 0.05 * consensus.get('top_count', 1))
    feats['consensus_boost'] = cons_boost

    # Reranker signal (cross-encoder)
    feats['reranker'] = None if reranker_score is None else round(float(reranker_score), 4)

    # Composite score
    s = 0.0
    if not safe or not av['parses']: s = 0.05
    elif executable is False: s = 0.15
    else:
        s = 0.20
        s += 0.12 * (1.0 if not sv['unknown_tables'] else 0.0)
        s += 0.08 * (1.0 if not sv['unknown_columns'] else 0.0)
        s += 0.04 * (1.0 if not sv['ambiguous_columns'] else 0.5)
        s += 0.04 * (1.0 if feats['rows_count'] > 0 else 0.4)
        s += 0.08 * intent['intent']
        s += cons_boost
        if reranker_score is not None:
            s += 0.20 * float(reranker_score)
        else:
            # No reranker available: redistribute weight onto intent so the
            # composite range stays comparable.
            s += 0.10 * intent['intent']
        # Risk penalty: prefer simpler sources on otherwise tied candidates
        s -= 0.01 * SOURCE_RISK.get(src, 0)
    feats['score'] = round(min(1.0, max(0.0, s)), 4)
    return feats


def rank_candidates(candidates: list[dict], ir, *, executor=None,
                     question: str = '', non_harm_margin: float = 0.06,
                     reranker=None, schema_hint: str = '') -> list[dict]:
    """Return candidates with score; sorted by score desc, then by source risk asc.

    Applies the non-harm tie-break: when top-2 are within `non_harm_margin`,
    prefer the lower-risk source.

    `reranker` (optional) is a callable taking a list of (question, sql)
    pairs and returning probabilities in [0,1]. Typically the
    `reranker_v2.score_pairs` function. When supplied, its score becomes a
    feature in the composite ranker — closes the BIRD discrimination gap.
    """
    # First pass: collect rows signatures for consensus
    pre = []
    for c in candidates:
        feats = score_candidate(c, ir, executor=executor, question=question)
        pre.append({'cand': c, 'feats': feats})
    cons = consensus_signal([p['feats']['rows_signature'] for p in pre])
    # Reranker pass (batched)
    rer_scores: list[float | None] = [None] * len(pre)
    if reranker is not None:
        try:
            pairs = [(question, p['cand'].get('sql','')) for p in pre]
            rer_scores = reranker(pairs, schema_hint=schema_hint)
        except Exception:
            rer_scores = [None] * len(pre)
    # Second pass: re-score with consensus + reranker
    out = []
    for p, rs in zip(pre, rer_scores):
        feats = score_candidate(p['cand'], ir, executor=executor,
                                question=question, consensus=cons,
                                reranker_score=rs)
        rec = {**p['cand'], 'verifier': feats}
        out.append(rec)
    # Sort
    out.sort(key=lambda r: (-r['verifier']['score'],
                              SOURCE_RISK.get(r['source'], 99)))
    # Non-harm tie-break for top-2
    if len(out) >= 2:
        s1 = out[0]['verifier']['score']; s2 = out[1]['verifier']['score']
        if (s1 - s2) < non_harm_margin and \
           SOURCE_RISK.get(out[0]['source'], 99) > SOURCE_RISK.get(out[1]['source'], 99):
            out[0], out[1] = out[1], out[0]
    return out, cons
