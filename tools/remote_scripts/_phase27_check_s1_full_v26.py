"""Check Spider2-Snow FULL v26 baseline on S1."""
import json, os, sys
from pathlib import Path

candidates = [
    '/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_snow/runs',
    '/content/drive/MyDrive/diploma_plan_sql/outputs/spider2/snow/runs',
    '/content/drive/MyDrive/diploma_plan_sql/outputs/runs',
]
for c in candidates:
    print(f'check: {c} exists={Path(c).exists()}')

# Find any v26 run
import subprocess
out = subprocess.getoutput('find /content/drive/MyDrive/diploma_plan_sql/outputs -maxdepth 5 -type d -name "*v26*" 2>/dev/null | head -30')
print('=== v26 dirs ===')
print(out)
print('FLUSH', flush=True)
sys.stdout.flush()
