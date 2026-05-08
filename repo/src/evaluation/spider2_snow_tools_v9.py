"""spider2_snow_tools_v9 — v9 SF tools = v8 + dialect normalizer.

Adds `normalize_then_verify(sql, sf_executor)` which:
  1. Runs the BigQuery-ism detector.
  2. If detected, applies `snowflake_dialect_normalizer_v9.normalize`
     and stores `{original_sql, normalized_sql, applied_fixes}`.
  3. Calls SF EXPLAIN dry_run on the normalized SQL.
  4. Returns the same verifier dict shape as v8 + a `dialect_fix` field.
"""
from __future__ import annotations

from typing import Callable

from spider2_snow_tools_v8 import is_snowflake_specific  # noqa: F401
from snowflake_dialect_normalizer_v9 import normalize, has_bigquery_isms


def normalize_then_verify(sql: str, sf_executor: Callable) -> dict:
    out: dict = {
        'safe_select': True, 'parses': False,
        'unknown_tables': [], 'unknown_columns': [],
        'executable': None, 'rows_count': 0,
        'error_type': '', 'error_message': '',
        'has_join': False, 'has_groupby': False, 'has_subquery': False,
        'dialect_fix': None,  # {original_sql, normalized_sql, applied_fixes, notes}
    }
    sql = sql or ''
    if not sql.strip():
        out['error_type'] = 'empty_sql'
        return out

    s_low = sql.lower()
    out['has_join'] = ' join ' in s_low
    out['has_groupby'] = ' group by' in s_low
    out['has_subquery'] = '(select' in s_low or '( select' in s_low

    used_sql = sql
    if has_bigquery_isms(sql):
        norm = normalize(sql)
        if norm.applied or norm.sql != sql:
            out['dialect_fix'] = {
                'applied_fixes': norm.applied,
                'notes': norm.notes,
                'original_chars': len(sql),
                'normalized_chars': len(norm.sql),
            }
            used_sql = norm.sql

    out['final_sql'] = used_sql

    try:
        res = sf_executor(used_sql, dry_run=True, dialect='snowflake')
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
