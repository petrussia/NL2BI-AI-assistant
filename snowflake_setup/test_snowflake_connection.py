"""Snowflake connection smoke test.

Reads credentials from `snowflake_setup/.env` (or environment variables if
already exported) and runs three trivial probes:
  1. SELECT CURRENT_VERSION()
  2. SELECT CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()
  3. SHOW WAREHOUSES (lists available warehouses, useful sanity)

Prints diagnostic output ONLY — no password, account, or query results that
could leak data. The account identifier is partially masked.

Usage (assuming snowflake-connector-python is installed):
    pip install --upgrade snowflake-connector-python python-dotenv
    cp snowflake_setup/.env.template snowflake_setup/.env
    # ...edit snowflake_setup/.env with creds from the friend...
    python snowflake_setup/test_snowflake_connection.py

If anything fails, the script prints exactly what's missing (env var name or
SF error code) without dumping the credentials themselves.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
DOTENV = HERE / '.env'


def load_env_file(path: Path) -> dict[str, str]:
    """Tiny .env parser — no external dep, no shell expansion."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'): continue
        if '=' not in line: continue
        k, _, v = line.partition('=')
        k = k.strip(); v = v.strip().strip('"').strip("'")
        if k: out[k] = v
    return out


def mask(s: str | None, *, keep: int = 3) -> str:
    if not s: return '<unset>'
    if len(s) <= keep + 2: return s[:1] + '*' * (len(s) - 1)
    return s[:keep] + '*' * 4 + f'(len={len(s)})'


def main() -> int:
    env_file = load_env_file(DOTENV)
    # Env var wins over .env file
    def get(name: str) -> str:
        return os.environ.get(name) or env_file.get(name) or ''

    account = get('SNOWFLAKE_ACCOUNT')
    user = get('SNOWFLAKE_USER')
    password = get('SNOWFLAKE_PASSWORD')
    private_key_path = get('SNOWFLAKE_PRIVATE_KEY_PATH')
    private_key_pass = get('SNOWFLAKE_PRIVATE_KEY_PASSPHRASE')
    role = get('SNOWFLAKE_ROLE')
    warehouse = get('SNOWFLAKE_WAREHOUSE')
    database = get('SNOWFLAKE_DATABASE')
    schema = get('SNOWFLAKE_SCHEMA')
    region = get('SNOWFLAKE_REGION')
    auth = get('SNOWFLAKE_AUTHENTICATOR')
    query_tag = get('SNOWFLAKE_QUERY_TAG') or 'spider2-lite-smoke'

    print('=== ENV (masked) ===')
    print(f'  SNOWFLAKE_ACCOUNT   = {mask(account)}')
    print(f'  SNOWFLAKE_USER      = {mask(user)}')
    print(f'  SNOWFLAKE_PASSWORD  = {"<set>" if password else "<unset>"}')
    print(f'  SNOWFLAKE_PRIVATE_KEY_PATH = {private_key_path or "<unset>"}')
    print(f'  SNOWFLAKE_ROLE      = {role or "<unset>"}')
    print(f'  SNOWFLAKE_WAREHOUSE = {warehouse or "<unset>"}')
    print(f'  SNOWFLAKE_DATABASE  = {database or "<unset>"}')
    print(f'  SNOWFLAKE_SCHEMA    = {schema or "<unset>"}')
    print(f'  SNOWFLAKE_REGION    = {region or "<unset>"}')
    print(f'  SNOWFLAKE_AUTHENTICATOR = {auth or "<unset>"}')

    missing = []
    if not account: missing.append('SNOWFLAKE_ACCOUNT')
    if not user: missing.append('SNOWFLAKE_USER')
    if not (password or private_key_path or auth):
        missing.append('SNOWFLAKE_PASSWORD or SNOWFLAKE_PRIVATE_KEY_PATH or SNOWFLAKE_AUTHENTICATOR')
    if missing:
        print('\nMISSING ENV VARS:', ', '.join(missing))
        print('Edit snowflake_setup/.env or export the variables and re-run.')
        return 2

    try:
        import snowflake.connector  # type: ignore
    except ImportError:
        print('\nFAIL: `snowflake-connector-python` not installed.')
        print('Run: pip install --upgrade snowflake-connector-python')
        return 3

    # Build connector kwargs without leaking secrets to logs
    kwargs: dict[str, object] = dict(
        account=account, user=user, application='spider2_lite_smoke',
    )
    if role: kwargs['role'] = role
    if warehouse: kwargs['warehouse'] = warehouse
    if database: kwargs['database'] = database
    if schema: kwargs['schema'] = schema
    if region: kwargs['region'] = region
    if auth:
        kwargs['authenticator'] = auth
        if auth.lower() == 'externalbrowser':
            print('\nWARN: SNOWFLAKE_AUTHENTICATOR=externalbrowser is interactive '
                  '(SSO browser popup) and will NOT work for headless runs. '
                  'Use password or key-pair for the Spider2 runner.')

    if private_key_path:
        # Key-pair auth; load and parse the PEM key
        try:
            from cryptography.hazmat.primitives import serialization
        except ImportError:
            print('\nFAIL: cryptography is required for key-pair auth. '
                  'Run: pip install cryptography')
            return 3
        try:
            with open(private_key_path, 'rb') as f:
                pkey = serialization.load_pem_private_key(
                    f.read(),
                    password=(private_key_pass.encode() if private_key_pass else None),
                )
            der = pkey.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            kwargs['private_key'] = der
            kwargs['authenticator'] = 'snowflake_jwt'
        except Exception as exc:
            print(f'\nFAIL: could not load private key from {private_key_path}: '
                  f'{type(exc).__name__}: {exc}')
            return 4
    elif password:
        kwargs['password'] = password

    print('\nCONNECTING…')
    try:
        conn = snowflake.connector.connect(**kwargs)
    except Exception as exc:
        msg = str(exc)
        # Strip any password value from the printed message defensively
        if password and password in msg:
            msg = msg.replace(password, '<PASSWORD>')
        print(f'CONNECT_FAIL {type(exc).__name__}: {msg[:400]}')
        return 5
    print('CONNECT_OK')

    cur = conn.cursor()
    try:
        cur.execute(f"alter session set query_tag = '{query_tag}'")
    except Exception:
        pass

    def q(sql: str) -> list[tuple]:
        cur.execute(sql)
        return cur.fetchall()

    try:
        v = q('SELECT CURRENT_VERSION()')
        print(f'\n[1] CURRENT_VERSION = {v[0][0] if v else "?"}')
    except Exception as exc:
        print(f'[1] CURRENT_VERSION_FAIL: {exc}')

    try:
        ctx = q('SELECT CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()')
        if ctx:
            r, w, db, sc = ctx[0]
            print(f'[2] CONTEXT role={r} warehouse={w} database={db} schema={sc}')
    except Exception as exc:
        print(f'[2] CONTEXT_FAIL: {exc}')

    try:
        whs = q('SHOW WAREHOUSES')
        names = [row[0] for row in whs[:5]]
        print(f'[3] SHOW_WAREHOUSES n={len(whs)} sample={names}')
    except Exception as exc:
        print(f'[3] SHOW_WAREHOUSES_FAIL: {exc}')

    cur.close(); conn.close()
    print('\nALL_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
