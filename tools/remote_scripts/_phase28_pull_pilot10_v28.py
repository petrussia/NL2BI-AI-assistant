"""Pull pilot10 v28 metrics + traces + classify per-task."""
import json
from pathlib import Path

RUN = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_lite/runs/lite_snow_pilot10_v28')

print('=== progress.json ===')
pj = (RUN / 'progress.json')
if pj.exists():
    d = json.loads(pj.read_text())
    for k in sorted(d.keys()):
        print(f'  {k}: {d[k]}')

print('\n=== _DONE ===')
done = (RUN / '_DONE')
if done.exists():
    d = json.loads(done.read_text())
    for k in sorted(d.keys()):
        print(f'  {k}: {d[k]}')

print('\n=== metrics.csv ===')
m = RUN / 'metrics.csv'
if m.exists():
    print(m.read_text())

print('\n=== error_taxonomy.csv ===')
e = RUN / 'error_taxonomy.csv'
if e.exists():
    print(e.read_text())

# Per-task detail
print('=== per-task ===')
preds = {}
with open(RUN / 'predictions.jsonl') as f:
    for ln in f:
        p = json.loads(ln); preds[p['instance_id']] = p

traces = {}
with open(RUN / 'traces.jsonl') as f:
    for ln in f:
        t = json.loads(ln); traces[t.get('instance_id', t.get('iid'))] = t

print(f"{'iid':14s} {'sv':>4s} {'parse':>5s} {'exec':>5s} {'req':>3s} {'wrp':>3s} {'err_msg':70s}")
print('-'*120)
for iid in sorted(preds.keys()):
    p = preds[iid]
    t = traces.get(iid, {})
    sv = str(t.get('schema_valid', '?'))
    pa = str(t.get('parse_ok', '?'))
    ex = str(t.get('explain_ok', '?'))
    req = (t.get('f2a') or {}).get('requoted_n', '?')
    wrp = (t.get('f4') or {}).get('wrapped_n', '?')
    msg = ((t.get('explain_msg') or t.get('sv_msg') or t.get('guard_error') or '')
           .replace('\n', ' '))[:70]
    print(f'{iid:14s} {sv:>4s} {pa:>5s} {ex:>5s} {str(req):>3s} {str(wrp):>3s} {msg}')

# Also pull the f2a/f4 traces in detail for OK cases
print('\n=== full traces for any execute_ok=True case ===')
for iid, t in traces.items():
    if t.get('explain_ok'):
        print(f'\n--- {iid} ---')
        for k in sorted(t.keys()):
            v = t[k]
            if isinstance(v, str) and len(v) > 200:
                v = v[:200] + '...'
            print(f'  {k}: {v}')
        sql = (preds.get(iid, {}).get('sql') or '').strip()[:400]
        print(f'  SQL: {sql}')

# And first 3 SQL samples for understanding
print('\n=== sample SQL emissions (first 3 in id-order) ===')
for iid in sorted(preds.keys())[:3]:
    sql = (preds[iid].get('sql') or '').strip()
    print(f'\n--- {iid} ---')
    print(sql[:500])
