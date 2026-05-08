"""spider2_snow_agent_v9 — v9 agent = v8 + dialect normalizer hooks.

Differences from v8:
  - `_verify_via_executor` replaced by
    `spider2_snow_tools_v9.normalize_then_verify`. The candidate's SQL
    is auto-fixed for BigQuery-isms (backticks, SAFE_CAST, UNNEST, DATE_*
    arg order, REGEXP_CONTAINS) before EXPLAIN.
  - `final_sql` is the normalized form. We log both `original_sql`
    (per candidate) and `final_sql` so we can quantify dialect-fix
    impact.
  - Repair uses the normalized SQL as the seed.
  - `applied_fixes` per-candidate is included in the result audit.

The selector and candidate generator are unchanged.
"""
from __future__ import annotations

import time
from typing import Callable

from spider2_sf_schema_index_v8 import SfSchemaIndex, render_subset
from spider2_snow_schema_retrieval_v8 import retrieve_relevant_keys
from spider2_snow_candidate_generator_v8 import make_candidates
from spider2_snow_selector_v8 import select_candidate
from spider2_snow_repair_v8 import attempt_repair
from spider2_snow_tools_v9 import normalize_then_verify


def run_snow_agent_step_v9(question: str, idx: SfSchemaIndex, *,
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
    """Single Spider2-Snow item end-to-end with v9 dialect normalization."""
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
        c['original_sql'] = c['sql']
        v = normalize_then_verify(c['sql'], sf_executor)
        c['verifier'] = v
        # Replace candidate sql with normalized form (used by selector + execute)
        if v.get('final_sql'):
            c['sql'] = v['final_sql']

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
                          'original_sql': repair_record['sql']}
            new_cand['verifier'] = normalize_then_verify(repair_record['sql'],
                                                            sf_executor)
            if new_cand['verifier'].get('final_sql'):
                new_cand['sql'] = new_cand['verifier']['final_sql']
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
        'original_sql': (chosen or {}).get('original_sql', ''),
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
        'dialect_fix': (chosen or {}).get('verifier', {}).get('dialect_fix'),
        'query_id': query_id,
        'elapsed_ms': elapsed_ms,
        'candidate_count': len(cands),
        'candidates_summary': [{
            'source': c['source'],
            'parses': (c.get('verifier') or {}).get('parses'),
            'executable': (c.get('verifier') or {}).get('executable'),
            'sql_chars': len(c.get('sql') or ''),
            'original_sql_chars': len(c.get('original_sql') or ''),
            'error_type': (c.get('verifier') or {}).get('error_type', ''),
            'dialect_fix': (c.get('verifier') or {}).get('dialect_fix'),
        } for c in cands],
        'repair_record': repair_record,
        'selector_audit': sel_audit,
        'wall_time_s': round(time.time() - t0, 2),
    }
