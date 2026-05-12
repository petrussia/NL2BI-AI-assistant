"""Snapshot S2 Lite-Snow run dir to preserve current Drive state (40 synced preds +
progress.json showing n=119 in-memory counters). Safe to re-run."""
import shutil, time
from pathlib import Path

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
SRC = DRV / 'outputs/spider2_lite/runs/lite_snow_full_v28_revert_a'
ts = time.strftime('%Y%m%d_%H%M%S')
DST = DRV / 'outputs/spider2_lite/runs' / f'lite_snow_full_v28_revert_a_snapshot_{ts}'

assert SRC.exists(), f'src missing: {SRC}'
shutil.copytree(SRC, DST)
print(f'snapshot: {DST}')
for p in sorted(DST.iterdir()):
    print(f'  {p.name}: {p.stat().st_size}B')
