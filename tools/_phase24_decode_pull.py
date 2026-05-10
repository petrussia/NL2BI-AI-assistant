"""Decode Phase 24 pilot50 base64 envelope."""
import json, base64, os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TMP_DIR = os.environ.get('TEMP', '/tmp')
src = Path(TMP_DIR) / '_p24_pull.json'
if not src.is_file():
    src = Path('/tmp/_p24_pull.json')

env = json.loads(src.read_text(encoding='utf-8'))
out = env.get('stdout', '')
s = out.find('===PULL===')
e = out.find('===PULL_END===')
payload = json.loads(out[s + len('===PULL===\n'):e].strip())

dest = REPO / 'outputs' / 'spider2_lite' / 'runs' / 'lite_bq_v24_pilot50'
dest.mkdir(parents=True, exist_ok=True)
n = 0
for fn, b64 in payload.items():
    (dest / fn).write_bytes(base64.b64decode(b64))
    n += 1
print(f'wrote {n} files to {dest.relative_to(REPO).as_posix()}')
