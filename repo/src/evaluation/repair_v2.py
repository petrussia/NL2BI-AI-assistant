"""repair_v2 — bounded repair for the top candidate.

Triggered by verifier_ranker_v2 when the chosen candidate is unsafe / fails
parse / fails to execute. Tries one targeted LLM repair using the original
schema and the executor's error message.

Public API:
  attempt_repair(question, ir, candidate, executor, gen, *, max_rounds=1) -> dict
"""
from __future__ import annotations

import re
import textwrap

from schema_ir_v2 import render_compact_schema
from dialect_utils_v2 import is_safe_select


def _extract_sql(text: str) -> str:
    text = (text or '').strip()
    text = re.sub(r"^```(?:sql)?", "", text, flags=re.I).strip()
    text = re.sub(r"```$", "", text).strip()
    m = re.search(r"(?is)(select\b.*)", text)
    if m: text = m.group(1).strip()
    text = text.split("\n\n")[0].strip()
    if ";" in text: text = text.split(";", 1)[0].strip()
    return text.rstrip(";") + ";"


def _repair_prompt(schema_text: str, question: str, bad_sql: str, error: str) -> str:
    return textwrap.dedent(f"""
    The following SQL did not produce a usable result for the question.
    Return a corrected SQLite SQL query that fixes the issue. Use only the
    given schema. Return SQL only, no markdown and no explanation.

    Schema:
    {schema_text}

    Question: {question}

    Original SQL:
    {bad_sql}

    Error: {error}

    Corrected SQL:
    """).strip()


def attempt_repair(question: str, ir, candidate: dict, executor, gen, *,
                    max_rounds: int = 1) -> dict:
    """Returns dict with: sql, safe, executable, rounds, repair_history."""
    history = []
    cur_sql = candidate.get('sql', '')
    cur_safe = candidate.get('safe', False)
    schema_text = render_compact_schema(ir, include_comments=False)
    executable = None; err = ''; rows = None
    if cur_safe:
        try: executable, rows, err_t, err_m = executor(cur_sql); err = f'{err_t}: {err_m}'.strip()
        except Exception as exc: executable = False; err = f'{type(exc).__name__}: {exc}'
    else:
        err = 'unsafe_or_parse_failed'

    rounds = 0
    while rounds < max_rounds and (not cur_safe or executable is False):
        prompt = _repair_prompt(schema_text, question, cur_sql, err)
        raw = gen(prompt, max_new=256)
        new_sql = _extract_sql(raw)
        new_safe, new_why = is_safe_select(new_sql, ir.dialect)
        history.append({
            'round': rounds + 1,
            'before_sql': cur_sql,
            'before_safe': cur_safe,
            'before_error': err,
            'after_sql': new_sql,
            'after_safe': new_safe,
            'safe_reason': new_why,
        })
        cur_sql = new_sql; cur_safe = new_safe
        if cur_safe:
            try:
                executable, rows, err_t, err_m = executor(cur_sql)
                err = f'{err_t}: {err_m}'.strip()
            except Exception as exc:
                executable = False; err = f'{type(exc).__name__}: {exc}'
        rounds += 1
    return {
        'sql': cur_sql, 'safe': cur_safe, 'executable': executable,
        'rounds': rounds, 'history': history, 'final_error': err if not executable else '',
    }
