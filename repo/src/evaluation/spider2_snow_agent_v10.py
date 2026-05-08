"""spider2_snow_agent_v10 — H1-aware Snow agent.

Pipeline diff vs v9:
  1. Candidate generation uses v10 prompts (`direct/retrieval/cte_prompt_v10`)
     which render schema with the canonical unquoted DB.SCHEMA.TABLE form
     and forbid 4-part identifiers + segment duplication explicitly.
  2. Each candidate's SQL is normalized BEFORE EXPLAIN by:
       a. v9 dialect normalizer (backticks/UNNEST/SAFE_CAST/...).
       b. v10 identifier normalizer (`A.B.B.C` → `A.B.C`,
          `"A.B.C"` → `A.B.C`).
  3. `original_sql`, `final_sql`, `applied_dialect_fixes`, and
     `applied_identifier_fixes` are all logged per candidate so the
     impact is quantifiable.
"""
from __future__ import annotations

import time
from typing import Callable

from spider2_agent_v7 import _extract_sql
from spider2_sf_schema_index_v8 import SfSchemaIndex
from spider2_snow_schema_retrieval_v8 import retrieve_relevant_keys
from spider2_snow_schema_render_v10 import (
    render_subset_v10, normalize_identifiers_v10,
)
from spider2_snow_prompting_v10 import (
    direct_prompt_v10, retrieval_prompt_v10, cte_prompt_v10,
    repair_prompt_v10,
)
from snowflake_dialect_normalizer_v9 import normalize as _dialect_normalize
from spider2_snow_selector_v8 import select_candidate


def _gen_one(prompt: str, gen: Callable, max_new: int) -> str:
    try:
        raw = gen(prompt, max_new=max_new)
    except Exception as exc:
        return f'-- gen_error: {type(exc).__name__}'
    return _extract_sql(raw) or (raw.strip() if raw else '')


def _normalize_v10(sql: str) -> dict:
    """Apply v9 dialect + v10 identifier normalizers in sequence."""
    out: dict = {'original_sql': sql, 'applied_dialect_fixes': [],
                 'applied_identifier_fixes': {}, 'final_sql': sql}
    if not sql:
        return out
    d = _dialect_normalize(sql)
    cur = d.sql
    out['applied_dialect_fixes'] = d.applied
    ident = normalize_identifiers_v10(cur)
    cur = ident.sql
    out['applied_identifier_fixes'] = {
        'n_4part_collapsed': ident.n_4part_collapsed,
        'n_quoted_blob_unwrapped': ident.n_quoted_blob_unwrapped,
    }
    out['final_sql'] = cur
    return out


def _verify(sql: str, sf_executor: Callable) -> dict:
    out = {'parses': False, 'safe_select': True,
            'executable': None, 'rows_count': 0,
            'error_type': '', 'error_message': '',
            'has_join': False, 'has_groupby': False, 'has_subquery': False}
    if not sql.strip():
        out['error_type'] = 'empty_sql'
        return out
    s_low = sql.lower()
    out['has_join'] = ' join ' in s_low
    out['has_groupby'] = ' group by' in s_low
    out['has_subquery'] = '(select' in s_low or '( select' in s_low
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


def _attempt_repair_v10(question: str, schema_text: str, broken_sql: str,
                              error_msg: str, *, gen: Callable,
                              sf_executor: Callable, max_rounds: int = 1,
                              max_new: int = 700) -> dict:
    cur_sql = (broken_sql or '').strip()
    cur_err = error_msg or ''
    trace: list = []
    rounds = 0
    while rounds < max_rounds:
        rounds += 1
        prompt = repair_prompt_v10(question, schema_text, cur_sql, cur_err)
        try:
            raw = gen(prompt, max_new=max_new)
        except Exception as exc:
            trace.append({'round': rounds, 'gen_error': type(exc).__name__})
            break
        new_sql = _extract_sql(raw) or (raw.strip() if raw else '')
        if not new_sql or new_sql.strip() == cur_sql.strip():
            trace.append({'round': rounds, 'reason': 'empty_or_unchanged'})
            break
        norm = _normalize_v10(new_sql)
        check_sql = norm['final_sql']
        try:
            dry = sf_executor(check_sql, dry_run=True, dialect='snowflake')
        except Exception as exc:
            trace.append({'round': rounds, 'exec_error': type(exc).__name__})
            cur_sql = check_sql; continue
        trace.append({'round': rounds, 'dry_ok': bool(dry.get('ok')),
                        'error_short': (dry.get('error_message') or '')[:120]})
        if dry.get('ok'):
            return {'sql': check_sql, 'rounds': rounds, 'success': True,
                     'trace': trace,
                     'applied_dialect_fixes': norm['applied_dialect_fixes'],
                     'applied_identifier_fixes': norm['applied_identifier_fixes']}
        cur_sql = check_sql
        cur_err = dry.get('error_message') or cur_err
    return {'sql': cur_sql, 'rounds': rounds, 'success': False, 'trace': trace}


