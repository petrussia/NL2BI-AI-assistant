"""sqlite_lane_resolver_v9 — robust per-task SQLite db path resolution.

Pilot v8: `local002` task with `db=E_commerce` failed because the
canonical path on Drive uses different casing / nested layout. We try
several path patterns and fall through case-insensitive listing.

Local cache: `data/spider2_lite/resource/databases/sqlite/<DB>/<DB>.sqlite`.

Important: Spider2-Lite SQLite databases are *sample-rows stubs*, not
the real data. The resolver flags every result with
`non_comparable=True`. The runner MUST treat SQLite execute_ok as a
parsing-quality signal only, never as official EX.
"""
from __future__ import annotations

import base64
import json
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LOCAL_SQLITE = REPO / 'data' / 'spider2_lite' / 'resource' / 'databases' / 'sqlite'


def _bridge_url() -> str:
    return (REPO / 'tools' / '.bridge_url').read_text(encoding='utf-8').strip().rstrip('/')


def _bridge_exec(code: str, timeout: int = 90) -> dict:
    payload = json.dumps({'code': code}).encode('utf-8')
    req = urllib.request.Request(_bridge_url() + '/exec', data=payload,
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def resolve_sqlite_db(db: str) -> Path | None:
    """Try multiple path/casing combinations on Drive; cache locally.
    Returns the local path or None if not found.
    """
    target_dir = LOCAL_SQLITE / db
    target = target_dir / f'{db}.sqlite'
    if target.exists():
        return target

    candidates = [db, db.lower(), db.upper(), db.title(),
                   db.replace('_', ''), db.replace('-', '_')]
    seen = set()
    cand_pruned = [c for c in candidates if not (c in seen or seen.add(c))]

    code = ('import os, base64, json\n'
            f'CANDS = {json.dumps(cand_pruned)}\n'
            'BASE = "/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/sqlite"\n'
            'found = None\n'
            'for c in CANDS:\n'
            '    p = os.path.join(BASE, c, c + ".sqlite")\n'
            '    if os.path.isfile(p):\n'
            '        found = p; break\n'
            '    # Try case-insensitive dir listing fallback\n'
            '    if os.path.isdir(BASE):\n'
            '        for d in os.listdir(BASE):\n'
            '            if d.lower() == c.lower():\n'
            '                inner = os.path.join(BASE, d)\n'
            '                if os.path.isdir(inner):\n'
            '                    for f in os.listdir(inner):\n'
            '                        if f.lower().endswith(".sqlite"):\n'
            '                            found = os.path.join(inner, f); break\n'
            '                    if found: break\n'
            '        if found: break\n'
            'if not found:\n'
            '    print(json.dumps({"ok": False, "tried": CANDS}))\n'
            'else:\n'
            '    sz = os.path.getsize(found)\n'
            '    print(json.dumps({"ok": True, "src": found, "size": sz}))\n')
    try:
        r = _bridge_exec(code, timeout=120)
    except Exception:
        return None
    out = (r.get('stdout') or '').strip()
    try:
        meta = json.loads(out.split('\n')[-1])
    except Exception:
        return None
    if not meta.get('ok'):
        return None

    # Now stream the file via base64
    src = meta['src']
    code2 = ('import base64\n'
             f'with open({json.dumps(src)}, "rb") as f: data = f.read()\n'
             'print("===B64START===")\n'
             'print(base64.b64encode(data).decode())\n'
             'print("===B64END===")\n')
    try:
        r2 = _bridge_exec(code2, timeout=180)
    except Exception:
        return None
    out2 = (r2.get('stdout') or '')
    if '===B64START===' not in out2:
        return None
    b64 = out2.split('===B64START===\n', 1)[1].split('\n===B64END===', 1)[0]
    target_dir.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64decode(b64))
    return target
