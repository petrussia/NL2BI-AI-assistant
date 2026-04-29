"""Replace empty cell e40d182b with a catbox.moe export cell."""
import json
from pathlib import Path

NB = Path(r"D:\HSE\Диплом\NL2BI-AI-assistant\notebooks\example.ipynb")
TARGET_ID = "e40d182b"

SRC = '''# B1_EXPORT_CATBOX
import datetime as dt
import shutil
import subprocess
import tarfile
from pathlib import Path

MARKER = 'B1_EXPORT_CATBOX'
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

backup_drive = PROJECT_ROOT / 'exports' / tarball.name
backup_drive.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(tarball, backup_drive)
print(f'BACKUP_TO_DRIVE: {backup_drive}')

# Try catbox.moe (most reliable anonymous file host as of 2026)
def try_catbox():
    r = subprocess.run(
        ['curl', '-sS',
         '-F', 'reqtype=fileupload',
         '-F', f'fileToUpload=@{tarball}',
         'https://catbox.moe/user/api.php'],
        capture_output=True, text=True, timeout=300,
    )
    out = (r.stdout or '').strip()
    if r.returncode == 0 and out.startswith('http'):
        return ('catbox.moe', out)
    return ('catbox_failed', f'rc={r.returncode} stdout={out!r} stderr={r.stderr!r}')

# Fallback: tmpfiles.org
def try_tmpfiles():
    r = subprocess.run(
        ['curl', '-sS', '-F', f'file=@{tarball}', 'https://tmpfiles.org/api/v1/upload'],
        capture_output=True, text=True, timeout=300,
    )
    out = (r.stdout or '').strip()
    if r.returncode == 0 and 'tmpfiles.org' in out:
        try:
            import json as _json
            j = _json.loads(out)
            url = j.get('data', {}).get('url', '')
            if url:
                # tmpfiles gives a viewer URL; convert to direct
                direct = url.replace('://tmpfiles.org/', '://tmpfiles.org/dl/')
                return ('tmpfiles.org', direct)
        except Exception:
            pass
        return ('tmpfiles_parse_fail', out)
    return ('tmpfiles_failed', f'rc={r.returncode} stdout={out!r} stderr={r.stderr!r}')

# Fallback: oshi.at
def try_oshi():
    r = subprocess.run(
        ['curl', '-sS', '-F', f'f=@{tarball}', 'https://oshi.at'],
        capture_output=True, text=True, timeout=300,
    )
    out = (r.stdout or '')
    # oshi returns lines like "DL: <url>\nADMIN: <url>"
    for line in out.splitlines():
        if line.startswith('DL:'):
            url = line.split(':', 1)[1].strip()
            if url.startswith('http'):
                return ('oshi.at', url)
    return ('oshi_failed', f'rc={r.returncode} stdout={out!r} stderr={r.stderr!r}')

success = False
for fn in (try_catbox, try_tmpfiles, try_oshi):
    name, info = fn()
    print(f'TRY {name}: {info}')
    if name in ('catbox.moe', 'tmpfiles.org', 'oshi.at') and info and info.startswith('http'):
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
for c in nb["cells"]:
    if c.get("id") == TARGET_ID:
        c["source"] = SRC.splitlines(keepends=True)
        c["outputs"] = []
        c["execution_count"] = None
        NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"Updated cell {TARGET_ID} with B1_EXPORT_CATBOX content ({len(SRC)} chars)")
        break
else:
    print(f"Cell {TARGET_ID} not found")
