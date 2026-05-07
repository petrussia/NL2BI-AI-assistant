"""spider2_snow_repair_v8 — bounded repair loop for Snowflake errors.

Given a broken SQL + Snowflake error message, ask the model to produce a
fix. We re-verify via the SF executor's dry_run (EXPLAIN). Bounded by
`max_rounds` and stops on first dry-run-pass.

Mirrors `spider2_bq_repair_v8` but uses SF prompts.
"""
from __future__ import annotations

from typing import Callable

from spider2_agent_v7 import _extract_sql
from spider2_sf_prompting_v8 import repair_prompt


def attempt_repair(question: str, schema_text: str,
                     broken_sql: str, error_message: str,
                     *, gen: Callable, sf_executor: Callable,
                     max_rounds: int = 2,
                     max_new: int = 700) -> dict:
    """Returns {'sql': str, 'rounds': int, 'success': bool, 'trace': [...]}."""
    cur_sql = (broken_sql or '').strip()
    cur_err = error_message or ''
    trace: list[dict] = []
    rounds = 0
    while rounds < max_rounds:
        rounds += 1
        prompt = repair_prompt(question, schema_text, cur_sql, cur_err)
        try:
            raw = gen(prompt, max_new=max_new)
        except Exception as exc:
            trace.append({'round': rounds, 'gen_error': type(exc).__name__})
            break
        new_sql = _extract_sql(raw) or ''
        if not new_sql or new_sql.strip() == cur_sql.strip():
            trace.append({'round': rounds, 'reason': 'empty_or_unchanged'})
            break
        try:
            dry = sf_executor(new_sql, dry_run=True, dialect='snowflake')
        except Exception as exc:
            trace.append({'round': rounds, 'exec_error': type(exc).__name__,
                            'sql_chars': len(new_sql)})
            cur_sql = new_sql
            continue
        trace.append({'round': rounds, 'dry_ok': bool(dry.get('ok')),
                        'error_short': (dry.get('error_message') or '')[:120]})
        if dry.get('ok'):
            return {'sql': new_sql, 'rounds': rounds, 'success': True,
                     'trace': trace}
        cur_sql = new_sql
        cur_err = dry.get('error_message') or cur_err
    return {'sql': cur_sql, 'rounds': rounds, 'success': False, 'trace': trace}
