"""Print full trace fields for the 10 pilot10c tasks to find the OK one + dialect samples."""
import json
from pathlib import Path

RUN = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_lite/runs/lite_snow_pilot10_v27c')
traces = {}
with open(RUN / 'traces.jsonl') as f:
    for ln in f:
        t = json.loads(ln); traces[t.get('instance_id', t.get('iid'))] = t

preds = {}
with open(RUN / 'predictions.jsonl') as f:
    for ln in f:
        p = json.loads(ln); preds[p['instance_id']] = p

for iid in sorted(preds.keys()):
    t = traces.get(iid, {})
    print(f'\n=== {iid} ===')
    for k in sorted(t.keys()):
        v = t[k]
        if isinstance(v, str) and len(v) > 200:
            v = v[:200] + '...'
        print(f'  {k}: {v}')
    # also print the SQL
    sql = (preds[iid].get('sql') or '').strip()
    print(f'  SQL: {sql[:400]}')
