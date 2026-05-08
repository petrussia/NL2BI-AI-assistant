"""spider2_snow_schema_grounding_v11 — strict schema validator + nearest matches.

Given generated SQL and the catalog, produces a structured `validate_sql`
result with:
  - referenced_tables: parsed from SQL
  - referenced_columns: parsed from SQL where possible
  - unknown_tables: not in catalog
  - unknown_columns: not in any selected table
  - suggestions: nearest exact identifiers from catalog (Levenshtein)
  - schema_valid: bool — gate before execution

Repair hints:
  - For unknown table T → list candidate tables from current DB whose
    Levenshtein distance to T is <= 2 OR whose lowercase is the same.
  - For unknown column C → search across selected tables only; if not
    found, search across all tables in current DB and report the table
    that hosts the closest match.

Uses sqlglot to parse identifiers; falls back to a regex extractor if
sqlglot fails.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from spider2_snow_catalog_v11 import Catalog, Table


@dataclass
class ValidationResult:
    schema_valid: bool = False
    referenced_tables: list = field(default_factory=list)
    referenced_columns: list = field(default_factory=list)
    unknown_tables: list = field(default_factory=list)
    unknown_columns: list = field(default_factory=list)
    suggestions: dict = field(default_factory=dict)  # name -> list of close matches
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


def _suggest_close(needle: str, haystack: list[str], *,
                       max_d: int = 3, top_k: int = 5) -> list[str]:
    if not haystack: return []
    scored = []
    for h in haystack:
        d = _levenshtein(needle, h)
        if d <= max_d:
            scored.append((d, h))
    scored.sort()
    return [h for _, h in scored[:top_k]]


_TABLE_REF_RE = re.compile(
    r'\bFROM\s+([A-Za-z_"][A-Za-z0-9_."]*)|'
    r'\bJOIN\s+([A-Za-z_"][A-Za-z0-9_."]*)',
    re.IGNORECASE)


def _strip_quotes(name: str) -> str:
    return (name or '').replace('"', '').replace('`', '').strip()


def _split_3part(qualified: str) -> tuple[str, str, str]:
    """Return (db, schema, table) from a 1/2/3-part identifier."""
    parts = [_strip_quotes(p) for p in qualified.split('.')]
    parts = [p for p in parts if p]
    if len(parts) >= 3:
        return parts[-3], parts[-2], parts[-1]
    if len(parts) == 2:
        return '', parts[0], parts[1]
    if len(parts) == 1:
        return '', '', parts[0]
    return '', '', ''


def _extract_tables_regex(sql: str) -> list[tuple[str, str, str, str]]:
    """Returns [(raw_match, db, schema, table), ...]."""
    refs = []
    for m in _TABLE_REF_RE.finditer(sql):
        ident = m.group(1) or m.group(2) or ''
        ident = ident.rstrip(',').strip()
        if not ident: continue
        # Trim alias suffix like ` AS x` — regex pattern doesn't include it
        db, sch, tbl = _split_3part(ident)
        refs.append((ident, db.upper(), sch.upper(), tbl.upper()))
    return refs


def _extract_tables_sqlglot(sql: str) -> list[tuple[str, str, str, str]] | None:
    try:
        import sqlglot
        from sqlglot import exp
    except ImportError:
        return None
    try:
        tree = sqlglot.parse_one(sql, read='snowflake')
    except Exception:
        return None
    refs = []
    for t in tree.find_all(exp.Table):
        try:
            db = (t.args.get('catalog') and t.args['catalog'].name) or ''
            sch = (t.args.get('db') and t.args['db'].name) or ''
            tbl = t.name
            ident = '.'.join(p for p in [db, sch, tbl] if p)
            refs.append((ident, db.upper(), sch.upper(), tbl.upper()))
        except Exception:
            continue
    return refs


def validate_sql(sql: str, *, catalog: Catalog,
                    db: str,
                    selected_table_keys: list[str] | None = None) -> ValidationResult:
    res = ValidationResult()
    if not sql or not sql.strip():
        res.notes.append('empty_sql')
        return res

    refs = _extract_tables_sqlglot(sql)
    if refs is None:
        refs = _extract_tables_regex(sql)
        res.notes.append('regex_fallback')
    res.referenced_tables = [{'raw': r[0], 'db': r[1], 'schema': r[2], 'table': r[3]}
                                  for r in refs]

    db_u = db.upper()
    available_tables = {t.table.upper(): t for t in catalog.all_tables(db_u)}
    fq_to_table = {t.fq_name.upper(): t for t in catalog.all_tables(db_u)}

    for raw, ref_db, ref_sch, ref_tbl in refs:
        if not ref_tbl: continue
        # Identify by full-fq if all 3 parts present, else by table name only
        if ref_db and ref_sch:
            fq = f'{ref_db}.{ref_sch}.{ref_tbl}'
            if fq in fq_to_table: continue
        if ref_tbl in available_tables: continue
        # Unknown — suggest
        sugg = _suggest_close(ref_tbl, list(available_tables.keys()))
        res.unknown_tables.append({'raw': raw, 'table': ref_tbl,
                                       'suggestions': sugg})
        res.suggestions[raw] = sugg

    # Column validation: only via sqlglot reliably
    selected_set = None
    if selected_table_keys:
        selected_set = {k.split('.')[-1].upper() for k in selected_table_keys}
    col_refs = _extract_columns_sqlglot(sql)
    if col_refs is not None:
        # Build column index per table
        col_by_table = {}
        for t in catalog.all_tables(db_u):
            col_by_table[t.table.upper()] = {c.name.upper() for c in t.columns}
        # For each column reference: if table specified, check that table; else
        # check across selected tables.
        for raw_col, qual_table, col_name in col_refs:
            if not col_name: continue
            if qual_table:
                tbls_to_check = [qual_table.upper()]
            else:
                tbls_to_check = list(selected_set or available_tables.keys())
            found = False
            for tbl_u in tbls_to_check:
                cols = col_by_table.get(tbl_u, set())
                if col_name.upper() in cols:
                    found = True
                    break
            if not found:
                # Search globally and report the table that hosts the closest match
                global_pool = []
                for tbl_u, cols in col_by_table.items():
                    for c in cols:
                        global_pool.append((tbl_u, c))
                close = []
                for tbl_u, c in global_pool:
                    d = _levenshtein(col_name, c)
                    if d <= 2:
                        close.append((d, f'{tbl_u}.{c}'))
                close.sort()
                sugg = [n for _, n in close[:5]]
                res.unknown_columns.append({'raw': raw_col, 'col': col_name,
                                                'qualified_table': qual_table,
                                                'suggestions': sugg})
                res.suggestions[raw_col] = sugg
            res.referenced_columns.append({'raw': raw_col, 'table': qual_table,
                                                 'col': col_name, 'found': found})
    else:
        res.notes.append('no_column_validation_sqlglot_unavailable')

    res.schema_valid = (not res.unknown_tables) and (not res.unknown_columns)
    return res


def _extract_columns_sqlglot(sql: str) -> list[tuple[str, str, str]] | None:
    """Returns [(raw, qualifier, col), ...] or None if sqlglot unavailable."""
    try:
        import sqlglot
        from sqlglot import exp
    except ImportError:
        return None
    try:
        tree = sqlglot.parse_one(sql, read='snowflake')
    except Exception:
        return None
    out = []
    for c in tree.find_all(exp.Column):
        try:
            qual = (c.args.get('table') and c.args['table'].name) or ''
            name = c.name
            raw = c.sql(dialect='snowflake')
            out.append((raw, qual, name))
        except Exception:
            continue
    return out


def render_validation_for_repair(res: ValidationResult, *, max_lines: int = 10) -> str:
    lines = []
    if res.unknown_tables:
        lines.append('UNKNOWN_TABLES (must be replaced with one of suggested):')
        for ent in res.unknown_tables[:max_lines]:
            lines.append(f"  - `{ent['raw']}` (parsed table={ent['table']})  "
                          f"suggestions={ent['suggestions']}")
    if res.unknown_columns:
        lines.append('UNKNOWN_COLUMNS (must be replaced with one of suggested):')
        for ent in res.unknown_columns[:max_lines]:
            lines.append(f"  - `{ent['raw']}` (parsed col={ent['col']}, "
                          f"qual_table={ent['qualified_table']})  "
                          f"suggestions={ent['suggestions']}")
    if not lines:
        lines.append('OK: all referenced identifiers found in catalog.')
    return '\n'.join(lines)
