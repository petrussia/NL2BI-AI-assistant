"""Launch Spider2-Snow FULL 547 on this kernel (S1) with v28-revert-A stack.

Frozen code. Per-task Drive writes. Resume-aware (if /content/drive/.../snow_full_v28_revert_a
exists with prior predictions, picks up where it left off)."""
import sys, importlib, threading, inspect, json
from pathlib import Path

g = inspect.currentframe().f_globals

# Verify aliases (already set up earlier, but be defensive)
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

# Re-exec runner so all helpers register in shared globals
runner_src = open('/tmp/_phase27_snow_runner.py', encoding='utf-8').read()
exec(compile(runner_src, '/tmp/_phase27_snow_runner.py', 'exec'), g)

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
jsonl_path = DRV / 'external_benchmarks/spider2_snow/raw/Spider2/spider2-snow/spider2-snow.jsonl'

def _runner():
    try:
        g['_PHASE27_RUN_SNOW'](
            run_id='snow_full_v28_revert_a',
            jsonl_path=str(jsonl_path),
            out_subdir='spider2_snow',
        )
    except Exception as e:
        import traceback
        OUT = DRV / 'outputs/spider2_snow/runs/snow_full_v28_revert_a'
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / '_RUNNER_ERROR').write_text(
            f'{type(e).__name__}: {e}\n\n{traceback.format_exc()}')
        print(f'RUNNER CRASHED: {e}')

# Kill any prior Phase28FullS1Chain if present (defensive)
import ctypes
for t in threading.enumerate():
    if t.name == 'Phase28FullS1Chain' and t.is_alive():
        print(f'killing stale {t.name} (tid={t.ident})')
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(t.ident), ctypes.py_object(SystemExit))

t = threading.Thread(target=_runner, name='Phase28FullS1Chain', daemon=True)
t.start()
print(f'Phase28FullS1Chain started: alive={t.is_alive()} ident={t.ident}')
print(f'  run_id=snow_full_v28_revert_a')
print(f'  jsonl={jsonl_path}')
print(f'  out_dir={DRV / "outputs/spider2_snow/runs/snow_full_v28_revert_a"}')
