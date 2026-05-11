"""Phase 28 driver — break into small exec calls to avoid Cloudflare 502."""
import base64, json, urllib.request, time, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIDGE = (ROOT / 'tools/.bridge_url').read_text(encoding='utf-8').strip() + '/exec'

def b64(path):
    return base64.b64encode((ROOT / path).read_bytes()).decode('ascii')

def post(code, timeout=120, label=''):
    req = urllib.request.Request(
        BRIDGE, data=json.dumps({'code': code}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print(f'  [{label}] HTTP failed: {type(e).__name__}: {e}')
        return None
    if d.get('stdout'): print(f'  [{label}] stdout: {d["stdout"][:300]}')
    if d.get('stderr'): print(f'  [{label}] stderr: {d["stderr"][:300]}')
    if d.get('traceback'): print(f'  [{label}] tb: {d["traceback"][:600]}')
    return d

print('STEP A: upload each module separately')
modules = {
    'schema_pack_builder_v18.py': b64('repo/src/evaluation/schema_pack_builder_v18.py'),
    'snow_identifier_guard_v27.py': b64('repo/src/evaluation/snow_identifier_guard_v27.py'),
    'snow_dialect_fixer_v28.py': b64('repo/src/evaluation/snow_dialect_fixer_v28.py'),
}
for name, content_b64 in modules.items():
    code = (
        'import base64\n'
        f'p = "/content/drive/MyDrive/diploma_plan_sql/repo/src/evaluation/{name}"\n'
        f'open(p, "wb").write(base64.b64decode({content_b64!r}))\n'
        f'import os; print(f"wrote {{p}} -> {{os.path.getsize(p)}}B")\n'
    )
    print(f'  uploading {name} ({len(content_b64)}B b64)')
    post(code, label=name)

print('\nSTEP B: upload runner to /tmp + verify')
runner_b64 = b64('tools/remote_scripts/_phase27_snow_runner.py')
print(f'  runner b64 size: {len(runner_b64)}')
code = (
    'import base64\n'
    f'open("/tmp/_phase27_snow_runner.py", "wb").write(base64.b64decode({runner_b64!r}))\n'
    'import os; print("runner size:", os.path.getsize("/tmp/_phase27_snow_runner.py"))\n'
)
post(code, label='runner')

print('\nSTEP C: import + reload + run')
trigger = '''
import sys, importlib, threading, json
from pathlib import Path

EVAL = Path("/content/drive/MyDrive/diploma_plan_sql/repo/src/evaluation")
if str(EVAL) not in sys.path: sys.path.insert(0, str(EVAL))

for mod in ["schema_linking_v18", "schema_pack_builder_v18",
            "structured_plan_v18", "snow_identifier_guard_v27",
            "snow_dialect_fixer_v28"]:
    if mod in sys.modules:
        importlib.reload(sys.modules[mod])
        print(f"reloaded {mod}")

# Run guard self-test inline as sanity
import snow_dialect_fixer_v28 as f28
allowed = {"COUNTRY"}
fixed, info = f28.fix_mixedcase_quoting('SELECT "country" FROM T', allowed)
print(f"F2a sanity: {fixed} info={info}")
fixed2, info2 = f28.wrap_date_fn_on_nondate('SELECT EXTRACT(YEAR FROM "PD") FROM T', {"PD": "NUMBER(38,0)"})
print(f"F4 sanity: {fixed2[:80]} info={info2}")

# Verify model globals
g = sys.modules["__main__"].__dict__
needed = ["_TOK_EMIT", "_MDL_EMIT", "_PROF_EMIT", "_TOK_PLAN", "_MDL_PLAN", "_PROF_PLAN"]
missing = [k for k in needed if k not in g]
print(f"missing model globals: {missing}")

# Exec the runner module to register helpers in __main__ globals
runner_src = open("/tmp/_phase27_snow_runner.py", encoding="utf-8").read()
exec(compile(runner_src, "/tmp/_phase27_snow_runner.py", "exec"), g)

# Start pilot10 v28
pilot10_iids = {
    "sf_bq026", "sf_bq027", "sf_bq029", "sf_bq033", "sf_bq091",
    "sf_bq099", "sf_bq209", "sf_bq210", "sf_bq211", "sf_bq213",
}
DRV = Path("/content/drive/MyDrive/diploma_plan_sql")
jsonl_path = DRV / "external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl"

def _runner():
    try:
        g["_PHASE27_RUN_SNOW"](
            run_id="lite_snow_pilot10_v28",
            jsonl_path=str(jsonl_path),
            instance_ids_set=pilot10_iids,
            out_subdir="spider2_lite",
        )
    except Exception as e:
        import traceback
        OUT = DRV / "outputs/spider2_lite/runs/lite_snow_pilot10_v28"
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "_RUNNER_ERROR").write_text(f"{type(e).__name__}: {e}\\n\\n{traceback.format_exc()}")
        print(f"RUNNER CRASHED: {e}")

t = threading.Thread(target=_runner, name="Phase28Chain", daemon=True)
t.start()
print(f"Phase28Chain started: alive={t.is_alive()} ident={t.ident}")
'''
post(trigger, timeout=60, label='trigger')

print('\nDONE — Phase28Chain should now be running on S1')
