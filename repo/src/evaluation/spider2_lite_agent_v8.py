"""spider2_lite_agent_v8 — lane-aware Spider2-Lite orchestrator.

Per-item:
  1. Route via spider2_lite_router_v8.classify
  2. Build appropriate schema index (BQ / SF / SQLite)
  3. Dispatch to lane-specific agent step
  4. Return uniform result envelope with `lane` and `non_comparable` flags

The runner owns: dataset iteration, schema/db caching, output writes,
and aggregate metrics. This module only does per-item dispatch.
"""
from __future__ import annotations

from typing import Callable

from spider2_lite_router_v8 import classify


def run_lite_step_dispatch(item: dict, *, gen: Callable,
                              bq_executor: Callable | None = None,
                              sf_executor: Callable | None = None,
                              sqlite_executor: Callable | None = None,
                              bq_idx_loader: Callable | None = None,
                              sf_idx_loader: Callable | None = None,
                              max_repair_rounds: int = 1,
                              max_rows: int = 1000) -> dict:
    """Returns dict with 'lane', 'non_comparable', and lane-specific
    result fields (parse, executable, sql, ...)."""
    route = classify(item)
    lane = route['lane']
    iid = route['instance_id']
    db = route['db']
    question = route['question']

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
        res = run_bq_agent_step(question, idx, gen=gen,
                                  bq_executor=bq_executor,
                                  max_repair_rounds=max_repair_rounds,
                                  max_rows_exec=max_rows)
        return {**route, **res}

    if lane == 'A_sf':
        from spider2_snow_agent_v8 import run_snow_agent_step
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
        res = run_snow_agent_step(question, idx, gen=gen,
                                    sf_executor=sf_executor,
                                    max_repair_rounds=max_repair_rounds,
                                    max_rows_exec=max_rows)
        return {**route, **res}

    # SQLite stub — non-comparable.
    if sqlite_executor is None:
        return {**route, 'mode': 'blocked_no_sqlite_setup',
                 'parses': False, 'executable': False,
                 'error_type': 'missing_sqlite_executor', 'sql': '',
                 'wall_time_s': 0.0, 'candidate_count': 0}
    # SQLite path: simplest — single-shot direct prompt + parse.
    from spider2_sf_prompting_v8 import direct_prompt as _sf_direct  # reuse minimal
    # Lightweight prompt (no schema index — just question + db name hint):
    prompt = (f"You are answering a SQLite question. Generate a single SELECT.\n"
                f"DATABASE: {db}\nQUESTION: {question}\n"
                "Reply with SQL inside ```sql ... ``` fence.")
    try:
        from spider2_agent_v7 import _extract_sql
        raw = gen(prompt, max_new=600)
        sql = _extract_sql(raw) or ''
    except Exception as exc:
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
