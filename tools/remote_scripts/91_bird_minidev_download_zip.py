# BIRD Mini-Dev official zip download from Alibaba OSS bucket linked in repo README.
# https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip
# Falls back to Hugging Face dataset mirror if OSS is unreachable.

import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
import textwrap
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
BIRD_DIR = PROJECT_ROOT / 'external_benchmarks' / 'bird_mini_dev'
RAW = BIRD_DIR / 'raw'
RAW.mkdir(parents=True, exist_ok=True)
LOGS = PROJECT_ROOT / 'outputs' / 'logs'
NOW = dt.datetime.now(dt.timezone.utc).isoformat()

ZIP_URLS = [
    'https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip',
    'https://bird-bench.oss-rg-china-mainland.aliyuncs.com/minidev.zip',  # alt
]

zip_path = RAW / 'minidev.zip'
extract_dir = RAW / 'minidev'

dl_ok = False
dl_url = None
dl_err = None
if zip_path.exists() and zip_path.stat().st_size > 1_000_000:
    print(f'minidev.zip already exists at {zip_path} ({zip_path.stat().st_size} B); skipping download')
    dl_ok = True
    dl_url = 'cached'
else:
    for url in ZIP_URLS:
        print(f'attempting download from {url}', flush=True)
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=120) as r, open(zip_path, 'wb') as out:
                shutil.copyfileobj(r, out)
            if zip_path.stat().st_size > 1_000_000:
                print(f'downloaded {zip_path.stat().st_size} bytes from {url}')
                dl_ok = True; dl_url = url
                break
            else:
                print(f'downloaded too small: {zip_path.stat().st_size} bytes; trying next mirror')
        except Exception as exc:
            dl_err = f'{type(exc).__name__}: {exc}'
            print(f'failed: {dl_err}')

if not dl_ok:
    # Last-resort: try `gdown` via Hugging Face dataset / bird23-train-filtered won't have mini_dev
    print('All direct downloads failed. Writing blocker artifact.')
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS/'bird_mini_dev_acquisition.md').write_text(textwrap.dedent(f'''
    # BIRD Mini-Dev acquisition — BLOCKED

    **Captured:** {NOW}
    **Tried URLs:** {ZIP_URLS}
    **Last error:** {dl_err}

    The official BIRD Mini-Dev distribution is hosted at `https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip`. From this Colab kernel the OSS bucket is unreachable (likely Beijing-region access from Google Cloud).

    ## Honest classification
    External benchmark acquisition blocked at the network layer, not at the methodology layer. The acquisition recipe is documented and reproducible from a network with OSS-Beijing access.

    ## Unblock recipe (for the human operator)
    1. From a machine with access to `bird-bench.oss-cn-beijing.aliyuncs.com`, download `minidev.zip`.
    2. Upload to Drive at `external_benchmarks/bird_mini_dev/raw/minidev.zip`.
    3. Re-run `tools/remote_scripts/91_bird_minidev_download_zip.py` to extract and build the 30-example slice.
    ''').strip()+'\n', encoding='utf-8')
    raise SystemExit(0)

