"""spider2_snow_agent_v8 — Snowflake-specific multi-candidate agent.

Wraps the building blocks from:
  - spider2_snow_candidate_generator_v8 (C0..C4)
  - spider2_snow_selector_v8 (heuristic + optional judge)
  - spider2_snow_repair_v8 (bounded repair)
  - spider2_sf_schema_index_v8 (schema retrieval)
  - spider2_sf_executor_v8 (Snowflake EXPLAIN dry_run + execute)

This is the entry point Phase 1 runners call. It returns a structured
result dict with full audit (per-candidate, repair trace, selector audit,
final SQL, executable, error_taxonomy class).
"""
from __future__ import annotations

import time
from typing import Callable

from spider2_sf_schema_index_v8 import SfSchemaIndex, render_subset
from spider2_snow_schema_retrieval_v8 import retrieve_relevant_keys
from spider2_snow_candidate_generator_v8 import make_candidates
from spider2_snow_selector_v8 import select_candidate
from spider2_snow_repair_v8 import attempt_repair
from spider2_snow_tools_v8 import is_snowflake_specific


def _verify_via_executor(sql: str, sf_executor: Callable) -> dict:
    """Snowflake EXPLAIN-based dry_run."""
    out: dict = {
        'safe_select': True, 'parses': False,
        'unknown_tables': [], 'unknown_columns': [],
        'executable': None, 'rows_count': 0,
        'error_type': '', 'error_message': '',
        'has_join': False, 'has_groupby': False, 'has_subquery': False,
    }
    sql = sql or ''
    if not sql.strip():
        out['error_type'] = 'empty_sql'
        return out
    s_low = sql.lower()
    out['has_join'] = ' join ' in s_low
    out['has_groupby'] = ' group by' in s_low
    out['has_subquery'] = '(select' in s_low or '( select' in s_low
    if not is_snowflake_specific(sql):
        out['error_type'] = 'wrong_dialect'
        out['error_message'] = 'BigQuery backticks or T-SQL brackets detected'
        return out
    try:
        res = sf_executor(sql, dry_run=True, dialect='snowflake')
    except Exception as exc:
        out['error_type'] = 'executor_exception'
        out['error_message'] = f'{type(exc).__name__}: {exc}'[:300]
        return out
    if res.get('ok'):
        out['parses'] = True
    else:
        out['error_type'] = res.get('error_type') or 'dry_run_failed'
        out['error_message'] = (res.get('error_message') or '')[:400]
    return out


def run_snow_agent_step(question: str, idx: SfSchemaIndex, *,
                          gen: Callable, sf_executor: Callable,
                          judge_gen: Callable | None = None,
                          k_tables: int = 6,
                          include_direct: bool = True,
                          include_retrieval: bool = True,
                          include_cte: bool = True,
                          include_tool_loop: bool = False,
                          max_repair_rounds: int = 1,
                          execute_chosen_query: bool = True,
                          max_rows_exec: int = 1000,
                          max_new_sql: int = 800,
                          max_new_cte: int = 1100) -> dict:
    """Run one Spider2-Snow item end-to-end. Returns full audit dict."""
    t0 = time.time()
    keys = retrieve_relevant_keys(idx, question, k_tables=k_tables)
    schema_short = render_subset(idx, keys, max_cols=18, include_samples=False)

    cands = make_candidates(question, idx, keys,
                              gen=gen,
                              include_direct=include_direct,
                              include_retrieval=include_retrieval,
                              include_cte=include_cte,
                              include_tool_loop=include_tool_loop,
                              max_new_sql=max_new_sql,
                              max_new_cte=max_new_cte)
    for c in cands:
        c['verifier'] = _verify_via_executor(c['sql'], sf_executor)

    repair_record = None
    parses_any = any((c.get('verifier') or {}).get('parses') for c in cands)
    if not parses_any and cands:
        seed = cands[0]
        sv = seed.get('verifier') or {}
        repair_record = attempt_repair(question, schema_short,
                                          seed.get('sql', ''),
                                          sv.get('error_message', ''),
                                          gen=gen, sf_executor=sf_executor,
                                          max_rounds=max_repair_rounds,
                                          max_new=max_new_sql)
        if repair_record.get('success'):
            new_cand = {'source': 'C3_repaired',
                          'sql': repair_record['sql'],
                          'audit': {'rounds': repair_record['rounds']}}
            new_cand['verifier'] = _verify_via_executor(repair_record['sql'],
                                                            sf_executor)
            cands.append(new_cand)

    chosen, sel_audit = select_candidate(cands, question,
                                              judge_gen=judge_gen,
                                              schema_summary=schema_short)
    elapsed_ms = None
    rows_count = 0
    rows_sample: list = []
    query_id = None
    if chosen is not None and execute_chosen_query:
        v = chosen.get('verifier') or {}
        if v.get('parses'):
            try:
                res = sf_executor(chosen['sql'], dry_run=False,
                                    max_rows_override=max_rows_exec,
                                    dialect='snowflake')
                v['executable'] = bool(res.get('ok'))
                v['rows_count'] = res.get('row_count', 0)
                rows_count = v['rows_count']
                rows_sample = (res.get('rows') or [])[:5]
                query_id = res.get('query_id')
                elapsed_ms = res.get('elapsed_ms')
                if not res.get('ok'):
                    v['error_type'] = res.get('error_type') or v.get('error_type', '')
                    v['error_message'] = (res.get('error_message') or '')[:400]
            except Exception as exc:
                v['executable'] = False
                v['error_type'] = 'executor_exception'
                v['error_message'] = f'{type(exc).__name__}: {exc}'[:300]

    return {
        'sql': (chosen or {}).get('sql', ''),
        'final_source': (chosen or {}).get('source', ''),
        'parses': (chosen or {}).get('verifier', {}).get('parses'),
        'executable': (chosen or {}).get('verifier', {}).get('executable'),
        'rows_count': rows_count,
        'rows_sample': rows_sample,
        'has_join': (chosen or {}).get('verifier', {}).get('has_join'),
        'has_groupby': (chosen or {}).get('verifier', {}).get('has_groupby'),
        'has_subquery': (chosen or {}).get('verifier', {}).get('has_subquery'),
        'error_type': (chosen or {}).get('verifier', {}).get('error_type', ''),
        'error_message': (chosen or {}).get('verifier', {}).get('error_message', ''),
        'query_id': query_id,
        'elapsed_ms': elapsed_ms,
        'candidate_count': len(cands),
        'candidates_summary': [{
            'source': c['source'],
            'parses': (c.get('verifier') or {}).get('parses'),
            'executable': (c.get('verifier') or {}).get('executable'),
            'sql_chars': len(c.get('sql') or ''),
            'error_type': (c.get('verifier') or {}).get('error_type', ''),
        } for c in cands],
        'repair_record': repair_record,
        'selector_audit': sel_audit,
        'wall_time_s': round(time.time() - t0, 2),
    }
