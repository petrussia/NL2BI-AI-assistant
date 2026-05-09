"""spider2_lite_sqlite_tools_v8 — SQLite stub executor for Spider2-Lite.

The Spider2 repo ships a sample-rows-only SQLite DB per `local*` task.
Real EX comparison against gold rows is *not* meaningful (the stub has
~5 sample rows per table). This executor still parses the SQL and runs
it for parse/execute_ok logging, but every result is flagged
`non_comparable=True`.

Path layout on Drive (mirrors Spider2 repo):
  resource/databases/sqlite/<DB>/<DB>.sqlite

We stream the .sqlite file via the bridge once per DB, cache locally,
and run via stdlib `sqlite3`. No write side effects.
"""
from __future__ import annotations

import base64
import json
import re
import sqlite3
import time
import urllib.request
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parents[3]
LOCAL_SQLITE = REPO / 'data' / 'spider2_lite' / 'resource' / 'databases' / 'sqlite'


def _bridge_url() -> str:
    return (REPO / 'tools' / '.bridge_url').read_text(encoding='utf-8').strip().rstrip('/')


def _bridge_exec(code: str, timeout: int = 120) -> dict:
    payload = json.dumps({'code': code}).encode('utf-8')
    req = urllib.request.Request(_bridge_url() + '/exec', data=payload,
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def fetch_sqlite_db(db: str) -> Path | None:
    """Lazy-pull the per-DB .sqlite file from Drive."""
    target_dir = LOCAL_SQLITE / db
    target = target_dir / f'{db}.sqlite'
    if target.exists():
        return target
    target_dir.mkdir(parents=True, exist_ok=True)
    code = (
        'import os, base64, json\n'
        f'SRC = "/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/sqlite/{db}/{db}.sqlite"\n'
        'if not os.path.isfile(SRC):\n'
        '    print(json.dumps({"ok": False, "err": "no_src", "src": SRC}))\n'
        'else:\n'
        '    with open(SRC, "rb") as f:\n'
        '        b = f.read()\n'
        '    print(json.dumps({"ok": True, "size": len(b),\n'
        '                       "b64": base64.b64encode(b).decode()}))\n'
    )
    r = _bridge_exec(code, timeout=120)
    out = (r.get('stdout') or '').strip()
    try:
        obj = json.loads(out.split('\n')[-1])
    except Exception:
        return None
    if not obj.get('ok'):
        return None
    target.write_bytes(base64.b64decode(obj['b64']))
    return target


_SYNTAX_RE = re.compile(r'(syntax error|near .*: syntax error)', re.IGNORECASE)
_NOTABLE_RE = re.compile(r'no such (table|column)', re.IGNORECASE)


def build_sqlite_executor(db: str, *, max_rows: int = 1000,
                            timeout_s: int = 30) -> Callable:
    """Returns an executor compatible with the BQ/SF executor contract.
    Always emits non_comparable=True in result.
    """
    db_path = fetch_sqlite_db(db)

    def executor(sql: str, *, dry_run: bool = False,
                  max_rows_override: int = None,
                  dialect: str = 'sqlite', **kw) -> dict:
        t0 = time.time()
        if not db_path or not db_path.exists():
            return {'ok': False, 'error_type': 'sqlite_db_missing',
                     'error_message': f'no sqlite for {db}',
                     'non_comparable': True, 'mode': 'sqlite_stub'}
        try:
            conn = sqlite3.connect(str(db_path), timeout=timeout_s,
                                       check_same_thread=False)
            cur = conn.cursor()
            if dry_run:
                # Use EXPLAIN to validate parseability without executing
                cur.execute('EXPLAIN ' + sql)
                _ = cur.fetchone()
                return {'ok': True, 'mode': 'sqlite_stub',
                         'non_comparable': True,
                         'elapsed_ms': int((time.time() - t0) * 1000)}
            cur.execute(sql)
            rows = cur.fetchmany(max_rows_override or max_rows)
            cols = [d[0] for d in (cur.description or [])]
            row_dicts = [dict(zip(cols, r)) for r in rows]
            return {'ok': True, 'rows': row_dicts, 'row_count': len(row_dicts),
                     'mode': 'sqlite_stub', 'non_comparable': True,
                     'elapsed_ms': int((time.time() - t0) * 1000)}
        except Exception as exc:
            msg = str(exc)
            et = 'syntax' if _SYNTAX_RE.search(msg) else (
                  'object_not_found' if _NOTABLE_RE.search(msg) else
                  type(exc).__name__)
            return {'ok': False, 'error_type': et, 'error_message': msg[:300],
                     'mode': 'sqlite_stub', 'non_comparable': True,
                     'elapsed_ms': int((time.time() - t0) * 1000)}
        finally:
            try: conn.close()
            except Exception: pass

    return executor
