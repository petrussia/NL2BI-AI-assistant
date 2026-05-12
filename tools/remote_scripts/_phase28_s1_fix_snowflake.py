"""Repair S1 post-kernel-restart: load Snowflake creds, test connection,
clean connect_fail entries from predictions/traces, then ready for re-launch."""
import os, json, time, inspect, threading, ctypes
from pathlib import Path

g = inspect.currentframe().f_globals

# Step 1: kill any stragglers (in case previous kill didn't take)
print('=== ensure chains killed ===')
for t in threading.enumerate():
    if t.name in ('Phase28FullS1Chain', 'Phase28S1Supervisor') and t.is_alive():
        print(f'  killing {t.name} tid={t.ident}')
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(t.ident), ctypes.py_object(SystemExit))
time.sleep(2)
for t in threading.enumerate():
    if t.name in ('Phase28FullS1Chain', 'Phase28S1Supervisor'):
        print(f'  {t.name}: alive={t.is_alive()}')

# Step 2: load Snowflake creds from Drive
SECRETS = Path('/content/drive/MyDrive/diploma_plan_sql/secrets/snowflake.json')
print(f'\n=== loading {SECRETS} ===')
sf = json.loads(SECRETS.read_text(encoding='utf-8'))
print(f'  keys: {list(sf.keys())}')

# Map Drive keys -> env vars
key_map = {
    'account': 'SNOWFLAKE_ACCOUNT',
    'user': 'SNOWFLAKE_USER',
    'password': 'SNOWFLAKE_PASSWORD',
    'role': 'SNOWFLAKE_ROLE',
    'warehouse': 'SNOWFLAKE_WAREHOUSE',
    'database': 'SNOWFLAKE_DATABASE',
    'schema': 'SNOWFLAKE_SCHEMA',
    # In case keys are CAPS already in JSON
    'SNOWFLAKE_ACCOUNT': 'SNOWFLAKE_ACCOUNT',
    'SNOWFLAKE_USER': 'SNOWFLAKE_USER',
    'SNOWFLAKE_PASSWORD': 'SNOWFLAKE_PASSWORD',
    'SNOWFLAKE_ROLE': 'SNOWFLAKE_ROLE',
    'SNOWFLAKE_WAREHOUSE': 'SNOWFLAKE_WAREHOUSE',
}
set_keys = []
for k, v in sf.items():
    env = key_map.get(k) or key_map.get(k.lower())
    if env and v:
        os.environ[env] = str(v)
        set_keys.append(env)
print(f'  set env vars: {set_keys}')

# Step 3: test connection
print('\n=== test Snowflake connect ===')
try:
    import snowflake.connector
    c = snowflake.connector.connect(
        account=os.environ['SNOWFLAKE_ACCOUNT'],
        user=os.environ['SNOWFLAKE_USER'],
        password=os.environ['SNOWFLAKE_PASSWORD'],
        role=os.environ.get('SNOWFLAKE_ROLE') or None,
        warehouse=os.environ.get('SNOWFLAKE_WAREHOUSE') or None,
    )
    cur = c.cursor()
    cur.execute('SELECT CURRENT_TIMESTAMP()')
    row = cur.fetchone()
    print(f'  CONNECT OK: {row}')
    c.close()
except Exception as e:
    print(f'  CONNECT FAILED: {type(e).__name__}: {e}')
    raise SystemExit('Snowflake connection still broken — cannot proceed')

# Step 4: clean connect_fail entries from predictions.jsonl + traces.jsonl
RUN = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_snow/runs/snow_full_v28_revert_a')
pf_path = RUN / 'predictions.jsonl'
tf_path = RUN / 'traces.jsonl'

print('\n=== cleaning connect_fail entries ===')
# Read preds
preds = []
with open(pf_path, encoding='utf-8') as f:
    for ln in f:
        if not ln.strip(): continue
        preds.append(json.loads(ln))
before = len(preds)
bad_iids = set()
for p in preds:
    if p.get('explain_class') == 'connect_fail' or 'connect_fail' in str(p.get('error', '')):
        bad_iids.add(p.get('instance_id'))
print(f'  bad iids to remove: {len(bad_iids)} ({sorted(bad_iids)[:5]}...)')

# Filter out
clean_preds = [p for p in preds if p.get('instance_id') not in bad_iids]
print(f'  preds: {before} -> {len(clean_preds)}')

# Write back atomically
tmp = pf_path.with_suffix('.jsonl.tmp')
with open(tmp, 'w', encoding='utf-8') as f:
    for p in clean_preds:
        f.write(json.dumps(p, default=str) + '\n')
tmp.replace(pf_path)
print(f'  wrote cleaned predictions.jsonl: {sum(1 for _ in open(pf_path))} rows')

# Filter traces too
if tf_path.exists():
    traces = []
    with open(tf_path, encoding='utf-8') as f:
        for ln in f:
            if not ln.strip(): continue
            try:
                traces.append(json.loads(ln))
            except Exception:
                pass
    before_t = len(traces)
    clean_traces = [t for t in traces if t.get('instance_id') not in bad_iids]
    tmp = tf_path.with_suffix('.jsonl.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        for t in clean_traces:
            f.write(json.dumps(t, default=str) + '\n')
    tmp.replace(tf_path)
    print(f'  traces: {before_t} -> {len(clean_traces)}')

print('\n=== ready: env set, conn tested, files cleaned ===')
print(f'Now safe to re-trigger Phase28FullS1Chain (resume will skip {len(clean_preds)} done iids)')
