"""schema_ir_v2 — dialect-aware Schema IR for the v2 NL2SQL stack.

Represents a single database as a structured object with:
- db_id, dialect
- tables (with comments / aliases / business glossary terms)
- columns (with dtype, comment, low-cardinality value hints)
- pk/fk edges
- evidence refs (per-cell hint id pointers; evidence content lives in
  evidence_store_v2)

Builders accept the canonical metadata shipped with each benchmark:
- Spider/BIRD: tables.json entry + sqlite path
- Spider2-Lite: per-db schema dump from raw resources

The IR is intentionally narrow and deterministic: no LM output ever
mutates it. Retrieval, planner, compiler and validator all consume it.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable, Sequence


SUPPORTED_DIALECTS = ('sqlite', 'postgres', 'mysql', 'bigquery', 'snowflake')


@dataclass
class ColumnMeta:
    name: str                       # canonical (lowercased identifier)
    original_name: str              # as written in source schema
    table_name: str                 # canonical lowercase
    dtype: str = ''                 # type token from CREATE / metadata
    comment: str = ''               # docstring / column_meaning
    aliases: list[str] = field(default_factory=list)
    glossary_terms: list[str] = field(default_factory=list)
    low_card_values: list[str] = field(default_factory=list)
    is_pk: bool = False
    is_fk: bool = False


@dataclass
class TableMeta:
    name: str
    original_name: str
    columns: list[ColumnMeta] = field(default_factory=list)
    comment: str = ''
    aliases: list[str] = field(default_factory=list)
    glossary_terms: list[str] = field(default_factory=list)
    primary_key_columns: list[str] = field(default_factory=list)


@dataclass
class FKEdge:
    from_table: str
    from_column: str
    to_table: str
    to_column: str


@dataclass
class EvidenceRef:
    """Pointer into evidence_store_v2 — content lives there, not here."""
    key: str
    scope: str = 'database'         # 'database' | 'table' | 'column'
    table: str = ''
    column: str = ''


@dataclass
class SchemaIR:
    db_id: str
    dialect: str
    tables: list[TableMeta] = field(default_factory=list)
    fk_edges: list[FKEdge] = field(default_factory=list)
    evidence_refs: list[EvidenceRef] = field(default_factory=list)
    comment: str = ''               # database-level description
    source: str = ''                # 'spider' | 'bird' | 'spider2_lite' | ...

    # ---------- helpers ----------
    def table(self, name: str) -> TableMeta | None:
        n = name.lower()
        for t in self.tables:
            if t.name == n: return t
        return None

    def column(self, table: str, column: str) -> ColumnMeta | None:
        t = self.table(table)
        if t is None: return None
        cn = column.lower()
        for c in t.columns:
            if c.name == cn: return c
        return None

    def all_columns(self) -> Iterable[ColumnMeta]:
        for t in self.tables:
            for c in t.columns:
                yield c

    def neighbours(self, table: str) -> list[str]:
        n = table.lower()
        out: set[str] = set()
        for e in self.fk_edges:
            if e.from_table == n: out.add(e.to_table)
            if e.to_table == n: out.add(e.from_table)
        return sorted(out)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------- builders ----------------------------

def _norm(s: str) -> str:
    return (s or '').strip().lower()


def _extract_dtype_from_create(create_sql: str, col_name: str) -> str:
    """Pull dtype token out of a CREATE TABLE body for a given column.

    Best-effort regex; survives quoted identifiers and trailing commas.
    """
    if not create_sql: return ''
    body = create_sql
    # Try quoted variants and bare
    patterns = [
        rf'["`\[]?{re.escape(col_name)}["`\]]?\s+([A-Za-z][A-Za-z0-9_()]*)',
    ]
    for p in patterns:
        m = re.search(p, body, re.IGNORECASE)
        if m: return m.group(1).upper()
    return ''


def from_spider_tables_entry(entry: dict, sqlite_path: str | None = None,
                             dialect: str = 'sqlite',
                             source: str = 'spider') -> SchemaIR:
    """Build a SchemaIR from one entry of spider/bird `tables.json`.

    Falls back to original_name when canonical names are missing.
    Pulls dtype from sqlite CREATE statements when sqlite_path is given.
    """
    db_id = entry['db_id']
    table_names = entry.get('table_names_original') or entry.get('table_names') or []
    column_names = entry.get('column_names_original') or entry.get('column_names') or []
    column_types = entry.get('column_types', [])
    primary_keys = entry.get('primary_keys', [])
    foreign_keys = entry.get('foreign_keys', [])

    tables: list[TableMeta] = []
    for ti, tname in enumerate(table_names):
        t = TableMeta(name=_norm(tname), original_name=tname)
        tables.append(t)

    # CREATE statements (sqlite) for dtype enrichment
    create_by_table: dict[str, str] = {}
    if sqlite_path and Path(sqlite_path).exists():
        try:
            with sqlite3.connect(f'file:{sqlite_path}?mode=ro', uri=True) as con:
                cur = con.cursor()
                cur.execute("select name, sql from sqlite_master where type='table'")
                for nm, sql in cur.fetchall():
                    create_by_table[_norm(nm)] = sql or ''
        except Exception:
            pass

    # Columns: column_names is list[ [table_index, col_name] ], position 0 is "*"
    for ci, item in enumerate(column_names):
        if ci == 0: continue  # the * sentinel
        ti, cname = item
        if ti < 0 or ti >= len(tables): continue
        t = tables[ti]
        dtype = column_types[ci] if ci < len(column_types) else ''
        if not dtype and t.original_name in create_by_table:
            dtype = _extract_dtype_from_create(create_by_table[t.original_name], cname)
        col = ColumnMeta(
            name=_norm(cname),
            original_name=cname,
            table_name=t.name,
            dtype=(dtype or '').lower(),
        )
        t.columns.append(col)

    # PKs: list of column indexes (or list[list[int]] for composite)
    pk_idx_set = set()
    for pk in primary_keys:
        if isinstance(pk, list):
            pk_idx_set.update(pk)
        else:
            pk_idx_set.add(pk)
    for ci in pk_idx_set:
        if ci <= 0 or ci >= len(column_names): continue
        ti, cname = column_names[ci]
        if 0 <= ti < len(tables):
            tables[ti].primary_key_columns.append(_norm(cname))
            for c in tables[ti].columns:
                if c.name == _norm(cname): c.is_pk = True

    # FKs
    fk_edges: list[FKEdge] = []
    for src, dst in foreign_keys:
        if src <= 0 or dst <= 0 or src >= len(column_names) or dst >= len(column_names):
            continue
        s_ti, s_cn = column_names[src]; d_ti, d_cn = column_names[dst]
        if not (0 <= s_ti < len(tables) and 0 <= d_ti < len(tables)): continue
        edge = FKEdge(
            from_table=tables[s_ti].name, from_column=_norm(s_cn),
            to_table=tables[d_ti].name, to_column=_norm(d_cn),
        )
        fk_edges.append(edge)
        for c in tables[s_ti].columns:
            if c.name == edge.from_column: c.is_fk = True

    return SchemaIR(db_id=db_id, dialect=dialect, tables=tables,
                    fk_edges=fk_edges, source=source)


def from_bird_tables_entry(entry: dict, sqlite_path: str | None = None,
                           description_dir: str | Path | None = None) -> SchemaIR:
    """Same as from_spider_tables_entry but enriches column comments
    from BIRD's database_description CSVs (if directory is provided).
    """
    ir = from_spider_tables_entry(entry, sqlite_path=sqlite_path,
                                   dialect='sqlite', source='bird')
    if description_dir:
        d = Path(description_dir)
        if d.is_dir():
            for t in ir.tables:
                csv_path = d / f'{t.original_name}.csv'
                if not csv_path.exists():
                    csv_path = d / f'{t.name}.csv'
                if not csv_path.exists(): continue
                try:
                    import csv as _csv
                    with csv_path.open(encoding='utf-8-sig', errors='ignore') as f:
                        reader = _csv.DictReader(f)
                        for row in reader:
                            col_orig = (row.get('original_column_name') or
                                         row.get('column_name') or '').strip()
                            meaning = (row.get('column_description') or
                                        row.get('value_description') or
                                        row.get('column_meaning') or '').strip()
                            if not col_orig: continue
                            for c in t.columns:
                                if c.original_name.lower() == col_orig.lower():
                                    if meaning and not c.comment:
                                        c.comment = meaning
                except Exception:
                    continue
    return ir


def from_spider2_proxy(db_id: str, schema_text: str,
                        dialect: str = 'snowflake') -> SchemaIR:
    """Best-effort: build a thin SchemaIR for Spider2-Lite where the only
    available representation is a free-form schema text. Tables/columns
    are extracted by regex; dtypes left empty. Used so that the v2
    pipeline still has a SchemaIR object even when full metadata is
    absent.
    """
    tables: list[TableMeta] = []
    cur_table: TableMeta | None = None
    for line in (schema_text or '').splitlines():
        l = line.strip()
        if l.lower().startswith('create table') or l.lower().startswith('table '):
            m = re.search(r'(?:create table|table)\s+["`]?([A-Za-z0-9_.]+)["`]?', l, re.I)
            if m:
                name = m.group(1).split('.')[-1]
                cur_table = TableMeta(name=_norm(name), original_name=name)
                tables.append(cur_table)
            continue
        if cur_table is not None:
            m = re.match(r'^["`]?([A-Za-z_][A-Za-z0-9_]*)["`]?\s+([A-Za-z][A-Za-z0-9_()]*)?', l)
            if m:
                cn = m.group(1); dt = (m.group(2) or '').upper()
                if cn.lower() in ('primary','foreign','constraint'): continue
                cur_table.columns.append(ColumnMeta(
                    name=_norm(cn), original_name=cn,
                    table_name=cur_table.name, dtype=dt.lower()))
    return SchemaIR(db_id=db_id, dialect=dialect, tables=tables,
                    fk_edges=[], source='spider2_lite')


# ---------------------------- rendering ----------------------------

def render_compact_schema(ir: SchemaIR, *, include_comments: bool = True,
                           include_fks: bool = True,
                           subset_tables: Sequence[str] | None = None) -> str:
    """Render a schema-prompt friendly text representation.

    Caller can subset tables (after retrieval) for token economy.
    """
    sel = set(t.lower() for t in subset_tables) if subset_tables else None
    out: list[str] = [f'-- DB: {ir.db_id} ({ir.dialect})']
    for t in ir.tables:
        if sel is not None and t.name not in sel: continue
        cols_repr = []
        for c in t.columns:
            tok = c.original_name
            if c.dtype: tok += f' {c.dtype.upper()}'
            if c.is_pk: tok += ' PK'
            if c.is_fk: tok += ' FK'
            if include_comments and c.comment:
                tok += f' /* {c.comment[:80]} */'
            cols_repr.append(tok)
        head = f'CREATE TABLE {t.original_name}'
        if include_comments and t.comment:
            head += f'  -- {t.comment[:120]}'
        out.append(head + ' (')
        out.append('  ' + ',\n  '.join(cols_repr))
        out.append(');')
    if include_fks and ir.fk_edges:
        out.append('-- FK edges:')
        for e in ir.fk_edges:
            if sel is not None and (e.from_table not in sel or e.to_table not in sel):
                continue
            out.append(f'--   {e.from_table}.{e.from_column} -> {e.to_table}.{e.to_column}')
    return '\n'.join(out)


def serialize(ir: SchemaIR) -> str:
    return json.dumps(ir.to_dict(), ensure_ascii=False, indent=2)


def deserialize(text: str) -> SchemaIR:
    raw = json.loads(text)
    tables = []
    for t in raw.get('tables', []):
        cols = [ColumnMeta(**c) for c in t.get('columns', [])]
        tm = TableMeta(name=t['name'], original_name=t['original_name'],
                        columns=cols, comment=t.get('comment',''),
                        aliases=t.get('aliases',[]),
                        glossary_terms=t.get('glossary_terms',[]),
                        primary_key_columns=t.get('primary_key_columns',[]))
        tables.append(tm)
    fk = [FKEdge(**e) for e in raw.get('fk_edges', [])]
    ev = [EvidenceRef(**e) for e in raw.get('evidence_refs', [])]
    return SchemaIR(db_id=raw['db_id'], dialect=raw['dialect'],
                     tables=tables, fk_edges=fk, evidence_refs=ev,
                     comment=raw.get('comment',''), source=raw.get('source',''))
