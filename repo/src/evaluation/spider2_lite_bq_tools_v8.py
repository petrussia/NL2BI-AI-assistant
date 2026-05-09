"""spider2_lite_bq_tools_v8 — BigQuery executor that runs through the Colab bridge.

Why through bridge: the BQ service-account key lives on Drive, not local
disk, so we keep it there and dispatch SQL via the Colab kernel. The
contract matches `build_bq_executor` from `spider2_tools_v7` so it's a
drop-in for the BQ agent.

executor(sql, *, dry_run=False, max_bytes_billed=..., dialect='bigquery',
           max_rows_override=None) -> dict
    {ok, rows, row_count, bytes_processed, bytes_billed, query_id,
     error_type, error_message, elapsed_ms, mode='bigquery_via_bridge'}

Errors are normalized into a small taxonomy.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parents[3]


def _bridge_url() -> str:
    return (REPO / 'tools' / '.bridge_url').read_text(encoding='utf-8').strip().rstrip('/')


def _bridge_exec(code: str, timeout: int = 120) -> dict:
    payload = json.dumps({'code': code}).encode('utf-8')
    req = urllib.request.Request(_bridge_url() + '/exec', data=payload,
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


_NOT_FOUND_RE = re.compile(r'(not found|does not exist|no such (table|column))', re.IGNORECASE)
_PERM_RE = re.compile(r'(permission denied|access denied|not authorized)', re.IGNORECASE)
_QUOTA_RE = re.compile(r'(quota|exceeded.*bytes_billed|maximum bytes billed)', re.IGNORECASE)
_SYNTAX_RE = re.compile(r'(syntax error|invalid syntax)', re.IGNORECASE)


def _classify_bq_error(et: str, em: str) -> str:
    msg = f'{et}\n{em}'
    if _NOT_FOUND_RE.search(msg): return 'object_not_found'
    if _PERM_RE.search(msg): return 'permission_denied'
    if _QUOTA_RE.search(msg): return 'bytes_billed_exceeded'
    if _SYNTAX_RE.search(msg): return 'syntax'
    return 'unknown'


def build_bq_executor(*, sa_path: str = None,
                        max_bytes_billed: int = 1 * 1024 ** 3,
                        timeout_s: int = 120) -> Callable:
    """Build a BQ executor that talks to BigQuery via the Colab bridge."""
    sa_path = sa_path or '/content/drive/MyDrive/diploma_plan_sql/secrets/spider2_bq_sa.json'

    bootstrap = (
        'import os\n'
        f'os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = {json.dumps(sa_path)}\n'
        'if not globals().get("_BQ_CLIENT"):\n'
        '    from google.cloud import bigquery\n'
        '    globals()["bigquery"] = bigquery\n'
        '    globals()["_BQ_CLIENT"] = bigquery.Client()\n'
        '    print("BQ_CLIENT_PROJECT=", _BQ_CLIENT.project)\n'
    )
    boot_r = _bridge_exec(bootstrap, timeout=120)
    if not boot_r.get('ok'):
        raise RuntimeError(f'bq bootstrap failed: {(boot_r.get("traceback") or "")[:500]}')

    def executor(sql: str, *, dry_run: bool = False,
                  max_bytes_billed_override: int = None,
                  max_rows_override: int = None,
                  dialect: str = 'bigquery') -> dict:
        cap = max_bytes_billed_override or max_bytes_billed
        max_rows = max_rows_override or 1000
        code = (
            'import time, json\n'
            f'_SQL = {json.dumps(sql)}\n'
            f'_DRY = {bool(dry_run)}\n'
            f'_CAP = {int(cap)}\n'
            f'_MAX_ROWS = {int(max_rows)}\n'
            't0 = time.time()\n'
            'res = {"ok": False, "mode": "bigquery_via_bridge"}\n'
            'try:\n'
            '    cfg = bigquery.QueryJobConfig(dry_run=_DRY, use_query_cache=False)\n'
            '    if not _DRY: cfg.maximum_bytes_billed = _CAP\n'
            '    job = _BQ_CLIENT.query(_SQL, job_config=cfg)\n'
            '    if _DRY:\n'
            '        res.update({"ok": True, "bytes_processed": job.total_bytes_processed,\n'
            '                     "query_id": job.job_id,\n'
            '                     "elapsed_ms": int((time.time()-t0)*1000)})\n'
            '    else:\n'
            '        rs = job.result(max_results=_MAX_ROWS)\n'
            '        rows = []\n'
            '        for r in rs: rows.append(dict(r))\n'
            '        res.update({"ok": True, "rows": rows, "row_count": len(rows),\n'
            '                      "bytes_processed": job.total_bytes_processed,\n'
            '                      "bytes_billed": job.total_bytes_billed or 0,\n'
            '                      "query_id": job.job_id,\n'
            '                      "elapsed_ms": int((time.time()-t0)*1000)})\n'
            'except Exception as e:\n'
            '    res.update({"ok": False, "error_type": type(e).__name__,\n'
            '                  "error_message": str(e)[:500],\n'
            '                  "elapsed_ms": int((time.time()-t0)*1000)})\n'
            'print("===BQ_RES===")\n'
            'print(json.dumps(res))\n'
            'print("===BQ_END===")\n'
        )
        try:
            r = _bridge_exec(code, timeout=timeout_s)
        except Exception as exc:
            return {'ok': False, 'error_type': 'bridge_exception',
                     'error_message': f'{type(exc).__name__}: {exc}'[:300],
                     'mode': 'bigquery_via_bridge'}
        out = (r.get('stdout') or '')
        if '===BQ_RES===' in out and '===BQ_END===' in out:
            payload = out.split('===BQ_RES===\n', 1)[1].split('\n===BQ_END===', 1)[0]
            try:
                obj = json.loads(payload)
            except Exception:
                obj = {'ok': False, 'error_type': 'parse',
                        'error_message': payload[:300]}
        else:
            obj = {'ok': False, 'error_type': 'no_response',
                    'error_message': (r.get('traceback') or out)[:300]}
        if not obj.get('ok') and obj.get('error_message'):
            obj['error_type'] = _classify_bq_error(
                obj.get('error_type', ''), obj.get('error_message', ''))
        obj.setdefault('mode', 'bigquery_via_bridge')
        return obj

    return executor
