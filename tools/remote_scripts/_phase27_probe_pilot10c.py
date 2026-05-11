"""Probe pilot10c state by reading progress.json + _STARTED + dir listing."""
import os, json, time
from pathlib import Path

RUN = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_lite/runs/lite_snow_pilot10_v27c')
print(f'=== ls {RUN} ===')
for p in sorted(RUN.iterdir()):
    st = p.stat()
    age = time.time() - st.st_mtime
    print(f'  {p.name:30s} {st.st_size:>10d}B  age={age/60:.1f}min')

print('\n=== progress.json ===')
pj = RUN / 'progress.json'
if pj.exists():
    try:
        d = json.loads(pj.read_text())
        for k, v in d.items():
            print(f'  {k}: {v}')
    except Exception as e:
        print(f'  err: {e}')
        print(pj.read_text())
else:
    print('  (no progress.json)')

print('\n=== _STARTED ===')
st = RUN / '_STARTED'
if st.exists():
    print(st.read_text())

# Look up wider — sibling Phase 27 runs
print('\n=== other Phase 27 runs on Drive ===')
parent = RUN.parent
for p in sorted(parent.iterdir()):
    if 'v27' in p.name or 'phase27' in p.name.lower():
        try:
            n_pred = 0
            pred = p / 'predictions.jsonl'
            if pred.exists():
                with open(pred) as f:
                    n_pred = sum(1 for _ in f)
            done = (p / '_DONE').exists()
            started = (p / '_STARTED').exists()
            print(f'  {p.name:40s} preds={n_pred:4d}  DONE={done}  STARTED={started}')
        except Exception as e:
            print(f'  {p.name}: {e}')
