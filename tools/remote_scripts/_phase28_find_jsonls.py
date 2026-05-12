"""Find the Spider2-Snow benchmark jsonl + verify Lite-Snow path."""
import subprocess
from pathlib import Path

print('=== search for spider2 jsonl files ===')
out = subprocess.getoutput(
    "find /content/drive/MyDrive/diploma_plan_sql/external_benchmarks -name '*.jsonl' "
    "-not -path '*/.git/*' 2>/dev/null | head -30")
print(out)

print('\n=== verify expected Lite-Snow jsonl ===')
lite = Path('/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl')
print(f'  lite exists: {lite.exists()}  size: {lite.stat().st_size if lite.exists() else 0}B')

# Sample first row of each candidate
import json
for path_str in out.strip().split('\n'):
    if not path_str.strip(): continue
    p = Path(path_str.strip())
    try:
        with open(p) as f:
            first = f.readline().strip()
            n = sum(1 for _ in f) + 1
        try:
            t = json.loads(first)
            iid = t.get('instance_id', '?')
            db = t.get('db') or t.get('db_id', '?')
            print(f'  {p.name}: {n} rows, first iid={iid} db={db}')
        except Exception:
            print(f'  {p.name}: {n} rows, first NOT json: {first[:80]}')
    except Exception as e:
        print(f'  {p.name}: error: {e}')

# Also probe known Phase 23/24/25 Snow run dirs to see what jsonl_path they used
print('\n=== last v25 _STARTED to infer jsonl_path used ===')
sf = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_snow/runs/snow_full_v25')
if sf.exists():
    started = sf / '_STARTED'
    if started.exists():
        print(started.read_text()[:400])
