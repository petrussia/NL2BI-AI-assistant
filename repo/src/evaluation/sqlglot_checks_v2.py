"""sqlglot_checks_v2 — AST-level checks, structural diff and validity scoring.

Every output is a small, JSON-serialisable dict so verifier_ranker_v2
can ingest it without re-parsing SQL.
"""
from __future__ import annotations

from typing import Iterable

import sqlglot
from sqlglot import exp

from dialect_utils_v2 import is_safe_select, referenced_tables, referenced_columns


def parse_or_none(sql: str, dialect: str = 'sqlite'):
    try:
        return sqlglot.parse_one(sql, read=dialect)
    except Exception:
        return None


def ast_validity(sql: str, dialect: str = 'sqlite') -> dict:
    tree = parse_or_none(sql, dialect)
    return {
        'parses': tree is not None,
        'safe_select': is_safe_select(sql, dialect)[0],
    }


def schema_validity(sql: str, ir, dialect: str | None = None) -> dict:
    """Check whether the SQL only mentions tables/columns that exist in IR.

    `ir` is a SchemaIR (schema_ir_v2.SchemaIR). Returns counts and the
    actual unknown identifiers — useful for the error taxonomy.
    """
    d = dialect or getattr(ir, 'dialect', 'sqlite')
    used_tables = set(referenced_tables(sql, d))
    used_cols = referenced_columns(sql, d)
    table_set = {t.name for t in ir.tables}
    unknown_tables = sorted(used_tables - table_set)

    col_index: dict[str, set[str]] = {t.name: {c.name for c in t.columns} for t in ir.tables}
    unknown_cols: list[str] = []
    ambiguous_cols: list[str] = []
    for tab, col in used_cols:
        if tab and tab in col_index:
            if col not in col_index[tab]: unknown_cols.append(f'{tab}.{col}')
        elif tab and tab not in table_set:
            # alias / unknown table — defer to ambiguity
            ambiguous_cols.append(f'{tab}.{col}')
        else:
            # bare column — find which tables expose it
            owners = [t for t, cs in col_index.items() if col in cs]
            if not owners: unknown_cols.append(col)
            elif len(owners) > 1: ambiguous_cols.append(col)
    return {
        'used_tables': sorted(used_tables),
        'unknown_tables': unknown_tables,
        'unknown_columns': sorted(set(unknown_cols)),
        'ambiguous_columns': sorted(set(ambiguous_cols)),
        'all_known': not unknown_tables and not unknown_cols,
    }


def structural_features(sql: str, dialect: str = 'sqlite') -> dict:
    tree = parse_or_none(sql, dialect)
    if tree is None:
        return {'parses': False}
    sub = list(tree.find_all(exp.Subquery))
    grp = list(tree.find_all(exp.Group))
    hav = list(tree.find_all(exp.Having))
    win = list(tree.find_all(exp.Window))
    union = list(tree.find_all(exp.Union))
    intersect = list(tree.find_all(exp.Intersect))
    except_ = list(tree.find_all(exp.Except))
    distinct = bool(list(tree.find_all(exp.Distinct)))
    joins = list(tree.find_all(exp.Join))
    aggs = sum(1 for f in tree.find_all(exp.AggFunc))
    order = list(tree.find_all(exp.Order))
    limit = list(tree.find_all(exp.Limit))
    return {
        'parses': True,
        'has_subquery': bool(sub), 'subquery_count': len(sub),
        'has_group_by': bool(grp), 'has_having': bool(hav),
        'has_window': bool(win),
        'has_union': bool(union), 'has_intersect': bool(intersect),
        'has_except': bool(except_),
        'has_distinct': distinct,
        'join_count': len(joins),
        'aggregate_count': aggs,
        'has_order_by': bool(order),
        'has_limit': bool(limit),
    }


def feature_distance(a: dict, b: dict) -> int:
    """Cheap structural distance: count features where the two dicts differ."""
    keys = ('has_subquery','has_group_by','has_having','has_window',
            'has_union','has_intersect','has_except','has_distinct',
            'has_order_by','has_limit')
    d = 0
    for k in keys:
        if a.get(k) != b.get(k): d += 1
    if abs((a.get('join_count') or 0) - (b.get('join_count') or 0)) > 0: d += 1
    if abs((a.get('aggregate_count') or 0) - (b.get('aggregate_count') or 0)) > 0: d += 1
    return d


def select_columns(sql: str, dialect: str = 'sqlite') -> list[str]:
    """Surface labels of the SELECT projection (alias if present, else expr)."""
    tree = parse_or_none(sql, dialect)
    if tree is None: return []
    out: list[str] = []
    sel = tree.find(exp.Select) if not isinstance(tree, exp.Select) else tree
    if sel is None: return []
    for proj in sel.expressions:
        if isinstance(proj, exp.Alias):
            out.append((proj.alias or '').lower())
        elif isinstance(proj, exp.Column):
            out.append(proj.name.lower())
        else:
            out.append(proj.sql().lower())
    return out
