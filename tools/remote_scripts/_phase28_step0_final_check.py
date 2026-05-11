"""Phase26Chain killed but preds went 508→509. Check if another worker thread is feeding."""
import ctypes, threading, time
from pathlib import Path

print('=== all threads (long-running) ===')
suspects = []
for t in threading.enumerate():
    if t.name in ('MainThread', 'IOPub', 'Heartbeat', 'Control', 'bridge-flask',
                  'process_request_thread'):
        continue
    if not t.is_alive():
        continue
    print(f'  {t.name}: daemon={t.daemon} ident={t.ident}')
    suspects.append(t)

# Look for Phase25/Phase26 lingering or Thread-N workers
for t in suspects:
    if any(p in t.name for p in ('Phase', 'Chain', '_runner', 'worker', 'sequential', 'Inference')):
        tid = t.ident
        r = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(tid), ctypes.py_object(SystemExit))
        print(f'  -> killing {t.name} (tid={tid}): r={r}')

time.sleep(15)

RUN = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_snow/runs/snow_full_v25')
pred = RUN / 'predictions.jsonl'
n = sum(1 for _ in open(pred)) if pred.exists() else 0
print(f'\nfinal preds count: {n}')
print(f'progress mtime: {time.time() - (RUN / "progress.json").stat().st_mtime:.0f}s ago')

print('\n=== threads after cleanup ===')
for t in threading.enumerate():
    if t.name in ('MainThread', 'IOPub', 'Heartbeat', 'Control', 'bridge-flask',
                  'process_request_thread'):
        continue
    print(f'  {t.name}: alive={t.is_alive()}')

# Drop a final _STOPPED marker so we know baseline is sealed
RUN.joinpath('_STOPPED_PHASE28').write_text(
    f'{{"n_total": {n}, "stopped_ts": {time.time()}, "reason": "phase28_step0_kill"}}'
)
print(f'\nSTOPPED marker written.')
