"""Launch Lite-Snow FULL 207 on this kernel (S2) with v28-revert-A stack.

Filters Lite jsonl to the 207 Snow-lane instance_ids by reading the existing
v26 Lite-Snow FULL predictions on Drive (those define the 207 Snow tasks).
Frozen code. Per-task Drive writes. Resume-aware.
"""
import sys, importlib, threading, inspect, json
from pathlib import Path

g = inspect.currentframe().f_globals

for k in ['_TOK_EMIT', '_MDL_EMIT', '_PROF_EMIT', '_TOK_PLAN', '_MDL_PLAN', '_PROF_PLAN']:
    if k not in g:
        src = {'_TOK_EMIT':'tok_b','_MDL_EMIT':'mdl_b','_PROF_EMIT':'prof_b',
               '_TOK_PLAN':'tok_a','_MDL_PLAN':'mdl_a','_PROF_PLAN':'prof_a'}[k]
        if src in g:
            g[k] = g[src]
            print(f'  aliased {k} <- {src}')

EVAL = Path('/content/drive/MyDrive/diploma_plan_sql/repo/src/evaluation')
if str(EVAL) not in sys.path: sys.path.insert(0, str(EVAL))
for mod in ['schema_pack_builder_v18', 'snow_identifier_guard_v27',
            'snow_dialect_fixer_v28', 'schema_linking_v18',
            'structured_plan_v18']:
    if mod in sys.modules:
        importlib.reload(sys.modules[mod])

runner_src = open('/tmp/_phase27_snow_runner.py', encoding='utf-8').read()
exec(compile(runner_src, '/tmp/_phase27_snow_runner.py', 'exec'), g)

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')

# Derive the 207 Snow-lane instance_ids from existing v26 Lite-Snow predictions
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
            except Exception:
                pass
print(f'Snow-lane iids derived from v26: {len(snow_iids)}')
assert len(snow_iids) == 207, f'expected 207 Snow iids, got {len(snow_iids)}'

jsonl_path = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl'

def _runner():
    try:
        g['_PHASE27_RUN_SNOW'](
            run_id='lite_snow_full_v28_revert_a',
            jsonl_path=str(jsonl_path),
            instance_ids_set=snow_iids,
            out_subdir='spider2_lite',
        )
    except Exception as e:
        import traceback
        OUT = DRV / 'outputs/spider2_lite/runs/lite_snow_full_v28_revert_a'
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / '_RUNNER_ERROR').write_text(
            f'{type(e).__name__}: {e}\n\n{traceback.format_exc()}')
        print(f'RUNNER CRASHED: {e}')

import ctypes
for t in threading.enumerate():
    if t.name == 'Phase28FullS2Chain' and t.is_alive():
        print(f'killing stale {t.name} (tid={t.ident})')
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(t.ident), ctypes.py_object(SystemExit))

t = threading.Thread(target=_runner, name='Phase28FullS2Chain', daemon=True)
t.start()
print(f'Phase28FullS2Chain started: alive={t.is_alive()} ident={t.ident}')
print(f'  run_id=lite_snow_full_v28_revert_a  (Snow-lane subset of {len(snow_iids)} iids)')
print(f'  jsonl={jsonl_path}')
print(f'  out_dir={DRV / "outputs/spider2_lite/runs/lite_snow_full_v28_revert_a"}')
