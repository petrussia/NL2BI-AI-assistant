# Stage 7 (c): build versioned final tarball with all current artefacts.

import datetime as dt
import shutil
import tarfile
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
PRACTICE = PROJECT_ROOT / 'practice'
SPIDER_AUDIT = PROJECT_ROOT / 'data' / 'spider' / 'SOURCE_AND_AUDIT.md'
REPO_DOCS = PROJECT_ROOT / 'repo' / 'docs'
REPO_EVAL = PROJECT_ROOT / 'repo' / 'src' / 'evaluation'

ts = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
tarball = Path(f'/content/diploma_b3_b4_results_{ts}.tar.gz')

with tarfile.open(tarball, 'w:gz') as tar:
    if OUTPUTS.exists(): tar.add(OUTPUTS, arcname='outputs')
    if PRACTICE.exists(): tar.add(PRACTICE, arcname='practice')
    if SPIDER_AUDIT.exists(): tar.add(SPIDER_AUDIT, arcname='data/spider/SOURCE_AND_AUDIT.md')
    if REPO_DOCS.exists():
        for p in REPO_DOCS.iterdir():
            if p.is_file(): tar.add(p, arcname=f'repo/docs/{p.name}')
    if REPO_EVAL.exists():
        for p in REPO_EVAL.iterdir():
            if p.is_file(): tar.add(p, arcname=f'repo/src/evaluation/{p.name}')

backup = PROJECT_ROOT / 'exports' / tarball.name
backup.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(tarball, backup)
stable = PROJECT_ROOT / 'exports' / 'latest_b3_b4.tar.gz'
shutil.copy2(tarball, stable)

print(f'TARBALL_DRIVE_PATH: {backup}')
print(f'TARBALL_STABLE_PATH: {stable}')
print(f'TARBALL_SIZE: {tarball.stat().st_size}')
