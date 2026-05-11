"""Upload patched runner to S1 + run smoke check."""
import base64, json, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIDGE = (ROOT / 'tools/.bridge_url').read_text(encoding='utf-8').strip() + '/exec'

def b64(p):
    return base64.b64encode((ROOT / p).read_bytes()).decode('ascii')

def post(code, label, timeout=120):
    req = urllib.request.Request(
        BRIDGE, data=json.dumps({'code': code}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print(f'  [{label}] HTTP failed: {type(e).__name__}: {e}'); return None
    if d.get('stdout'): print(d['stdout'])
    if d.get('stderr'): print('STDERR:', d['stderr'][:600])
    if d.get('traceback'): print('TB:', d['traceback'][:800])
    return d

print('STEP A: re-upload patched runner to /tmp')
runner_b64 = b64('tools/remote_scripts/_phase27_snow_runner.py')
print(f'  runner b64 size: {len(runner_b64)}')
code = (
    'import base64\n'
    f'open("/tmp/_phase27_snow_runner.py", "wb").write(base64.b64decode({runner_b64!r}))\n'
    'import os; print("runner size:", os.path.getsize("/tmp/_phase27_snow_runner.py"))\n'
)
post(code, 'upload-runner')

print('\nSTEP B: run smoke check')
smoke_src = (ROOT / 'tools/remote_scripts/_phase28_revert_smoke_check.py').read_text(encoding='utf-8')
post(smoke_src, 'smoke', timeout=120)
