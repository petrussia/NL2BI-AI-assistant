"""Phase 28 S1 supervisor — watch for Spider2-Snow FULL _DONE, then auto-launch
Lite-Snow FULL on the same S1 kernel (models stay resident).

Resume scaffolding in the runner picks up from whatever predictions.jsonl is on
Drive at that moment. If S2 has synced its 119 entries by then, S1 picks up
from 120. If not, S1 picks up from 41 and reprocesses 41-119 (acceptable).
"""
import sys, time, threading, json, inspect
from pathlib import Path

g = inspect.currentframe().f_globals

# Sanity: models still loaded?
required = ['_TOK_EMIT', '_MDL_EMIT', '_PROF_EMIT', '_TOK_PLAN', '_MDL_PLAN', '_PROF_PLAN']
missing = [k for k in required if k not in g]
if missing:
    print(f'ABORT: missing model globals on S1: {missing}')
else:
    print('OK: model globals present on S1')

# Already running?
already = [t for t in threading.enumerate() if t.name == 'Phase28S1Supervisor' and t.is_alive()]
if already:
    print(f'Supervisor already running (ident={already[0].ident}); aborting duplicate')
else:
    DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
    SNOW_DONE = DRV / 'outputs/spider2_snow/runs/snow_full_v28_revert_a/_DONE'
    LITE_OUT = DRV / 'outputs/spider2_lite/runs/lite_snow_full_v28_revert_a'

    def _supervisor():
        print(f'[supervisor] watching for {SNOW_DONE}', flush=True)
        # Wait for Snow chain to complete
        n_polls = 0
        while not SNOW_DONE.exists():
            n_polls += 1
            if n_polls % 30 == 0:  # every 30 min
                progress = DRV / 'outputs/spider2_snow/runs/snow_full_v28_revert_a/progress.json'
                if progress.exists():
                    try:
                        d = json.loads(progress.read_text())
                        print(f'[supervisor] still waiting Snow chain; n={d.get("n_total")}/547 '
                              f'exec={d.get("execute_ok")}', flush=True)
                    except Exception:
                        pass
            time.sleep(60)

        print(f'[supervisor] SNOW_DONE detected', flush=True)
        time.sleep(5)  # let final writes flush

        # Check if S2-side Lite chain still alive (in case it somehow restarted)
        s2_chain_alive = any(t.name == 'Phase28FullS2Chain' and t.is_alive()
                              for t in threading.enumerate())
        if s2_chain_alive:
            print('[supervisor] WARNING: Phase28FullS2Chain alive on this kernel; aborting Lite launch')
            return

        # Re-exec runner so all helpers register in shared globals (defensive)
        try:
            runner_src = open('/tmp/_phase27_snow_runner.py', encoding='utf-8').read()
            exec(compile(runner_src, '/tmp/_phase27_snow_runner.py', 'exec'), g)
            print('[supervisor] runner re-exec\'d')
        except Exception as e:
            print(f'[supervisor] runner re-exec FAILED: {e}')
            return

        # Derive 207 Snow-lane iids
        v26_pred = DRV / 'outputs/spider2_lite/runs/lite_snow_full_v26/predictions.jsonl'
        snow_iids = set()
        if v26_pred.exists():
            with open(v26_pred, encoding='utf-8') as f:
                for ln in f:
                    if not ln.strip(): continue
                    try:
                        p = json.loads(ln)
                        iid = p.get('instance_id')
                        if iid: snow_iids.add(iid)
                    except Exception: pass
        print(f'[supervisor] Snow-lane iids: {len(snow_iids)}')

        jsonl_path = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl'

        def _lite_runner():
            try:
                g['_PHASE27_RUN_SNOW'](
                    run_id='lite_snow_full_v28_revert_a',
                    jsonl_path=str(jsonl_path),
                    instance_ids_set=snow_iids,
                    out_subdir='spider2_lite',
                )
            except Exception as e:
                import traceback
                LITE_OUT.mkdir(parents=True, exist_ok=True)
                (LITE_OUT / '_RUNNER_ERROR_S1').write_text(
                    f'{type(e).__name__}: {e}\n\n{traceback.format_exc()}')
                print(f'[supervisor] LITE RUNNER CRASHED: {e}', flush=True)

        lite_t = threading.Thread(target=_lite_runner, name='Phase28S1ChainLite', daemon=True)
        lite_t.start()
        print(f'[supervisor] Phase28S1ChainLite started: alive={lite_t.is_alive()} '
              f'ident={lite_t.ident}', flush=True)
        print(f'[supervisor] auto-handoff complete; supervisor exiting', flush=True)

    sup_t = threading.Thread(target=_supervisor, name='Phase28S1Supervisor', daemon=True)
    sup_t.start()
    print(f'Phase28S1Supervisor started: alive={sup_t.is_alive()} ident={sup_t.ident}')
    print('  Will fire once outputs/spider2_snow/runs/snow_full_v28_revert_a/_DONE appears.')
