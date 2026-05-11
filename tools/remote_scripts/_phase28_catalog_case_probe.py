"""Probe the Snow catalog for actual column casing in PATENTS.PATENTS.PUBLICATIONS."""
import json
from pathlib import Path

cat_path = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/cache/spider2_snow_live_catalog_v18.jsonl')

# What fields does each row carry?
print('=== sample row fields ===')
with open(cat_path) as f:
    for i, ln in enumerate(f):
        if not ln.strip(): continue
        r = json.loads(ln)
        print(f'row {i}: keys={list(r.keys())}')
        print(f'   sample: {r}')
        if i >= 2: break

# Now scan PATENTS.PATENTS.PUBLICATIONS columns
print('\n=== scan for PATENTS.PATENTS.PUBLICATIONS ===')
found = {}
TARGET = ('PATENTS', 'PATENTS', 'PUBLICATIONS')
n_scanned = 0
with open(cat_path) as f:
    for ln in f:
        if not ln.strip(): continue
        n_scanned += 1
        r = json.loads(ln)
        # Try multiple field names
        db = (r.get('database') or r.get('db') or r.get('TABLE_CATALOG') or '').upper()
        sch = (r.get('schema') or r.get('TABLE_SCHEMA') or '').upper()
        tbl = (r.get('table') or r.get('TABLE_NAME') or '').upper()
        if (db, sch, tbl) != TARGET:
            continue
        col = r.get('column') or r.get('field_path') or r.get('COLUMN_NAME') or ''
        if not col: continue
        found[col] = r.get('data_type') or r.get('DATA_TYPE', '')

print(f'  scanned {n_scanned} rows; matched {len(found)} cols')
if found:
    # Case distribution
    lower = [c for c in found if c == c.lower()]
    upper = [c for c in found if c == c.upper()]
    mixed = [c for c in found if c != c.lower() and c != c.upper()]
    print(f'  case dist: lower={len(lower)} upper={len(upper)} mixed={len(mixed)}')
    print(f'\n  first 20 sorted cols + types:')
    for c in sorted(found.keys())[:20]:
        print(f'    {c!r} -> {found[c]!r}')
    # Probe specific cols
    print('\n  specific col case check:')
    for q in ['family_id', 'FAMILY_ID', 'grant_date', 'GRANT_DATE', 'assignee', 'ASSIGNEE',
              'date', 'DATE', 'country', 'COUNTRY', 'kind_code', 'KIND_CODE',
              'publication_date', 'PUBLICATION_DATE', 'fterm', 'FTERM']:
        present = q in found
        upper_form = q.upper() in found
        lower_form = q.lower() in found
        print(f'    {q!r}: exact={present} upper_in={upper_form} lower_in={lower_form}')
