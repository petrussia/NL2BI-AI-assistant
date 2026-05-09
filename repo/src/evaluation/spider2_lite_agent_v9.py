"""spider2_lite_agent_v9 — v9 lane-aware Spider2-Lite orchestrator.

Differences from v8:
  - SF lane uses `spider2_snow_agent_v9.run_snow_agent_step_v9`
    (dialect normalizer fixes BQ-isms before EXPLAIN).
  - BQ lane normalizes SQL with `bigquery_dialect_normalizer_v9` after
    generation (fixes `DATE("YYYYMMDD")` → typed `DATE 'YYYY-MM-DD'`).
  - SQLite lane uses `sqlite_lane_resolver_v9.resolve_sqlite_db` for
    case-insensitive db path resolution; result still flagged
    `non_comparable=True`.
"""
from __future__ import annotations

from typing import Callable

from spider2_lite_router_v8 import classify
from bigquery_dialect_normalizer_v9 import normalize as _bq_norm, has_snowflake_isms


def run_lite_step_dispatch_v9(item: dict, *, gen: Callable,
                                  bq_executor: Callable | None = None,
                                  sf_executor: Callable | None = None,
                                  sqlite_executor: Callable | None = None,
                                  bq_idx_loader: Callable | None = None,
                                  sf_idx_loader: Callable | None = None,
                                  max_repair_rounds: int = 1,
                                  max_rows: int = 1000) -> dict:
    route = classify(item)
    lane = route['lane']
    iid = route['instance_id']; db = route['db']; question = route['question']

    if lane == 'A_bq':
        from spider2_agent_v8 import run_bq_agent_step
        if bq_idx_loader is None or bq_executor is None:
            return {**route, 'mode': 'blocked_no_bq_setup',
                     'parses': False, 'executable': False,
                     'error_type': 'missing_bq_executor', 'sql': '',
                     'wall_time_s': 0.0, 'candidate_count': 0}
        idx = bq_idx_loader(db)
        if idx is None:
            return {**route, 'mode': 'blocked_no_schema',
                     'parses': False, 'executable': False,
                     'error_type': 'schema_missing', 'sql': '',
                     'wall_time_s': 0.0, 'candidate_count': 0}

        # Wrap bq_executor to apply BQ dialect normalizer per call
        def _bq_executor_wrapped(sql, *, dry_run=False, **kw):
            n = _bq_norm(sql)
            sql_use = n.sql if n.applied else sql
            res = bq_executor(sql_use, dry_run=dry_run, **kw)
            res['dialect_fix'] = ({'applied_fixes': n.applied}
                                       if n.applied else None)
            res['final_sql'] = sql_use
            return res

        res = run_bq_agent_step(question, idx, gen=gen,
                                  bq_executor=_bq_executor_wrapped,
                                  max_repair_rounds=max_repair_rounds,
                                  max_rows_exec=max_rows)
        return {**route, **res}

    if lane == 'A_sf':
        from spider2_snow_agent_v9 import run_snow_agent_step_v9
        if sf_idx_loader is None or sf_executor is None:
            return {**route, 'mode': 'blocked_no_sf_setup',
                     'parses': False, 'executable': False,
                     'error_type': 'missing_sf_executor', 'sql': '',
                     'wall_time_s': 0.0, 'candidate_count': 0}
        idx = sf_idx_loader(db)
        if idx is None:
            return {**route, 'mode': 'blocked_no_schema',
                     'parses': False, 'executable': False,
                     'error_type': 'schema_missing', 'sql': '',
                     'wall_time_s': 0.0, 'candidate_count': 0}
        res = run_snow_agent_step_v9(question, idx, gen=gen,
                                          sf_executor=sf_executor,
                                          max_repair_rounds=max_repair_rounds,
                                          max_rows_exec=max_rows)
        return {**route, **res}

    # SQLite stub — non-comparable
    if sqlite_executor is None:
        return {**route, 'mode': 'blocked_no_sqlite_setup',
                 'parses': False, 'executable': False,
                 'error_type': 'missing_sqlite_executor', 'sql': '',
                 'wall_time_s': 0.0, 'candidate_count': 0}
    prompt = (f"You are answering a SQLite question. Generate a single SELECT.\n"
                f"DATABASE: {db}\nQUESTION: {question}\n"
                "Reply with SQL inside ```sql ... ``` fence.")
    try:
        from spider2_agent_v7 import _extract_sql
        raw = gen(prompt, max_new=600)
        sql = _extract_sql(raw) or ''
    except Exception:
        sql = ''
    res = sqlite_executor(sql, dry_run=False, max_rows_override=max_rows)
    return {**route,
             'sql': sql, 'final_source': 'C0_direct',
             'parses': bool(res.get('ok')),
             'executable': bool(res.get('ok')),
             'rows_count': res.get('row_count', 0),
             'error_type': res.get('error_type', ''),
             'error_message': res.get('error_message', ''),
             'mode': 'sqlite_stub_non_comparable',
             'non_comparable': True,
             'wall_time_s': (res.get('elapsed_ms') or 0) / 1000.0,
             'candidate_count': 1,
             'candidates_summary': [{'source': 'C0_direct',
                                       'parses': bool(res.get('ok')),
                                       'executable': bool(res.get('ok')),
                                       'sql_chars': len(sql),
                                       'error_type': res.get('error_type', '')}]}
