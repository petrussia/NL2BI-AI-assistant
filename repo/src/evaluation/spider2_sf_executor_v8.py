"""spider2_sf_executor_v8 — Snowflake executor for the A_sf lane.

Mirrors `spider2_tools_v7.build_bq_executor` contract so the v8 agent
can swap engines without modifying the agent code:

    executor(sql, *, dry_run=False, max_rows=1000, dialect='snowflake')
        -> dict with ok / rows / error_type / ... / mode='snowflake'

Key differences from BQ:
  - Snowflake has no free `dry_run`. We approximate via `EXPLAIN USING TEXT`
    which is cheap (no warehouse compute needed for explain) and validates
    syntax + object existence.
  - `bytes_billed` is always 0 (Snowflake bills credits, not bytes).
  - Errors are normalized into our taxonomy
    (object_not_found / database_missing / permission_denied / ...).

No password/private-key value ever flows into log/print output here.
"""
from __future__ import annotations

import re
import time
from typing import Any, Callable

import sqlglot

from spider2_sf_readiness_v8 import get_credentials


_OBJECT_NOT_FOUND_RE = re.compile(
    r'(does not exist|not authorized|invalid identifier|object .* not found)',
    re.IGNORECASE)
_DB_MISSING_RE = re.compile(r"database .* does not exist", re.IGNORECASE)
_SCHEMA_MISSING_RE = re.compile(r"schema .* does not exist", re.IGNORECASE)
_TABLE_MISSING_RE = re.compile(r"(table|view) .* does not exist", re.IGNORECASE)
_PERMISSION_DENIED_RE = re.compile(
    r"(insufficient privilege|access denied|not authorized to)", re.IGNORECASE)
_WAREHOUSE_RE = re.compile(r'(warehouse .* (suspended|not running)|no .*warehouse)',
                              re.IGNORECASE)
_AUTH_RE = re.compile(r'(authentication|invalid (username|password|user/password))',
                        re.IGNORECASE)
_TIMEOUT_RE = re.compile(r'(timed out|timeout|statement_timeout)', re.IGNORECASE)
_SYNTAX_RE = re.compile(r'(syntax error|sql compilation error)', re.IGNORECASE)


def _classify_error(et: str, em: str) -> str:
    """Normalize a Snowflake error message into our taxonomy."""
    msg = f'{et}\n{em}'
    if _DB_MISSING_RE.search(msg): return 'database_missing'
    if _SCHEMA_MISSING_RE.search(msg): return 'schema_missing'
    if _TABLE_MISSING_RE.search(msg): return 'table_missing'
    if _OBJECT_NOT_FOUND_RE.search(msg): return 'object_not_found'
    if _PERMISSION_DENIED_RE.search(msg): return 'permission_denied'
    if _WAREHOUSE_RE.search(msg): return 'warehouse_error'
    if _AUTH_RE.search(msg): return 'auth_error'
    if _TIMEOUT_RE.search(msg): return 'timeout'
    if _SYNTAX_RE.search(msg): return 'syntax'
    return 'unknown'


