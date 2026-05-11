"""Kill Phase26Chain thread on S1 — cleanly stop Spider2-Snow FULL v25."""
import ctypes, threading, time, json
from pathlib import Path

TARGET = 'Phase26Chain'

# Find thread
hits = [t for t in threading.enumerate() if t.name == TARGET]
print(f'target: {TARGET}; hits: {[(t.name, t.ident) for t in hits]}')

for t in hits:
    tid = t.ident
    print(f'sending SystemExit to tid={tid}')
    r = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_ulong(tid), ctypes.py_object(SystemExit))
    print(f'  PyThreadState_SetAsyncExc returned {r}')
    # r == 1 means OK, >1 means rolled back (couldn't deliver)
    if r > 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(tid), None)
        print('  rolled back — exception delivery failed')

# Give it a moment
time.sleep(3)
print('\n=== threads after kill ===')
for t in threading.enumerate():
    if t.name in (TARGET, 'MainThread', 'bridge-flask'):
        print(f'  {t.name}: alive={t.is_alive()}')

# Confirm mtime stops advancing
RUN = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_snow/runs/snow_full_v25')
pj = RUN / 'progress.json'
print(f'\nprogress.json mtime now: {time.time() - pj.stat().st_mtime:.0f}s ago (was 24s)')
