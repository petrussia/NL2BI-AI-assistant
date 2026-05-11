"""Phase 28 pilot10 driver — upload patched modules + runner, then schedule.

Verifies model globals are loaded (LLMs already in GPU mem from S1's previous
v25 run), uploads the three Snow modules + runner, and starts pilot10_v28
in a background daemon thread.

Same 10 instance_ids as pilot10c so the comparison is clean.
"""
import os, sys, base64, json, time, threading
from pathlib import Path

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
EVAL = DRV / 'repo/src/evaluation'
RUN_ID = 'lite_snow_pilot10_v28'
OUT = DRV / 'outputs/spider2_lite/runs' / RUN_ID

# Step 1: verify model globals (must be loaded from earlier session)
g = sys.modules['__main__'].__dict__
required = ['_TOK_EMIT', '_MDL_EMIT', '_PROF_EMIT', '_TOK_PLAN', '_MDL_PLAN', '_PROF_PLAN']
missing = [k for k in required if k not in g]
if missing:
    print(f'ABORT: missing model globals: {missing}')
    print(f'available __main__ keys with _TOK/_MDL: '
          f'{[k for k in g.keys() if "_TOK" in k or "_MDL" in k or "_PROF" in k]}')
    sys.exit(1)
print('OK: model globals present')

# Step 2: pull module bytes from placeholders (replaced by local driver before exec)
modules = {
    'schema_pack_builder_v18.py': '__PACK_B64__',
    'snow_identifier_guard_v27.py': '__GUARD_B64__',
    'snow_dialect_fixer_v28.py': '__FIXER_B64__',
}
for relname, b64 in modules.items():
    if b64.startswith('__'):
        print(f'WARN: placeholder for {relname} not substituted — keeping old version on Drive')
        continue
    dst = EVAL / relname
    dst.write_bytes(base64.b64decode(b64))
    print(f'  uploaded {relname} ({dst.stat().st_size} B)')

# Reload modules if already imported
import importlib
for mod in ['schema_linking_v18', 'schema_pack_builder_v18',
            'structured_plan_v18', 'snow_identifier_guard_v27',
            'snow_dialect_fixer_v28']:
    if mod in sys.modules:
        try:
            importlib.reload(sys.modules[mod])
            print(f'  reloaded {mod}')
        except Exception as e:
            print(f'  reload {mod} failed: {e}')

# Step 3: install runner via base64 inline + exec
runner_b64 = '__RUNNER_B64__'
runner_src = base64.b64decode(runner_b64).decode('utf-8')
# Strip the b64 placeholders inside the runner's _upload_modules_to_drive
# (those are for the runner's own use, not for this driver). They were just
# replaced above by us anyway. The runner's _upload helper will fail with the
# placeholder content if invoked — but we don't call it.
runner_path = Path('/tmp/_phase28_snow_runner_inlined.py')
runner_path.write_text(runner_src, encoding='utf-8')
print(f'runner inlined at {runner_path} ({runner_path.stat().st_size} B)')

# Bring runner into globals
exec(compile(runner_src, str(runner_path), 'exec'), g)

# Step 4: 10 instance_ids — same as pilot10c
pilot10_iids = {
    'sf_bq026', 'sf_bq027', 'sf_bq029', 'sf_bq033', 'sf_bq091',
    'sf_bq099', 'sf_bq209', 'sf_bq210', 'sf_bq211', 'sf_bq213',
}
jsonl_path = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl'

# Step 5: kick off run in a daemon thread named Phase28Chain
def _runner():
    try:
        g['_PHASE27_RUN_SNOW'](
            run_id=RUN_ID,
            jsonl_path=str(jsonl_path),
            instance_ids_set=pilot10_iids,
            out_subdir='spider2_lite',
        )
    except Exception as e:
        import traceback
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / '_RUNNER_ERROR').write_text(
            f'{type(e).__name__}: {e}\n\n{traceback.format_exc()}')

t = threading.Thread(target=_runner, name='Phase28Chain', daemon=True)
t.start()
print(f'STARTED Phase28Chain for run_id={RUN_ID} '
      f'(10 instance_ids; output: {OUT})')
print(f'thread alive: {t.is_alive()}, ident={t.ident}')
