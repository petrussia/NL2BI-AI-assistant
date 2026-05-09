# Step 17: rebuild tarball with B2 artefacts included.

import datetime as dt
import shutil
import tarfile
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
PRACTICE = PROJECT_ROOT / 'practice'
SPIDER_AUDIT = PROJECT_ROOT / 'data' / 'spider' / 'SOURCE_AND_AUDIT.md'
PLAN_SCHEMA = PROJECT_ROOT / 'repo' / 'docs' / 'plan_schema.json'
B2_MODULE = PROJECT_ROOT / 'repo' / 'src' / 'evaluation' / 'baselines_b2.py'
B1_MODULE = PROJECT_ROOT / 'repo' / 'src' / 'evaluation' / 'baselines.py'

ts = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
tarball = Path(f'/content/diploma_b2_smoke10_results_{ts}.tar.gz')

with tarfile.open(tarball, 'w:gz') as tar:
    tar.add(OUTPUTS, arcname='outputs')
    tar.add(PRACTICE, arcname='practice')
    if SPIDER_AUDIT.exists():
        tar.add(SPIDER_AUDIT, arcname='data/spider/SOURCE_AND_AUDIT.md')
    if PLAN_SCHEMA.exists():
        tar.add(PLAN_SCHEMA, arcname='repo/docs/plan_schema.json')
    if B2_MODULE.exists():
        tar.add(B2_MODULE, arcname='repo/src/evaluation/baselines_b2.py')
    if B1_MODULE.exists():
        tar.add(B1_MODULE, arcname='repo/src/evaluation/baselines.py')

backup = PROJECT_ROOT / 'exports' / tarball.name
backup.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(tarball, backup)
stable = PROJECT_ROOT / 'exports' / 'latest_b2_smoke10.tar.gz'
shutil.copy2(tarball, stable)

print(f'TARBALL_DRIVE_PATH: {backup}')
print(f'TARBALL_STABLE_PATH: {stable}')
print(f'TARBALL_SIZE: {tarball.stat().st_size}')
