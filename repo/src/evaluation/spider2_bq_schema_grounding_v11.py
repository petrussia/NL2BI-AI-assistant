"""spider2_bq_schema_grounding_v11 — strict schema validator for BigQuery.

Mirrors `spider2_snow_schema_grounding_v11` but uses BigQuery dialect
in sqlglot and supports `project.dataset.table` 3-part identifiers.

For each parsed BQ SQL:
  - Extract referenced tables (catalog/db/dataset/table).
  - Extract referenced columns + their qualifier (table alias).
  - Resolve aliases via the FROM/JOIN tree if available.
  - Compare against the catalog: any unknown table/column is reported
    with Levenshtein nearest-match suggestions.

This is what gates BQ live-execute. SQL with unknown identifiers is
classified `schema_invalid` and goes to schema-aware repair instead of
burning BQ bytes-billed on a doomed query.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from spider2_bq_catalog_v11 import BqCatalog


@dataclass
class BqValidationResult:
    schema_valid: bool = False
    referenced_tables: list = field(default_factory=list)
    referenced_columns: list = field(default_factory=list)
    unknown_tables: list = field(default_factory=list)
    unknown_columns: list = field(default_factory=list)
    suggestions: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)


def _levenshtein(a: str, b: str) -> int:
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    a, b = a.lower(), b.lower()
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(cur[j-1] + 1, prev[j] + 1,
                              prev[j-1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _suggest_close(needle: str, pool: list[str], *,
                       max_d: int = 3, top_k: int = 5) -> list[str]:
    sc = []
    for h in pool:
        d = _levenshtein(needle, h)
        if d <= max_d: sc.append((d, h))
    sc.sort()
    return [h for _, h in sc[:top_k]]


def _build_alias_map_sqlglot(tree) -> dict[str, str]:
    """alias_lower -> table_name_upper. Best-effort with sqlglot."""
    try:
        from sqlglot import exp
    except ImportError:
        return {}
    alias_map: dict[str, str] = {}
    try:
        for t in tree.find_all(exp.Table):
            tbl = (t.name or '').upper()
            if not tbl: continue
            alias_node = t.args.get('alias')
            alias = alias_node.alias if alias_node and hasattr(alias_node, 'alias') else None
            alias_str = (alias.name if alias and hasattr(alias, 'name') else (alias_node.name if alias_node else None))
            if alias_str:
                alias_map[alias_str.lower()] = tbl
            # also accept the table itself as its own alias
            alias_map[tbl.lower()] = tbl
    except Exception:
        pass
    return alias_map


def validate_sql(sql: str, *, catalog: BqCatalog,
                    db: str,
                    selected_table_keys: list[str] | None = None) -> BqValidationResult:
    res = BqValidationResult()
    if not sql or not sql.strip():
        res.notes.append('empty_sql')
        return res

    available_tables = {t.table.upper(): t for t in catalog.all_tables(db.upper())}
    fq_to_table = {t.fq_name.upper(): t for t in catalog.all_tables(db.upper())}
    if not available_tables:
        res.notes.append('catalog_empty_for_db')

    try:
        import sqlglot
        from sqlglot import exp
    except ImportError:
        res.notes.append('sqlglot_unavailable')
        res.schema_valid = False
        return res

    try:
        tree = sqlglot.parse_one(sql, read='bigquery')
    except Exception as exc:
        res.notes.append(f'sqlglot_parse_failed:{type(exc).__name__}')
        # Cannot determine schema validity — gate as invalid
        res.schema_valid = False
        return res

    # Tables
    for t in tree.find_all(exp.Table):
        try:
            cat = (t.args.get('catalog') and t.args['catalog'].name) or ''
            ds = (t.args.get('db') and t.args['db'].name) or ''
            tbl = t.name
            ident = '.'.join(p for p in [cat, ds, tbl] if p)
            res.referenced_tables.append({'raw': ident, 'project': cat,
                                              'dataset': ds, 'table': tbl})
            tbl_u = (tbl or '').upper()
            if not tbl_u: continue
            # Match by fq if 3-part, else by table name only
            if cat and ds:
                fq = f'{cat}.{ds}.{tbl}'
                if fq in fq_to_table: continue
            if tbl_u in available_tables: continue
            sugg = _suggest_close(tbl_u, list(available_tables.keys()))
            res.unknown_tables.append({'raw': ident, 'table': tbl_u,
                                           'suggestions': sugg})
            res.suggestions[ident or tbl_u] = sugg
        except Exception:
            continue

    # Columns
    alias_map = _build_alias_map_sqlglot(tree)
    selected_set = ({k.split('.')[-1].upper() for k in (selected_table_keys or [])}
                       or set(available_tables.keys()))
    col_by_table = {}
    for tbl_u, t in available_tables.items():
        col_by_table[tbl_u] = {c.name.upper() for c in t.columns}

    for c in tree.find_all(exp.Column):
        try:
            cname = (c.name or '').upper()
            if not cname: continue
            qual = (c.args.get('table') and c.args['table'].name) or ''
            qual_u = qual.upper()
            res.referenced_columns.append({'raw': c.sql(dialect='bigquery'),
                                                'qual': qual_u, 'col': cname})
            # Resolve alias if present
            tbls_to_check = []
            if qual_u:
                resolved = alias_map.get(qual_u.lower(), qual_u)
                tbls_to_check = [resolved]
            else:
                tbls_to_check = list(selected_set)
            found = any(cname in col_by_table.get(t, set()) for t in tbls_to_check)
            if not found:
                pool = []
                for tbl_u, cols in col_by_table.items():
                    for cc in cols:
                        pool.append(f'{tbl_u}.{cc}')
                sugg = _suggest_close(cname, pool, max_d=2)
                res.unknown_columns.append({'col': cname, 'qual': qual_u,
                                                'suggestions': sugg})
                res.suggestions[c.sql(dialect='bigquery')] = sugg
        except Exception:
            continue

    res.schema_valid = (not res.unknown_tables) and (not res.unknown_columns)
    return res


def render_validation_for_repair(res: BqValidationResult, *,
                                       max_lines: int = 10) -> str:
    lines = []
    if res.unknown_tables:
        lines.append('UNKNOWN_TABLES (replace with one of suggested):')
        for ent in res.unknown_tables[:max_lines]:
            lines.append(f"  - `{ent['raw']}` (parsed table={ent['table']})  "
                          f"suggestions={ent['suggestions']}")
    if res.unknown_columns:
        lines.append('UNKNOWN_COLUMNS (replace with one of suggested):')
        for ent in res.unknown_columns[:max_lines]:
            lines.append(f"  - {ent['col']} (qual={ent['qual'] or '-'})  "
                          f"suggestions={ent['suggestions']}")
    if not lines: lines.append('OK: all referenced identifiers found.')
    return '\n'.join(lines)
