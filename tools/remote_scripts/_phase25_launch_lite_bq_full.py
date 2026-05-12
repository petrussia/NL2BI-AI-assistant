"""Phase 25 — launch Lite-BQ FULL 205 with --force-no-gate.

Direct bridge launcher; does NOT block on the 4h poll loop.
The BG runner on the bridge continues independently. We poll separately.
"""
import sys, json, urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from run_spider2_sequential_v24 import RUNNER_TEMPLATE  # noqa

BRIDGE = open(REPO / 'tools' / '.bridge_url', encoding='utf-8').read().strip().rstrip('/')
RUN_ID = 'lite_bq_full_v25'
invocation = (
    f'\nresult = start_v24_lite_bq_bg(run_id={RUN_ID!r}, mode="full", limit=None)\n'
    "import json as _j\nprint('===STARTED===')\nprint(_j.dumps(result))\nprint('===STARTED_END===')\n")

req = urllib.request.Request(
    BRIDGE + '/exec',
    data=json.dumps({'code': RUNNER_TEMPLATE + invocation}).encode('utf-8'),
    headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req, timeout=60) as r:
    out = json.loads(r.read().decode('utf-8'))
sd = out.get('stdout', '')
print(sd[-2000:])
