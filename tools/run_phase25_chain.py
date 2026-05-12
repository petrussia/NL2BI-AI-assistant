"""Phase 25 sequential chain runner.

Polls Lite-BQ FULL on bridge → when DONE, kicks off Spider2-Snow FULL
on bridge → when DONE, kicks off DBT FULL ablation locally.

Designed to run as a long-lived background process. Writes chain
progress to outputs/logs/spider2_phase25_chain_progress.json (overwritten
each tick) and stage transitions to outputs/logs/spider2_phase25_chain.log
(append-only).

Failure policy:
  - Per-stage `_FAILED` marker → log + skip remaining stages of that
    benchmark (do NOT abort the whole chain).
  - Lock acquisition failure → wait 60s and retry up to 5×.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

LOG_DIR = REPO / 'outputs' / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
PROGRESS_PATH = LOG_DIR / 'spider2_phase25_chain_progress.json'
LOG_PATH = LOG_DIR / 'spider2_phase25_chain.log'

LITE_BQ_RUN_ID = 'lite_bq_full_v25'
SNOW_RUN_ID = 'snow_full_v25'
DBT_RUN_ID = 'dbt_full_v25'

POLL_INTERVAL_SEC = 60
MAX_WALL_SEC = 24 * 3600  # 24h cap on whole chain

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


def bridge_url():
    return (REPO / 'tools' / '.bridge_url').read_text(encoding='utf-8').strip().rstrip('/')


def bridge_exec(code, timeout=60):
    payload = json.dumps({'code': code}).encode('utf-8')
    req = urllib.request.Request(bridge_url() + '/exec', data=payload,
                                  headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        return {'ok': False, 'error': f'{type(e).__name__}: {e}'}


def log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    line = f'[{ts}] {msg}'
    print(line, flush=True)
    with LOG_PATH.open('a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def write_progress(d):
    PROGRESS_PATH.write_text(json.dumps(d, indent=2, default=str), encoding='utf-8')


def poll_bridge_run(run_id, status_fn_name, status_fn_arg=None):
    """Poll the bridge for a given run via status function."""
    arg = repr(status_fn_arg) if status_fn_arg else repr(run_id)
    code = (
        f'import json\n'
        f'_st = {status_fn_name}({arg})\n'
        f"print('===STATUS==='); print(json.dumps(_st, default=str)); print('===END===')\n"
    )
    r = bridge_exec(code, timeout=30)
    if not r.get('ok'):
        return None
    out = r.get('stdout', '')
    if '===STATUS===' not in out:
        return None
    try:
        return json.loads(out.split('===STATUS===\n', 1)[1].split('\n===END===', 1)[0])
    except Exception:
        return None


def stage_lite_bq():
    """Wait for already-running Lite-BQ FULL v25."""
    log('STAGE 1 (Lite-BQ FULL): polling existing run')
    t0 = time.time()
    last_n = -1
    while time.time() - t0 < MAX_WALL_SEC:
        s = poll_bridge_run(LITE_BQ_RUN_ID, 'v24_status')
        if s is None:
            log('  poll failed; sleep 60s')
            time.sleep(60); continue
        n = s.get('n_predictions', 0)
        if n != last_n:
            prog = s.get('progress') or {}
            log(f"  n={n}/205 sv={prog.get('schema_valid',0)} "
                f"exec={prog.get('execute_ok',0)} wall={prog.get('wall_sec',0)}s "
                f"last={prog.get('last_task','?')}")
            last_n = n
            write_progress({'stage': 'lite_bq', 'status': s,
                              'phase': 'running'})
        if s.get('done'):
            log(f"STAGE 1 DONE: {s.get('summary')}")
            write_progress({'stage': 'lite_bq', 'status': s, 'phase': 'done'})
            return True
        if s.get('failed'):
            log(f"STAGE 1 FAILED: {s.get('failure')}")
            write_progress({'stage': 'lite_bq', 'status': s, 'phase': 'failed'})
            return False
        time.sleep(POLL_INTERVAL_SEC)
    log('STAGE 1 TIMEOUT')
    return False


def stage_snow():
    """Launch Spider2-Snow FULL v25 then poll."""
    log('STAGE 2 (Spider2-Snow FULL): launching on bridge')
    # Re-upload Snow runner (in case kernel rotated)
    snow_runner_path = REPO / 'tools' / 'remote_scripts' / '_phase25_snow_full_runner.py'
    upload_code = snow_runner_path.read_text(encoding='utf-8')
    r = bridge_exec(upload_code, timeout=60)
    if not r.get('ok'):
        log(f"STAGE 2 launch failed: bridge upload error: {r.get('error')}")
        return False
    if 'PHASE25_SNOW_RUNNER_REGISTERED' not in r.get('stdout', ''):
        log(f"STAGE 2 launch failed: runner upload incomplete; tail: {r.get('stdout','')[-400:]}")
        return False

    # Verify Snow auth env is still set
    auth_check = bridge_exec(
        "import os\nprint('SNOWFLAKE_USER' in os.environ, 'SNOWFLAKE_PASSWORD' in os.environ)",
        timeout=20)
    log(f'  snow auth env present: {auth_check.get("stdout","").strip()}')

    # Kick off Snow FULL
    launch_code = (
        f'_r = _PHASE25_START_SNOW_FULL({SNOW_RUN_ID!r})\n'
        f'import json; print("===KICK==="); print(json.dumps(_r, default=str)); print("===END===")\n'
    )
    r = bridge_exec(launch_code, timeout=30)
    if '===KICK===' not in r.get('stdout', ''):
        log(f'STAGE 2 KICK failed: tail: {r.get("stdout","")[-400:]}')
        return False
    kick = json.loads(r['stdout'].split('===KICK===\n', 1)[1].split('\n===END===', 1)[0])
    log(f'STAGE 2 kicked: {kick}')
    if not kick.get('started'):
        log(f"STAGE 2 lock failure: {kick.get('lock_failure')}")
        return False

    # Poll
    t0 = time.time()
    last_n = -1
    while time.time() - t0 < MAX_WALL_SEC:
        s = poll_bridge_run(SNOW_RUN_ID, 'v25_snow_status')
        if s is None:
            log('  snow poll failed; sleep 60s')
            time.sleep(60); continue
        n = s.get('n_predictions', 0)
        if n != last_n:
            prog = s.get('progress') or {}
            log(f"  n={n}/547 sv={prog.get('schema_valid',0)} "
                f"exec={prog.get('execute_ok',0)} wall={prog.get('wall_sec',0)}s "
                f"last={prog.get('last_task','?')}")
            last_n = n
            write_progress({'stage': 'snow', 'status': s, 'phase': 'running'})
        if s.get('done'):
            log(f"STAGE 2 DONE: {s.get('summary')}")
            write_progress({'stage': 'snow', 'status': s, 'phase': 'done'})
            return True
        if s.get('failed'):
            log(f"STAGE 2 FAILED: {s.get('failure')}")
            write_progress({'stage': 'snow', 'status': s, 'phase': 'failed'})
            return False
        time.sleep(POLL_INTERVAL_SEC)
    log('STAGE 2 TIMEOUT')
    return False


def stage_dbt():
    """Launch DBT v4 ablation locally."""
    log('STAGE 3 (DBT FULL 68): launching local ablation')
    tasks_path = REPO / '_all_68.txt'
    if not tasks_path.is_file():
        log('STAGE 3 FAILED: _all_68.txt missing')
        return False
    tasks = tasks_path.read_text(encoding='utf-8').strip().split()
    cmd = [sys.executable, str(REPO / 'spider2_dbt_bridge' / 'run_dbt_ablation.py'),
            '--tasks'] + tasks + ['--variants', 'v4', '--max-new', '1500',
                                       '--run-id', DBT_RUN_ID]
    log(f'  cmd: {" ".join(cmd[:6])} ... ({len(tasks)} tasks)')
    log_p = REPO / 'outputs' / 'spider2_dbt' / 'runs' / DBT_RUN_ID
    log_p.mkdir(parents=True, exist_ok=True)
    runlog = log_p / '_runlog.txt'
    with runlog.open('w', encoding='utf-8') as fh:
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT)
    log(f'  DBT subprocess PID: {proc.pid}; log: {runlog}')
    write_progress({'stage': 'dbt', 'phase': 'running', 'pid': proc.pid,
                      'log': str(runlog)})
    rc = proc.wait()
    log(f'STAGE 3 exit code: {rc}')
    write_progress({'stage': 'dbt', 'phase': 'done' if rc == 0 else 'failed',
                      'rc': rc})
    return rc == 0


def main():
    log('=== PHASE 25 CHAIN START ===')
    log_lite = stage_lite_bq()
    log(f'STAGE 1 (Lite-BQ) → {"OK" if log_lite else "FAIL/skip"}')

    log_snow = stage_snow()
    log(f'STAGE 2 (Snow) → {"OK" if log_snow else "FAIL/skip"}')

    log_dbt = stage_dbt()
    log(f'STAGE 3 (DBT) → {"OK" if log_dbt else "FAIL/skip"}')

    log('=== PHASE 25 CHAIN END ===')
    log(f'  lite_bq={log_lite} snow={log_snow} dbt={log_dbt}')
    return 0 if (log_lite and log_snow and log_dbt) else 1


if __name__ == '__main__':
    sys.exit(main())
