"""Phase 28 S1 supervisor v2 — Snow→Lite auto-handoff with hardening:
  - Drive heartbeat every 5 min so external observers see supervisor liveness
    without needing the bridge
  - Outer try/except wraps the watch loop (transient errors don't kill it)
  - Verifies _DONE *and* predictions.jsonl row count matches before firing
  - Kills any pre-existing Phase28S1Supervisor before installing v2
  - Logs all events to outputs/spider2_snow/runs/snow_full_v28_revert_a/_supervisor.log
"""
import sys, time, threading, json, inspect, ctypes, traceback
from pathlib import Path

g = inspect.currentframe().f_globals

# Sanity check
required = ['_TOK_EMIT','_MDL_EMIT','_PROF_EMIT','_TOK_PLAN','_MDL_PLAN','_PROF_PLAN']
missing = [k for k in required if k not in g]
if missing:
    print(f'ABORT: missing model globals: {missing}')
else:
    print('OK: model globals present')

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
SNOW_DIR = DRV / 'outputs/spider2_snow/runs/snow_full_v28_revert_a'
LITE_DIR = DRV / 'outputs/spider2_lite/runs/lite_snow_full_v28_revert_a'
HEARTBEAT = SNOW_DIR / '_supervisor_heartbeat.txt'
LOG = SNOW_DIR / '_supervisor.log'

def log(msg):
    line = f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {msg}'
    print(line, flush=True)
    try:
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass

# Kill any pre-existing supervisor
for t in threading.enumerate():
    if t.name == 'Phase28S1Supervisor' and t.is_alive():
        log(f'killing pre-existing supervisor tid={t.ident}')
        try:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_ulong(t.ident), ctypes.py_object(SystemExit))
            time.sleep(2)
        except Exception:
            pass

def _supervisor():
    log('supervisor v2 started — watching for SNOW _DONE')
    last_hb = 0
    n_polls = 0
    while True:
        try:
            n_polls += 1
            now = time.time()

            # Heartbeat every 5 min (300s)
            if now - last_hb >= 300:
                try:
                    snow_n = -1
                    pj = SNOW_DIR / 'progress.json'
                    if pj.exists():
                        snow_n = json.loads(pj.read_text()).get('n_total', -1)
                    snow_chain_alive = any(t.name == 'Phase28FullS1Chain' and t.is_alive()
                                            for t in threading.enumerate())
                    HEARTBEAT.write_text(
                        f'ts={time.strftime("%Y-%m-%d %H:%M:%S")} '
                        f'poll={n_polls} '
                        f'snow_progress={snow_n}/547 '
                        f'snow_chain_alive={snow_chain_alive} '
                        f'snow_done={(SNOW_DIR / "_DONE").exists()}\n')
                    last_hb = now
                except Exception as e:
                    log(f'heartbeat write failed: {e}')

            # Has Snow chain produced _DONE?
            done_path = SNOW_DIR / '_DONE'
            if done_path.exists():
                log(f'_DONE detected at {done_path}')

                # Verify integrity: predictions.jsonl row count should match
                # progress.n_total. If they disagree (FUSE sync lag), wait.
                pj = SNOW_DIR / 'progress.json'
                pf = SNOW_DIR / 'predictions.jsonl'
                if pj.exists() and pf.exists():
                    try:
                        prog_n = json.loads(pj.read_text()).get('n_total', -1)
                        pf_rows = sum(1 for _ in open(pf, encoding='utf-8'))
                        log(f'integrity check: prog_n={prog_n} pf_rows={pf_rows}')
                        if pf_rows < prog_n - 5:
                            log(f'sync lag detected; waiting 60s for FUSE sync')
                            time.sleep(60)
                            continue
                    except Exception as e:
                        log(f'integrity check err (proceeding anyway): {e}')

                time.sleep(5)  # final flush window

                # Confirm no Lite chain running already (in case S2 came back)
                if any(t.name == 'Phase28S1ChainLite' and t.is_alive()
                       for t in threading.enumerate()):
                    log('Phase28S1ChainLite already alive — supervisor exiting')
                    return
                if any(t.name == 'Phase28FullS2Chain' and t.is_alive()
                       for t in threading.enumerate()):
                    log('Phase28FullS2Chain alive on this kernel — supervisor exiting')
                    return

                # Re-exec runner to register helpers + pick up periodic-flush patch
                try:
                    runner_src = open('/tmp/_phase27_snow_runner.py', encoding='utf-8').read()
                    exec(compile(runner_src, '/tmp/_phase27_snow_runner.py', 'exec'), g)
                    log('runner re-exec OK (Lite chain will use periodic-flush version)')
                except Exception as e:
                    log(f'runner re-exec FAILED: {e}; supervisor exiting')
                    HEARTBEAT.write_text(f'FAILED_AT_RUNNER_REEXEC ts={time.time()} err={e}\n')
                    return

                # Derive 207 Snow-lane iids
                snow_iids = set()
                v26 = DRV / 'outputs/spider2_lite/runs/lite_snow_full_v26/predictions.jsonl'
                if v26.exists():
                    with open(v26, encoding='utf-8') as f:
                        for ln in f:
                            if not ln.strip(): continue
                            try:
                                iid = json.loads(ln).get('instance_id')
                                if iid: snow_iids.add(iid)
                            except Exception: pass
                log(f'derived Snow-lane iids: {len(snow_iids)}')

                if len(snow_iids) != 207:
                    log(f'WARN: expected 207 iids, got {len(snow_iids)}; proceeding anyway')

                jsonl_path = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl'

                def _lite_runner():
                    try:
                        log('Phase28S1ChainLite: starting _PHASE27_RUN_SNOW for Lite-Snow 207')
                        g['_PHASE27_RUN_SNOW'](
                            run_id='lite_snow_full_v28_revert_a',
                            jsonl_path=str(jsonl_path),
                            instance_ids_set=snow_iids,
                            out_subdir='spider2_lite',
                        )
                        log('Phase28S1ChainLite: completed normally')
                    except Exception as e:
                        log(f'Phase28S1ChainLite CRASHED: {type(e).__name__}: {e}')
                        try:
                            LITE_DIR.mkdir(parents=True, exist_ok=True)
                            (LITE_DIR / '_RUNNER_ERROR_S1').write_text(
                                f'{type(e).__name__}: {e}\n\n{traceback.format_exc()}')
                        except Exception: pass

                lite_t = threading.Thread(target=_lite_runner, name='Phase28S1ChainLite', daemon=True)
                lite_t.start()
                log(f'Phase28S1ChainLite started: ident={lite_t.ident}; supervisor exiting')
                HEARTBEAT.write_text(
                    f'HANDOFF_OK ts={time.strftime("%Y-%m-%d %H:%M:%S")} '
                    f'lite_chain_ident={lite_t.ident}\n')
                return

            time.sleep(60)
        except Exception as e:
            log(f'supervisor outer loop exception (continuing): {type(e).__name__}: {e}')
            log(traceback.format_exc()[:600])
            time.sleep(60)

sup_t = threading.Thread(target=_supervisor, name='Phase28S1Supervisor', daemon=True)
sup_t.start()
log(f'Phase28S1Supervisor v2 spawned: ident={sup_t.ident}')
print(f'log: {LOG}')
print(f'heartbeat: {HEARTBEAT}  (updates every 5 min)')
