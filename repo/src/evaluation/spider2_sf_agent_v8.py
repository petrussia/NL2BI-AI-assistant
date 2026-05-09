"""spider2_sf_agent_v8 — Snowflake A_sf agent (mirrors BQ v8 structure).

Reuses the v7 schema retrieval helpers + the v8 BQ candidate scaffolding
where possible, with SF-specific prompting and the SF executor.

Public entry:
    run_sf_agent_step(question, idx, *, gen, sf_executor, ...)
        -> result dict identical-shape to BQ v8 result.

The runner gates calls behind `spider2_sf_readiness_v8.check_readiness`;
this module assumes the executor is already verified.
"""
from __future__ import annotations

import time
from typing import Callable

from spider2_agent_v7 import _extract_sql  # WITH-preserving extractor
from spider2_sf_schema_index_v8 import SfSchemaIndex, render_subset
from spider2_sf_prompting_v8 import (
    direct_prompt, retrieval_prompt, cte_prompt, repair_prompt,
)


def _verify_candidate(sql: str, idx: SfSchemaIndex, *, sf_executor,
                        dry_only: bool) -> dict:
    """Snowflake-side verification: dry_run via EXPLAIN."""
    out: dict = {
        'sql_chars': len(sql or ''),
        'safe_select': True,
        'parses': False, 'parses_executor': False,
        'all_known': None,
        'unknown_tables': [], 'unknown_columns': [],
        'executable': None, 'rows_count': 0,
        'phase': 'init', 'error_type': '', 'error_message': '',
        'has_join': False, 'has_groupby': False, 'has_subquery': False,
        'bytes_processed': 0, 'bytes_billed': 0,
        'query_id': None,
    }
    if not (sql or '').strip():
        out['phase'] = 'empty'; out['error_type'] = 'empty_sql'
        return out

    s_low = sql.lower()
    out['has_join'] = ' join ' in s_low
    out['has_groupby'] = ' group by' in s_low
    out['has_subquery'] = '(select' in s_low or '( select' in s_low

    if sf_executor is None or getattr(sf_executor, 'mode', None) == 'noop':
        out['phase'] = 'no_executor'
        return out

    res = sf_executor(sql, dry_run=True, dialect='snowflake')
    out['phase'] = 'dry_run'
    if res.get('ok'):
        out['parses'] = True
        out['parses_executor'] = True
        out['query_id'] = res.get('query_id')
    else:
        out['parses'] = False
        out['error_type'] = res.get('error_type') or 'dry_run_failed'
        out['error_message'] = (res.get('error_message') or '')[:400]
    return out


def _candidate_score(c: dict) -> float:
    v = c.get('verifier') or {}
    s = 0.0
    if v.get('parses'): s += 3.0
    if v.get('safe_select'): s += 0.5
    s += 0.05 * {'C0_direct': 0, 'C1_retrieval_docs': 1,
                   'C2_cte_decomp': 2, 'C3_repaired': 1.5}.get(c.get('source',''), 0)
    return s


def _attempt_repair(question: str, schema_text: str, broken: dict,
                      *, gen: Callable, sf_executor: Callable,
                      max_rounds: int = 1) -> dict | None:
    sql = (broken.get('sql') or '').strip()
    em = (broken.get('verifier') or {}).get('error_message') or ''
    rounds = 0
    cur_sql = sql; cur_err = em
    trace = []
    while rounds < max_rounds:
        rounds += 1
        prompt = repair_prompt(question, schema_text, cur_sql, cur_err)
        try:
            raw = gen(prompt, max_new=600)
        except Exception as exc:
            trace.append({'round': rounds, 'error': f'gen_exc:{type(exc).__name__}'})
            break
        new_sql = _extract_sql(raw)
        if not new_sql or new_sql.strip() == cur_sql.strip():
            trace.append({'round': rounds, 'reason': 'empty_or_unchanged'})
            break
        dry = sf_executor(new_sql, dry_run=True, dialect='snowflake')
        trace.append({'round': rounds, 'dry_ok': bool(dry.get('ok')),
                       'error_short': (dry.get('error_message') or '')[:120]})
        if dry.get('ok'):
            return {'sql': new_sql, 'rounds': rounds, 'success': True,
                     'trace': trace}
        cur_sql = new_sql; cur_err = dry.get('error_message') or cur_err
    return {'sql': cur_sql, 'rounds': rounds, 'success': False, 'trace': trace}


