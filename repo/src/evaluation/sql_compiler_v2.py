"""sql_compiler_v2 — deterministic compile of plan_schema_v5 plans to SQL.

Supported families (renders complete SQL deterministically):
  - count / aggregate / scalar measure
  - filter (WHERE with =, <, >, <=, >=, !=, in, like, between, is [not] null)
  - group-by + aggregates
  - having
  - distinct
  - top-k (ORDER BY + LIMIT)
  - simple multi-table joins via FK paths
  - set operations (UNION, UNION ALL, INTERSECT, EXCEPT) — recurses on other_plan

Unsupported (compiler emits "skeleton" — partial SQL with TODO markers — and
returns it as a guided hint for the synth LM to finalize):
  - nested subqueries (requires_nested=True)
  - window functions (requires_window=True)

Public API:
  compile_plan(plan, ir, dialect='sqlite') -> dict {
    sql, status: 'ok'|'skeleton'|'failed',
    families_used: [...],
    audit: {compiler_warnings, compiler_errors, columns_qualified, joins_emitted}
  }
"""
from __future__ import annotations
import re
from typing import Any


# ---------------- helpers ----------------

def _qid(name: str, dialect: str = 'sqlite') -> str:
    """Quote an identifier safely. Uses dialect-appropriate quotes."""
    name = (name or '').strip()
    if not name: return name
    # Already qualified or quoted
    if '"' in name or '`' in name: return name
    if dialect == 'mysql': return f'`{name}`'
    return f'"{name}"'


def _qtab_col(qualified: str, dialect: str = 'sqlite') -> str:
    """Quote 'table.column' safely. Pass-through for '*' and 'table.*'."""
    s = (qualified or '').strip()
    if s == '*' or s.endswith('.*'):
        if s == '*': return '*'
        t = s[:-2]
        return f'{_qid(t, dialect)}.*'
    if '.' in s:
        t, c = s.split('.', 1)
        return f'{_qid(t, dialect)}.{_qid(c, dialect)}'
    return _qid(s, dialect)


