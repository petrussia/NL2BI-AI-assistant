"""Pull revert-A traces per-task, classify residual failures."""
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
revA = load('lite_snow_pilot10_v28_revertA')

print('=== three-way side by side ===')
hdr = f'{"iid":12s} | {"v27c":>14s} | {"v28":>14s} | {"v28-revertA":>14s} | {"wrp":>3s} | failure'
print(hdr); print('-'*120)
def cell(t):
    sv = t.get('schema_valid')
    ex = t.get('explain_ok')
    return f"sv={('T' if sv else 'F' if sv is False else '?')} ex={('T' if ex else 'F' if ex is False else '?')}"
for iid in sorted(revA['traces'].keys()):
    t_a = revA['traces'][iid]
    t_b = v28['traces'].get(iid, {})
    t_c = v27c['traces'].get(iid, {})
    wrp = (t_a.get('f4') or {}).get('wrapped_n', 0)
    err = (t_a.get('explain_msg') or t_a.get('sv_msg') or t_a.get('guard_error') or '').split('\n')[0][:70]
    print(f'{iid:12s} | {cell(t_c):>14s} | {cell(t_b):>14s} | {cell(t_a):>14s} | {wrp:>3d} | {err}')

print('\n=== OK tasks in revert-A ===')
for iid, t in revA['traces'].items():
    if t.get('explain_ok'):
        sql = (revA['preds'].get(iid, {}).get('sql') or '').strip()
        print(f'\n--- {iid} ---')
        print(f'  wrapped_n: {(t.get("f4") or {}).get("wrapped_n", 0)}')
        print(f'  SQL: {sql[:300]}')

print('\n=== residual failures (top patterns) ===')
from collections import Counter
err_pat = Counter()
for iid, t in revA['traces'].items():
    if t.get('explain_ok'):
        continue
    msg = (t.get('explain_msg') or t.get('sv_msg') or '').lower()
    if 'invalid identifier' in msg: pat = 'invalid_identifier'
    elif 'does not exist' in msg: pat = 'object_missing'
    elif 'syntax error' in msg: pat = 'syntax_error'
    elif 'does not support' in msg and 'number' in msg: pat = 'date_fn_on_number'
    elif 'does not support variant' in msg: pat = 'date_fn_on_variant'
    elif 'parse_failed' in msg or 'parse error' in msg: pat = 'parse_failure'
    elif 'unknown' in msg: pat = 'schema_invalid_unknown'
    else: pat = 'other'
    err_pat[pat] += 1
for pat, n in err_pat.most_common():
    print(f'  {pat:25s} x{n}')

# Sample of failing SQL
print('\n=== sample failing SQL (first 3) ===')
fail_iids = [iid for iid, t in revA['traces'].items() if not t.get('explain_ok')]
for iid in sorted(fail_iids)[:3]:
    sql = (revA['preds'].get(iid, {}).get('sql') or '').strip()
    msg = (revA['traces'][iid].get('explain_msg') or revA['traces'][iid].get('sv_msg') or '')
    print(f'\n--- {iid} ---')
    print(f'  err: {msg[:200]}')
    print(f'  SQL: {sql[:300]}')
