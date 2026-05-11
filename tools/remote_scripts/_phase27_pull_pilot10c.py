"""Pull pilot10c traces + predictions to local outputs/, dump compact summary."""
import json, shutil
from pathlib import Path

REMOTE = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_lite/runs/lite_snow_pilot10_v27c')
LOCAL = Path('/content/drive/MyDrive/diploma_plan_sql/_pull_phase27')
LOCAL.mkdir(parents=True, exist_ok=True)

for fn in ['predictions.jsonl', 'traces.jsonl', 'progress.json', 'metrics.csv', 'error_taxonomy.csv']:
    src = REMOTE / fn
    if src.exists():
        shutil.copy(src, LOCAL / fn)
        print(f'  pulled {fn} ({src.stat().st_size}B)')

# Match preds to traces and tabulate per-task
preds = {}
with open(REMOTE / 'predictions.jsonl') as f:
    for ln in f:
        p = json.loads(ln); preds[p['instance_id']] = p

traces = {}
with open(REMOTE / 'traces.jsonl') as f:
    for ln in f:
        t = json.loads(ln); traces[t.get('instance_id', t.get('iid'))] = t

print(f'\n=== {len(preds)} preds / {len(traces)} traces ===')
print()
print(f"{'iid':22s} {'sv':>3s} {'parse':>5s} {'exec':>4s} {'err':40s}")
print('-'*120)
for iid in sorted(preds.keys()):
    p = preds[iid]
    t = traces.get(iid, {})
    sv = t.get('schema_valid', '?')
    pa = t.get('parse_ok', '?')
    ex = t.get('execute_ok', '?')
    err = (t.get('exec_err') or t.get('explain_msg') or t.get('sv_msg') or '')[:90]
    print(f'{iid:22s} {str(sv):>3s} {str(pa):>5s} {str(ex):>4s} {err}')

print('\n=== sample SQL emissions (3) ===')
for iid in sorted(preds.keys())[:3]:
    p = preds[iid]
    sql = (p.get('sql') or '').replace('\n', ' ').strip()[:300]
    print(f'\n{iid}:')
    print(f'  {sql}')

print('\n=== top exec_err patterns ===')
from collections import Counter
errs = Counter()
err_examples = {}
for iid, t in traces.items():
    msg = t.get('exec_err') or t.get('explain_msg') or t.get('sv_msg') or ''
    if not msg: continue
    # canonical token
    tok = 'other'
    if 'invalid identifier' in msg.lower(): tok = 'invalid_identifier'
    elif 'syntax error' in msg.lower(): tok = 'syntax_error'
    elif 'not exist' in msg.lower(): tok = 'object_not_exists'
    elif 'numeric value' in msg.lower(): tok = 'numeric_cast'
    elif 'parse_error_guard' in msg.lower(): tok = 'parse_guard'
    elif 'schema_invalid' in msg.lower(): tok = 'schema_invalid'
    errs[tok] += 1
    if tok not in err_examples:
        err_examples[tok] = (iid, msg[:200])

for tok, n in errs.most_common():
    iid, msg = err_examples[tok]
    print(f'  [{tok:20s}] x{n}  e.g. {iid}: {msg}')
