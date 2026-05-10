"""Phase 23 — pull all run artifacts from Drive to local for committing.

Uses base64 chunked transfer like the v18 launcher's pull_code path.
"""
import os, base64, json
from pathlib import Path

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
files_to_pull = {
    'lite_bq_full': DRV / 'outputs/spider2_lite/runs/lite_full_diagnostic_v23_bq',
    'lite_snow_full': DRV / 'outputs/spider2_lite/runs/lite_full_diagnostic_v23_snow',
    'snow_full': DRV / 'outputs/spider2_snow/runs/snow_full_diagnostic_v23',
}

out = {}
for label, base in files_to_pull.items():
    if not base.is_dir():
        out[label] = {'error': 'dir_missing'}
        continue
    files = {}
    for f in sorted(base.iterdir()):
        if f.is_file() and f.stat().st_size < 8_000_000:
            try:
                files[f.name] = base64.b64encode(f.read_bytes()).decode()
            except Exception as e:
                files[f.name] = f'ERR:{type(e).__name__}'
    out[label] = files

print('===PULL_BEGIN===')
print(json.dumps(out))
print('===PULL_END===')