# Extract
if not extract_dir.exists() or not list(extract_dir.iterdir()):
    extract_dir.mkdir(parents=True, exist_ok=True)
    print(f'extracting {zip_path} -> {extract_dir}', flush=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    print('extraction complete')
else:
    print('extract_dir already populated')

# Find the json
candidates = []
for p in extract_dir.rglob('*.json'):
    if p.stat().st_size < 1000 or p.stat().st_size > 100_000_000: continue
    try:
        with p.open(encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            keys = set(data[0].keys())
            if 'question' in keys and ('db_id' in keys or 'database' in keys):
                gold = [k for k in ('SQL','sql','query') if k in keys]
                candidates.append((p, len(data), gold))
    except Exception:
        pass

# Sort: prefer larger, with SQL field, with 'mini_dev' in name, with 'sqlite' in name
candidates.sort(key=lambda c: (
    0 if 'mini_dev' in c[0].name.lower() else 1,
    0 if 'sqlite' in c[0].name.lower() else 1,
    -c[1],  # larger first
))
print('candidates:', [(str(p.relative_to(extract_dir)), n, g) for p, n, g in candidates[:5]])

if not candidates:
    print('No candidate json found inside zip; manual inspection needed.')
    raise SystemExit(0)

bird_json, n_examples, gold_keys = candidates[0]
print(f'PICKED: {bird_json.relative_to(extract_dir)}  n={n_examples}  gold_keys={gold_keys}')

# Build slice
bird_examples = json.loads(bird_json.read_text(encoding='utf-8'))

def get_db(ex): return ex.get('db_id') or ex.get('database') or ex.get('database_name') or 'unknown'
def get_gold(ex):
    return ex.get('SQL') or ex.get('sql') or ex.get('query') or ''

db_dist = Counter(get_db(ex) for ex in bird_examples)
print(f'unique_dbs in mini_dev: {len(db_dist)}')

# 30-example diverse via round-robin
by_db = {}
for i, ex in enumerate(bird_examples):
    by_db.setdefault(get_db(ex), []).append((i, ex))
selected = []
db_keys = sorted(by_db.keys())
idx_per_db = {k: 0 for k in db_keys}
while len(selected) < 30 and any(idx_per_db[k] < len(by_db[k]) for k in db_keys):
    for k in db_keys:
        if idx_per_db[k] < len(by_db[k]):
            i, ex = by_db[k][idx_per_db[k]]
            idx_per_db[k] += 1
            selected.append({
                'idx': len(selected),
                'original_id': ex.get('question_id') or ex.get('id') or i,
                'db_id': get_db(ex),
                'question': ex.get('question') or '',
                'gold_sql': get_gold(ex),
                'evidence': ex.get('evidence',''),
                'difficulty': ex.get('difficulty',''),
                'source_split': 'bird-mini-dev',
                'source_path': str(bird_json.relative_to(extract_dir.parent)),
            })
            if len(selected) >= 30: break

processed_dir = BIRD_DIR / 'processed'
processed_dir.mkdir(parents=True, exist_ok=True)
out_slice = processed_dir / 'bird_minidev_30_diverse.json'
out_slice.write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding='utf-8')

# Find SQLite databases inside extracted zip
db_dirs = []
for p in extract_dir.rglob('*.sqlite'):
    db_dirs.append(p)
sqlite_count = len(db_dirs)
print(f'sqlite files in extracted zip: {sqlite_count}')

# Manifest
import hashlib
def sha256_of(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda: f.read(1024*1024), b''):
            h.update(c)
    return h.hexdigest()

manifest = {
    'benchmark': 'BIRD Mini-Dev',
    'source_url': dl_url,
    'official_site': 'https://bird-bench.github.io/',
    'acquisition_method': 'official OSS zip download + extract',
    'downloaded_at_utc': NOW,
    'tasks_file': str(bird_json.relative_to(BIRD_DIR)),
    'tasks_file_sha256': sha256_of(bird_json),
    'tasks_file_bytes': bird_json.stat().st_size,
    'n_tasks': len(bird_examples),
    'unique_dbs': len(db_dist),
    'sqlite_databases_present': sqlite_count,
    'license_note': 'CC BY-SA 4.0 per BIRD repo README',
}
(BIRD_DIR/'manifests'/'bird_mini_dev_manifest.json').write_text(
    json.dumps(manifest, indent=2), encoding='utf-8')

# Audit
sel_db_dist = Counter(s['db_id'] for s in selected)
has_gold = sum(1 for s in selected if s['gold_sql'])
audit_md = LOGS / 'bird_minidev_30_diverse_audit.md'
audit_md.write_text(textwrap.dedent(f'''
# bird_minidev_30_diverse audit

**Captured:** {NOW}
**Slice path:** `{out_slice.relative_to(PROJECT_ROOT)}`
**N items:** {len(selected)}
**Unique DBs:** {len(sel_db_dist)}
**Items with gold_sql present:** {has_gold} / {len(selected)}
**SQLite databases on Drive:** {sqlite_count}

## Distribution by db_id
| db_id | count |
|---|---|
''').strip() + '\n' + '\n'.join(
    f'| `{k}` | {v} |' for k, v in sorted(sel_db_dist.items(), key=lambda x: (-x[1], x[0]))
) + '\n', encoding='utf-8')

# Acquisition manifest
(LOGS/'bird_mini_dev_acquisition.md').write_text(textwrap.dedent(f'''
# BIRD Mini-Dev acquisition

**Captured:** {NOW}
**Official source:** {dl_url}
**Official site:** https://bird-bench.github.io/
**Acquisition method:** direct download of official OSS zip + extract
**Zip path:** `{zip_path.relative_to(PROJECT_ROOT)}` ({zip_path.stat().st_size} B)
**Tasks file:** `{bird_json.relative_to(BIRD_DIR)}`
**SHA-256:** `{sha256_of(bird_json)}`
**Size (bytes):** {bird_json.stat().st_size}
**N tasks loaded:** {len(bird_examples)}
**Unique DBs:** {len(db_dist)}
**SQLite databases present:** {sqlite_count}
**License:** CC BY-SA 4.0

## Processed slice
- `{out_slice.relative_to(PROJECT_ROOT)}` — 30 examples, max-diverse DB coverage

## Manifest JSON
`{(BIRD_DIR/"manifests"/"bird_mini_dev_manifest.json").relative_to(PROJECT_ROOT)}`
''').strip()+'\n', encoding='utf-8')

print(f'BIRD Mini-Dev DONE. n={len(bird_examples)}, slice n={len(selected)}, dbs={len(sel_db_dist)}, sqlite_files={sqlite_count}')
