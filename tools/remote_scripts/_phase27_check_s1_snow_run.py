"""Check all spider2_snow runs."""
import json, subprocess
from pathlib import Path

base = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_snow/runs')
print(f'== {base} ==')
print(subprocess.getoutput(f'ls -la {base}'))

for p in sorted(base.iterdir()):
    if not p.is_dir(): continue
    pj = p / 'progress.json'
    pred = p / 'predictions.jsonl'
    n = 0
    if pred.exists():
        with open(pred) as f: n = sum(1 for _ in f)
    print(f'\n== {p.name} ==')
    if pj.exists():
        d = json.loads(pj.read_text())
        for k in ['n_total','n_target','plan_ok','schema_valid','parse_ok','execute_ok','wall_sec','last_task']:
            if k in d: print(f'  {k}: {d[k]}')
        if 'err_top' in d: print(f'  err_top: {d["err_top"]}')
    print(f'  predictions.jsonl rows: {n}')
    print(f'  _DONE: {(p / "_DONE").exists()}')
    print(f'  _STARTED: {(p / "_STARTED").exists()}')
