"""Diagnose why S2 post-resume has 0/79 exec_ok vs 11/40 pre-resume.

Hypotheses:
  A. Hard-DB cohort — pre-resume 40 were on easy DBs (PATENTS), post-resume on harder DBs
  B. Resume scaffolding broke pipeline (some state not restored)
  C. F4 wrapping wrong columns after resume

Approach:
  1. Per-DB breakdown of exec_ok / total in predictions.jsonl, split by pre/post resume boundary
  2. Sample 3-5 post-resume failures: SQL + error class
  3. Confirm fixer was actually called (trace.f4 nonzero on wrapped tasks)
"""
import json
from pathlib import Path
from collections import Counter, defaultdict

RUN = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_lite/runs/lite_snow_full_v28_revert_a')

# Read predictions
preds = []
with open(RUN / 'predictions.jsonl') as f:
    for ln in f:
        if not ln.strip(): continue
        preds.append(json.loads(ln))
print(f'total preds: {len(preds)}')

# The crash boundary: the first 40 were pre-crash, the rest are post-resume.
# Try to detect: traces.jsonl may have a discontinuity. Simpler: use index.
PRE = preds[:40]
POST = preds[40:]
print(f'pre-resume (first 40): {len(PRE)} | post-resume: {len(POST)}')

def stats(rows, label):
    ex = sum(1 for p in rows if p.get('explain_ok'))
    sv = sum(1 for p in rows if p.get('schema_valid'))
    pa = sum(1 for p in rows if p.get('parse_ok'))
    dbs = Counter()
    for p in rows: dbs[p.get('task_db', '?')] += 1
    print(f'\n=== {label} ({len(rows)}) ===')
    print(f'  sv={sv}/{len(rows)}, parse={pa}/{len(rows)}, exec={ex}/{len(rows)}')
    print(f'  unique DBs: {len(dbs)}')
    print(f'  top 10 DBs: {dbs.most_common(10)}')
    # Per-DB exec rate
    db_exec = defaultdict(lambda: [0,0])
    for p in rows:
        db = p.get('task_db', '?')
        db_exec[db][1] += 1
        if p.get('explain_ok'): db_exec[db][0] += 1
    print(f'  per-DB exec rates (sorted by total):')
    for db, (e, t) in sorted(db_exec.items(), key=lambda x: -x[1][1])[:15]:
        pct = e*100/t if t else 0
        print(f'    {db:30s} {e}/{t} ({pct:.0f}%)')

stats(PRE, 'pre-resume (first 40)')
stats(POST, 'post-resume (41+)')

# Sample post-resume failures
print('\n=== 5 sample post-resume FAILURES ===')
failed = [p for p in POST if not p.get('explain_ok')]
for i, p in enumerate(failed[:5]):
    sql = (p.get('sql') or '').replace('\n', ' ').strip()[:200]
    err = (p.get('explain_class') or p.get('error') or '?')
    print(f'\n#{i+1} iid={p.get("instance_id")} db={p.get("task_db")} err={err}')
    print(f'   SQL: {sql}')

# Check traces for fixer activity on post-resume tasks
print('\n=== fixer activity on post-resume sample ===')
traces = {}
with open(RUN / 'traces.jsonl') as f:
    for ln in f:
        if not ln.strip(): continue
        try:
            t = json.loads(ln)
            traces[t.get('instance_id')] = t
        except Exception:
            pass

for p in POST[:5]:
    iid = p.get('instance_id')
    t = traces.get(iid, {})
    f4 = t.get('f4', {})
    guard = t.get('guard', {})
    print(f'  {iid}: guard={guard} f4={f4} '
          f'sv={t.get("schema_valid")} ex={t.get("explain_ok")} '
          f'err={(t.get("explain_msg") or "")[:80]}')