def _esc_string(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def _render_rhs(rhs, rhs_type: str | None) -> str:
    if rhs is None: return 'NULL'
    t = (rhs_type or '').lower()
    if t in ('int', 'float'):
        try: return str(int(rhs)) if t == 'int' else str(float(rhs))
        except Exception: return _esc_string(str(rhs))
    if t == 'date': return _esc_string(str(rhs))
    if t == 'column': return _qtab_col(str(rhs))
    if t in ('list_int', 'list_string', 'tuple'):
        if not isinstance(rhs, (list, tuple)):
            # Tolerate string forms like "1,2,3"
            rhs = [x.strip() for x in str(rhs).strip('()[] ').split(',') if x.strip()]
        if t == 'list_int':
            return '(' + ', '.join(str(int(x)) for x in rhs) + ')'
        return '(' + ', '.join(_esc_string(str(x)) for x in rhs) + ')'
    # Default: string
    return _esc_string(str(rhs))


def _render_time_grain(expr: str, grain: str, dialect: str = 'sqlite') -> str:
    qexpr = _qtab_col(expr, dialect)
    if dialect == 'sqlite':
        m = {'year': "%Y", 'month': "%Y-%m", 'day': "%Y-%m-%d",
             'week': "%Y-%W", 'quarter': None}
        fmt = m.get(grain)
        if fmt: return f"STRFTIME('{fmt}', {qexpr})"
        if grain == 'quarter':
            return f"((CAST(STRFTIME('%m', {qexpr}) AS INTEGER) + 2) / 3)"
        return qexpr
    return qexpr


def _render_measure(m: dict, dialect: str = 'sqlite') -> tuple[str, str]:
    agg = (m.get('agg') or 'none').lower()
    expr = m.get('expr') or '*'
    alias = m.get('alias')
    if agg == 'none':
        col = _qtab_col(expr, dialect)
        return col, (alias or '')
    if agg == 'count_distinct':
        col = _qtab_col(expr, dialect)
        sql = f'COUNT(DISTINCT {col})'
    elif agg == 'count':
        col = _qtab_col(expr, dialect) if expr != '*' else '*'
        sql = f'COUNT({col})'
    else:
        col = _qtab_col(expr, dialect)
        sql = f'{agg.upper()}({col})'
    out_alias = alias or f'{agg}_{re.sub(r"[^a-z0-9_]","_",(expr or "x").lower())}'
    return f'{sql} AS {_qid(out_alias, dialect)}', out_alias


def _render_dimension(d: dict, dialect: str = 'sqlite') -> tuple[str, str]:
    expr = d.get('expr') or ''
    grain = d.get('time_grain')
    alias = d.get('alias')
    if grain:
        col = _render_time_grain(expr, grain, dialect)
        out_alias = alias or f'{grain}_{re.sub(r"[^a-z0-9_]","_",expr.lower())}'
        return f'{col} AS {_qid(out_alias, dialect)}', out_alias
    col = _qtab_col(expr, dialect)
    if alias: return f'{col} AS {_qid(alias, dialect)}', alias
    return col, expr.split('.')[-1] if '.' in expr else expr


def _render_filter(f: dict, dialect: str = 'sqlite') -> str:
    expr = _qtab_col(f['expr'], dialect)
    op = (f.get('op') or '=').lower()
    rhs = f.get('rhs'); rhs_type = f.get('rhs_type')
    if op in ('is null', 'is not null'): return f'{expr} {op.upper()}'
    if op == 'between':
        if isinstance(rhs, (list, tuple)) and len(rhs) == 2:
            return f"{expr} BETWEEN {_render_rhs(rhs[0], rhs_type)} AND {_render_rhs(rhs[1], rhs_type)}"
        return f'{expr} = NULL /* malformed between */'
    if op in ('in', 'not in'):
        if rhs_type not in ('list_int', 'list_string', 'tuple'):
            rhs_type = 'list_string'
        return f'{expr} {op.upper()} {_render_rhs(rhs, rhs_type)}'
    if op in ('like', 'not like'):
        return f"{expr} {op.upper()} {_esc_string(str(rhs))}"
    return f'{expr} {op} {_render_rhs(rhs, rhs_type)}'


def _render_join_clause(edge: str, dialect: str = 'sqlite',
                         used_tables: set[str] | None = None) -> tuple[str, str | None, str | None]:
    """Edge format: 'tableA.colA -> tableB.colB'.

    Returns (join_sql, new_table_name_to_add_to_used, error_or_None).
    """
    m = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*->\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*$', edge)
    if not m: return ('', None, f'unparseable_edge:{edge!r}')
    a_t, a_c, b_t, b_c = m.groups()
    used = used_tables or set()
    # Pick the side that's NOT yet in FROM
    if a_t in used and b_t not in used:
        new_table = b_t
    elif b_t in used and a_t not in used:
        new_table = a_t
    elif a_t not in used and b_t not in used:
        new_table = b_t  # arbitrary; caller seeds first
    else:
        return ('', None, f'both_sides_used:{a_t},{b_t}')
    cond = f'{_qid(a_t, dialect)}.{_qid(a_c, dialect)} = {_qid(b_t, dialect)}.{_qid(b_c, dialect)}'
    return (f'INNER JOIN {_qid(new_table, dialect)} ON {cond}', new_table, None)


# ---------------- main compile ----------------

def compile_plan(plan: dict, ir, *, dialect: str = 'sqlite',
                  max_compile_depth: int = 2) -> dict:
    if not isinstance(plan, dict):
        return {'sql': '', 'status': 'failed', 'families_used': [],
                 'audit': {'compiler_errors': ['plan_not_dict'], 'compiler_warnings': []}}
    audit = {'compiler_errors': [], 'compiler_warnings': [],
              'columns_qualified': [], 'joins_emitted': []}
    families: list[str] = []

    # 1. Set operation: recurse
    sop = plan.get('set_operation')
    if sop and max_compile_depth > 0 and isinstance(sop.get('other_plan'), dict):
        left = compile_plan({**plan, 'set_operation': None}, ir, dialect=dialect,
                             max_compile_depth=max_compile_depth-1)
        right = compile_plan(sop['other_plan'], ir, dialect=dialect,
                              max_compile_depth=max_compile_depth-1)
        if left['status'] == 'ok' and right['status'] == 'ok':
            op = (sop.get('op') or 'union').upper().replace('_', ' ')
            sql = f'({left["sql"]}) {op} ({right["sql"]})'
            families = sorted(set(left['families_used'] + right['families_used']) | {'set_operation'})
            audit['compiler_warnings'].extend(left['audit']['compiler_warnings'])
            audit['compiler_warnings'].extend(right['audit']['compiler_warnings'])
            return {'sql': sql + ';', 'status': 'ok', 'families_used': families, 'audit': audit}
        # Fall through with left only as skeleton
        audit['compiler_warnings'].append('set_op_partial')

    # 2. Skeleton-only families
    if plan.get('requires_window'):
        families.append('window')
        skel = '/* TODO window fn (compiler skeleton) */ SELECT * FROM ' + \
               _qid((plan.get('join_anchor_nodes') or ['?'])[0], dialect)
        return {'sql': skel + ';', 'status': 'skeleton',
                 'families_used': families,
                 'audit': {'compiler_errors': [], 'compiler_warnings': ['unsupported:window']}}
    if plan.get('requires_nested'):
        families.append('nested')
        # Try a basic correlated subquery scaffold
        skel = '/* TODO nested (compiler skeleton) */ SELECT * FROM ' + \
               _qid((plan.get('join_anchor_nodes') or ['?'])[0], dialect)
        return {'sql': skel + ';', 'status': 'skeleton',
                 'families_used': families,
                 'audit': {'compiler_errors': [], 'compiler_warnings': ['unsupported:nested']}}

    # 3. Validate anchors
    anchors = plan.get('join_anchor_nodes') or []
    if not anchors:
        return {'sql': '', 'status': 'failed', 'families_used': [],
                 'audit': {'compiler_errors': ['no_join_anchor'], 'compiler_warnings': []}}
    table_set = {t.name for t in ir.tables}
    for a in anchors:
        if a.lower() not in table_set:
            return {'sql': '', 'status': 'failed', 'families_used': [],
                     'audit': {'compiler_errors': [f'unknown_anchor:{a}'], 'compiler_warnings': []}}

    used_tables: set[str] = {anchors[0].lower()}
    from_clause = _qid(anchors[0], dialect)
    join_clauses: list[str] = []

    # 4. JOINs from join_path_ids (each path is a list of edges)
    for path in (plan.get('join_path_ids') or []):
        for edge in path:
            join_sql, new_t, err = _render_join_clause(edge, dialect, used_tables)
            if err:
                audit['compiler_warnings'].append(err); continue
            if new_t:
                used_tables.add(new_t.lower())
                join_clauses.append(join_sql)
                audit['joins_emitted'].append(edge)

    # Add additional anchor tables that weren't in any join_path
    for a in anchors[1:]:
        if a.lower() not in used_tables:
            audit['compiler_warnings'].append(f'anchor_not_joined:{a}')
            join_clauses.append(f'INNER JOIN {_qid(a, dialect)} ON 1=1')
            used_tables.add(a.lower())

    if join_clauses: families.append('join')

    # 5. SELECT clause
    proj_parts: list[str] = []
    proj_aliases: list[str] = []
    for d in (plan.get('dimensions') or []):
        sql_part, alias = _render_dimension(d, dialect)
        proj_parts.append(sql_part); proj_aliases.append(alias)
    for m in (plan.get('measures') or []):
        sql_part, alias = _render_measure(m, dialect)
        proj_parts.append(sql_part); proj_aliases.append(alias)
    if not proj_parts:
        proj_parts = ['*']
    if any(d.get('time_grain') for d in (plan.get('dimensions') or [])):
        families.append('time_grain')
    if any((m.get('agg') or 'none').lower() != 'none' for m in (plan.get('measures') or [])):
        families.append('aggregate')
    if (plan.get('measures') or []) and (plan.get('dimensions') or []):
        families.append('group_by')

    distinct = bool(plan.get('distinct'))
    if distinct: families.append('distinct')

    # 6. WHERE
    where_parts = [_render_filter(f, dialect) for f in (plan.get('filters') or [])]
    if where_parts: families.append('filter')

    # 7. GROUP BY
    group_parts: list[str] = []
    has_agg_measure = any((m.get('agg') or 'none').lower() != 'none' for m in (plan.get('measures') or []))
    if has_agg_measure and (plan.get('dimensions') or []):
        for d in plan.get('dimensions'):
            if d.get('time_grain'):
                group_parts.append(_render_time_grain(d['expr'], d['time_grain'], dialect))
            else:
                group_parts.append(_qtab_col(d['expr'], dialect))

    # 8. HAVING
    having_parts: list[str] = []
    for h in (plan.get('having') or []):
        agg = (h.get('agg') or '').upper()
        expr = h.get('expr') or '*'
        col = _qtab_col(expr, dialect) if expr != '*' else '*'
        if agg == 'COUNT' and expr == '*': lhs = 'COUNT(*)'
        elif agg == 'COUNT_DISTINCT': lhs = f'COUNT(DISTINCT {col})'
        else: lhs = f'{agg}({col})' if agg else col
        having_parts.append(f"{lhs} {h.get('op','=')} {_render_rhs(h.get('rhs'), h.get('rhs_type'))}")
    if having_parts: families.append('having')

    # 9. ORDER BY
    order_parts: list[str] = []
    for o in (plan.get('ordering') or []):
        e = o.get('expr') or ''
        direction = (o.get('direction') or 'asc').upper()
        if e in proj_aliases:
            order_parts.append(f'{_qid(e, dialect)} {direction}')
        else:
            order_parts.append(f'{_qtab_col(e, dialect)} {direction}')

    # 10. LIMIT
    limit = plan.get('limit')
    if limit and order_parts: families.append('top_k')

    # ---- assemble ----
    sql_parts: list[str] = []
    sql_parts.append('SELECT ' + ('DISTINCT ' if distinct else '') + ', '.join(proj_parts))
    sql_parts.append(f'FROM {from_clause}')
    if join_clauses: sql_parts.append('\n'.join(join_clauses))
    if where_parts: sql_parts.append('WHERE ' + ' AND '.join(where_parts))
    if group_parts: sql_parts.append('GROUP BY ' + ', '.join(group_parts))
    if having_parts: sql_parts.append('HAVING ' + ' AND '.join(having_parts))
    if order_parts: sql_parts.append('ORDER BY ' + ', '.join(order_parts))
    if limit is not None:
        try: sql_parts.append(f'LIMIT {int(limit)}')
        except Exception: pass

    sql = '\n'.join(sql_parts) + ';'
    return {'sql': sql, 'status': 'ok',
             'families_used': sorted(set(families)) or ['simple'],
             'audit': audit}
