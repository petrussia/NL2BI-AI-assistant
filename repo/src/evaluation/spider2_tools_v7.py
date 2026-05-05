"""spider2_tools_v7 — tool implementations for the Spider2-Lite agent.

Each callable here is a tool the agent can invoke from inside its
bounded action loop. Tools are deterministic, side-effect-free except
for the executors, and never emit raw LLM output.

Tool surface (action JSON `action` values that map to these):
  metadata_doc_search   -> grep over Schema IR comments / glossary
  schema_search         -> BM25-lite over table / column identifiers
                            (camelCase + underscore split, useful for
                            enterprise Spider2 names)
  join_path_search      -> BFS over fk_edges from one table to another
  column_profile        -> distinct values from an executor when available
  sample_value_probe    -> SELECT DISTINCT col LIMIT k via executor
  dialect_check         -> sqlglot parse + transpile validation
  sql_dry_run_or_execute-> dry-run for BQ / actual exec for SQLite / parse-only
                            for C_struct
  cte_workspace_builder -> render a list of named CTE pieces into one SELECT
  bounded_repair        -> a single-round repair against the executor's error

Executor protocol — every executor passed in here implements:
  __call__(sql, *, dry_run=False, max_rows=None)
    -> {'ok': bool, 'rows': list|None, 'error_type': str, 'error_message': str,
        'bytes_billed': int, 'bytes_processed': int, 'mode': 'bq'|'sqlite'|'noop'}

Concrete executors (lazy imports — no creds needed at import time):
  build_sqlite_executor(db_path)
  build_bq_executor(creds_path, project, max_bytes=10**9)
  NoopExecutor() — for C_struct lane
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from collections import deque
from pathlib import Path
from typing import Callable, Iterable

# Lazy imports — sqlglot is the only hard dep at import time.
import sqlglot
from sqlglot import exp

from dialect_utils_v2 import is_safe_select, transpile, normalize_sql
from sqlglot_checks_v2 import schema_validity, structural_features


# ===================== executors =====================

class NoopExecutor:
    """Stand-in for the C_struct lane: never executes, always returns
    a parse-only verdict so the agent loop can still gate on something."""

    mode = 'noop'

    def __call__(self, sql: str, *, dry_run: bool = False,
                  max_rows: int | None = None, dialect: str = 'sqlite') -> dict:
        try:
            sqlglot.parse_one(sql, read=dialect)
            return {'ok': True, 'rows': None, 'error_type': '',
                    'error_message': 'parse_only_no_execute',
                    'bytes_billed': 0, 'bytes_processed': 0, 'mode': 'noop'}
        except Exception as exc:
            return {'ok': False, 'rows': None,
                    'error_type': type(exc).__name__,
                    'error_message': str(exc)[:300],
                    'bytes_billed': 0, 'bytes_processed': 0, 'mode': 'noop'}


def build_ir_from_stub_dir(db_id: str, db_dir: str | Path, *,
                              dialect: str = 'sqlite') -> object:
    """Build a SchemaIR from a Spider2 stub dir.

    Spider2 ships each table as `<name>.json` containing:
      {'table_name', 'table_fullname', 'column_names', 'column_types',
       'sample_rows', 'description'}
    DDL.csv carries the canonical CREATE TABLE strings — used as
    fallback when a JSON is missing or malformed.
    """
    import json as _json
    import csv as _csv
    from schema_ir_v2 import SchemaIR, TableMeta, ColumnMeta
    db_dir = Path(db_dir)

    # First pass: per-table JSON
    tables: list[TableMeta] = []
    seen_tables: set[str] = set()
    for jf in sorted(db_dir.glob('*.json')):
        try:
            d = _json.loads(jf.read_text(encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(d, dict): continue
        tname = (d.get('table_name') or jf.stem).strip()
        cols = d.get('column_names') or []
        types = d.get('column_types') or []
        if not tname or not cols: continue
        col_metas = []
        for i, cn in enumerate(cols):
            dt = (types[i] if i < len(types) else 'text') or 'text'
            col_metas.append(ColumnMeta(name=str(cn).lower(),
                                          original_name=str(cn),
                                          table_name=tname.lower(),
                                          dtype=str(dt).lower()))
        tables.append(TableMeta(name=tname.lower(), original_name=tname,
                                  columns=col_metas,
                                  comment=str(d.get('description') or '')[:300]))
        seen_tables.add(tname.lower())

    # Second pass: DDL.csv covers tables that didn't have a JSON
    ddl_csv = db_dir / 'DDL.csv'
    if ddl_csv.exists():
        try:
            with ddl_csv.open(encoding='utf-8', errors='ignore') as f:
                rd = _csv.DictReader(f)
                for row in rd:
                    tname = (row.get('table_name') or '').strip()
                    ddl = row.get('DDL') or row.get('ddl') or ''
                    if not tname or not ddl: continue
                    if tname.lower() in seen_tables: continue
                    cols = _parse_columns_from_create(ddl)
                    if not cols: continue
                    col_metas = [ColumnMeta(name=c[0].lower(),
                                              original_name=c[0],
                                              table_name=tname.lower(),
                                              dtype=c[1].lower())
                                  for c in cols]
                    tables.append(TableMeta(name=tname.lower(),
                                              original_name=tname,
                                              columns=col_metas))
                    seen_tables.add(tname.lower())
        except Exception:
            pass

    return SchemaIR(db_id=db_id, dialect=dialect, source='spider2_lite',
                     tables=tables, fk_edges=[])


def build_ir_from_bq_db_dir(db_id: str, db_dir: str | Path,
                              *, max_tables: int = 60) -> object:
    """Build a SchemaIR for a Spider2 BigQuery db directory.

    Layout: `bigquery/<db_id>/<fully_qualified_dataset>/<table>.json`
    Tables across multiple datasets within the same db are merged into
    one IR; each table's `original_name` becomes
    `<fully_qualified_dataset>.<table>` so the LLM sees the full path
    that BigQuery requires.

    `max_tables` caps the IR size — Spider2 datasets like ga360 ship
    hundreds of `ga_sessions_2017xxxx` daily-suffix tables that would
    blow past any prompt budget. We keep the first N (sorted) and
    rely on retrieval at agent time to surface the right ones.
    """
    import json as _json
    from schema_ir_v2 import SchemaIR, TableMeta, ColumnMeta
    db_dir = Path(db_dir)
    tables: list[TableMeta] = []
    seen: set[str] = set()
    if not db_dir.exists():
        return SchemaIR(db_id=db_id, dialect='bigquery',
                         source='spider2_lite', tables=[], fk_edges=[])
    for sub in sorted(db_dir.iterdir()):
        if not sub.is_dir(): continue
        fq_dataset = sub.name  # e.g. 'bigquery-public-data.ga_sessions'
        for jf in sorted(sub.glob('*.json')):
            try:
                d = _json.loads(jf.read_text(encoding='utf-8'))
            except Exception:
                continue
            if not isinstance(d, dict): continue
            tname = (d.get('table_name') or jf.stem).strip()
            cols = d.get('column_names') or []
            types = d.get('column_types') or []
            if not tname or not cols: continue
            full_name = f'{fq_dataset}.{tname}'
            key = full_name.lower()
            if key in seen: continue
            seen.add(key)
            col_metas = []
            for i, cn in enumerate(cols):
                dt = (types[i] if i < len(types) else 'STRING') or 'STRING'
                col_metas.append(ColumnMeta(name=str(cn).lower(),
                                              original_name=str(cn),
                                              table_name=tname.lower(),
                                              dtype=str(dt).lower()))
            tables.append(TableMeta(name=tname.lower(),
                                      original_name=full_name,
                                      columns=col_metas,
                                      comment=str(d.get('description') or '')[:300]))
            if len(tables) >= max_tables: break
        if len(tables) >= max_tables: break
    return SchemaIR(db_id=db_id, dialect='bigquery',
                     source='spider2_lite', tables=tables, fk_edges=[])


_CREATE_BODY_RE = re.compile(r'\(\s*(.*?)\s*\)\s*;?\s*$', re.DOTALL)


def _parse_columns_from_create(ddl: str) -> list[tuple[str, str]]:
    """Extract (col_name, dtype) pairs from a CREATE TABLE body.

    Best-effort: handles quoted identifiers and trailing commas. Skips
    table-level CONSTRAINT / PRIMARY KEY / FOREIGN KEY clauses.
    """
    m = _CREATE_BODY_RE.search(ddl)
    if not m: return []
    body = m.group(1)
    # split on commas not inside parens
    parts: list[str] = []
    depth = 0; cur = []
    for ch in body:
        if ch == '(' :
            depth += 1; cur.append(ch)
        elif ch == ')':
            depth -= 1; cur.append(ch)
        elif ch == ',' and depth == 0:
            parts.append(''.join(cur).strip()); cur = []
        else:
            cur.append(ch)
    if cur: parts.append(''.join(cur).strip())
    out: list[tuple[str, str]] = []
    for p in parts:
        ps = p.strip()
        if not ps: continue
        upper = ps.upper()
        if any(upper.startswith(k) for k in ('PRIMARY ', 'FOREIGN ', 'UNIQUE ',
                                                  'CHECK ', 'CONSTRAINT ')):
            continue
        m2 = re.match(r'^["`\[]?([A-Za-z_][A-Za-z0-9_]*)["`\]]?\s+'
                       r'([A-Za-z][A-Za-z0-9_()]*)', ps)
        if m2:
            out.append((m2.group(1), m2.group(2)))
    return out


def materialize_sqlite_from_dir(db_dir: str | Path,
                                  *, max_rows_per_table: int | None = None,
                                  out_path: str = ':memory:') -> sqlite3.Connection:
    """Build a SQLite database from a Spider2-Lite stub directory.

    Each `<name>.json` is a dict with keys
    `table_name | column_names | column_types | sample_rows | ...`.
    We use `column_names`/`column_types` to derive a typed CREATE TABLE
    and INSERT the `sample_rows` with positional binding.
    """
    import json as _json
    db_dir = Path(db_dir)
    # check_same_thread=False so func_timeout can call the connection
    # from its worker thread.
    con = sqlite3.connect(out_path, check_same_thread=False)
    con.text_factory = str
    cur = con.cursor()
    for jf in sorted(db_dir.glob('*.json')):
        try:
            d = _json.loads(jf.read_text(encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(d, dict): continue
        tname = (d.get('table_name') or jf.stem).strip()
        cols = d.get('column_names') or []
        types = d.get('column_types') or []
        rows = d.get('sample_rows') or []
        if not tname or not cols: continue
        # Build CREATE TABLE with mapped types
        col_defs = []
        for i, cn in enumerate(cols):
            dt = (types[i] if i < len(types) else 'text') or 'text'
            col_defs.append(f'"{cn}" {_sqlite_type(str(dt))}')
        try:
            cur.execute(f'DROP TABLE IF EXISTS "{tname}"')
            cur.execute(f'CREATE TABLE "{tname}" ({", ".join(col_defs)})')
        except Exception:
            continue
        if not isinstance(rows, list): continue
        rows_iter = rows if max_rows_per_table is None else rows[:max_rows_per_table]
        placeholders = ', '.join('?' * len(cols))
        col_list = ', '.join(f'"{c}"' for c in cols)
        for r in rows_iter:
            if not isinstance(r, dict): continue
            try:
                vals = tuple(_json_safe(r.get(c)) for c in cols)
                cur.execute(f'INSERT INTO "{tname}" ({col_list}) VALUES ({placeholders})', vals)
            except Exception:
                continue
    con.commit()
    return con


def _sqlite_type(t: str) -> str:
    """Map Spider2 declared column type to a sqlite-compatible token."""
    s = t.lower().strip()
    if 'int' in s or s in ('bigint', 'smallint'): return 'INTEGER'
    if 'float' in s or 'double' in s or 'real' in s or 'numeric' in s or 'decimal' in s:
        return 'REAL'
    if 'bool' in s: return 'INTEGER'
    if 'date' in s or 'time' in s: return 'TEXT'
    if 'json' in s or 'array' in s or 'struct' in s or 'record' in s:
        return 'TEXT'
    return 'TEXT'


def _json_safe(v):
    """Coerce arbitrary JSON values to a SQLite-friendly scalar."""
    if v is None: return None
    if isinstance(v, (int, float, str)): return v
    if isinstance(v, bool): return int(v)
    return str(v)[:8000]


def build_sqlite_executor(db_path: str, *, timeout_s: int = 8) -> Callable:
    """Returns an executor that runs against a local SQLite file (lane B
    when an actual `.sqlite` file is present)."""
    from func_timeout import FunctionTimedOut, func_timeout
    db_path = str(db_path)

    def _ex(sql: str, *, dry_run: bool = False,
             max_rows: int | None = 1000, dialect: str = 'sqlite') -> dict:
        if dry_run:
            try:
                sqlglot.parse_one(sql, read=dialect)
                return {'ok': True, 'rows': None, 'error_type': '',
                        'error_message': 'sqlite_dry_run_parse_ok',
                        'bytes_billed': 0, 'bytes_processed': 0, 'mode': 'sqlite'}
            except Exception as exc:
                return {'ok': False, 'rows': None,
                        'error_type': type(exc).__name__,
                        'error_message': str(exc)[:300],
                        'bytes_billed': 0, 'bytes_processed': 0, 'mode': 'sqlite'}
        def _run():
            with sqlite3.connect(f'file:{db_path}?mode=ro', uri=True) as con:
                con.text_factory = bytes
                cur = con.cursor()
                cur.execute(sql)
                if max_rows is None:
                    rows = cur.fetchall()
                else:
                    rows = cur.fetchmany(max_rows)
                return rows
        try:
            rows = func_timeout(timeout_s, _run)
            return {'ok': True, 'rows': rows, 'error_type': '', 'error_message': '',
                    'bytes_billed': 0, 'bytes_processed': 0, 'mode': 'sqlite'}
        except FunctionTimedOut:
            return {'ok': False, 'rows': None, 'error_type': 'timeout',
                    'error_message': f'>{timeout_s}s',
                    'bytes_billed': 0, 'bytes_processed': 0, 'mode': 'sqlite'}
        except Exception as exc:
            return {'ok': False, 'rows': None,
                    'error_type': type(exc).__name__,
                    'error_message': str(exc)[:300],
                    'bytes_billed': 0, 'bytes_processed': 0, 'mode': 'sqlite'}
    return _ex


def build_sqlite_conn_executor(con: sqlite3.Connection, *,
                                  timeout_s: int = 8) -> Callable:
    """Executor wrapping an already-open sqlite3.Connection (used after
    `materialize_sqlite_from_dir`).
    """
    from func_timeout import FunctionTimedOut, func_timeout

    def _ex(sql: str, *, dry_run: bool = False,
             max_rows: int | None = 1000, dialect: str = 'sqlite') -> dict:
        if dry_run:
            try:
                sqlglot.parse_one(sql, read=dialect)
                return {'ok': True, 'rows': None, 'error_type': '',
                        'error_message': 'sqlite_dry_run_parse_ok',
                        'bytes_billed': 0, 'bytes_processed': 0,
                        'mode': 'sqlite_mem'}
            except Exception as exc:
                return {'ok': False, 'rows': None,
                        'error_type': type(exc).__name__,
                        'error_message': str(exc)[:300],
                        'bytes_billed': 0, 'bytes_processed': 0,
                        'mode': 'sqlite_mem'}
        def _run():
            cur = con.cursor()
            cur.execute(sql)
            if max_rows is None:
                return cur.fetchall()
            return cur.fetchmany(max_rows)
        try:
            rows = func_timeout(timeout_s, _run)
            return {'ok': True, 'rows': rows, 'error_type': '',
                    'error_message': '',
                    'bytes_billed': 0, 'bytes_processed': 0,
                    'mode': 'sqlite_mem'}
        except FunctionTimedOut:
            return {'ok': False, 'rows': None, 'error_type': 'timeout',
                    'error_message': f'>{timeout_s}s',
                    'bytes_billed': 0, 'bytes_processed': 0,
                    'mode': 'sqlite_mem'}
        except Exception as exc:
            return {'ok': False, 'rows': None,
                    'error_type': type(exc).__name__,
                    'error_message': str(exc)[:300],
                    'bytes_billed': 0, 'bytes_processed': 0,
                    'mode': 'sqlite_mem'}
    _ex.mode = 'sqlite_mem'
    return _ex


def build_bq_executor(creds_path: str, project: str, *,
                       max_bytes: int = 10**9,
                       hard_max_bytes: int = 10**11,
                       timeout_s: int = 60) -> Callable:
    """Returns an executor against BigQuery (lane A_bq).

    Uses dry_run=True path to validate + estimate without billing. The
    actual exec is gated by `maximum_bytes_billed=max_bytes` so we never
    silently scan the whole warehouse.
    """
    from google.cloud import bigquery
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_file(creds_path)
    client = bigquery.Client(project=project, credentials=creds)

    def _ex(sql: str, *, dry_run: bool = False,
             max_rows: int | None = 1000, dialect: str = 'bigquery') -> dict:
        try:
            if dry_run:
                cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
                j = client.query(sql, job_config=cfg)
                return {'ok': True, 'rows': None, 'error_type': '',
                        'error_message': 'bq_dry_run_ok',
                        'bytes_billed': 0,
                        'bytes_processed': int(j.total_bytes_processed or 0),
                        'mode': 'bq_dry'}
            cfg = bigquery.QueryJobConfig(maximum_bytes_billed=max_bytes,
                                           use_query_cache=False)
            j = client.query(sql, job_config=cfg)
            rows = list(j.result(timeout=timeout_s,
                                  max_results=max_rows or 10**9))
            return {'ok': True,
                    'rows': [tuple(r.values()) for r in rows],
                    'error_type': '', 'error_message': '',
                    'bytes_billed': int(j.total_bytes_billed or 0),
                    'bytes_processed': int(j.total_bytes_processed or 0),
                    'mode': 'bq'}
        except Exception as exc:
            msg = str(exc)[:400]
            et = type(exc).__name__
            # bytesBilledExceeded -> caller can retry with hard_max_bytes
            return {'ok': False, 'rows': None, 'error_type': et,
                    'error_message': msg,
                    'bytes_billed': 0, 'bytes_processed': 0, 'mode': 'bq'}
    _ex.client = client
    _ex.project = project
    _ex.max_bytes = max_bytes
    _ex.hard_max_bytes = hard_max_bytes
    return _ex


# ===================== text utils =====================

# Camel-case boundary only fires on lowercase->uppercase or
# uppercase->Uppercase+lowercase transitions, so 'SCREAMING_SNAKE' is
# preserved as a single token after the underscore-split, but
# 'orderItemFulfillment' splits cleanly.
_CAMEL_RE = re.compile(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')


def _split_identifier(s: str) -> list[str]:
    """Tokenize identifiers handling camelCase, snake_case, dotted, and
    SCREAMING_SNAKE without splitting the latter character-by-character."""
    if not s: return []
    parts = re.split(r'[_\s\-/.]+', s)
    out: list[str] = []
    for p in parts:
        if not p: continue
        out.extend(t for t in _CAMEL_RE.split(p) if t)
    return [t.lower() for t in out if t]


def _stem(t: str) -> str:
    """Cheap singular/plural normalization: drop trailing 's' on words >=4
    chars. Keeps 'orders' and 'order' matched as the same key."""
    if len(t) >= 4 and t.endswith('s') and not t.endswith('ss'):
        return t[:-1]
    return t


def _toks_stemmed(s: str) -> set[str]:
    return {_stem(t) for t in _split_identifier(s)}


def _question_terms(question: str) -> list[str]:
    STOP = {'a','an','the','of','in','on','at','for','to','from','by','with',
            'is','are','was','were','what','which','who','whom','whose','how',
            'many','much','show','list','find','give','me','all','each','every',
            'any','do','does','did','please','can','could','would','should',
            'and','or','but','as','that','this','these','those'}
    parts = _split_identifier(question)
    return [p for p in parts if p not in STOP and len(p) > 1]


# ===================== tools =====================

def metadata_doc_search(ir, terms: list[str], k: int = 8) -> list[dict]:
    """Substring-match `terms` against ir.comment / table.comment /
    column.comment / aliases / glossary. Returns up to k hits."""
    tlist = [t.lower() for t in terms if t]
    if not tlist: return []
    hits: list[tuple[float, dict]] = []
    db_doc = (getattr(ir, 'comment', '') or '').lower()
    if db_doc:
        score = sum(1 for t in tlist if t in db_doc)
        if score: hits.append((score, {'scope': 'database', 'doc': db_doc[:200]}))
    for tab in ir.tables:
        td = (tab.comment or '').lower()
        if td:
            s = sum(1 for t in tlist if t in td)
            if s: hits.append((s, {'scope': 'table', 'table': tab.original_name,
                                    'doc': tab.comment[:200]}))
        for col in tab.columns:
            cd = (col.comment or '').lower()
            if not cd: continue
            s = sum(1 for t in tlist if t in cd)
            if s: hits.append((s + 0.1, {'scope': 'column',
                                          'table': tab.original_name,
                                          'column': col.original_name,
                                          'doc': col.comment[:200]}))
    hits.sort(key=lambda x: -x[0])
    return [h for _, h in hits[:k]]


def schema_search(ir, query: str, *, k_tables: int = 6,
                   k_columns: int = 12) -> dict:
    """Lexical retrieval over identifiers (table + column names). Ranks
    by token overlap with question; tie-break by length-normalized score.

    Returns {'tables': [(name, score)], 'columns': [(table, col, score)]}.
    """
    qt = {_stem(t) for t in _question_terms(query)}
    if not qt: return {'tables': [], 'columns': []}
    table_scores: list[tuple[str, float]] = []
    col_scores: list[tuple[str, str, float]] = []
    for t in ir.tables:
        ttoks = (_toks_stemmed(t.original_name) | _toks_stemmed(t.name)
                  | {_stem(a.lower()) for a in t.aliases})
        s = len(qt & ttoks) * 2.0
        if s > 0: table_scores.append((t.original_name, s))
        for c in t.columns:
            ctoks = (_toks_stemmed(c.original_name) | _toks_stemmed(c.name)
                      | _toks_stemmed(c.comment)
                      | {_stem(a.lower()) for a in c.aliases})
            cs = len(qt & ctoks)
            if cs > 0:
                col_scores.append((t.original_name, c.original_name, cs))
    table_scores.sort(key=lambda x: -x[1])
    col_scores.sort(key=lambda x: -x[2])
    return {'tables': table_scores[:k_tables],
            'columns': col_scores[:k_columns]}


def join_path_search(ir, t_from: str, t_to: str, *,
                      max_depth: int = 4) -> list[list[str]]:
    """BFS over fk_edges to enumerate join chains from t_from to t_to.
    Returns list of paths; each path is [table0, table1, ...]."""
    a, b = t_from.lower(), t_to.lower()
    adj: dict[str, set[str]] = {}
    for e in ir.fk_edges:
        adj.setdefault(e.from_table, set()).add(e.to_table)
        adj.setdefault(e.to_table, set()).add(e.from_table)
    if a not in adj or b not in adj:
        return []
    q = deque([(a, [a])])
    seen = {a}
    paths: list[list[str]] = []
    while q:
        node, path = q.popleft()
        if len(path) - 1 > max_depth: continue
        if node == b:
            paths.append(path); continue
        for nxt in adj.get(node, ()):
            if nxt in seen and nxt != b: continue
            seen.add(nxt)
            q.append((nxt, path + [nxt]))
    paths.sort(key=len)
    return paths[:5]


def column_profile(executor, table: str, column: str, *,
                    k: int = 10) -> dict:
    """Run SELECT DISTINCT col FROM tbl LIMIT k via executor.

    Quotes identifiers conservatively; falls back to no-quote if the
    quoted variant fails. Returns {'values': [...], 'error': str}.
    """
    if executor is None or getattr(executor, 'mode', None) == 'noop':
        return {'values': [], 'error': 'no_executor'}
    sql_q = f'SELECT DISTINCT "{column}" FROM "{table}" LIMIT {int(k)}'
    out = executor(sql_q, dry_run=False, max_rows=k)
    if not out['ok']:
        sql_b = f'SELECT DISTINCT {column} FROM {table} LIMIT {int(k)}'
        out = executor(sql_b, dry_run=False, max_rows=k)
    if not out['ok']:
        return {'values': [], 'error': out['error_type'] or 'exec_failed'}
    rows = out.get('rows') or []
    values = [r[0] if r else None for r in rows]
    return {'values': [str(v)[:80] for v in values], 'error': ''}


def dialect_check(sql: str, *, source: str = 'sqlite',
                   target: str = 'bigquery') -> dict:
    """Parse with `source` dialect; transpile to `target`. Used to detect
    SQLite-only idioms in candidates aimed at a BQ executor."""
    out = {'parses_source': False, 'parses_target': False,
            'transpiled_target': '', 'safe_select_target': False,
            'safe_reason_target': ''}
    try:
        sqlglot.parse_one(sql, read=source)
        out['parses_source'] = True
    except Exception as exc:
        out['parse_source_error'] = str(exc)[:200]
        return out
    if source == target:
        out['parses_target'] = True
        out['transpiled_target'] = sql
    else:
        t = transpile(sql, source=source, target=target)
        if t is None:
            out['parses_target'] = False
            return out
        out['parses_target'] = True
        out['transpiled_target'] = t
    safe, reason = is_safe_select(out['transpiled_target'], target)
    out['safe_select_target'] = safe
    out['safe_reason_target'] = reason
    return out


def sql_dry_run_or_execute(sql: str, executor, *,
                             dialect: str = 'sqlite',
                             dry_only: bool = False,
                             max_rows: int = 100) -> dict:
    """Single entry point used inside the agent loop.

    Order: parse-safety -> dry-run -> (if not dry_only) actual exec.
    """
    safe, why = is_safe_select(sql, dialect)
    if not safe:
        return {'ok': False, 'phase': 'safety', 'error_type': 'unsafe',
                'error_message': why,
                'rows': None, 'bytes_billed': 0, 'bytes_processed': 0,
                'mode': getattr(executor, 'mode', 'noop')}
    dry = executor(sql, dry_run=True, dialect=dialect)
    if not dry['ok']:
        return {**dry, 'phase': 'dry_run'}
    if dry_only:
        return {**dry, 'phase': 'dry_run'}
    real = executor(sql, dry_run=False, max_rows=max_rows, dialect=dialect)
    return {**real, 'phase': 'execute'}


def cte_workspace_builder(steps: list[dict], *, final_sql: str,
                            dialect: str = 'sqlite') -> str:
    """Combine a list of named CTE pieces into one query.

    `steps`: list of {'name': str, 'sql': str}. `final_sql` is the
    SELECT that consumes them (uses the CTE names directly).

    Output: WITH name1 AS (sql1), name2 AS (sql2), ... <final_sql>
    No transpilation here — caller decides dialect at write time.
    """
    if not steps: return final_sql
    parts = []
    for s in steps:
        nm = re.sub(r'[^A-Za-z0-9_]', '_', str(s.get('name', '')) or 'cte')
        body = (s.get('sql') or '').rstrip().rstrip(';')
        if not body: continue
        parts.append(f'{nm} AS (\n  {body}\n)')
    if not parts: return final_sql
    return 'WITH ' + ',\n'.join(parts) + '\n' + final_sql


def bounded_repair(sql: str, error_msg: str, *,
                    gen, executor, dialect: str = 'sqlite',
                    max_rounds: int = 1) -> dict:
    """One LLM-driven repair round. Generic — does not call repair_v2 to
    avoid pulling its Spider-specific assumptions into Spider2 lane.

    Returns {'sql': str, 'safe': bool, 'rounds': int, 'final_error': str}.
    """
    cur = sql; final_err = error_msg or ''
    rounds = 0
    while rounds < max_rounds:
        rounds += 1
        prompt = (
            'You wrote SQL that failed. Below is the original SQL and the '
            'execution error. Return ONLY a corrected SQL query (no markdown, '
            f'no explanation). Target dialect: {dialect}.\n\n'
            f'ORIGINAL_SQL:\n{cur}\n\nERROR:\n{final_err[:400]}\n\nFIXED_SQL:'
        )
        try:
            raw = gen(prompt, max_new=300)
        except Exception as exc:
            return {'sql': cur, 'safe': False, 'rounds': rounds,
                    'final_error': f'gen_exc:{type(exc).__name__}'}
        new_sql = _strip_md_sql(raw).strip()
        if not new_sql:
            return {'sql': cur, 'safe': False, 'rounds': rounds,
                    'final_error': 'empty_repair'}
        out = sql_dry_run_or_execute(new_sql, executor, dialect=dialect,
                                       max_rows=10)
        if out['ok']:
            return {'sql': new_sql, 'safe': True, 'rounds': rounds,
                    'final_error': ''}
        cur = new_sql; final_err = out.get('error_message') or ''
    return {'sql': cur, 'safe': False, 'rounds': rounds,
            'final_error': final_err[:300]}


_SQL_FENCE = re.compile(r'```(?:sql)?\s*(.+?)```', re.DOTALL | re.IGNORECASE)


def _strip_md_sql(raw: str) -> str:
    raw = (raw or '').strip()
    m = _SQL_FENCE.search(raw)
    if m: return m.group(1).strip()
    # strip leading "SQL:" tags
    raw = re.sub(r'^\s*(?:fixed_?sql|sql)\s*[:\-]\s*', '', raw, flags=re.I)
    return raw
