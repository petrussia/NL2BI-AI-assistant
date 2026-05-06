"""spider2_sf_readiness_v8 — gate real Snowflake execution behind a
machine-readable readiness check.

The runner calls `check_readiness(required_dbs)` BEFORE generating SQL.
If `can_execute_real_sql` is False, items routed to A_sf are recorded
with `mode='blocked_missing_snowflake_database'` and the SF executor
is never invoked.

Reads creds from snowflake_setup/.env (or env vars). Never prints
secrets.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEFAULT_ENV = REPO / 'snowflake_setup' / '.env'


@dataclass
class SfReadiness:
    connection_ok: bool = False
    role_ok: bool = False
    warehouse_ok: bool = False
    default_db_set: bool = False
    visible_databases: list[str] = field(default_factory=list)
    required_databases: list[str] = field(default_factory=list)
    missing_databases: list[str] = field(default_factory=list)
    visible_match: list[str] = field(default_factory=list)
    has_patents: bool = False
    cloud: str = ''
    region: str = ''
    self_host_eligible: bool = False
    can_execute_real_sql: bool = False
    reason: str = ''
    error: str = ''

    def to_dict(self) -> dict: return asdict(self)


def _load_env(path: Path = DEFAULT_ENV) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists(): return out
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k, _, v = line.partition('=')
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _get_env(name: str, env_file: dict[str, str]) -> str:
    return os.environ.get(name) or env_file.get(name) or ''


def get_credentials(env_path: Path | None = None) -> dict:
    """Build a dict suitable for snowflake.connector.connect(**kwargs).
    Refuses to return anything if minimum required fields are missing.
    """
    env = _load_env(env_path or DEFAULT_ENV)
    kw: dict = dict(
        account=_get_env('SNOWFLAKE_ACCOUNT', env),
        user=_get_env('SNOWFLAKE_USER', env),
        application='spider2_sf_v8',
    )
    for k in ('ROLE', 'WAREHOUSE', 'DATABASE', 'SCHEMA', 'REGION'):
        v = _get_env(f'SNOWFLAKE_{k}', env)
        if v: kw[k.lower()] = v
    pw = _get_env('SNOWFLAKE_PASSWORD', env)
    pkey_path = _get_env('SNOWFLAKE_PRIVATE_KEY_PATH', env)
    pkey_pass = _get_env('SNOWFLAKE_PRIVATE_KEY_PASSPHRASE', env)
    auth = _get_env('SNOWFLAKE_AUTHENTICATOR', env)
    if pkey_path:
        try:
            from cryptography.hazmat.primitives import serialization
            with open(pkey_path, 'rb') as f:
                pkey = serialization.load_pem_private_key(
                    f.read(),
                    password=(pkey_pass.encode() if pkey_pass else None))
            kw['private_key'] = pkey.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption())
            kw['authenticator'] = 'snowflake_jwt'
        except Exception as e:
            raise RuntimeError(f'private key load failed: {type(e).__name__}: {e}')
    elif pw:
        kw['password'] = pw
    if auth and 'authenticator' not in kw:
        kw['authenticator'] = auth
    if not kw.get('account') or not kw.get('user'):
        raise RuntimeError('SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER are required')
    if 'password' not in kw and 'private_key' not in kw and not auth:
        raise RuntimeError('one of SNOWFLAKE_PASSWORD / '
                            'SNOWFLAKE_PRIVATE_KEY_PATH / '
                            'SNOWFLAKE_AUTHENTICATOR is required')
    return kw


def check_readiness(required_dbs: list[str] | None = None,
                      *, env_path: Path | None = None) -> SfReadiness:
    """Connect, list visible databases, compare against required_dbs.

    Returns a SfReadiness; never raises (errors captured into `error`).
    """
    rd = SfReadiness(required_databases=sorted(required_dbs or []))
    try:
        kw = get_credentials(env_path)
    except Exception as e:
        rd.error = f'creds:{type(e).__name__}:{e}'
        return rd
    try:
        import snowflake.connector
    except ImportError:
        rd.error = 'snowflake-connector-python not installed'
        return rd

    try:
        conn = snowflake.connector.connect(**kw)
    except Exception as e:
        rd.error = f'connect:{type(e).__name__}:{str(e)[:200]}'
        return rd
    rd.connection_ok = True
    rd.role_ok = (kw.get('role') == 'SPIDER2_RW')
    rd.warehouse_ok = (kw.get('warehouse') == 'SPIDER2_WH')
    rd.default_db_set = bool(kw.get('database'))

    cur = conn.cursor()
    try:
        cur.execute("ALTER SESSION SET QUERY_TAG = 'spider2_sf_readiness_v8'")
        # Region/cloud
        try:
            cur.execute('SELECT CURRENT_REGION()')
            region = (cur.fetchone()[0] or '').upper()
            m = re.match(r'([A-Z]+)_([A-Z0-9_-]+)', region)
            if m:
                rd.cloud = m.group(1)
                rd.region = m.group(2).replace('_', '-').lower()
            rd.self_host_eligible = (rd.cloud == 'AWS' and rd.region == 'us-west-2')
        except Exception: pass

        cur.execute('SHOW DATABASES')
        cols = [c[0] for c in cur.description]
        idx = cols.index('name') if 'name' in cols else 1
        rd.visible_databases = sorted({str(r[idx]) for r in cur.fetchall()})
    except Exception as e:
        rd.error = f'show_databases:{type(e).__name__}:{str(e)[:200]}'
    finally:
        try: cur.close()
        except Exception: pass
        try: conn.close()
        except Exception: pass

    visible_set = set(rd.visible_databases)
    req_set = set(rd.required_databases)
    rd.visible_match = sorted(visible_set & req_set)
    rd.missing_databases = sorted(req_set - visible_set)
    rd.has_patents = 'PATENTS' in visible_set
    rd.can_execute_real_sql = (
        rd.connection_ok and rd.role_ok and rd.warehouse_ok and
        rd.default_db_set and (
            (req_set and not rd.missing_databases) or
            (not req_set and rd.has_patents)
        )
    )
    if not rd.can_execute_real_sql:
        if not rd.connection_ok: rd.reason = 'connection_failed'
        elif not rd.role_ok: rd.reason = 'role_not_SPIDER2_RW'
        elif not rd.warehouse_ok: rd.reason = 'warehouse_not_SPIDER2_WH'
        elif rd.missing_databases: rd.reason = (
            f'{len(rd.missing_databases)} required databases not visible '
            f'(first missing: {rd.missing_databases[:3]})')
        else: rd.reason = 'unknown_blocker'
    else:
        rd.reason = 'all_checks_passed'
    return rd


if __name__ == '__main__':
    rd = check_readiness()
    print(json.dumps(rd.to_dict(), indent=2, ensure_ascii=False))
