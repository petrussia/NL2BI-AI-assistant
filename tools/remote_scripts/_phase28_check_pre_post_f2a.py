"""Examine sf_bq211 (the regression case) — was lowercase emitted by the
model and then uppercased by F2a, or did the model already emit uppercase?"""
import json
from pathlib import Path

RUN = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_lite/runs/lite_snow_pilot10_v28')

print('=== v28 full trace for all 10 tasks ===')
traces = {}
with open(RUN / 'traces.jsonl') as f:
    for ln in f:
        t = json.loads(ln); traces[t.get('instance_id')] = t

for iid in ['sf_bq211', 'sf_bq026', 'sf_bq099', 'sf_bq210']:
    t = traces.get(iid, {})
    print(f'\n--- {iid} ---')
    for k in ['sql_pre_guard', 'guard', 'f2a', 'f4', 'sv_msg', 'pa_msg',
              'schema_valid', 'parse_ok', 'explain_ok', 'explain_class', 'explain_msg',
              'guard_error', 'plan_ok']:
        if k in t:
            v = t[k]
            if isinstance(v, str) and len(v) > 240:
                v = v[:240] + '...'
            print(f'  {k}: {v}')
