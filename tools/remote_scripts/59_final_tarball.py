# Final tarball with all current artefacts.

import datetime as dt
import shutil
import tarfile
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')

ts = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
tarball = Path(f'/content/diploma_tz_closure_{ts}.tar.gz')

with tarfile.open(tarball, 'w:gz') as tar:
    for sub in ['outputs','practice','data/spider/SOURCE_AND_AUDIT.md']:
        p = PROJECT_ROOT / sub
        if p.exists(): tar.add(p, arcname=sub)
    for p in (PROJECT_ROOT / 'repo').rglob('*'):
        if p.is_file():
            tar.add(p, arcname=str(p.relative_to(PROJECT_ROOT)))

backup = PROJECT_ROOT / 'exports' / tarball.name
backup.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(tarball, backup)
stable = PROJECT_ROOT / 'exports' / 'latest_tz_closure.tar.gz'
shutil.copy2(tarball, stable)

print(f'TARBALL_DRIVE_PATH: {backup}')
print(f'TARBALL_STABLE_PATH: {stable}')
print(f'TARBALL_SIZE: {tarball.stat().st_size}')
