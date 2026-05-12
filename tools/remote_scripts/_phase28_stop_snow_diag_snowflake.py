"""Stop Phase28FullS1Chain AND Phase28S1Supervisor, then probe Snowflake state.

Stopping is critical: the chain is producing connect_fail for every task and
those failures get recorded as "done" iids — resume scaffolding skips them
on next restart, so we'd lose them permanently. Kill now, clean later.
"""
import ctypes, threading, time, json, os, inspect
g = inspect.currentframe().f_globals

print('=== killing Phase28FullS1Chain + Phase28S1Supervisor ===')
for t in threading.enumerate():
    if t.name in ('Phase28FullS1Chain', 'Phase28S1Supervisor') and t.is_alive():
        print(f'  killing {t.name} tid={t.ident}')
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(t.ident), ctypes.py_object(SystemExit))

time.sleep(3)

# Verify dead
for t in threading.enumerate():
    if t.name in ('Phase28FullS1Chain', 'Phase28S1Supervisor'):
        print(f'  {t.name}: alive={t.is_alive()}')

print('\n=== Snowflake state on S1 ===')
# Common Snowflake globals
sf_keys = ['SNOWFLAKE_READY', 'SNOWFLAKE_STATUS', 'snow_conn', 'SF_CONN', '_snow_conn',
           'SNOWFLAKE_ACCOUNT', 'SNOWFLAKE_USER']
for k in sf_keys:
    if k in g:
        v = g[k]
        if isinstance(v, dict):
            print(f'  {k}: {v}')
        else:
            print(f'  {k}: {type(v).__name__} {str(v)[:120]}')

# Env vars
print('\n=== env vars ===')
for k in ['SNOWFLAKE_USER','SNOWFLAKE_PASSWORD','SNOWFLAKE_ACCOUNT','SNOWFLAKE_PRIVATE_KEY_PATH','SNOWFLAKE_WAREHOUSE']:
    v = os.environ.get(k)
    if v:
        # mask secrets
        if 'PASSWORD' in k or 'KEY' in k:
            v = v[:10] + '...' + str(len(v)) + 'chars'
        print(f'  {k}={v}')
    else:
        print(f'  {k}=<not set>')

# Test direct connect
print('\n=== Direct Snowflake connect test ===')
try:
    import snowflake.connector
    print(f'  snowflake.connector version: {snowflake.connector.__version__}')
    # Try the same connection the runner uses (look for setup)
    import sys
    sys.path.insert(0, '/content/drive/MyDrive/diploma_plan_sql/repo/src/evaluation')
    # Find the runner's connect helper
    runner_src = open('/tmp/_phase27_snow_runner.py').read()
    import re
    sf_calls = re.findall(r'snow\w*\.connect|snowflake\.connector\.connect', runner_src)
    print(f'  snow connect calls in runner: {len(sf_calls)}')

    # Look for snowflake setup function in the runner
    if 'def _snow_explain' in runner_src:
        start = runner_src.find('def _snow_explain')
        end = runner_src.find('\ndef ', start + 1)
        snippet = runner_src[start:end]
        print(f'\n  _snow_explain function preview:')
        for ln in snippet.split('\n')[:30]:
            print(f'    {ln}')
except Exception as e:
    print(f'  err: {type(e).__name__}: {e}')
