"""spider2_bq_verifier_v8 — BigQuery-aware candidate verifier.

For each candidate:
  1. Strip + safe_select (regex; sqlglot's BQ parse is unreliable)
  2. BQ dry_run via the executor (free)
  3. Bytes-billed sanity (if estimated > soft cap, flag for repair)
  4. Optional real exec (only the chosen candidate runs after selector)

Returns a verifier dict per candidate populating:
  parses (= dry_run_ok), all_known (best-effort sqlglot), executable=None
  (real exec is selector's job), bytes_processed, error_type/_message,
  table_refs, has_join/group/subquery/window/unnest, sql_chars.
"""
from __future__ import annotations

import re

import sqlglot
from sqlglot import exp

from dialect_utils_v2 import is_safe_select


_TABLE_RE = re.compile(r'`([^`]+)`')
_DOTTED_RE = re.compile(r'(?:^|[\s,(\[\.])([A-Za-z][\w\-]*\.[A-Za-z][\w\-]*\.[A-Za-z][\w\-]*)')


def _table_refs(sql: str) -> list[str]:
    out, seen = [], set()
    for r in _TABLE_RE.findall(sql or ''):
        if '.' in r and r.lower() not in seen:
            seen.add(r.lower()); out.append(r)
    for r in _DOTTED_RE.findall(sql or ''):
        if r.lower() not in seen:
            seen.add(r.lower()); out.append(r)
    return out


def _structural(sql: str) -> dict:
    s = sql or ''
    s_low = s.lower()
    has_join = ' join ' in s_low
    has_group = ' group by' in s_low
    has_subquery = '(select' in s_low or '( select' in s_low
    has_window = ' over(' in s_low or ' over (' in s_low or 'partition by' in s_low
    has_unnest = ' unnest(' in s_low or 'unnest (' in s_low
    has_with = s_low.lstrip().startswith('with')
    return {
        'has_join': has_join, 'has_groupby': has_group,
        'has_subquery': has_subquery, 'has_window': has_window,
        'has_unnest': has_unnest, 'has_with': has_with,
    }


def _sqlglot_known(sql: str, idx) -> dict:
    """Best-effort schema-validity vs the schema index. BigQuery's
    sqlglot dialect is incomplete, so this is advisory only."""
    out = {'all_known': None, 'unknown_tables': [], 'unknown_columns': []}
    try:
        tree = sqlglot.parse_one(sql, read='bigquery')
    except Exception:
        return out
    used_tables: set[str] = set()
    for t in tree.find_all(exp.Table):
        n = (t.name or '').lower()
        if n: used_tables.add(n)
    table_keys = {t.table_name.lower() for t in idx.tables}
    unknown = [t for t in used_tables if t not in table_keys]
    out['all_known'] = (len(unknown) == 0 and bool(used_tables))
    out['unknown_tables'] = sorted(unknown)
    return out


def verify_candidate(cand: dict, idx, bq_executor, *,
                       max_bytes_soft: int = 5 * 10**9) -> dict:
    """Mutates cand in place: adds `verifier` dict. Returns cand.

    Always runs dry_run (free). Real exec is the selector's job.
    """
    sql = (cand.get('sql') or '').strip()
    out: dict = {
        'sql_chars': len(sql),
        'safe_select': False, 'safe_reason': '',
        'parses': False, 'parses_executor': False,
        'all_known': None,
        'unknown_tables': [], 'unknown_columns': [],
        'table_refs': [], 'table_refs_n': 0,
        'has_join': False, 'has_groupby': False,
        'has_subquery': False, 'has_window': False,
        'has_unnest': False, 'has_with': False,
        'executable': None, 'rows_count': 0,
        'bytes_processed': 0, 'bytes_billed': 0,
        'error_type': '', 'error_message': '', 'phase': 'init',
        'over_soft_cap': False,
    }
    if not sql:
        out['error_type'] = 'empty_sql'; out['phase'] = 'empty'
        cand['verifier'] = out; return cand

    safe, why = is_safe_select(sql, 'bigquery')
    out['safe_select'] = safe; out['safe_reason'] = why
    if not safe:
        out['error_type'] = 'unsafe'; out['phase'] = 'safety'
        cand['verifier'] = out; return cand

    out['table_refs'] = _table_refs(sql); out['table_refs_n'] = len(out['table_refs'])
    out.update(_structural(sql))
    sg = _sqlglot_known(sql, idx)
    out['all_known'] = sg['all_known']
    out['unknown_tables'] = sg['unknown_tables']

    if bq_executor is None or getattr(bq_executor, 'mode', None) == 'noop':
        # No real BQ executor: parse-only verdict
        try:
            sqlglot.parse_one(sql, read='bigquery')
            out['parses'] = True
        except Exception as exc:
            out['error_type'] = 'parse_error'
            out['error_message'] = str(exc)[:200]
        out['phase'] = 'parse_only'
        cand['verifier'] = out; return cand

    # BQ dry_run is authoritative
    res = bq_executor(sql, dry_run=True, dialect='bigquery')
    out['phase'] = 'dry_run'
    if res.get('ok'):
        out['parses_executor'] = True
        out['parses'] = True
        out['bytes_processed'] = int(res.get('bytes_processed') or 0)
        if out['bytes_processed'] > max_bytes_soft:
            out['over_soft_cap'] = True
    else:
        out['parses_executor'] = False
        out['parses'] = False
        out['error_type'] = res.get('error_type', '') or 'dry_run_failed'
        out['error_message'] = (res.get('error_message') or '')[:400]
    cand['verifier'] = out
    return cand


def execute_chosen(cand: dict, bq_executor, *,
                    max_rows: int = 1000) -> dict:
    """Run the chosen candidate via real BQ exec. Updates verifier dict."""
    v = cand.get('verifier') or {}
    sql = (cand.get('sql') or '').strip()
    if not sql:
        v['executable'] = False
        v['phase'] = 'empty_after_select'
        cand['verifier'] = v; return cand
    res = bq_executor(sql, dry_run=False, max_rows=max_rows, dialect='bigquery')
    v['executable'] = bool(res.get('ok'))
    v['rows_count'] = len(res.get('rows') or [])
    v['rows'] = res.get('rows') or []
    v['bytes_billed'] = int(res.get('bytes_billed') or 0)
    v['bytes_processed'] = int(res.get('bytes_processed') or 0)
    v['phase'] = 'execute'
    if not res.get('ok'):
        v['error_type'] = res.get('error_type', '') or v.get('error_type','')
        v['error_message'] = (res.get('error_message') or v.get('error_message',''))[:400]
    cand['verifier'] = v
    return cand
