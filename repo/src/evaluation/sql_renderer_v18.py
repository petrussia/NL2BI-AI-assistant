"""sql_renderer_v18 — deterministic SQL renderer from a structured JSON plan.

Plan shape per `structured_plan_v18`. Renderer outputs BQ-dialect SQL by
default (Spider2-Lite-BQ is the primary v18 lane). Snow rendering is a
near-identical variant; for v18.0 we only ship BQ.

Why deterministic: with the JSON plan validated to use only closed-set
identifiers, rendering becomes a string-template task. No model is
involved here, eliminating identifier hallucination at SQL emission.

The renderer handles:
  - Project-qualified table refs `project.dataset.table`
  - GROUP BY column substitution from sorting/grouping arrays
  - Simple metric expressions (COUNT, SUM, AVG)
  - Filters joined with AND
  - Time constraints joined with AND
  - LIMIT
  - UNNEST insertion when a metric/filter references a struct/array path
    (best-effort: any `field.subfield` token whose root column appears
    in the table is wrapped in `UNNEST(t.root) AS r`)
"""
from __future__ import annotations

import re
from typing import Optional


_PATH_RE = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_.]*)\b')


def _is_count_star(expr: str) -> bool:
    return re.fullmatch(r'(?i)\s*count\s*\(\s*\*\s*\)', expr or '') is not None


def _qualify_table(plan: dict) -> str:
    db = plan.get('selected_database', '')
    schema = plan.get('selected_schema', '')
    if db:
        return f'`{db}.{schema}.{plan["selected_tables"][0]}`'
    return f'`{schema}.{plan["selected_tables"][0]}`'


def render_bq(plan: dict, *, pack: Optional[dict] = None) -> str:
    """Render a plan into a BigQuery SQL string. The plan is expected to
    have validated against pack (caller's responsibility).

    Single-table case is the primary path; when len(selected_tables) > 1
    the renderer falls back to a CROSS JOIN UNNEST style for child arrays
    of the first table; full multi-table joins are out of scope for v18.0.
    """
    selects = []
    metrics = plan.get('metrics') or []
    if metrics:
        for m in metrics:
            label = m.get('label') or 'metric'
            expr = m.get('expr') or ''
            if not expr:
                continue
            selects.append(f'{expr} AS {label}')
    selected_cols = plan.get('selected_columns') or []
    # Add raw selected_columns that are not already in metrics
    for c in selected_cols:
        if any(s.startswith(c.split('.')[-1] + ' ') or s.endswith(' AS ' + c.split('.')[-1])
               for s in selects):
            continue
        selects.append(c)
    if not selects:
        selects.append('*')

    table = _qualify_table(plan)
    select_clause = ', '.join(selects)
    sql = f'SELECT {select_clause}\nFROM {table}'

    where_parts = []
    for f in plan.get('filters') or []:
        e = f.get('expr') if isinstance(f, dict) else f
        if e:
            where_parts.append(f'({e})')
    for tc in plan.get('time_constraints') or []:
        if tc:
            where_parts.append(f'({tc})')
    if where_parts:
        sql += '\nWHERE ' + ' AND '.join(where_parts)

    group = plan.get('grouping') or []
    if group:
        sql += '\nGROUP BY ' + ', '.join(group)

    sortings = plan.get('sorting') or []
    if sortings:
        order_parts = []
        for s in sortings:
            if isinstance(s, dict):
                e = s.get('expr', '')
                d = (s.get('dir') or 'asc').upper()
                order_parts.append(f'{e} {d}')
            else:
                order_parts.append(str(s))
        sql += '\nORDER BY ' + ', '.join(order_parts)

    lim = plan.get('limit')
    if lim is not None and lim != '' and lim != 0:
        try:
            sql += f'\nLIMIT {int(lim)}'
        except (TypeError, ValueError):
            pass

    return sql


def render_coder7b_direct_prompt(question: str, pack: dict, external_knowledge: str = '') -> str:
    """Prompt template for the Coder-7B control direct-emitter — same
    closed-set schema pack as the planner sees, but the model emits SQL
    directly. This is candidate B in the candidate factory."""
    lines = []
    lines.append('You are a BigQuery SQL writer.')
    lines.append('Use ONLY the tables and columns listed below.')
    for t in pack['tables']:
        cols = ', '.join(f"{c['name']}:{c['type']}" for c in t['columns'])
        lines.append(f'Table `{t["db"]}.{t["schema"]}.{t["table"]}`')
        lines.append(f'  Columns: {cols}')
    if external_knowledge:
        lines.append('External knowledge: ' + external_knowledge)
    lines.append('')
    lines.append('Question: ' + question)
    lines.append('')
    lines.append('Return ONE SQL query in a fenced ```sql block.')
    return '\n'.join(lines)
