"""Probe Drive state after S1 kernel death — figure out where Snow + Lite
stopped, plus what we still have from the supervisor."""
import json, time
from pathlib import Path

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')

print('=== Spider2-Snow FULL 547 run dir ===')
SNOW = DRV / 'outputs/spider2_snow/runs/snow_full_v28_revert_a'
if SNOW.exists():
    for p in sorted(SNOW.iterdir()):
        age = (time.time() - p.stat().st_mtime) / 60
        print(f'  {p.name:38s} {p.stat().st_size:>10d}B  age={age:.0f}min')

    pj = SNOW / 'progress.json'
    if pj.exists():
        d = json.loads(pj.read_text())
        print(f'\n  progress.json final state:')
        for k in sorted(d.keys()):
            print(f'    {k}: {d[k]}')

    pred = SNOW / 'predictions.jsonl'
    if pred.exists():
        n_pred = sum(1 for _ in open(pred, encoding='utf-8'))
        print(f'\n  predictions.jsonl rows on Drive: {n_pred}')

    hb = SNOW / '_supervisor_heartbeat.txt'
    if hb.exists():
        age = (time.time() - hb.stat().st_mtime) / 60
        print(f'\n  supervisor heartbeat (age={age:.0f}min):')
        print(f'    {hb.read_text().strip()}')

    log = SNOW / '_supervisor.log'
    if log.exists():
        text = log.read_text()
        lines = text.strip().split('\n')
        print(f'\n  supervisor log (last 10 lines, total={len(lines)}):')
        for ln in lines[-10:]:
            print(f'    {ln}')

print('\n=== Lite-Snow FULL run dir ===')
LITE = DRV / 'outputs/spider2_lite/runs/lite_snow_full_v28_revert_a'
if LITE.exists():
    for p in sorted(LITE.iterdir()):
        age = (time.time() - p.stat().st_mtime) / 60
        print(f'  {p.name:38s} {p.stat().st_size:>10d}B  age={age:.0f}min')

    pj = LITE / 'progress.json'
    if pj.exists():
        d = json.loads(pj.read_text())
        print(f'\n  Lite progress.json final state:')
        for k in sorted(d.keys()):
            print(f'    {k}: {d[k]}')

    pred = LITE / 'predictions.jsonl'
    if pred.exists():
        n_pred = sum(1 for _ in open(pred, encoding='utf-8'))
        print(f'\n  Lite predictions.jsonl rows on Drive: {n_pred}')

print('\n=== Lite snapshots (S2 backup) ===')
for p in sorted((DRV / 'outputs/spider2_lite/runs').iterdir()):
    if 'snapshot' in p.name and 'v28' in p.name:
        n = 0
        pf = p / 'predictions.jsonl'
        if pf.exists():
            n = sum(1 for _ in open(pf, encoding='utf-8'))
        print(f'  {p.name}: predictions.jsonl rows={n}')
