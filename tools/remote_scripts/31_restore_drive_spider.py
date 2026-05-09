# Restore Spider data on Drive (re-download from gdown).

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
SPIDER_DIR = PROJECT_ROOT / 'data' / 'spider'
SPIDER_DIR.mkdir(parents=True, exist_ok=True)

if (SPIDER_DIR / 'dev.json').exists() and (SPIDER_DIR / 'tables.json').exists() and (SPIDER_DIR / 'database').exists():
    print('Spider data already present, skipping download')
else:
    print('Downloading Spider...')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'gdown'], check=True)
    tmp = PROJECT_ROOT / '.tmp' / 'spider_download'
    tmp.mkdir(parents=True, exist_ok=True)
    zip_path = tmp / 'spider_data.zip'
    if zip_path.exists():
        zip_path.unlink()
    subprocess.run([sys.executable, '-m', 'gdown', '--fuzzy',
                    'https://drive.google.com/uc?id=1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J',
                    '-O', str(zip_path)], check=True)
    extract_dir = tmp / 'extract'
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    all_paths = list(extract_dir.rglob('*'))
    for filename in ['dev.json','tables.json','train_spider.json','train_others.json']:
        matches = [p for p in all_paths if p.is_file() and p.name == filename]
        if matches:
            shutil.copy2(matches[0], SPIDER_DIR / filename)
    db_src = next((p for p in all_paths if p.is_dir() and p.name == 'database' and list(p.rglob('*.sqlite'))), None)
    if db_src:
        dst = SPIDER_DIR / 'database'
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(db_src, dst)

# Make subsets
import json as _json
dev = _json.loads((SPIDER_DIR / 'dev.json').read_text(encoding='utf-8'))
subsets_dir = SPIDER_DIR / 'subsets'
subsets_dir.mkdir(parents=True, exist_ok=True)
for n in [10, 25, 50]:
    p = subsets_dir / f'smoke_{n}.json'
    if not p.exists():
        p.write_text(_json.dumps(dev[:n], ensure_ascii=False, indent=2), encoding='utf-8')

# Multidb_30 already designed; rebuild via stage 4 logic if missing
md_path = subsets_dir / 'multidb_30.json'
if not md_path.exists():
    from collections import defaultdict
    by_db = defaultdict(list)
    for ex in dev: by_db[ex['db_id']].append(ex)
    PER_DB = 5
    SKIP = {'concert_singer'}
    selected = []
    for db_id in sorted(by_db.keys()):
        if db_id in SKIP: continue
        if len(by_db[db_id]) < PER_DB: continue
        selected.extend(by_db[db_id][:PER_DB])
        if len(selected) >= 30: break
    selected = selected[:30]
    md_path.write_text(_json.dumps(selected, ensure_ascii=False, indent=2), encoding='utf-8')

print('SPIDER_RESTORED')
print(f'  dev: {(SPIDER_DIR / "dev.json").stat().st_size} B')
print(f'  tables: {(SPIDER_DIR / "tables.json").stat().st_size} B')
print(f'  database/: {sum(1 for _ in (SPIDER_DIR / "database").rglob("*.sqlite"))} sqlite files')
print(f'  subsets/: {sorted(p.name for p in subsets_dir.iterdir())}')
print('STATUS=DONE')