def build_sf_executor(*, query_tag: str = 'spider2_sf_v8',
                       timeout_s: int = 60, max_rows: int = 1000,
                       env_path: str | None = None) -> Callable:
    """Returns a callable matching the BQ executor contract.

    The connection is lazy: it opens on first call and is reused.
    Pass `query_tag` per-run so SF query_history audits are clean.
    """
    import snowflake.connector
    creds = get_credentials(env_path)

    state: dict[str, Any] = {'conn': None, 'cur': None, 'cfg_done': False}

    def _ensure() -> None:
        if state['conn'] is None:
            state['conn'] = snowflake.connector.connect(**creds)
            state['cur'] = state['conn'].cursor()
        if not state['cfg_done']:
            try:
                state['cur'].execute(
                    f"ALTER SESSION SET QUERY_TAG = '{query_tag}'")
                state['cur'].execute(
                    f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {int(timeout_s)}")
                state['cur'].execute(
                    f"ALTER SESSION SET ROWS_PER_RESULTSET = {int(max_rows)}")
            except Exception: pass
            state['cfg_done'] = True

    def _close():
        try:
            if state['cur']: state['cur'].close()
            if state['conn']: state['conn'].close()
        finally:
            state['cur'] = None; state['conn'] = None

    def _fail(err_type: str, msg: str, *, phase: str, started: float) -> dict:
        return {
            'ok': False, 'rows': None, 'row_count': 0,
            'error_type': err_type, 'error_message': msg,
            'mode': 'snowflake', 'query_id': None,
            'warehouse': creds.get('warehouse', ''),
            'role': creds.get('role', ''),
            'bytes_processed': 0, 'bytes_billed': 0,
            'credits_used_cloud_services': None,
            'query_tag': query_tag,
            'elapsed_ms': int((time.time() - started) * 1000),
            'phase': phase,
        }

    def executor(sql: str, *, dry_run: bool = False,
                   max_rows_override: int | None = None,
                   dialect: str = 'snowflake') -> dict:
        started = time.time()
        sql_clean = (sql or '').strip().rstrip(';').strip()
        if not sql_clean:
            return _fail('empty_sql', '', phase='precheck', started=started)
        # Block obvious DDL/DML
        bad = re.search(
            r'\b(insert|update|delete|drop|truncate|alter|create|grant|revoke)\b',
            sql_clean, re.IGNORECASE)
        if bad:
            return _fail('unsafe', f'forbidden:{bad.group(0)}',
                          phase='safety', started=started)

        # Dry-run path: try sqlglot parse first, then EXPLAIN
        if dry_run:
            try:
                sqlglot.parse_one(sql_clean, read='snowflake')
            except Exception as e:
                # sqlglot's snowflake parser is incomplete; fall through to EXPLAIN
                pass
            try:
                _ensure()
                state['cur'].execute(f'EXPLAIN USING TEXT {sql_clean}')
                # Drain
                state['cur'].fetchall()
                return {
                    'ok': True, 'rows': None, 'row_count': 0,
                    'error_type': None, 'error_message': None,
                    'mode': 'snowflake_explain',
                    'query_id': state['cur'].sfqid,
                    'warehouse': creds.get('warehouse', ''),
                    'role': creds.get('role', ''),
                    'bytes_processed': 0, 'bytes_billed': 0,
                    'credits_used_cloud_services': None,
                    'query_tag': query_tag,
                    'elapsed_ms': int((time.time() - started) * 1000),
                    'phase': 'dry_run',
                }
            except Exception as e:
                msg = str(e)[:400]
                et = type(e).__name__
                return _fail(_classify_error(et, msg), msg,
                                phase='dry_run', started=started)

        # Real execution
        try:
            _ensure()
            state['cur'].execute(sql_clean)
            cap = int(max_rows_override or max_rows)
            rows = state['cur'].fetchmany(cap)
            return {
                'ok': True,
                'rows': [tuple(r) for r in rows],
                'row_count': len(rows),
                'error_type': None, 'error_message': None,
                'mode': 'snowflake',
                'query_id': state['cur'].sfqid,
                'warehouse': creds.get('warehouse', ''),
                'role': creds.get('role', ''),
                'bytes_processed': 0, 'bytes_billed': 0,
                'credits_used_cloud_services': None,
                'query_tag': query_tag,
                'elapsed_ms': int((time.time() - started) * 1000),
                'phase': 'execute',
            }
        except Exception as e:
            msg = str(e)[:400]; et = type(e).__name__
            return _fail(_classify_error(et, msg), msg,
                            phase='execute', started=started)

    executor.mode = 'snowflake'
    executor.close = _close
    executor.role = creds.get('role', '')
    executor.warehouse = creds.get('warehouse', '')
    return executor
