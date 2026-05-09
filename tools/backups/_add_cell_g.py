import json
import uuid
from pathlib import Path

NB = Path(r"D:\HSE\Диплом\NL2BI-AI-assistant\notebooks\example.ipynb")

CELL_G_SOURCE = '''# B1_EXPORT_TARBALL
import datetime as dt
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

MARKER = 'B1_EXPORT_TARBALL'
PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
PRACTICE = PROJECT_ROOT / 'practice'
SPIDER_AUDIT = PROJECT_ROOT / 'data' / 'spider' / 'SOURCE_AND_AUDIT.md'

ts = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
tarball = Path(f'/content/diploma_b1_results_{ts}.tar.gz')

with tarfile.open(tarball, 'w:gz') as tar:
    tar.add(OUTPUTS, arcname='outputs')
    tar.add(PRACTICE, arcname='practice')
    if SPIDER_AUDIT.exists():
        tar.add(SPIDER_AUDIT, arcname='data/spider/SOURCE_AND_AUDIT.md')

size = tarball.stat().st_size
print(f'TARBALL: {tarball} size={size} bytes')

# Backup copy to Drive so the tarball survives even if uploads fail
backup_drive = PROJECT_ROOT / 'exports' / tarball.name
backup_drive.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(tarball, backup_drive)
print(f'BACKUP_TO_DRIVE: {backup_drive}')

def try_0x0st():
    r = subprocess.run(
        ['curl', '-sS', '-F', f'file=@{tarball}', '-F', 'expires=24', 'https://0x0.st'],
        capture_output=True, text=True, timeout=180,
    )
    out = (r.stdout or '').strip()
    if r.returncode == 0 and out.startswith('http'):
        return ('0x0.st', out)
    return ('0x0.st_failed', f'rc={r.returncode} stdout={out!r} stderr={r.stderr!r}')

def try_fileio():
    r = subprocess.run(
        ['curl', '-sS', '-F', f'file=@{tarball}', 'https://file.io/?expires=1d'],
        capture_output=True, text=True, timeout=180,
    )
    if r.returncode == 0:
        try:
            j = json.loads(r.stdout)
            if j.get('success') and j.get('link'):
                return ('file.io', j['link'])
        except Exception:
            pass
    return ('file.io_failed', f'rc={r.returncode} stdout={r.stdout!r} stderr={r.stderr!r}')

success = False
for fn in (try_0x0st, try_fileio):
    name, info = fn()
    print(f'TRY {name}: {info}')
    if name in ('0x0.st', 'file.io') and info and info.startswith('http'):
        print(f'EXPORT_URL: {info}')
        print(f'EXPORT_HOST: {name}')
        print(f'EXPORT_SIZE: {size}')
        print(MARKER + '_OK')
        success = True
        break

if not success:
    print(MARKER + '_FAILED_ALL_HOSTS')
    print(f'Tarball backup on Drive: {backup_drive}')
'''

nb = json.loads(NB.read_text(encoding="utf-8"))

# Check if already present
exists = any("B1_EXPORT_TARBALL" in "".join(c["source"]) for c in nb["cells"])
if exists:
    print("Cell B1_EXPORT_TARBALL already present, skipping")
else:
    new_cell = {
        "cell_type": "code",
        "id": uuid.uuid4().hex[:8],
        "metadata": {},
        "outputs": [],
        "execution_count": None,
        "source": CELL_G_SOURCE.splitlines(keepends=True),
    }
    nb["cells"].append(new_cell)
    NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Inserted export cell with id {new_cell['id']}")
    print(f"Total cells now: {len(nb['cells'])}")
