"""Verify Phase26Chain is dead; if still in long inference, re-raise."""
import ctypes, threading, time, json
from pathlib import Path

RUN = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_snow/runs/snow_full_v25')
pj = RUN / 'progress.json'
pred = RUN / 'predictions.jsonl'

# Re-send the exception in case thread was in long C call (gpu inference, drive write)
hits = [t for t in threading.enumerate() if t.name == 'Phase26Chain']
for t in hits:
    tid = t.ident
    r = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_ulong(tid), ctypes.py_object(SystemExit))
    print(f're-send SystemExit to {tid}: r={r}')

# Count preds before and after
def npred():
    n = 0
    if pred.exists():
        with open(pred) as f:
            for _ in f: n += 1
    return n

n0 = npred()
m0 = pj.stat().st_mtime
print(f'preds: {n0}  progress mtime: {time.time() - m0:.0f}s ago')

# Wait 30s then re-check
time.sleep(30)

n1 = npred()
m1 = pj.stat().st_mtime
print(f'after 30s: preds={n1} (delta={n1-n0}) progress mtime: {time.time() - m1:.0f}s ago')

# State
hits2 = [t for t in threading.enumerate() if t.name == 'Phase26Chain']
print(f'Phase26Chain threads alive: {len(hits2)}')

if n1 == n0 and (time.time() - m1) > 30:
    print('VERDICT: runner stopped — no new tasks landed in last 30s')
else:
    print('VERDICT: runner still moving — may need notebook stop')
