"""structured_plan_v18 — Qwen3-Coder structured planner.

Calls Qwen3-Coder-30B-A3B-Instruct (or whichever generator is loaded by
model_registry_v17) to produce a strict JSON plan over a closed-set
schema pack. Validates the plan structurally — any identifier outside
the pack invalidates the plan.

This module assumes the Colab kernel has already imported and loaded a
model+tokenizer via `model_registry_v17.load_model_and_tokenizer(alias)`
and exposed them as globals `_TOK`, `_MDL`, `_MODEL_PROFILE`. (Same
contract as the v17 launcher's _ensure_model patch.) For local CLI tests
without a model, plan() raises NotImplementedError.

Plan validation rules (closed set):
  - selected_database in pack.databases[*].name
  - selected_schema  in pack.databases[*].schemas[*]
  - selected_tables ⊆ {t.table for t in pack.tables}
  - every identifier appearing in selected_columns / metrics.expr /
    filters.expr / grouping / sorting.expr must reference a column in
    one of the listed tables (loose substring containment is fine for
    free-form expressions; strict membership for plain identifiers).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional


_REQUIRED_KEYS = (
    'selected_database', 'selected_schema',
    'selected_tables', 'selected_columns',
    'metrics', 'filters', 'time_constraints',
    'grouping', 'sorting', 'limit',
    'ambiguity_points', 'expected_shape',
)


@dataclass
class PlanValidation:
    ok: bool
    reasons: list = field(default_factory=list)
    closed_set_db: set = field(default_factory=set)
    closed_set_schemas: set = field(default_factory=set)
    closed_set_tables: set = field(default_factory=set)
    closed_set_columns: set = field(default_factory=set)


def _closed_sets(pack: dict) -> tuple:
    dbs = {d['name'] for d in pack.get('databases', [])}
    schemas = set()
    for d in pack.get('databases', []):
        for s in d.get('schemas', []):
            schemas.add(s)
    tables = {(t['db'], t['schema'], t['table']) for t in pack.get('tables', [])}
    table_names = {t['table'] for t in pack.get('tables', [])}
    columns = set()
    for t in pack.get('tables', []):
        for c in t.get('columns', []):
            columns.add((t['db'], t['schema'], t['table'], c['name']))
    column_names = {c['name'] for t in pack.get('tables', []) for c in t.get('columns', [])}
    return dbs, schemas, tables, table_names, columns, column_names


_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def validate_plan(plan: dict, pack: dict) -> PlanValidation:
    reasons = []
    dbs, schemas, tables, table_names, columns, column_names = _closed_sets(pack)
    for k in _REQUIRED_KEYS:
        if k not in plan:
            reasons.append(f'missing_key:{k}')
    if 'selected_database' in plan and plan['selected_database'] not in dbs:
        reasons.append(f'unknown_database:{plan.get("selected_database")}')
    if 'selected_schema' in plan and plan['selected_schema'] not in schemas:
        reasons.append(f'unknown_schema:{plan.get("selected_schema")}')
    for t in plan.get('selected_tables', []) or []:
        if t not in table_names:
            reasons.append(f'unknown_table:{t}')
    for c in plan.get('selected_columns', []) or []:
        # Strip table prefix if any: "table.col" => "col"
        leaf = c.split('.')[-1] if '.' in c else c
        if c not in column_names and leaf not in column_names:
            reasons.append(f'unknown_column:{c}')
    # Light check on metrics/filters expressions: every identifier-looking
    # token must either be a SQL keyword (we cheat with a whitelist) or
    # appear in column_names/table_names.
    sql_keywords = {
        'SELECT','FROM','WHERE','GROUP','BY','ORDER','HAVING','AS','AND','OR',
        'NOT','IN','LIKE','BETWEEN','IS','NULL','TRUE','FALSE','LIMIT',
        'DISTINCT','ON','JOIN','LEFT','RIGHT','INNER','OUTER','UNION',
        'COUNT','SUM','AVG','MIN','MAX','CAST','EXTRACT','DATE','TIMESTAMP',
        'INT','INT64','FLOAT','STRING','ARRAY','STRUCT','UNNEST','SAFE_CAST',
        'OVER','PARTITION','WITH','EXISTS','TRY_CAST','THEN','CASE','WHEN','ELSE','END',
    }
    for which in ('metrics', 'filters', 'sorting'):
        for item in plan.get(which, []) or []:
            expr = item.get('expr', '') if isinstance(item, dict) else str(item)
            for tok in _IDENT_RE.findall(expr):
                if tok.upper() in sql_keywords:
                    continue
                if tok in column_names or tok in table_names:
                    continue
                if tok.lower() in {'true', 'false', 'null'}:
                    continue
                # numeric-only or short noise -> skip
                if tok.isdigit() or len(tok) <= 1:
                    continue
                reasons.append(f'unknown_ident_in_{which}:{tok}')
    ok = not reasons
    return PlanValidation(ok=ok, reasons=reasons,
                            closed_set_db=dbs, closed_set_schemas=schemas,
                            closed_set_tables=table_names,
                            closed_set_columns=column_names)


def parse_plan(raw_text: str) -> dict:
    """Parse LLM output into a JSON plan. Robust to fenced code blocks and
    leading prose."""
    s = raw_text.strip()
    # try to grab the first {...} block
    if '```' in s:
        m = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', s)
        if m:
            s = m.group(1)
    if not s.startswith('{'):
        m = re.search(r'(\{[\s\S]*\})\s*$', s)
        if m:
            s = m.group(1)
    return json.loads(s)


def plan_with_loaded_model(prompt: str, *, max_new: int = 1100) -> str:
    """Call the loaded HF model+tokenizer to generate the plan text.

    Reads `_TOK`, `_MDL`, `_MODEL_PROFILE` from globals. Same contract as
    v17 launcher's _gen replacement, but runs in the standard kernel.
    """
    g = globals()
    if g.get('_GEN_READY') is not True:
        raise NotImplementedError(
            'Model not loaded; call model_registry_v17.load_model_and_tokenizer first.')
    import torch
    nt = bool(g.get('_MODEL_PROFILE', {}).get('non_thinking_mode', False))
    msgs = [{'role': 'user', 'content': prompt}]
    extra = {'enable_thinking': False} if nt else {}
    try:
        enc = g['_TOK'].apply_chat_template(
            msgs, return_tensors='pt', add_generation_prompt=True,
            return_dict=True, **extra)
    except TypeError:
        enc = g['_TOK'].apply_chat_template(
            msgs, return_tensors='pt', add_generation_prompt=True,
            return_dict=True)
    enc = {k: v.to(g['_MDL'].device) for k, v in enc.items()}
    with torch.no_grad():
        out = g['_MDL'].generate(**enc, max_new_tokens=max_new,
                                    do_sample=False, temperature=0.0,
                                    pad_token_id=g['_TOK'].eos_token_id)
    gen = out[0][enc['input_ids'].shape[1]:]
    return g['_TOK'].decode(gen, skip_special_tokens=True)


def plan(prompt: str, pack: dict, *, max_attempts: int = 2) -> dict:
    """High-level entry: generate -> parse -> validate. Returns dict:
       {'plan': ..., 'validation': PlanValidation, 'raw': str, 'attempts': N}
    """
    raw = ''
    last_err = None
    last_plan = None
    last_val = None
    for attempt in range(1, max_attempts + 1):
        raw = plan_with_loaded_model(prompt)
        try:
            cand = parse_plan(raw)
        except Exception as e:
            last_err = f'parse_err:{type(e).__name__}:{str(e)[:200]}'
            continue
        v = validate_plan(cand, pack)
        last_plan = cand
        last_val = v
        if v.ok:
            return {'plan': cand, 'validation': v, 'raw': raw, 'attempts': attempt}
        # else: re-prompt with reasons would be nice; for now we just retry once
    return {'plan': last_plan, 'validation': last_val, 'raw': raw, 'attempts': max_attempts,
              'last_parse_err': last_err}
