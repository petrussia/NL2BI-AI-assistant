"""Verify on S2 directly: how many lines in predictions.jsonl + traces.jsonl,
and check pf/tf file handle status."""
import os, time, inspect
from pathlib import Path

g = inspect.currentframe().f_globals

RUN = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_lite/runs/lite_snow_full_v28_revert_a')
for fn in ['predictions.jsonl', 'traces.jsonl', 'progress.json']:
    p = RUN / fn
    if p.exists():
        n = sum(1 for _ in open(p, encoding='utf-8'))
        print(f'  {fn}: {p.stat().st_size}B, lines={n}, mtime_age={time.time()-p.stat().st_mtime:.0f}s')

# Find the runner's pf/tf handles via gc (if they're held alive)
import gc, io
for obj in gc.get_objects():
    if isinstance(obj, io.TextIOWrapper) and not obj.closed:
        nm = getattr(obj, 'name', '')
        if 'predictions.jsonl' in nm or 'traces.jsonl' in nm:
            print(f'  open file: {nm} mode={obj.mode} closed={obj.closed}')

# Detect runner thread
import threading
print('\n=== threads ===')
for t in threading.enumerate():
    if 'Phase' in t.name or '_runner' in t.name:
        print(f'  {t.name}: alive={t.is_alive()} ident={t.ident}')

# Probe predictions.jsonl write directly to confirm Drive is writable
print('\n=== direct write test to Drive run dir ===')
probe = RUN / '_phase28_write_probe.txt'
try:
    probe.write_text(f'{time.time()}', encoding='utf-8')
    print(f'  wrote {probe} ({probe.stat().st_size}B)')
    probe.unlink()
    print(f'  unlinked OK')
except Exception as e:
    print(f'  WRITE FAILED: {type(e).__name__}: {e}')