def run_snow_agent_step_v10(question: str, idx: SfSchemaIndex, *,
                                  gen: Callable, sf_executor: Callable,
                                  judge_gen: Callable | None = None,
                                  k_tables: int = 6,
                                  include_direct: bool = True,
                                  include_retrieval: bool = True,
                                  include_cte: bool = True,
                                  max_repair_rounds: int = 1,
                                  execute_chosen_query: bool = True,
                                  max_rows_exec: int = 1000,
                                  max_new_sql: int = 800,
                                  max_new_cte: int = 1100) -> dict:
    t0 = time.time()
    keys = retrieve_relevant_keys(idx, question, k_tables=k_tables)
    schema_short = render_subset_v10(idx, keys, max_cols=18, include_samples=False)

    cands: list[dict] = []
    if include_direct:
        p = direct_prompt_v10(question, idx, keys)
        sql_raw = _gen_one(p, gen, max_new_sql)
        norm = _normalize_v10(sql_raw)
        c = {'source': 'C0_direct', 'sql': norm['final_sql'],
              'original_sql': norm['original_sql'],
              'applied_dialect_fixes': norm['applied_dialect_fixes'],
              'applied_identifier_fixes': norm['applied_identifier_fixes']}
        c['verifier'] = _verify(c['sql'], sf_executor)
        cands.append(c)
    if include_retrieval:
        p = retrieval_prompt_v10(question, idx, keys)
        sql_raw = _gen_one(p, gen, max_new_sql)
        norm = _normalize_v10(sql_raw)
        c = {'source': 'C1_retrieval_docs', 'sql': norm['final_sql'],
              'original_sql': norm['original_sql'],
              'applied_dialect_fixes': norm['applied_dialect_fixes'],
              'applied_identifier_fixes': norm['applied_identifier_fixes']}
        c['verifier'] = _verify(c['sql'], sf_executor)
        cands.append(c)
    if include_cte:
        p = cte_prompt_v10(question, idx, keys)
        sql_raw = _gen_one(p, gen, max_new_cte)
        norm = _normalize_v10(sql_raw)
        c = {'source': 'C2_cte_decomp', 'sql': norm['final_sql'],
              'original_sql': norm['original_sql'],
              'applied_dialect_fixes': norm['applied_dialect_fixes'],
              'applied_identifier_fixes': norm['applied_identifier_fixes']}
        c['verifier'] = _verify(c['sql'], sf_executor)
        cands.append(c)

    repair_record = None
    if not any((c.get('verifier') or {}).get('parses') for c in cands) and cands:
        seed = cands[0]
        sv = seed.get('verifier') or {}
        repair_record = _attempt_repair_v10(question, schema_short,
                                                  seed.get('sql', ''),
                                                  sv.get('error_message', ''),
                                                  gen=gen, sf_executor=sf_executor,
                                                  max_rounds=max_repair_rounds,
                                                  max_new=max_new_sql)
        if repair_record.get('success'):
            new_cand = {'source': 'C3_repaired',
                          'sql': repair_record['sql'],
                          'original_sql': repair_record['sql'],
                          'applied_dialect_fixes': repair_record.get('applied_dialect_fixes', []),
                          'applied_identifier_fixes': repair_record.get('applied_identifier_fixes', {})}
            new_cand['verifier'] = _verify(repair_record['sql'], sf_executor)
            cands.append(new_cand)

    chosen, sel_audit = select_candidate(cands, question,
                                              judge_gen=judge_gen,
                                              schema_summary=schema_short)
    elapsed_ms = None; rows_count = 0; rows_sample: list = []; query_id = None
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
        'applied_dialect_fixes': (chosen or {}).get('applied_dialect_fixes', []),
        'applied_identifier_fixes': (chosen or {}).get('applied_identifier_fixes', {}),
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
            'applied_dialect_fixes': c.get('applied_dialect_fixes', []),
            'applied_identifier_fixes': c.get('applied_identifier_fixes', {}),
        } for c in cands],
        'repair_record': repair_record,
        'selector_audit': sel_audit,
        'wall_time_s': round(time.time() - t0, 2),
    }