def run_sf_agent_step(question: str, idx: SfSchemaIndex,
                        *, gen: Callable, sf_executor: Callable,
                        selected_keys: list[str] | None = None,
                        include_direct: bool = True,
                        include_retrieval: bool = True,
                        include_cte: bool = True,
                        max_new_sql: int = 800,
                        max_new_cte: int = 1000,
                        max_repair_rounds: int = 1,
                        execute_chosen_query: bool = True,
                        max_rows_exec: int = 1000) -> dict:
    """Single-shot SF agent. selected_keys defaults to first 6 tables of idx."""
    t0 = time.time()
    keys = selected_keys or [t.fq_name for t in idx.tables[:6]]
    schema_text_short = render_subset(idx, keys, max_cols=18,
                                          include_samples=False)

    cands: list[dict] = []
    if include_direct:
        p0 = direct_prompt(question, idx, keys, max_cols=22)
        s0 = _extract_sql(gen(p0, max_new=max_new_sql))
        c0 = {'source': 'C0_direct', 'sql': s0, 'prompt_chars': len(p0)}
        c0['verifier'] = _verify_candidate(s0, idx,
                                              sf_executor=sf_executor,
                                              dry_only=True)
        cands.append(c0)

    if include_retrieval:
        p1 = retrieval_prompt(question, idx, keys, max_cols=22)
        s1 = _extract_sql(gen(p1, max_new=max_new_sql))
        c1 = {'source': 'C1_retrieval_docs', 'sql': s1, 'prompt_chars': len(p1)}
        c1['verifier'] = _verify_candidate(s1, idx,
                                              sf_executor=sf_executor,
                                              dry_only=True)
        cands.append(c1)

    if include_cte:
        p2 = cte_prompt(question, idx, keys, max_cols=22)
        s2 = _extract_sql(gen(p2, max_new=max_new_cte))
        c2 = {'source': 'C2_cte_decomp', 'sql': s2, 'prompt_chars': len(p2)}
        c2['verifier'] = _verify_candidate(s2, idx,
                                              sf_executor=sf_executor,
                                              dry_only=True)
        cands.append(c2)

    # Repair on no-pass
    if not any((c.get('verifier') or {}).get('parses') for c in cands) and cands:
        seed = cands[0]
        rep = _attempt_repair(question, schema_text_short, seed,
                                gen=gen, sf_executor=sf_executor,
                                max_rounds=max_repair_rounds)
        if rep and rep.get('success'):
            new_cand = {'source': 'C3_repaired', 'sql': rep['sql']}
            new_cand['verifier'] = _verify_candidate(rep['sql'], idx,
                                                       sf_executor=sf_executor,
                                                       dry_only=True)
            new_cand['repair'] = rep
            cands.append(new_cand)

    cands.sort(key=lambda c: -_candidate_score(c))
    chosen = cands[0] if cands else None
    if chosen is None:
        return {'sql': '', 'final_source': '', 'parses': False,
                 'executable': False, 'rows_count': 0,
                 'error_type': 'no_candidate', 'error_message': '',
                 'wall_time_s': round(time.time() - t0, 2),
                 'candidates_summary': []}

    # Real execution if dry_run passed
    v = chosen.get('verifier') or {}
    if execute_chosen_query and v.get('parses'):
        res = sf_executor(chosen['sql'], dry_run=False,
                            max_rows_override=max_rows_exec,
                            dialect='snowflake')
        v['executable'] = bool(res.get('ok'))
        v['rows_count'] = res.get('row_count', 0)
        v['rows_sample'] = (res.get('rows') or [])[:5]
        v['query_id'] = res.get('query_id')
        v['phase'] = 'execute'
        v['elapsed_ms'] = res.get('elapsed_ms')
        if not res.get('ok'):
            v['error_type'] = res.get('error_type') or v.get('error_type','')
            v['error_message'] = (res.get('error_message') or v.get('error_message',''))[:400]

    return {
        'sql': chosen['sql'],
        'final_source': chosen['source'],
        'parses': v.get('parses'),
        'executable': v.get('executable'),
        'rows_count': v.get('rows_count', 0),
        'rows_sample': v.get('rows_sample', []),
        'has_join': v.get('has_join'), 'has_groupby': v.get('has_groupby'),
        'has_subquery': v.get('has_subquery'),
        'error_type': v.get('error_type', ''),
        'error_message': v.get('error_message', ''),
        'phase': v.get('phase', ''),
        'query_id': v.get('query_id'),
        'elapsed_ms': v.get('elapsed_ms'),
        'candidate_count': len(cands),
        'candidates_summary': [{
            'source': c['source'],
            'parses': (c.get('verifier') or {}).get('parses'),
            'sql_chars': len(c.get('sql','') or ''),
            'error_type': (c.get('verifier') or {}).get('error_type', ''),
        } for c in cands],
        'wall_time_s': round(time.time() - t0, 2),
    }
