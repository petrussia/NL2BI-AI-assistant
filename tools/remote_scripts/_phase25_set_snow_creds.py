"""Phase 25 — set Snowflake creds in bridge kernel env.

Reads `secrets/snowflake.json` LOCALLY, sends only the kv pairs into
os.environ on the bridge side. The user authorized this transfer
explicitly: "Создал папку с секретами ... Там есть для подключения к
сноуфлейку".

Tests connection with a CURRENT_VERSION() probe.
"""
import os, json, urllib.request

# This script is run via tools/exec_remote.py --code-file but parameterized
# by environment vars (so the secret payload is not on disk on bridge side).
# We splice the creds into the source as escaped strings.

CREDS_JSON = os.environ.get('PHASE25_SNOW_PAYLOAD')
if not CREDS_JSON:
    raise SystemExit('PHASE25_SNOW_PAYLOAD env var not set on caller')

creds = json.loads(CREDS_JSON)


def main():
    BRIDGE_URL = open('tools/.bridge_url', encoding='utf-8').read().strip().rstrip('/')
    code = (
        "import os, json\n"
        f"_creds = {json.dumps(creds)}\n"
        "os.environ['SNOWFLAKE_ACCOUNT'] = _creds['account']\n"
        "os.environ['SNOWFLAKE_USER'] = _creds['user']\n"
        "os.environ['SNOWFLAKE_PASSWORD'] = _creds['password']\n"
        "os.environ['SNOWFLAKE_ROLE'] = _creds.get('role', '')\n"
        "os.environ['SNOWFLAKE_WAREHOUSE'] = _creds.get('warehouse', '')\n"
        "os.environ['SNOWFLAKE_DATABASE'] = _creds.get('database', '')\n"
        "import snowflake.connector\n"
        "try:\n"
        "    conn = snowflake.connector.connect(\n"
        "        account=os.environ['SNOWFLAKE_ACCOUNT'],\n"
        "        user=os.environ['SNOWFLAKE_USER'],\n"
        "        password=os.environ['SNOWFLAKE_PASSWORD'],\n"
        "        role=os.environ.get('SNOWFLAKE_ROLE') or None,\n"
        "        warehouse=os.environ.get('SNOWFLAKE_WAREHOUSE') or None,\n"
        "    )\n"
        "    cur = conn.cursor()\n"
        "    cur.execute('SELECT CURRENT_VERSION(), CURRENT_USER(), CURRENT_ACCOUNT(), CURRENT_ROLE(), CURRENT_WAREHOUSE()')\n"
        "    row = cur.fetchone()\n"
        "    print('SNOW_AUTH_OK', row)\n"
        "    conn.close()\n"
        "except Exception as e:\n"
        "    print(f'SNOW_AUTH_FAIL {type(e).__name__}: {str(e)[:300]}')\n"
        "print('vars set:', [k for k in os.environ if k.startswith('SNOWFLAKE')])\n"
    )
    payload = json.dumps({'code': code}).encode('utf-8')
    req = urllib.request.Request(BRIDGE_URL + '/exec', data=payload,
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        result = json.loads(r.read().decode('utf-8'))
    print(result.get('stdout', '')[:600])
    if result.get('stderr'):
        print('STDERR:', result['stderr'][:300])


if __name__ == '__main__':
    main()
