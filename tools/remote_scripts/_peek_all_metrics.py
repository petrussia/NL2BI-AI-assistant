import csv
from pathlib import Path
r = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/metrics')
for p in sorted(r.iterdir()):
    if p.suffix != '.csv': continue
    try:
        row = next(csv.DictReader(p.open(encoding='utf-8')))
        print(f"{p.stem:<46} EX={row.get('ex','—')}  exec={row.get('executable_count','—')}/{row.get('n','—')}  pv={row.get('plan_valid_count','—')}")
    except Exception as exc:
        print(f"{p.stem:<46} parse_error: {exc!r}")
