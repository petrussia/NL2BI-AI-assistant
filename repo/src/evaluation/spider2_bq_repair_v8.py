"""spider2_bq_repair_v8 — BigQuery-aware bounded repair.

Triggers repair only on actionable error classes; the LLM gets the
exact BQ error message + the schema text so it can substitute the
correct identifier or function.
"""
from __future__ import annotations

import re
from typing import Callable

from spider2_bq_prompting_v8 import repair_prompt
from spider2_agent_v7 import _extract_sql


REPAIRABLE = {
    'syntax_error', 'function_signature', 'unrecognized_column',
    'table_or_dataset_not_found', 'aggregation_error', 'type_mismatch',
    'subquery_error', 'date_parse_error', 'other_bad_request',
    'BadRequest',
}

# Some BQ errors are NOT repairable by LLM — surface them but skip repair
NOT_REPAIRABLE = {
    'permission_denied', 'Forbidden',
    'bytes_billed_exceeded',  # repair would need different query strategy
    'timeout',
    'parse_error',  # already reflects what the model emitted
}


def _bucket_error(et: str, em: str) -> str:
    em_l = (em or '').lower()
    if 'syntax error' in em_l: return 'syntax_error'
    if 'function not found' in em_l or 'no matching signature' in em_l: return 'function_signature'
    if 'unrecognized name' in em_l or 'no such column' in em_l: return 'unrecognized_column'
    if 'not found: table' in em_l or 'not found: dataset' in em_l: return 'table_or_dataset_not_found'
    if 'permission denied' in em_l or 'access denied' in em_l: return 'permission_denied'
    if 'bytesbilledexceeded' in em_l or 'maximum bytes' in em_l: return 'bytes_billed_exceeded'
    if 'aggregat' in em_l: return 'aggregation_error'
    if 'subquery' in em_l: return 'subquery_error'
    if 'parse_date' in em_l or 'parse_timestamp' in em_l: return 'date_parse_error'
    if 'type mismatch' in em_l: return 'type_mismatch'
    return et or 'unknown'


def attempt_repair(question: str, schema_text: str, broken_sql: str,
                     error_msg: str, *,
                     gen: Callable, bq_executor: Callable,
                     max_rounds: int = 2) -> dict:
    """Attempt up to `max_rounds` LLM-driven repairs. Returns a dict with
    the final sql, success flag, and per-round trace.
    """
    cur_sql = broken_sql
    cur_err = error_msg or ''
    trace: list[dict] = []
    rounds = 0
    success = False
    final_dry: dict = {}

    while rounds < max_rounds:
        rounds += 1
        bucket = _bucket_error('', cur_err)
        if bucket in NOT_REPAIRABLE:
            trace.append({'round': rounds, 'skip': True, 'reason': bucket})
            break

        prompt = repair_prompt(question, schema_text, cur_sql, cur_err)
        try:
            raw = gen(prompt, max_new=600)
        except Exception as exc:
            trace.append({'round': rounds, 'error': f'gen_exc:{type(exc).__name__}'})
            break

        new_sql = _extract_sql(raw)
        if not new_sql or new_sql.strip() == cur_sql.strip():
            trace.append({'round': rounds, 'reason': 'empty_or_unchanged',
                          'raw_chars': len(raw or '')})
            break

        # Dry-run the repaired SQL
        try:
            dry = bq_executor(new_sql, dry_run=True, dialect='bigquery')
        except Exception as exc:
            trace.append({'round': rounds, 'phase': 'dry_run_exc',
                          'error': f'{type(exc).__name__}'})
            cur_sql = new_sql; cur_err = str(exc)[:300]; continue

        trace.append({'round': rounds, 'bucket': bucket,
                      'dry_run_ok': bool(dry.get('ok')),
                      'bytes_processed': int(dry.get('bytes_processed') or 0),
                      'error_short': (dry.get('error_message') or '')[:160],
                      'sql_chars': len(new_sql)})
        if dry.get('ok'):
            cur_sql = new_sql
            success = True
            final_dry = dry
            break
        cur_sql = new_sql
        cur_err = dry.get('error_message') or cur_err

    return {
        'sql': cur_sql,
        'success': success,
        'rounds': rounds,
        'final_dry': final_dry,
        'trace': trace,
    }
