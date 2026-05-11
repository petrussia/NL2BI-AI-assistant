"""Status probe for pilot10 revert-A."""
import json, time, threading
from pathlib import Path

RUN = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_lite/runs/lite_snow_pilot10_v28_revertA')
print(f'dir exists: {RUN.exists()}')
if RUN.exists():
    for p in sorted(RUN.iterdir()):
        age = time.time() - p.stat().st_mtime
        print(f'  {p.name:32s} {p.stat().st_size:>8d}B  age={age:.0f}s')

pj = RUN / 'progress.json'
if pj.exists():
    print('\nprogress.json:')
    d = json.loads(pj.read_text())
    for k in sorted(d.keys()):
        print(f'  {k}: {d[k]}')

# Threads
print('\nthreads:')
for t in threading.enumerate():
    if 'Phase' in t.name or 'revert' in t.name.lower() or 'chain' in t.name.lower():
        print(f'  {t.name}: alive={t.is_alive()}')
