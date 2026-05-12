"""Diagnose why post-resume 74 tasks on S1 Snow have 0 exec_ok."""
import json
from pathlib import Path
from collections import Counter, defaultdict

RUN = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_snow/runs/snow_full_v28_revert_a')
preds = []
with open(RUN / 'predictions.jsonl') as f:
    for ln in f:
        if ln.strip(): preds.append(json.loads(ln))
print(f'total preds: {len(preds)}')

# Pre vs post resume — boundary is 261 (where kernel crashed)
PRE = preds[:261]
POST = preds[261:]
print(f'pre-resume (1-261): {len(PRE)} | post-resume (262+): {len(POST)}')

def cohort_stats(rows, label):
    if not rows: return
    sv = sum(1 for p in rows if p.get('schema_valid'))
    pa = sum(1 for p in rows if p.get('parse_ok'))
    ex = sum(1 for p in rows if p.get('explain_ok'))
    err_cls = Counter(p.get('explain_class','?') for p in rows if not p.get('explain_ok'))
    dbs = Counter(p.get('task_db','?') for p in rows)
    print(f'\n=== {label} (n={len(rows)}) ===')
    print(f'  sv={sv}/{len(rows)} ({sv*100//len(rows)}%)')
    print(f'  parse={pa}/{len(rows)} ({pa*100//len(rows)}%)')
    print(f'  exec={ex}/{len(rows)} ({ex*100//len(rows)}%)')
    print(f'  err class top 8:')
    for cls, n in err_cls.most_common(8):
        print(f'    {cls:30s} {n}')
    print(f'  unique DBs: {len(dbs)}')
    print(f'  top 15 DBs:')
    for db, n in dbs.most_common(15):
        # exec count for this DB
        e = sum(1 for p in rows if p.get('task_db')==db and p.get('explain_ok'))
        print(f'    {db:35s} {e}/{n}')

cohort_stats(PRE, 'PRE-resume (1-261)')
cohort_stats(POST, 'POST-resume (262+)')

# Sample post-resume failures
print('\n=== sample post-resume failures (5) ===')
failed = [p for p in POST if not p.get('explain_ok')]
for p in failed[:5]:
    iid = p.get('instance_id')
    db = p.get('task_db')
    cls = p.get('explain_class', '?')
    sql = (p.get('sql') or '').replace('\n', ' ').strip()[:180]
    print(f'\n  {iid} db={db} class={cls}')
    print(f'  SQL: {sql}')

# Check traces for fixer activity post-resume
tf = RUN / 'traces.jsonl'
trace_map = {}
if tf.exists():
    with open(tf) as f:
        for ln in f:
            if not ln.strip(): continue
            try:
                t = json.loads(ln)
                iid = t.get('instance_id')
                if iid: trace_map[iid] = t
            except Exception: pass

print('\n=== F4 wrap activity post-resume (sample of 8) ===')
for p in POST[:8]:
    iid = p.get('instance_id')
    t = trace_map.get(iid, {})
    print(f'  {iid}: f4={t.get("f4")} guard={t.get("guard")} sv={p.get("schema_valid")} ex={p.get("explain_ok")}')
