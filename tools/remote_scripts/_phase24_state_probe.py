"""Phase 24 STAGE 0 — state probe.
Reports GPU memory, alive BG threads from prior phase, BQ auth, Snow auth.
Does NOT touch any model or run.
"""
import os, json, time, gc, threading
from pathlib import Path

g = globals()
out = {'ts': int(time.time()), 'checks': {}}


def _check(name, fn):
    try:
        out['checks'][name] = {'ok': True, 'value': fn()}
    except Exception as e:
        out['checks'][name] = {'ok': False, 'error': f'{type(e).__name__}: {str(e)[:300]}'}


# Models loaded?
def _model_state():
    res = {}
    for k in ['_MDL_PLAN', '_MDL_EMIT', '_TOK_PLAN', '_TOK_EMIT', '_V18_MODELS_READY']:
        v = g.get(k)
        res[k] = (str(getattr(v, 'name_or_path', None)) if v is not None and hasattr(v, 'name_or_path') else type(v).__name__ if v is not None else None)
    try:
        import torch
        res['cuda_avail'] = torch.cuda.is_available()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
            free, total = torch.cuda.mem_get_info()
            res['cuda_mem_free_GB'] = round(free / (1024 ** 3), 2)
            res['cuda_mem_total_GB'] = round(total / (1024 ** 3), 2)
            res['cuda_mem_alloc_GB'] = round(torch.cuda.memory_allocated() / (1024 ** 3), 2)
    except Exception as e:
        res['cuda_err'] = str(e)
    return res

_check('models_and_gpu', _model_state)

# Threads
def _threads():
    ts = []
    for t in threading.enumerate():
        ts.append({'name': t.name, 'alive': t.is_alive(), 'daemon': t.daemon})
    runners = [t['name'] for t in ts if '_runner' in t['name']]
    return {'count': len(ts), 'runners': runners, 'all_names': sorted(t['name'] for t in ts)}

_check('threads', _threads)

# Phase 23 BG run progress
def _phase23_runs():
    DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
    res = {}
    for run, base in [
        ('bq', DRV / 'outputs/spider2_lite/runs/lite_full_diagnostic_v23_bq'),
        ('snow', DRV / 'outputs/spider2_snow/runs/snow_full_diagnostic_v23'),
        ('lite_snow', DRV / 'outputs/spider2_lite/runs/lite_full_diagnostic_v23_snow')]:
        if not base.is_dir():
            res[run] = 'missing'; continue
        prog = base / 'progress.json'
        done = base / '_DONE'; failed = base / '_FAILED'; cancelled = base / '_CANCELLED_OOM'
        rd = {'done': done.is_file(), 'failed': failed.is_file(), 'cancelled': cancelled.is_file()}
        if prog.is_file():
            try:
                p = json.loads(prog.read_text())
                rd['n_total'] = p.get('n_total'); rd['last_task'] = p.get('last_task'); rd['wall_sec'] = p.get('wall_sec')
                rd['err_top'] = p.get('err_top', [])[:3]
            except Exception:
                pass
        res[run] = rd
    return res

_check('phase23_runs', _phase23_runs)

# BQ auth probe
def _bq_probe():
    from google.cloud import bigquery
    c = bigquery.Client()
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    job = c.query('SELECT 1 AS x', job_config=job_config)
    return {'project': c.project, 'dry_run_bytes': job.total_bytes_processed}

_check('bq_dry_run_probe', _bq_probe)

# Snow probe (we DO want to know if it's authenticated, even though we won't run Snow)
def _snow_probe():
    import snowflake.connector
    user = os.environ.get('SNOWFLAKE_USER') or os.environ.get('SNOW_USER')
    acct = os.environ.get('SNOWFLAKE_ACCOUNT') or os.environ.get('SNOW_ACCOUNT')
    pwd = os.environ.get('SNOWFLAKE_PASSWORD') or os.environ.get('SNOW_PASSWORD')
    pem = os.environ.get('SNOWFLAKE_PRIVATE_KEY_PATH')
    auth = {}
    if pem: auth['private_key_path'] = pem
    elif pwd: auth['password'] = pwd
    if not user or not acct:
        return {'auth_unset': True, 'user_set': bool(user), 'acct_set': bool(acct)}
    conn = snowflake.connector.connect(user=user, account=acct, **auth)
    try:
        cur = conn.cursor()
        cur.execute('SELECT CURRENT_VERSION()')
        return {'version': str(cur.fetchone()[0])}
    finally:
        conn.close()

_check('snow_auth', _snow_probe)

# Lock dir on Drive
DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
LOCK_DIR = DRV / 'outputs/runtime'
def _lock_state():
    res = {'lock_dir_exists': LOCK_DIR.is_dir()}
    if LOCK_DIR.is_dir():
        res['contents'] = sorted([p.name for p in LOCK_DIR.iterdir()])
    return res

_check('gpu_lock_dir', _lock_state)

print('PHASE24_STATE_BEGIN')
print(json.dumps(out, indent=2, default=str))
print('PHASE24_STATE_END')
