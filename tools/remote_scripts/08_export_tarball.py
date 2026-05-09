# Step 8: build a fresh tarball of outputs/ + practice/ + audit, save to Drive,
# and just print the absolute Drive path. The agent then downloads it via bridge.

import datetime as dt
import shutil
import tarfile
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
PRACTICE = PROJECT_ROOT / 'practice'
SPIDER_AUDIT = PROJECT_ROOT / 'data' / 'spider' / 'SOURCE_AND_AUDIT.md'

ts = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
tarball = Path(f'/content/diploma_smoke25_results_{ts}.tar.gz')

with tarfile.open(tarball, 'w:gz') as tar:
    tar.add(OUTPUTS, arcname='outputs')
    tar.add(PRACTICE, arcname='practice')
    if SPIDER_AUDIT.exists():
        tar.add(SPIDER_AUDIT, arcname='data/spider/SOURCE_AND_AUDIT.md')

backup = PROJECT_ROOT / 'exports' / tarball.name
backup.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(tarball, backup)

# Also keep a stable name pointer
stable = PROJECT_ROOT / 'exports' / 'latest_smoke25.tar.gz'
shutil.copy2(tarball, stable)

print(f'TARBALL_DRIVE_PATH: {backup}')
print(f'TARBALL_STABLE_PATH: {stable}')
print(f'TARBALL_SIZE: {tarball.stat().st_size}')
