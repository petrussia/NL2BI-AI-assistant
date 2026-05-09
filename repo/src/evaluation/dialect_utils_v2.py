"""dialect_utils_v2 — dialect detection / normalization / transpilation.

Wraps SQLGlot's dialect surface so the rest of the v2 stack can stay
dialect-agnostic. We deliberately keep the public surface tiny: one
detector, one normalizer, one transpiler, one quote-helper.
"""
from __future__ import annotations

from typing import Iterable

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError, OptimizeError

SUPPORTED = ('sqlite', 'postgres', 'mysql', 'bigquery', 'snowflake')


def detect_dialect(db_id: str, source: str = '') -> str:
    """Pick the most appropriate sqlglot dialect token from benchmark hints.

    Used when the schema_ir doesn't have an explicit dialect (e.g. proxy IR
    for Spider2-Lite). Defaults to sqlite for Spider/BIRD.
    """
    s = (source or '').lower()
    if s == 'spider' or s == 'bird': return 'sqlite'
    if s.startswith('spider2'): return 'snowflake'
    return 'sqlite'


def normalize_sql(sql: str, dialect: str = 'sqlite') -> str:
    """Best-effort canonicalization: parse + re-emit with the target dialect.

    On parse error, return the original string unchanged. Never raises.
    """
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
        return tree.sql(dialect=dialect, normalize=True)
    except (ParseError, OptimizeError, Exception):
        return sql


def transpile(sql: str, *, source: str = 'sqlite', target: str = 'sqlite',
              pretty: bool = False) -> str | None:
    """Transpile between dialects. Returns None on parse failure."""
    if source == target:
        return sql
    try:
        return sqlglot.transpile(sql, read=source, write=target, pretty=pretty)[0]
    except Exception:
        return None


def quote_ident(name: str, dialect: str = 'sqlite') -> str:
    """Wrap identifier with the dialect's quoting rules."""
    if dialect in ('mysql',):  return f'`{name}`'
    if dialect in ('postgres','snowflake','sqlite','bigquery'):
        return f'"{name}"'
    return name


_FORBIDDEN_KEYWORDS = (
    'insert ', 'update ', 'delete ', 'drop ', 'truncate ', 'alter ',
    'create table', 'create view', 'create index',
    'attach ', 'detach ', 'pragma ', 'replace into',
)


def _regex_safety(sql: str) -> tuple[bool, str]:
    """Fallback when AST parse fails. Block obvious DDL/DML keywords.

    Conservative — false-positive on weird SQL (returns True), but
    relies on the executor / schema-validity checks downstream to catch
    nonsense. We only block what is clearly unsafe.
    """
    s = ' ' + (sql or '').strip().lower() + ' '
    for kw in _FORBIDDEN_KEYWORDS:
        if kw in s: return False, f'regex_forbidden:{kw.strip()}'
    if 'select' not in s: return False, 'regex_no_select'
    return True, 'ok_regex'


def is_safe_select(sql: str, dialect: str = 'sqlite') -> tuple[bool, str]:
    """SELECT-only guard. Tries sqlglot AST first; falls back to regex
    when parse fails so quirky-but-safe SQLite stays runnable.
    """
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except Exception:
        return _regex_safety(sql)
    if tree is None: return _regex_safety(sql)
    # Walk for any DML/DDL nodes
    for node in tree.walk():
        n = node[0] if isinstance(node, tuple) else node
        if isinstance(n, (exp.Insert, exp.Update, exp.Delete, exp.Drop,
                          exp.Create, exp.Alter, exp.TruncateTable)):
            return False, f'forbidden:{type(n).__name__}'
    # Top-level must reduce to a SELECT/UNION/CTE-of-SELECT shape
    if isinstance(tree, (exp.Select, exp.Union, exp.With, exp.Subquery)):
        return True, 'ok'
    # Sometimes wrapped in Paren
    inner = tree.unalias() if hasattr(tree, 'unalias') else tree
    if isinstance(inner, (exp.Select, exp.Union, exp.With)):
        return True, 'ok'
    return False, f'top_level_not_select:{type(tree).__name__}'


def referenced_tables(sql: str, dialect: str = 'sqlite') -> list[str]:
    """Return table identifiers referenced in the AST (lowercased, deduped)."""
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except Exception:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for tbl in tree.find_all(exp.Table):
        n = (tbl.name or '').lower()
        if n and n not in seen:
            seen.add(n); out.append(n)
    return out


def referenced_columns(sql: str, dialect: str = 'sqlite') -> list[tuple[str, str]]:
    """Return (table_or_alias, column) pairs referenced in the AST."""
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except Exception:
        return []
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for col in tree.find_all(exp.Column):
        t = (col.table or '').lower()
        c = (col.name or '').lower()
        key = (t, c)
        if c and key not in seen:
            seen.add(key); out.append(key)
    return out
