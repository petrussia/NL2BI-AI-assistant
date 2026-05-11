"""Phase 28 revert-A pilot10 run — F2a removed, prompt quoting line reverted,
col:TYPE kept. Same 10 instance_ids as pilot10c. Run id: lite_snow_pilot10_v28_revertA."""
import sys, importlib, threading, json, inspect, shutil
from pathlib import Path

g = inspect.currentframe().f_globals
print(f'globals id: {id(g)}')

# Verify aliases still set from previous session work
for k in ['_TOK_EMIT', '_MDL_EMIT', '_PROF_EMIT', '_TOK_PLAN', '_MDL_PLAN', '_PROF_PLAN']:
    if k in g:
        print(f'  OK: {k} = {type(g[k]).__name__}')
    else:
        # try aliasing
        src_map = {'_TOK_EMIT':'tok_b','_MDL_EMIT':'mdl_b','_PROF_EMIT':'prof_b',
                   '_TOK_PLAN':'tok_a','_MDL_PLAN':'mdl_a','_PROF_PLAN':'prof_a'}
        s = src_map.get(k)
        if s and s in g:
            g[k] = g[s]
            print(f'  ALIASED: {k} <- {s}')
        else:
            print(f'  STILL MISSING: {k}')

EVAL = Path('/content/drive/MyDrive/diploma_plan_sql/repo/src/evaluation')
if str(EVAL) not in sys.path: sys.path.insert(0, str(EVAL))
for mod in ['schema_pack_builder_v18', 'snow_identifier_guard_v27', 'snow_dialect_fixer_v28']:
    if mod in sys.modules:
        importlib.reload(sys.modules[mod])

# Re-exec patched runner so updated _snow_direct_prompt + dropped F2a call land
runner_src = open('/tmp/_phase27_snow_runner.py', encoding='utf-8').read()
exec(compile(runner_src, '/tmp/_phase27_snow_runner.py', 'exec'), g)
print('runner reloaded — _PHASE27_RUN_SNOW registered')

# Clean any prior revert-A run dir
RUN = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_lite/runs/lite_snow_pilot10_v28_revertA')
if RUN.exists():
    shutil.rmtree(RUN)
    print(f'cleared old {RUN}')

pilot10_iids = {
    'sf_bq026', 'sf_bq027', 'sf_bq029', 'sf_bq033', 'sf_bq091',
    'sf_bq099', 'sf_bq209', 'sf_bq210', 'sf_bq211', 'sf_bq213',
}
DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
jsonl_path = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl'

def _runner():
    try:
        g['_PHASE27_RUN_SNOW'](
            run_id='lite_snow_pilot10_v28_revertA',
            jsonl_path=str(jsonl_path),
            instance_ids_set=pilot10_iids,
            out_subdir='spider2_lite',
        )
    except Exception as e:
        import traceback
        OUT = DRV / 'outputs/spider2_lite/runs/lite_snow_pilot10_v28_revertA'
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / '_RUNNER_ERROR').write_text(f'{type(e).__name__}: {e}\n\n{traceback.format_exc()}')
        print(f'RUNNER CRASHED: {e}')

t = threading.Thread(target=_runner, name='Phase28RevertAChain', daemon=True)
t.start()
print(f'Phase28RevertAChain started: alive={t.is_alive()} ident={t.ident}')
