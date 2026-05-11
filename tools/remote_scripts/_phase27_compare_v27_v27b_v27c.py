"""Compare Phase 27 pilot10 progressions: v27 (initial), v27b (validator fix only),
   v27c (3 corrections + SELECT-alias)."""
import json
from pathlib import Path

BASE = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_lite/runs')

def read_progress(run_id):
    p = BASE / run_id / 'progress.json'
    if not p.exists(): return None
    return json.loads(p.read_text())

def read_metrics(run_id):
    m = BASE / run_id / 'metrics.csv'
    if not m.exists(): return None
    return m.read_text()

for run in ['lite_snow_full_v26', 'lite_snow_pilot10_v27', 'lite_snow_pilot10_v27b', 'lite_snow_pilot10_v27c']:
    print(f'=== {run} ===')
    pj = read_progress(run)
    if pj:
        for k in ['n_total', 'plan_ok', 'schema_valid', 'parse_ok', 'execute_ok',
                  'guard_leaks', 'guard_rewrites', 'wall_sec', 'last_task']:
            if k in pj: print(f'  {k}: {pj[k]}')
        if 'err_top' in pj:
            print(f'  err_top: {pj["err_top"]}')
    else:
        # Try metrics.csv
        m = read_metrics(run)
        if m: print(m)
        else: print('  (no progress.json or metrics.csv)')
    print()

# Per-task error rollup for v27c sorted with the dialect tag
print('\n=== v27c per-task dialect tags ===')
RUN = BASE / 'lite_snow_pilot10_v27c'
preds = {}
with open(RUN / 'predictions.jsonl') as f:
    for ln in f:
        p = json.loads(ln); preds[p['instance_id']] = p

traces = {}
with open(RUN / 'traces.jsonl') as f:
    for ln in f:
        t = json.loads(ln); traces[t.get('instance_id', t.get('iid'))] = t

def classify(msg):
    if not msg: return 'no_msg'
    m = msg.lower()
    if 'invalid identifier' in m and '"' in msg:
        return 'mixed_case_quoting'
    if 'invalid identifier' in m:
        return 'invalid_identifier'
    if 'does not support' in m and 'number(' in m:
        return 'date_fn_on_number'
    if 'does not support variant' in m:
        return 'date_fn_on_variant'
    if 'does not exist or not authorized' in m:
        return 'object_missing'
    if 'syntax error' in m:
        return 'syntax_error'
    if 'parse_error_guard' in m:
        return 'parse_guard'
    if 'schema_invalid' in m:
        return 'schema_invalid'
    return 'other'

print(f"{'iid':14s} {'tag':25s} {'first_err':80s}")
print('-'*125)
for iid in sorted(preds.keys()):
    t = traces.get(iid, {})
    msg = t.get('exec_err') or t.get('explain_msg') or t.get('sv_msg') or ''
    msg1 = msg.split('\n', 1)[0]
    print(f'{iid:14s} {classify(msg):25s} {msg1[:80]}')
