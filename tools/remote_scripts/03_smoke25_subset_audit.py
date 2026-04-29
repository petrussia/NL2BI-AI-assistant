# Step 3: smoke25 subset audit. Just inspect the existing subset, no inference.

import datetime as dt
import json
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
SPIDER_DIR = PROJECT_ROOT / 'data' / 'spider'
OUTPUTS = PROJECT_ROOT / 'outputs'

subset_path = SPIDER_DIR / 'subsets' / 'smoke_25.json'
assert subset_path.exists(), f'missing {subset_path}'

smoke25 = json.loads(subset_path.read_text(encoding='utf-8'))
n = len(smoke25)
db_counts = Counter(item['db_id'] for item in smoke25)
unique_dbs = len(db_counts)
all_have_question = all('question' in item and 'query' in item for item in smoke25)

# Cross-reference with tables.json + db_paths
import sys
mm = sys.modules['__main__']
tables_map = getattr(mm, 'tables_map', None) or globals().get('tables_map')
db_paths = getattr(mm, 'db_paths', None) or globals().get('db_paths')

dbs_in_tables = sum(1 for db in db_counts if db in (tables_map or {}))
dbs_in_paths = sum(1 for db in db_counts if db in (db_paths or {}))

# Check for overlap with smoke10
smoke10 = json.loads((SPIDER_DIR / 'subsets' / 'smoke_10.json').read_text(encoding='utf-8'))
smoke10_keys = {(it['db_id'], it['question']) for it in smoke10}
smoke25_keys = {(it['db_id'], it['question']) for it in smoke25}
overlap = smoke10_keys & smoke25_keys
overlap_count = len(overlap)

print(f'subset_path: {subset_path}')
print(f'n_items: {n}')
print(f'unique_dbs: {unique_dbs}')
print(f'all_have_question_and_query: {all_have_question}')
print(f'dbs_in_tables_map: {dbs_in_tables} / {unique_dbs}')
print(f'dbs_in_db_paths: {dbs_in_paths} / {unique_dbs}')
print(f'overlap_with_smoke10: {overlap_count} / {n}')
print()
print('--- db distribution ---')
for db, c in db_counts.most_common():
    print(f'  {c:>3}  {db}')

ts = dt.datetime.now(dt.timezone.utc).isoformat()
md_lines = [
    '# Smoke25 Subset Audit',
    '',
    f'Audited at: {ts}',
    f'Source: `{subset_path}`',
    '',
    f'- N items: **{n}**',
    f'- Unique databases: **{unique_dbs}**',
    f'- All have `question` + `query`: {all_have_question}',
    f'- Databases present in `tables.json`: {dbs_in_tables} / {unique_dbs}',
    f'- Databases present in DB paths (sqlite files): {dbs_in_paths} / {unique_dbs}',
    f'- Overlap with smoke10 (same db_id + question): {overlap_count} / {n}',
    '',
    '## Database distribution',
    '',
    '| Count | db_id |',
    '|---|---|',
]
for db, c in db_counts.most_common():
    md_lines.append(f'| {c} | `{db}` |')

target = OUTPUTS / 'logs' / 'smoke25_subset_audit.md'
target.write_text('\n'.join(md_lines) + '\n', encoding='utf-8')
print(f'\nWROTE {target}')
print(f'AUDIT_OK={all_have_question and dbs_in_tables == unique_dbs and dbs_in_paths == unique_dbs}')
