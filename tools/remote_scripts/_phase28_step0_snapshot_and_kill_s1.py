"""Step 0: snapshot S1 Spider2-Snow FULL v25 progress, identify the runner thread/proc,
then signal a clean stop. Print everything before any kill so we capture baseline."""
import json, os, subprocess, signal, time, threading
from pathlib import Path

RUN = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_snow/runs/snow_full_v25')

print('=== S1 v25 baseline snapshot ===')
pj = RUN / 'progress.json'
if pj.exists():
    d = json.loads(pj.read_text())
    for k in sorted(d.keys()):
        print(f'  {k}: {d[k]}')

pred = RUN / 'predictions.jsonl'
if pred.exists():
    n = 0
    with open(pred) as f:
        for _ in f: n += 1
    print(f'  predictions.jsonl rows: {n}')

print(f'  _DONE: {(RUN / "_DONE").exists()}')
print(f'  _STARTED: {(RUN / "_STARTED").exists()}')
print(f'  mtime progress: {time.time() - pj.stat().st_mtime:.0f}s ago' if pj.exists() else '')

# Find running python processes consistent with the runner
print('\n=== running python procs ===')
print(subprocess.getoutput('ps -ef | grep -E "(spider2|snow|v25|run_spider2)" | grep -v grep | head -20'))

# Thread inventory (this Colab kernel)
print('\n=== threads in current kernel ===')
for t in threading.enumerate():
    print(f'  {t.name}: daemon={t.daemon} alive={t.is_alive()}')
