"""Re-trigger pilot10 v28 after aliasing _TOK_EMIT/_MDL_EMIT etc."""
import sys, threading, json, importlib, inspect
from pathlib import Path

g = inspect.currentframe().f_globals
print(f'globals id: {id(g)}')

# Sanity: aliases present?
for k in ['_TOK_EMIT', '_MDL_EMIT', '_PROF_EMIT', '_TOK_PLAN', '_MDL_PLAN', '_PROF_PLAN']:
    if k in g:
        print(f'  OK: {k} = {type(g[k]).__name__}')
    else:
        print(f'  MISSING: {k}')

# Reload to pick up patched modules
EVAL = Path('/content/drive/MyDrive/diploma_plan_sql/repo/src/evaluation')
if str(EVAL) not in sys.path: sys.path.insert(0, str(EVAL))
for mod in ['schema_pack_builder_v18', 'snow_identifier_guard_v27',
            'snow_dialect_fixer_v28']:
    if mod in sys.modules:
        importlib.reload(sys.modules[mod])
        print(f'reloaded {mod}')

# Re-exec the runner src so all v28 helpers register in current globals
runner_src = open('/tmp/_phase27_snow_runner.py', encoding='utf-8').read()
exec(compile(runner_src, '/tmp/_phase27_snow_runner.py', 'exec'), g)
print('runner re-exec\'d, _PHASE27_RUN_SNOW registered')

# Delete the old run dir to start fresh
import shutil
RUN = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_lite/runs/lite_snow_pilot10_v28')
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
            run_id='lite_snow_pilot10_v28',
            jsonl_path=str(jsonl_path),
            instance_ids_set=pilot10_iids,
            out_subdir='spider2_lite',
        )
    except Exception as e:
        import traceback
        OUT = DRV / 'outputs/spider2_lite/runs/lite_snow_pilot10_v28'
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / '_RUNNER_ERROR').write_text(
            f'{type(e).__name__}: {e}\n\n{traceback.format_exc()}')
        print(f'RUNNER CRASHED: {e}')

t = threading.Thread(target=_runner, name='Phase28Chain', daemon=True)
t.start()
print(f'Phase28Chain started: alive={t.is_alive()} ident={t.ident}')
