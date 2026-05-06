"""probe_databases.py — readiness probe for Spider2 SF execution.

Reads .env, connects with SPIDER2_BENCH/SPIDER2_RW/SPIDER2_WH, lists
visible databases, cross-checks against the dbs Spider2-Lite SF tasks
need, and writes:
  outputs/snowflake/readiness/databases_visible.json
  outputs/snowflake/readiness/databases_visible.md

Also captures CURRENT_REGION / CURRENT_ACCOUNT / CURRENT_ORGANIZATION
for self-host eligibility analysis.

Read-only, no compute used (SHOW commands don't bill credits).
Costs nothing; refuses to run if creds are missing.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def load_env():
    p = HERE / '.env'
    env = {}
    if p.exists():
        for raw in p.read_text(encoding='utf-8').splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k, _, v = line.partition('=')
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _required_dbs_from_local() -> set[str]:
    """Walk Spider2-Lite resource/databases/snowflake/ if present and
    derive the set of database names. Falls back to extracting from
    spider2-lite.jsonl `db` field (uppercased).
    """
    sf_root = REPO / 'external_benchmarks' / 'spider2_lite' / 'raw' / 'Spider2' / 'spider2-lite' / 'resource' / 'databases' / 'snowflake'
    if sf_root.exists():
        return {d.name for d in sf_root.iterdir() if d.is_dir()}
    # Fallback: scan jsonl
    jl = REPO / 'external_benchmarks' / 'spider2_lite' / 'raw' / 'Spider2' / 'spider2-lite' / 'spider2-lite.jsonl'
    out: set[str] = set()
    if jl.exists():
        for ln in jl.open(encoding='utf-8'):
            try:
                it = json.loads(ln)
            except Exception: continue
            iid = str(it.get('instance_id') or '').lower()
            if iid.startswith('sf'):
                db = str(it.get('db') or '').strip()
                if db: out.add(db)
    return out


def main() -> int:
    env_file = load_env()
    def get(k): return os.environ.get(k) or env_file.get(k) or ''

    try:
        import snowflake.connector
    except ImportError:
        print('FAIL: snowflake-connector-python not installed'); return 3

    kwargs = dict(account=get('SNOWFLAKE_ACCOUNT'), user=get('SNOWFLAKE_USER'),
                    application='spider2_lite_probe')
    for k in ('ROLE', 'WAREHOUSE', 'DATABASE', 'SCHEMA', 'REGION'):
        v = get(f'SNOWFLAKE_{k}')
        if v: kwargs[k.lower()] = v
    pw = get('SNOWFLAKE_PASSWORD')
    if pw: kwargs['password'] = pw

    print(f'CONNECTING role={kwargs.get("role")} '
          f'warehouse={kwargs.get("warehouse")} '
          f'database={kwargs.get("database")} schema={kwargs.get("schema")}')
    t0 = time.time()
    conn = snowflake.connector.connect(**kwargs)
    cur = conn.cursor()
    cur.execute("ALTER SESSION SET QUERY_TAG = 'spider2_lite_readiness_probe'")
    print(f'CONNECTED in {(time.time()-t0)*1000:.0f}ms\n')

    def q(sql, max_rows=300):
        cur.execute(sql)
        cols = [c[0] for c in cur.description]
        return cur.fetchmany(max_rows), cols

    # 1. Account / region / org
    print('=== ACCOUNT IDENTITY ===')
    account_info: dict = {}
    for label, sql in [
        ('current_user',         'SELECT CURRENT_USER()'),
        ('current_role',         'SELECT CURRENT_ROLE()'),
        ('current_account',      'SELECT CURRENT_ACCOUNT()'),
        ('current_organization', 'SELECT CURRENT_ORGANIZATION_NAME()'),
        ('current_region',       'SELECT CURRENT_REGION()'),
        ('current_version',      'SELECT CURRENT_VERSION()'),
    ]:
        try:
            rs, _ = q(sql)
            v = rs[0][0] if rs else None
            account_info[label] = str(v) if v is not None else None
            print(f'  {label:24s} = {account_info[label]}')
        except Exception as e:
            account_info[label] = None
            print(f'  {label:24s} ERR {type(e).__name__}: {str(e)[:80]}')

    # 2. Cloud/region parsing
    region = (account_info.get('current_region') or '').upper()
    cloud, region_short = '', ''
    m = re.match(r'([A-Z]+)_([A-Z0-9_-]+)', region)
    if m:
        cloud, region_short = m.group(1), m.group(2).replace('_', '-').lower()
    self_host_eligible = (cloud == 'AWS' and region_short == 'us-west-2')
    print(f'  parsed: cloud={cloud!r} region={region_short!r} '
          f'self_host_eligible={self_host_eligible}')

    # 3. SHOW DATABASES
    print('\n=== SHOW DATABASES (visible to current role) ===')
    rs, cols = q('SHOW DATABASES')
    name_idx = cols.index('name') if 'name' in cols else 1
    origin_idx = cols.index('origin') if 'origin' in cols else None
    kind_idx = cols.index('kind') if 'kind' in cols else None
    dbs: list[dict] = []
    for r in rs:
        nm = r[name_idx]
        origin = r[origin_idx] if origin_idx is not None else ''
        kind = r[kind_idx] if kind_idx is not None else ''
        dbs.append({'name': str(nm), 'origin': str(origin or ''),
                     'kind': str(kind or '')})
        print(f'  {nm:42s} origin={origin or "-":36s} kind={kind or "-"}')
    print(f'  total visible: {len(dbs)}')

    # 4. Required dbs from Spider2-Lite SF tasks
    required = _required_dbs_from_local()
    visible_names = {d['name'] for d in dbs}
    missing = sorted(required - visible_names)
    visible_match = sorted(required & visible_names)
    print(f'\n=== REQUIRED Spider2-Lite SF DBs ({len(required)}) ===')
    if not required:
        print('  (no local snowflake metadata found; using empty required set)')
    else:
        print(f'  visible: {len(visible_match)}/{len(required)}')
        print(f'  sample required: {sorted(required)[:8]}')
        if missing:
            print(f'  MISSING: {len(missing)}')
            for m in missing[:15]: print(f'    {m}')
            if len(missing) > 15: print(f'    ...and {len(missing)-15} more')

    # 5. Specifically: PATENTS (first SF item in v8 routing is sf_bq029 -> PATENTS)
    has_patents = 'PATENTS' in visible_names
    print(f'\n=== sf_bq029 -> PATENTS ===')
    print(f'  has_patents = {has_patents}')

    # 6. WAREHOUSES
    print('\n=== SHOW WAREHOUSES ===')
    rs, _ = q('SHOW WAREHOUSES')
    warehouses = []
    for r in rs:
        warehouses.append({'name': str(r[0]), 'state': str(r[1] if len(r)>1 else ''),
                            'size': str(r[3] if len(r)>3 else '')})
        print(f'  {r[0]:30s} state={r[1] if len(r)>1 else "":12s} '
              f'size={r[3] if len(r)>3 else ""}')

    # 7. Build summary
    can_run = bool(has_patents and (kwargs.get('role') == 'SPIDER2_RW') and
                    any(w['name'] == 'SPIDER2_WH' for w in warehouses))
    summary = {
        'connection_ok': True,
        'account_info': account_info,
        'cloud': cloud or None,
        'region': region_short or None,
        'self_host_eligible': self_host_eligible,
        'visible_databases': dbs,
        'visible_database_count': len(dbs),
        'required_database_count': len(required),
        'missing_database_count': len(missing),
        'visible_match_count': len(visible_match),
        'has_patents': has_patents,
        'warehouses': warehouses,
        'can_run_real_sf_benchmark': can_run,
        'role': kwargs.get('role'),
        'warehouse': kwargs.get('warehouse'),
        'database_default': kwargs.get('database'),
        'schema_default': kwargs.get('schema'),
    }

    out_dir = REPO / 'outputs' / 'snowflake' / 'readiness'
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'databases_visible.json').write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')

    md = ['# Snowflake readiness — databases visible to SPIDER2_RW',
            '',
            f'_Generated by `snowflake_setup/probe_databases.py`._',
            '',
            '## Account identity',
            '', '| Field | Value |', '|---|---|']
    for k in ['current_user','current_role','current_account','current_organization',
                'current_region','current_version']:
        md.append(f'| {k} | `{account_info.get(k) or "?"}` |')
    md += ['',
            f'**Parsed:** cloud=`{cloud or "?"}` region=`{region_short or "?"}` '
            f'self_host_eligible=**{self_host_eligible}**',
            '',
            f'## Databases visible: {len(dbs)}',
            '', '| Name | Origin | Kind |', '|---|---|---|']
    for d in dbs:
        md.append(f'| `{d["name"]}` | `{d["origin"] or "-"}` | `{d["kind"] or "-"}` |')
    md += ['',
            f'## Required Spider2-Lite SF databases: {len(required)}',
            '',
            f'- visible match: **{len(visible_match)}**',
            f'- missing: **{len(missing)}**',
            f'- has PATENTS (first SF task target): **{has_patents}**',
            '']
    if missing:
        md += ['### Missing databases', '']
        md += ['- ' + m for m in missing[:50]]
        if len(missing) > 50: md.append(f'- ...and {len(missing)-50} more')
    md += ['',
            '## Warehouses',
            '',
            '| Name | State | Size |',
            '|---|---|---|']
    for w in warehouses:
        md.append(f'| `{w["name"]}` | {w["state"]} | {w["size"]} |')
    md += ['',
            '## Verdict',
            '',
            f'`can_run_real_sf_benchmark` = **{can_run}**',
            '',
            ('Real Spider2-Lite SF execution is **READY**.' if can_run else
             'Real Spider2-Lite SF execution is **BLOCKED** until the '
             'expected databases are attached (Marketplace share OR '
             'self-host via `assets/Spider2_Data_Host.md`). The SF runner '
             'will route blocked items to '
             '`mode=blocked_missing_snowflake_database` rather than '
             'manufacturing failed predictions.'),
            '']
    (out_dir / 'databases_visible.md').write_text('\n'.join(md), encoding='utf-8')
    print(f'\nWROTE {out_dir / "databases_visible.json"}')
    print(f'WROTE {out_dir / "databases_visible.md"}')

    cur.close(); conn.close()
    return 0 if summary['can_run_real_sf_benchmark'] else 1


if __name__ == '__main__':
    sys.exit(main())
