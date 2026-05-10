"""Decode the base64 envelope from the bridge pull and write files locally.
"""
import json, base64, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import os
TMP_DIR = os.environ.get('TEMP', '/tmp')
env_path = Path(TMP_DIR) / '_p23_pull.json'
if not env_path.is_file():
    env_path = Path('/tmp/_p23_pull.json')
env = json.loads(env_path.read_text(encoding='utf-8'))
out = env.get('stdout', '')
s = out.find('===PULL_BEGIN===')
e = out.find('===PULL_END===')
if s < 0 or e < 0:
    print('NO MARKERS in pull output:', out[:500]); sys.exit(2)
payload = json.loads(out[s + len('===PULL_BEGIN===\n'):e].strip())

dest_map = {
    'lite_bq_full': REPO / 'outputs' / 'spider2_lite' / 'runs' / 'lite_full_diagnostic_v23_bq',
    'lite_snow_full': REPO / 'outputs' / 'spider2_lite' / 'runs' / 'lite_full_diagnostic_v23_snow',
    'snow_full': REPO / 'outputs' / 'spider2_snow' / 'runs' / 'snow_full_diagnostic_v23',
}

for label, files in payload.items():
    base = dest_map.get(label)
    if not base:
        print(f'SKIP {label}: no dest')
        continue
    base.mkdir(parents=True, exist_ok=True)
    n = 0
    for fn, b64 in files.items():
        if isinstance(b64, str) and not b64.startswith('ERR:'):
            try:
                (base / fn).write_bytes(base64.b64decode(b64))
                n += 1
            except Exception as ex:
                print(f'  ERR {fn}: {ex}')
    print(f'{label}: wrote {n} files to {base.relative_to(REPO).as_posix()}')
