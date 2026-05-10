"""Phase 23 STAGE 0 — comprehensive bridge-side infra check.

Run via: python tools/exec_remote.py --code-file tools/remote_scripts/_phase23_infra_check.py

Probes:
- Models loaded (planner + emitter)
- BQ auth (dry_run on a tiny query)
- Snow auth (SELECT 1 / EXPLAIN)
- Datasets present on Drive
- Live catalogs present
- Disk space

Returns a single dict printed as JSON.
"""
import os
import sys
import json
import time
import traceback
from pathlib import Path

g = globals()
out = {'ts': int(time.time()), 'checks': {}}


def _check(name, fn):
    try:
        out['checks'][name] = {'ok': True, 'value': fn()}
    except Exception as e:
        out['checks'][name] = {'ok': False, 'error': f'{type(e).__name__}: {str(e)[:300]}'}


# 1. Drive root
DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
_check('drive_root', lambda: DRV.exists())

# 2. Datasets
LITE = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl'
SNOW = DRV / 'external_benchmarks/spider2_snow/raw/Spider2/spider2-snow/spider2-snow.jsonl'

def _count_jsonl(p):
    if not p.exists():
        return {'exists': False}
    n = 0
    with open(p, 'r', encoding='utf-8') as f:
        for _ in f:
            n += 1
    return {'exists': True, 'rows': n, 'size_kb': p.stat().st_size // 1024}

_check('lite_jsonl', lambda: _count_jsonl(LITE))
_check('snow_jsonl', lambda: _count_jsonl(SNOW))

# 3. Live catalogs
BQ_CAT = DRV / 'outputs/cache/spider2_bq_live_catalog_v18.jsonl'
SNOW_CAT = DRV / 'outputs/cache/spider2_snow_live_catalog_v18.jsonl'
_check('bq_catalog', lambda: _count_jsonl(BQ_CAT))
_check('snow_catalog', lambda: _count_jsonl(SNOW_CAT))

# 4. Models loaded?
def _model_state():
    res = {}
    for k in ['_MDL_EMIT', '_MDL_PLAN', '_TOK_EMIT', '_TOK_PLAN', '_PROF_EMIT', '_PROF_PLAN', '_V18_MODELS_READY']:
        v = g.get(k)
        if v is None:
            res[k] = None
        elif hasattr(v, 'name_or_path'):
            res[k] = str(getattr(v, 'name_or_path', type(v).__name__))
        elif isinstance(v, dict):
            res[k] = {kk: str(vv)[:120] for kk, vv in v.items()}
        else:
            res[k] = type(v).__name__
    # GPU
    try:
        import torch
        res['cuda_avail'] = torch.cuda.is_available()
        if torch.cuda.is_available():
            res['cuda_devices'] = torch.cuda.device_count()
            res['cuda_mem_alloc_GB'] = round(torch.cuda.memory_allocated() / (1024 ** 3), 2)
            res['cuda_mem_reserved_GB'] = round(torch.cuda.memory_reserved() / (1024 ** 3), 2)
    except Exception as e:
        res['cuda_err'] = str(e)
    return res

_check('models', _model_state)

# 5. BQ probe
def _bq_probe():
    from google.cloud import bigquery
    c = bigquery.Client()
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    job = c.query("SELECT 1 AS x", job_config=job_config)
    return {'project': c.project, 'dry_run_bytes': job.total_bytes_processed}

_check('bq_dry_run_probe', _bq_probe)

# 6. Snow probe
def _snow_probe():
    import snowflake.connector
    user = os.environ.get('SNOWFLAKE_USER') or os.environ.get('SNOW_USER')
    acct = os.environ.get('SNOWFLAKE_ACCOUNT') or os.environ.get('SNOW_ACCOUNT')
    pwd = os.environ.get('SNOWFLAKE_PASSWORD') or os.environ.get('SNOW_PASSWORD')
    pem = os.environ.get('SNOWFLAKE_PRIVATE_KEY_PATH')
    auth = {}
    if pem:
        auth['private_key_path'] = pem
    elif pwd:
        auth['password'] = pwd
    conn = snowflake.connector.connect(user=user, account=acct, **auth)
    try:
        cur = conn.cursor()
        cur.execute('SELECT CURRENT_VERSION(), CURRENT_USER(), CURRENT_ACCOUNT()')
        row = cur.fetchone()
        return {'version': str(row[0]), 'user': str(row[1]), 'account': str(row[2])}
    finally:
        conn.close()

_check('snow_probe', _snow_probe)

# 7. Spider2 Snow snapshots / DB roots
SNOW_DB_ROOT = DRV / 'external_benchmarks/spider2_snow/resource/databases'
_check('snow_db_root', lambda: {'exists': SNOW_DB_ROOT.exists(),
                                  'children': sorted([p.name for p in SNOW_DB_ROOT.iterdir()][:20]) if SNOW_DB_ROOT.exists() else []})

# 8. v22 runs present (sanity)
RUNS = DRV / 'outputs/spider2_lite/runs'
_check('runs_dir', lambda: {'exists': RUNS.exists(),
                              'children': sorted([p.name for p in RUNS.iterdir()][-12:]) if RUNS.exists() else []})

# 9. Free disk
import shutil
_check('disk_free', lambda: {'GB_free': round(shutil.disk_usage('/content').free / (1024 ** 3), 1)})

# 10. v18 evaluation modules
EVAL_DIR = DRV / 'repo/src/evaluation'
_check('eval_modules', lambda: sorted([p.name for p in EVAL_DIR.glob('*v18*.py')]))

print('PHASE23_INFRA_CHECK_BEGIN')
print(json.dumps(out, indent=2, default=str))
print('PHASE23_INFRA_CHECK_END')
