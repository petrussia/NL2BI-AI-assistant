"""Phase 25 — bridge-side chain daemon.

Runs as a daemon thread inside the bridge kernel. Survives even if the
local poller dies (which it has, repeatedly). Sequence:

  1. Wait until lite_bq_full_v25/_DONE exists on Drive.
  2. Kick off snow_full_v25 (uses _PHASE25_START_SNOW_FULL).
  3. Wait until snow_full_v25/_DONE exists.
  4. Write a "ready for dbt" marker so the local poller knows.

DBT FULL is launched locally after step 4 (separate process; needs
remote SSH to dbt server).
"""
import threading, time, json
from pathlib import Path

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
LITE_BQ_DIR = DRV / 'outputs/spider2_lite/runs/lite_bq_full_v25'
SNOW_DIR = DRV / 'outputs/spider2_snow/runs/snow_full_v25'
CHAIN_DIR = DRV / 'outputs/runtime/phase25_chain'
CHAIN_DIR.mkdir(parents=True, exist_ok=True)
CHAIN_LOG = CHAIN_DIR / 'chain.log'
CHAIN_STATE = CHAIN_DIR / 'state.json'

g = globals()


def _log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    line = f'[{ts}] {msg}'
    print(line, flush=True)
    with open(CHAIN_LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def _state(d):
    CHAIN_STATE.write_text(json.dumps(d, indent=2, default=str), encoding='utf-8')


def _wait_for_done(run_dir, label, timeout_sec=24 * 3600, poll=60):
    """Return True if _DONE appears, False if _FAILED appears or timeout."""
    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        if (run_dir / '_DONE').is_file():
            _log(f'  {label}: _DONE detected')
            return True
        if (run_dir / '_FAILED').is_file():
            _log(f'  {label}: _FAILED detected')
            return False
        time.sleep(poll)
    _log(f'  {label}: timeout after {timeout_sec}s')
    return False


def _chain_runner():
    try:
        _log('=== PHASE 25 BRIDGE CHAIN START ===')
        _state({'phase': 'wait_lite_bq', 'started_at': time.time()})

        # Wait Stage 1
        _log('Stage 1: waiting for lite_bq_full_v25/_DONE')
        ok1 = _wait_for_done(LITE_BQ_DIR, 'lite_bq_full_v25')
        _state({'phase': 'lite_bq_done' if ok1 else 'lite_bq_failed',
                  'lite_bq_ok': ok1})

        # Kick off Snow regardless (FAIL on Lite-BQ shouldn't block Snow)
        _log('Stage 2: launching snow_full_v25')
        snow_starter = g.get('_PHASE25_START_SNOW_FULL')
        if snow_starter is None:
            _log('  snow starter NOT registered; chain ABORTED for snow')
            _state({'phase': 'snow_starter_missing',
                      'lite_bq_ok': ok1})
            return
        kick = snow_starter('snow_full_v25')
        _log(f'  snow kick result: {kick}')
        _state({'phase': 'snow_running', 'lite_bq_ok': ok1,
                  'snow_kick': kick})

        if not kick.get('started'):
            _log('  snow lock acquisition failed; chain ABORTED for snow')
            return

        ok2 = _wait_for_done(SNOW_DIR, 'snow_full_v25')
        _log(f'Stage 2: snow_full_v25 done={ok2}')
        _state({'phase': 'snow_done' if ok2 else 'snow_failed',
                  'lite_bq_ok': ok1, 'snow_ok': ok2})

        # Write ready-for-DBT marker
        marker = CHAIN_DIR / '_READY_FOR_DBT'
        marker.write_text(json.dumps({
            'lite_bq_ok': ok1, 'snow_ok': ok2, 'ts': time.time()}))
        _log(f'  wrote READY_FOR_DBT marker: {marker}')
        _log('=== PHASE 25 BRIDGE CHAIN END (DBT step is local) ===')
    except Exception as e:
        import traceback
        _log(f'CHAIN EXC: {type(e).__name__}: {e}')
        _log(traceback.format_exc())


# Idempotent install — only one chain at a time
if g.get('_PHASE25_CHAIN_THREAD') is None or not g['_PHASE25_CHAIN_THREAD'].is_alive():
    t = threading.Thread(target=_chain_runner, daemon=True, name='Phase25Chain')
    t.start()
    g['_PHASE25_CHAIN_THREAD'] = t
    print('PHASE25_CHAIN_STARTED')
else:
    print('PHASE25_CHAIN_ALREADY_RUNNING')
