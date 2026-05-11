"""Phase 27 Step 1 — catalog drift diagnostic on v26 Lite-Snow predictions.

Reads predictions, extracts FROM/JOIN refs, classifies first-segment
catalog vs task.db.
"""
import json, re
from collections import Counter
from pathlib import Path

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')

# Build iid -> task_db map
tasks_by_iid = {}
with open(DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl') as f:
    for ln in f:
        if not ln.strip(): continue
        t = json.loads(ln)
        iid = t.get('instance_id')
        if iid: tasks_by_iid[iid] = (t.get('db') or t.get('db_id') or '').upper()

# Valid Snow DBs from catalog
valid_dbs = set()
n = 0
with open(DRV / 'outputs/cache/spider2_snow_live_catalog_v18.jsonl') as f:
    for ln in f:
        if not ln.strip(): continue
        n += 1
        if n > 200000: break
        r = json.loads(ln)
        if r.get('kind') in ('error','table'): continue
        db = r.get('database') or r.get('TABLE_CATALOG','')
        if db: valid_dbs.add(db.upper())
print(f'valid_dbs (sampled {n} rows): {len(valid_dbs)}')

FROM_RE = re.compile(r'\b(?:FROM|JOIN)\s+([\w\."`]+)', re.IGNORECASE)

preds_path = DRV / 'outputs/spider2_lite/runs/lite_snow_full_v26/predictions.jsonl'

correct_tasks = 0
wrong_tasks = 0
no_cat_tasks = 0
mixed_tasks = 0
no_refs = 0
wrong_examples = []
ref_distrib_per_class = Counter()

with open(preds_path) as f:
    for ln in f:
        if not ln.strip(): continue
        p = json.loads(ln)
        iid = p['instance_id']
        task_db = tasks_by_iid.get(iid, '')
        sql = p.get('sql','') or ''
        if not sql or not task_db: continue
        refs = FROM_RE.findall(sql)
        tags = []
        for ref in refs:
            clean = ref.replace('"','').replace('`','').strip().rstrip(';,)')
            parts = clean.split('.')
            if len(parts) == 3:
                cat = parts[0].upper()
                if cat == task_db: tags.append('correct')
                elif cat in valid_dbs: tags.append('wrong')
                else: tags.append('unknown')
            else:
                tags.append('no_cat')
            ref_distrib_per_class[tags[-1]] += 1
        if not tags:
            no_refs += 1
            continue
        unique = set(tags)
        if unique == {'correct'}: correct_tasks += 1
        elif 'wrong' in unique or 'unknown' in unique:
            if 'correct' in unique:
                mixed_tasks += 1
            else:
                wrong_tasks += 1
                if len(wrong_examples) < 5:
                    wrong_examples.append((iid, task_db, refs[:3]))
        elif unique == {'no_cat'}: no_cat_tasks += 1

total = correct_tasks + wrong_tasks + no_cat_tasks + mixed_tasks + no_refs
print()
print(f'=== Catalog drift diagnostic (Lite-Snow v26, n={total}) ===')
print(f'  correct_only  (all FROM use task_db catalog):  {correct_tasks} ({correct_tasks*100/max(total,1):.1f}%)')
print(f'  wrong/unknown (all FROM NOT task_db):          {wrong_tasks} ({wrong_tasks*100/max(total,1):.1f}%)')
print(f'  no_catalog    (bare TABLE or SCHEMA.TABLE):    {no_cat_tasks} ({no_cat_tasks*100/max(total,1):.1f}%)')
print(f'  mixed         (some correct + some wrong):     {mixed_tasks} ({mixed_tasks*100/max(total,1):.1f}%)')
print(f'  no_refs       (couldnt extract FROM):          {no_refs}')
print()
print('Per-reference (not per-task) classification:')
for cls, cnt in ref_distrib_per_class.most_common():
    print(f'  {cls}: {cnt}')
print()
print('Sample wrong cases (task_db vs refs):')
for iid, task_db, refs in wrong_examples:
    print(f'  {iid} task_db={task_db}: refs={refs}')
print()
print(f'VERDICT: (wrong + no_catalog + mixed) tasks = {wrong_tasks + no_cat_tasks + mixed_tasks} / {total} = {(wrong_tasks+no_cat_tasks+mixed_tasks)*100/max(total,1):.1f}%')
print(f'         correct_only tasks = {correct_tasks} / {total} = {correct_tasks*100/max(total,1):.1f}%')
