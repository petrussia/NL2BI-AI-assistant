"""Compare pilot10 v27c vs v28 per-task: SQL diff + catalog case check."""
import json
from pathlib import Path

BASE = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_lite/runs')

def load(run_id):
    out = {'preds': {}, 'traces': {}}
    for fname in ['predictions.jsonl', 'traces.jsonl']:
        p = BASE / run_id / fname
        if not p.exists(): continue
        with open(p) as f:
            for ln in f:
                r = json.loads(ln)
                key = r.get('instance_id') or r.get('iid')
                out['preds' if fname == 'predictions.jsonl' else 'traces'][key] = r
    return out

v27c = load('lite_snow_pilot10_v27c')
v28 = load('lite_snow_pilot10_v28')

print('=== per-task diff: was OK in v27c vs now ===')
for iid in sorted(set(v27c['traces']) & set(v28['traces'])):
    t_old = v27c['traces'][iid]
    t_new = v28['traces'][iid]
    sql_old = (v27c['preds'].get(iid, {}).get('sql') or '').strip()
    sql_new = (v28['preds'].get(iid, {}).get('sql') or '').strip()

    sv_old = t_old.get('schema_valid')
    sv_new = t_new.get('schema_valid')
    ex_old = t_old.get('explain_ok')
    ex_new = t_new.get('explain_ok')
    req = (t_new.get('f2a') or {}).get('requoted_n', 0)
    wrp = (t_new.get('f4') or {}).get('wrapped_n', 0)

    delta = []
    if sv_old != sv_new: delta.append(f'sv {sv_old}->{sv_new}')
    if ex_old != ex_new: delta.append(f'exec {ex_old}->{ex_new}')

    err_old = (t_old.get('explain_msg') or t_old.get('sv_msg') or '').split('\n')[0][:80]
    err_new = (t_new.get('explain_msg') or t_new.get('sv_msg') or t_new.get('guard_error') or '').split('\n')[0][:80]

    print(f'\n{iid}  | F2a={req} F4={wrp} | {", ".join(delta) or "no change"}')
    print(f'  v27c err: {err_old}')
    print(f'  v28  err: {err_new}')

# Specifically dump sf_bq211 — the one that regressed
print('\n\n=== sf_bq211 detailed diff ===')
iid = 'sf_bq211'
sql_old = v27c['preds'].get(iid, {}).get('sql', '').strip()
sql_new = v28['preds'].get(iid, {}).get('sql', '').strip()
print(f'v27c SQL: {sql_old}')
print(f'\nv28  SQL: {sql_new}')

# What's in the catalog for PUBLICATIONS that matters?
cat_path = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/cache/spider2_snow_live_catalog_v18.jsonl')
target_cols_v27c = ['family_id', 'grant_date', 'assignee']  # lower
target_cols_v28 = ['FAMILY_ID', 'GRANT_DATE', 'ASSIGNEE']    # upper

print('\n=== catalog probe: PATENTS.PATENTS.PUBLICATIONS columns ===')
found = {}
with open(cat_path) as f:
    for ln in f:
        if not ln.strip(): continue
        r = json.loads(ln)
        if (r.get('database', '').upper() != 'PATENTS' or
            r.get('schema', '').upper() != 'PATENTS' or
            r.get('table', '').upper() != 'PUBLICATIONS'):
            continue
        col = r.get('column') or r.get('field_path') or ''
        if not col: continue
        found[col] = r.get('data_type', '')
        if len(found) >= 200: break

# Print all columns and their case
print(f'  total cols found: {len(found)}')
for c in sorted(found.keys()):
    if any(c.lower() == t.lower() for t in target_cols_v27c + ['date', 'country', 'kind_code']):
        print(f'  {c!r} -> {found[c]}')

# Lower-case overlap
lower_keys = [c for c in found if c == c.lower()]
upper_keys = [c for c in found if c == c.upper()]
mixed = [c for c in found if c != c.lower() and c != c.upper()]
print(f'\n  case dist: lower={len(lower_keys)}, upper={len(upper_keys)}, mixed={len(mixed)}')
print(f'  first 5 lower: {lower_keys[:5]}')
print(f'  first 5 upper: {upper_keys[:5]}')
