"""Sanity check S1 post-restart: chains, supervisor, heartbeat, progress."""
import threading, time, json
from pathlib import Path

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
SNOW = DRV / 'outputs/spider2_snow/runs/snow_full_v28_revert_a'

print('=== threads ===')
for t in threading.enumerate():
    if t.name.startswith('Phase'):
        print(f'  {t.name}: alive={t.is_alive()} ident={t.ident}')

print('\n=== heartbeat ===')
hb = SNOW / '_supervisor_heartbeat.txt'
if hb.exists():
    age = int(time.time() - hb.stat().st_mtime)
    print(f'age={age}s: {hb.read_text().strip()}')
else:
    print('no heartbeat')

print('\n=== progress.json ===')
pj = SNOW / 'progress.json'
if pj.exists():
    age = int(time.time() - pj.stat().st_mtime)
    print(f'age={age}s')
    d = json.loads(pj.read_text())
    print(f"n_total={d['n_total']} sv={d['schema_valid']} exec={d['execute_ok']} "
          f"wrp={d.get('wrapped_n',0)} fb={d.get('guard_regex_fallback',0)} "
          f"last={d['last_task']} wall={d['wall_sec']/60:.1f}min")

print('\n=== predictions.jsonl ===')
pf = SNOW / 'predictions.jsonl'
if pf.exists():
    n = sum(1 for _ in open(pf, encoding='utf-8'))
    age = int(time.time() - pf.stat().st_mtime)
    print(f'rows={n}  age={age}s')

print('\n=== supervisor log tail ===')
log = SNOW / '_supervisor.log'
if log.exists():
    print(log.read_text()[-600:])
