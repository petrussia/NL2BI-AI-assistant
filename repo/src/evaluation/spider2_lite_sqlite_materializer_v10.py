"""spider2_lite_sqlite_materializer_v10 — F4 fix: build .sqlite from JSON stubs.

Spider2-Lite ships SQLite "stub" databases as per-table row-level JSON
files plus a `DDL.csv` that describes column types — there is NO actual
`.sqlite` binary on disk. The v8/v9 SQLite executor opened a path that
never existed, hence `sqlite_db_missing` failures even with the
case-insensitive resolver.

This module builds an actual `<DB>.sqlite` once per DB on local disk,
deterministic, idempotent, then `spider2_lite_sqlite_tools_v8` can run
against it.

Layout on Drive:
    resource/databases/sqlite/<DB_DISK>/DDL.csv
    resource/databases/sqlite/<DB_DISK>/<table>.json   (one per table)

Each `<table>.json` is a list of row dicts (sample rows). DDL.csv has
columns:  table_name, column_name, column_type, sample_values, primary_key, foreign_key...

Local layout (after materialization):
    data/spider2_lite/resource/databases/sqlite/<DB_DISK>/<DB_DISK>.sqlite

`resolve_sqlite_db(db_dataset_id)` returns the local .sqlite path or
None. Includes a 30-entry alias map for known dataset⇄disk mismatches
(e.g. `Db-IMDB` → `DB_IMDB`, `sqlite-sakila` → `SQLITE_SAKILA`).

All results from running queries against this db are NON-COMPARABLE to
official EX (sample data only). That flag is set by the executor.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
import urllib.request
from pathlib import Path
from dataclasses import dataclass

REPO = Path(__file__).resolve().parents[3]
LOCAL_BASE = REPO / 'data' / 'spider2_lite' / 'resource' / 'databases' / 'sqlite'


_KNOWN_ALIASES: dict[str, str] = {
    # dataset.db -> disk dir
    'Db-IMDB': 'DB_IMDB',
    'sqlite-sakila': 'SQLITE_SAKILA',
}


def _bridge_url() -> str:
    return (REPO / 'tools' / '.bridge_url').read_text(encoding='utf-8').strip().rstrip('/')


def _bridge_exec(code: str, timeout: int = 120) -> dict:
    payload = json.dumps({'code': code}).encode('utf-8')
    req = urllib.request.Request(_bridge_url() + '/exec', data=payload,
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


@dataclass
class ResolveResult:
    dataset_db: str
    disk_db: str | None
    local_sqlite: Path | None
    n_tables: int = 0
    n_rows_total: int = 0
    error: str = ''


_TYPE_MAP = {
    'int': 'INTEGER', 'integer': 'INTEGER', 'bigint': 'INTEGER',
    'smallint': 'INTEGER', 'tinyint': 'INTEGER',
    'real': 'REAL', 'float': 'REAL', 'double': 'REAL', 'numeric': 'REAL',
    'decimal': 'REAL',
    'text': 'TEXT', 'varchar': 'TEXT', 'char': 'TEXT', 'string': 'TEXT',
    'datetime': 'TEXT', 'timestamp': 'TEXT', 'date': 'TEXT', 'time': 'TEXT',
    'boolean': 'INTEGER', 'bool': 'INTEGER',
    'blob': 'BLOB',
}


def _sqlite_type(t: str) -> str:
    if not t: return 'TEXT'
    t_low = t.lower().strip()
    for k, v in _TYPE_MAP.items():
        if t_low.startswith(k): return v
    return 'TEXT'


def _quote_id(name: str) -> str:
    return '"' + (name or '').replace('"', '""') + '"'


def _list_disk_dbs() -> list[str]:
    code = ('import os, json\n'
            'BASE = "/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/sqlite"\n'
            'print(json.dumps(sorted(os.listdir(BASE)) if os.path.isdir(BASE) else []))\n')
    r = _bridge_exec(code, timeout=60)
    out = (r.get('stdout') or '').strip()
    try:
        return json.loads(out.split('\n')[-1])
    except Exception:
        return []


def _resolve_disk_db(dataset_db: str, disk_dirs: list[str]) -> str | None:
    if dataset_db in disk_dirs: return dataset_db
    if dataset_db in _KNOWN_ALIASES: return _KNOWN_ALIASES[dataset_db]
    for d in disk_dirs:
        if d.lower() == dataset_db.lower(): return d
    nd = dataset_db.lower().replace('_', '').replace('-', '')
    for d in disk_dirs:
        if d.lower().replace('_', '').replace('-', '') == nd:
            return d
    return None


def _fetch_db_payload(disk_db: str) -> dict | None:
    """Return {'ddl_csv': str, 'tables': {name: rows[]}}."""
    code = ('import os, json, csv\n'
            f'BASE = "/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/sqlite/{disk_db}"\n'
            'out = {"ddl_csv": "", "tables": {}}\n'
            'ddl = os.path.join(BASE, "DDL.csv")\n'
            'if os.path.isfile(ddl):\n'
            '    out["ddl_csv"] = open(ddl, encoding="utf-8", errors="replace").read()\n'
            'for f in sorted(os.listdir(BASE)) if os.path.isdir(BASE) else []:\n'
            '    if not f.endswith(".json"): continue\n'
            '    p = os.path.join(BASE, f)\n'
            '    try:\n'
            '        d = json.load(open(p, encoding="utf-8"))\n'
            '    except Exception:\n'
            '        continue\n'
            '    name = f[:-5]\n'
            '    if isinstance(d, list):\n'
            '        out["tables"][name] = d\n'
            '    elif isinstance(d, dict) and "sample_rows" in d:\n'
            '        out["tables"][name] = d["sample_rows"]\n'
            '    else:\n'
            '        out["tables"][name] = []\n'
            'print("===PAYLOAD_START===")\n'
            'print(json.dumps(out, ensure_ascii=False))\n'
            'print("===PAYLOAD_END===")\n')
    r = _bridge_exec(code, timeout=180)
    out = (r.get('stdout') or '')
    if '===PAYLOAD_START===' not in out: return None
    payload_str = out.split('===PAYLOAD_START===\n', 1)[1].split('\n===PAYLOAD_END===', 1)[0]
    try:
        return json.loads(payload_str)
    except Exception:
        return None


def _ddl_columns_for(ddl_csv: str, table_name: str) -> list[tuple[str, str]]:
    """Return list of (col, sqlite_type) for the table from DDL.csv."""
    cols: list[tuple[str, str]] = []
    if not ddl_csv: return cols
    rdr = csv.DictReader(io.StringIO(ddl_csv))
    for row in rdr:
        # heuristic field names — Spider2 DDL.csv layout varies a bit
        tn = (row.get('table_name') or row.get('table') or '').strip()
        cn = (row.get('column_name') or row.get('column') or '').strip()
        ct = (row.get('column_type') or row.get('type') or 'TEXT').strip()
        if tn.lower() == table_name.lower() and cn:
            cols.append((cn, _sqlite_type(ct)))
    return cols


def materialize_sqlite_from_payload(payload: dict, target: Path) -> tuple[int, int]:
    """Build a fresh .sqlite from the {ddl_csv, tables} payload.
    Returns (n_tables_created, n_rows_inserted)."""
    if target.exists(): target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    cur = conn.cursor()
    n_tables = 0; n_rows = 0
    ddl_csv = payload.get('ddl_csv', '')
    for tname, rows in (payload.get('tables') or {}).items():
        # Determine columns: prefer DDL, fallback to first row keys
        cols = _ddl_columns_for(ddl_csv, tname)
        if not cols and rows and isinstance(rows[0], dict):
            cols = [(c, 'TEXT') for c in rows[0].keys()]
        if not cols: continue
        cols_sql = ', '.join(f'{_quote_id(c)} {t}' for c, t in cols)
        try:
            cur.execute(f'CREATE TABLE IF NOT EXISTS {_quote_id(tname)} ({cols_sql})')
        except Exception:
            continue
        n_tables += 1
        # Insert rows
        col_names = [c for c, _ in cols]
        ph = ', '.join('?' for _ in col_names)
        col_list_sql = ', '.join(_quote_id(c) for c in col_names)
        for r in rows:
            if not isinstance(r, dict): continue
            vals = [r.get(c) for c in col_names]
            try:
                cur.execute(f'INSERT INTO {_quote_id(tname)} ({col_list_sql}) VALUES ({ph})',
                              vals)
                n_rows += 1
            except Exception:
                continue
    conn.commit()
    conn.close()
    return n_tables, n_rows


def resolve_sqlite_db(dataset_db: str) -> ResolveResult:
    """Resolve dataset_db → local .sqlite path. Builds it if missing.
    Returns ResolveResult with paths and stats.
    """
    disk_dirs = _list_disk_dbs()
    disk = _resolve_disk_db(dataset_db, disk_dirs)
    if disk is None:
        return ResolveResult(dataset_db=dataset_db, disk_db=None,
                             local_sqlite=None,
                             error=f'no disk match (tried alias/case/normalize); disk has {len(disk_dirs)} dirs')
    local_dir = LOCAL_BASE / disk
    target = local_dir / f'{disk}.sqlite'
    if target.exists():
        # Cache hit; count tables for sanity
        try:
            conn = sqlite3.connect(str(target))
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            n_t = cur.fetchone()[0]
            conn.close()
            return ResolveResult(dataset_db=dataset_db, disk_db=disk,
                                 local_sqlite=target, n_tables=n_t)
        except Exception as exc:
            return ResolveResult(dataset_db=dataset_db, disk_db=disk,
                                 local_sqlite=target,
                                 error=f'cached but unreadable: {exc!r}')
    payload = _fetch_db_payload(disk)
    if not payload:
        return ResolveResult(dataset_db=dataset_db, disk_db=disk,
                             local_sqlite=None,
                             error='fetch_payload_failed')
    n_t, n_r = materialize_sqlite_from_payload(payload, target)
    return ResolveResult(dataset_db=dataset_db, disk_db=disk,
                         local_sqlite=target if target.exists() else None,
                         n_tables=n_t, n_rows_total=n_r)
