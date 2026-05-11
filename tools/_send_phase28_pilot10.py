"""Local helper: substitute b64 placeholders into the Phase 28 pilot10 driver,
then POST to S1 bridge /exec to kick off the run."""
import base64, json, urllib.request, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIDGE = (ROOT / 'tools/.bridge_url').read_text(encoding='utf-8').strip()

def b64(path):
    return base64.b64encode((ROOT / path).read_bytes()).decode('ascii')

# Read the three module sources + the runner
subs = {
    '__PACK_B64__':   b64('repo/src/evaluation/schema_pack_builder_v18.py'),
    '__GUARD_B64__':  b64('repo/src/evaluation/snow_identifier_guard_v27.py'),
    '__FIXER_B64__':  b64('repo/src/evaluation/snow_dialect_fixer_v28.py'),
    '__RUNNER_B64__': b64('tools/remote_scripts/_phase27_snow_runner.py'),
}

driver = (ROOT / 'tools/remote_scripts/_phase28_pilot10_driver.py').read_text(encoding='utf-8')
for k, v in subs.items():
    driver = driver.replace(k, v)

# Verify no placeholders left
remaining = [k for k in subs if k in driver]
if remaining:
    print(f'WARN: placeholders not substituted: {remaining}'); sys.exit(1)

print(f'driver size after substitution: {len(driver)} B '
      f'(pack={len(subs["__PACK_B64__"])} guard={len(subs["__GUARD_B64__"])} '
      f'fixer={len(subs["__FIXER_B64__"])} runner={len(subs["__RUNNER_B64__"])})')

# POST
req = urllib.request.Request(
    BRIDGE + '/exec',
    data=json.dumps({'code': driver}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(req, timeout=180) as r:
    d = json.loads(r.read().decode('utf-8'))

print('=== stdout ===')
print(d.get('stdout', ''))
if d.get('stderr'): print('=== stderr ===\n' + d['stderr'][:1500])
if d.get('traceback'): print('=== traceback ===\n' + d['traceback'][:2500])
print(f'ok={d.get("ok")}')
