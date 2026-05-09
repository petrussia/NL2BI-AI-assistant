# Stage 4: build a reproducible multi-DB subset (~30 examples, >=5 unique DBs).

import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
SPIDER_DIR = PROJECT_ROOT / 'data' / 'spider'
OUTPUTS = PROJECT_ROOT / 'outputs'

dev = json.loads((SPIDER_DIR / 'dev.json').read_text(encoding='utf-8'))

# Group by db_id, preserve original order within each group
by_db = defaultdict(list)
for ex in dev:
    by_db[ex['db_id']].append(ex)

# Construction logic (deterministic, no random):
#   1. Sort db_ids alphabetically.
#   2. SKIP concert_singer (already covered by smoke10/25 — we want CROSS-DB signal).
#   3. For each db_id (in sorted order), take the first PER_DB examples
#      (PER_DB chosen so that cumulative count crosses 30 and gives >=5 distinct DBs).
PER_DB = 5  # 5 examples * 6 DBs = 30
SKIP = {'concert_singer'}

selected = []
db_used = []
for db_id in sorted(by_db.keys()):
    if db_id in SKIP:
        continue
    if len(by_db[db_id]) < PER_DB:
        continue  # require at least PER_DB examples available so each DB contributes equally
    take = by_db[db_id][:PER_DB]
    selected.extend(take)
    db_used.append(db_id)
    if len(selected) >= 30:
        break

# Trim to exactly 30 if overshoot (PER_DB * floor would be <=30 here, but be safe)
selected = selected[:30]

assert len(selected) == 30, f'expected 30, got {len(selected)}'
assert len(db_used) >= 5, f'need >=5 DBs, got {len(db_used)}'

subset_path = SPIDER_DIR / 'subsets' / 'multidb_30.json'
subset_path.parent.mkdir(parents=True, exist_ok=True)
subset_path.write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding='utf-8')

# Audit
ts = dt.datetime.now(dt.timezone.utc).isoformat()
md = ['# Multi-DB Subset Audit (multidb_30)', '',
      f'Built at: {ts}',
      f'Source: `data/spider/dev.json`',
      f'Output: `{subset_path}`',
      '',
      f'- N items: **{len(selected)}**',
      f'- Unique databases: **{len(db_used)}**',
      f'- Per-DB target: **{PER_DB}** items each',
      f'- Skipped DBs: **{sorted(SKIP)}** (covered by smoke10/smoke25)',
      f'- Selection rule: alphabetical sort of db_id, take first PER_DB items (deterministic, no randomness)',
      '',
      '## Selected DBs and counts', '',
      '| db_id | items |',
      '|---|---|']
for db in db_used:
    n = sum(1 for e in selected if e['db_id'] == db)
    md.append(f'| `{db}` | {n} |')
md += ['',
       '## Reproducibility',
       '',
       '- No `random.seed` involved.',
       '- Spider `dev.json` byte-identical (see `data/spider/SOURCE_AND_AUDIT.md`).',
       '- The same script produces the same subset on any kernel.',
       '',
       '## Why this composition (no cherry-picking)',
       '',
       '- Sorting by db_id is a property of the dataset, not of difficulty.',
       '- Taking the first PER_DB items per DB preserves the original Spider ordering within each DB.',
       '- This may include both easy and hard questions; the only filter applied is the per-DB count.',
       '']
audit_path = OUTPUTS / 'logs' / 'multidb_30_audit.md'
audit_path.write_text('\n'.join(md), encoding='utf-8')

print(f'WROTE {subset_path} ({subset_path.stat().st_size} B)')
print(f'WROTE {audit_path}')
print(f'N={len(selected)}  unique_dbs={len(db_used)}')
print(f'DBs: {db_used}')
print('STATUS=DONE')
