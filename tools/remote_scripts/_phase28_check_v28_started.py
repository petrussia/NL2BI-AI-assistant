"""Check if Phase28Chain started; if not, show why."""
import threading, json
from pathlib import Path

print('=== threads ===')
for t in threading.enumerate():
    if t.name in ('Phase28Chain', 'Phase27Chain', 'Phase26Chain', 'Phase25Chain') or '28' in t.name:
        print(f'  {t.name}: alive={t.is_alive()} ident={t.ident}')

run_dir = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_lite/runs/lite_snow_pilot10_v28')
print(f'\nrun_dir exists: {run_dir.exists()}')
if run_dir.exists():
    for p in sorted(run_dir.iterdir()):
        print(f'  {p.name} ({p.stat().st_size}B)')

# Check fixer module on Drive
fixer = Path('/content/drive/MyDrive/diploma_plan_sql/repo/src/evaluation/snow_dialect_fixer_v28.py')
print(f'\nfixer on Drive: exists={fixer.exists()} size={fixer.stat().st_size if fixer.exists() else 0}')
guard = Path('/content/drive/MyDrive/diploma_plan_sql/repo/src/evaluation/snow_identifier_guard_v27.py')
print(f'guard on Drive: exists={guard.exists()} size={guard.stat().st_size if guard.exists() else 0}')
