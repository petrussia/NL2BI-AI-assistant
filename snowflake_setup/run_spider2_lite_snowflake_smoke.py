"""run_spider2_lite_snowflake_smoke.py — select Snowflake-subset Spider2-Lite
tasks and (optionally) connect-test. Does NOT run the heavy LLM agent;
that is gated behind `--allow-generate` once SF access is confirmed.

Usage:
    python snowflake_setup/run_spider2_lite_snowflake_smoke.py \
        --benchmark spider2-lite \
        --engine snowflake \
        --subset snowflake \
        --limit 1

    --limit 3   then     --limit 10   for progressive smoke-up.

Outputs:
    outputs/spider2_lite_snowflake_smoke/tasks_selected.jsonl
    outputs/spider2_lite_snowflake_smoke/connection_probe.json (if --probe-connection)
    outputs/spider2_lite_snowflake_smoke/run_metadata.json

Discovery flow:
    1. Parse `spider2-lite.jsonl` (paths probed in order: see DEFAULT_PATHS).
    2. Filter to Snowflake items by instance_id prefix (`sf*`).
    3. Save the selected slice for the smoke runner downstream.
    4. Optional: probe SF connection to confirm credentials work.
    5. NEVER runs the agent unless --allow-generate AND a valid SF probe exists.

Safe by default — no SF queries are issued without an explicit flag.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


# Where to look for spider2-lite.jsonl. First match wins.
DEFAULT_PATHS = [
    REPO / 'external_benchmarks' / 'spider2_lite' / 'raw' / 'Spider2' / 'spider2-lite' / 'spider2-lite.jsonl',
    Path('/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl'),
]


def find_dataset(override: str | None = None) -> Path | None:
    if override:
        p = Path(override).expanduser()
        return p if p.exists() else None
    env = os.environ.get('SPIDER2_LITE_JSONL')
    if env:
        p = Path(env).expanduser()
        if p.exists(): return p
    for p in DEFAULT_PATHS:
        if p.exists():
            return p
    return None


def detect_engine(item: dict) -> str:
    """Return 'snowflake' / 'bigquery' / 'sqlite' / 'unknown' for one item.
    Uses instance_id prefix; a few `sf_bq*` items remain Snowflake-routed
    because the underlying engine is still SF in the v2 release.
    """
    iid = str(item.get('instance_id') or item.get('id') or '').lower()
    if iid.startswith('sf'): return 'snowflake'
    if iid.startswith('bq') or iid.startswith('ga'): return 'bigquery'
    if iid.startswith('local') or iid.startswith('sl'): return 'sqlite'
    return 'unknown'


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def select_tasks(jsonl_path: Path, *, engine_filter: str | None = None,
                   subset: str | None = None,
                   limit: int | None = None) -> list[dict]:
    """Read items, filter by engine/subset, take first `limit`. The order
    follows the JSONL order (deterministic given the same file). Adds an
    `_engine` field to each kept item.
    """
    out: list[dict] = []
    with jsonl_path.open(encoding='utf-8') as f:
        for ln in f:
            try:
                it = json.loads(ln)
            except Exception:
                continue
            eng = detect_engine(it)
            if engine_filter and eng != engine_filter:
                continue
            if subset and subset != eng:
                continue
            it['_engine'] = eng
            out.append(it)
            if limit is not None and len(out) >= limit:
                break
    return out


def write_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def probe_snowflake() -> dict:
    """Run the smoke connection test in-process; return a sanitized dict.
    Same code as test_snowflake_connection.py but condensed and returns
    a structured result instead of printing.
    """
    here = Path(__file__).resolve().parent
    dotenv = here / '.env'
    env: dict[str, str] = {}
    if dotenv.exists():
        for raw in dotenv.read_text(encoding='utf-8').splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k, _, v = line.partition('=')
            env[k.strip()] = v.strip().strip('"').strip("'")
    def get(name: str) -> str:
        return os.environ.get(name) or env.get(name) or ''

    res: dict = {'probed_at': utcnow(),
                  'have_account': bool(get('SNOWFLAKE_ACCOUNT')),
                  'have_user': bool(get('SNOWFLAKE_USER')),
                  'have_password': bool(get('SNOWFLAKE_PASSWORD')),
                  'have_pkey': bool(get('SNOWFLAKE_PRIVATE_KEY_PATH')),
                  'authenticator': get('SNOWFLAKE_AUTHENTICATOR') or 'password'}
    if not (res['have_account'] and res['have_user']
              and (res['have_password'] or res['have_pkey'])):
        res['ok'] = False
        res['reason'] = 'missing_env'
        return res
    try:
        import snowflake.connector  # type: ignore
    except ImportError:
        res['ok'] = False
        res['reason'] = 'snowflake_connector_not_installed'
        return res
    kwargs: dict = dict(
        account=get('SNOWFLAKE_ACCOUNT'), user=get('SNOWFLAKE_USER'),
        application='spider2_lite_smoke',
    )
    if get('SNOWFLAKE_ROLE'): kwargs['role'] = get('SNOWFLAKE_ROLE')
    if get('SNOWFLAKE_WAREHOUSE'): kwargs['warehouse'] = get('SNOWFLAKE_WAREHOUSE')
    if get('SNOWFLAKE_DATABASE'): kwargs['database'] = get('SNOWFLAKE_DATABASE')
    if get('SNOWFLAKE_SCHEMA'): kwargs['schema'] = get('SNOWFLAKE_SCHEMA')
    if get('SNOWFLAKE_REGION'): kwargs['region'] = get('SNOWFLAKE_REGION')
    if res['have_pkey']:
        try:
            from cryptography.hazmat.primitives import serialization
            with open(get('SNOWFLAKE_PRIVATE_KEY_PATH'), 'rb') as f:
                pkey = serialization.load_pem_private_key(
                    f.read(),
                    password=(get('SNOWFLAKE_PRIVATE_KEY_PASSPHRASE').encode()
                                if get('SNOWFLAKE_PRIVATE_KEY_PASSPHRASE') else None))
            kwargs['private_key'] = pkey.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption())
            kwargs['authenticator'] = 'snowflake_jwt'
        except Exception as exc:
            res['ok'] = False
            res['reason'] = f'pkey_load_fail:{type(exc).__name__}'
            return res
    elif get('SNOWFLAKE_PASSWORD'):
        kwargs['password'] = get('SNOWFLAKE_PASSWORD')
    if get('SNOWFLAKE_AUTHENTICATOR'):
        kwargs['authenticator'] = get('SNOWFLAKE_AUTHENTICATOR')

    t0 = time.time()
    try:
        conn = snowflake.connector.connect(**kwargs)
    except Exception as exc:
        msg = str(exc)
        # Strip password from any leaked exception text
        pw = get('SNOWFLAKE_PASSWORD')
        if pw and pw in msg:
            msg = msg.replace(pw, '<PASSWORD>')
        res['ok'] = False
        res['reason'] = f'connect_fail:{type(exc).__name__}'
        res['connect_error_short'] = msg[:300]
        return res
    cur = conn.cursor()
    try:
        cur.execute('SELECT CURRENT_VERSION()')
        res['current_version'] = str(cur.fetchone()[0])
        cur.execute('SELECT CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()')
        r, w, db, sc = cur.fetchone()
        res['current_role'] = str(r); res['current_warehouse'] = str(w)
        res['current_database'] = str(db); res['current_schema'] = str(sc)
        res['ok'] = True
    finally:
        cur.close(); conn.close()
    res['connect_ms'] = round((time.time() - t0) * 1000)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--benchmark', default='spider2-lite',
                     choices=['spider2-lite'],
                     help='Only spider2-lite is supported here (not spider2-snow).')
    ap.add_argument('--engine', default='snowflake',
                     choices=['snowflake', 'bigquery', 'sqlite', 'all'],
                     help='Filter items by execution engine.')
    ap.add_argument('--subset', default='snowflake',
                     help='Alias for --engine; kept for parity with the brief.')
    ap.add_argument('--limit', type=int, default=1,
                     help='Smoke step: 1 → 3 → 10 progressive.')
    ap.add_argument('--out-dir',
                     default=str(REPO / 'outputs' / 'spider2_lite_snowflake_smoke'),
                     help='Where to write tasks_selected.jsonl + run_metadata.json.')
    ap.add_argument('--probe-connection', action='store_true',
                     help='Run the SELECT CURRENT_VERSION() smoke against SF.')
    ap.add_argument('--dataset-path', default=None,
                     help='Override path to spider2-lite.jsonl. Falls back to '
                          'SPIDER2_LITE_JSONL env var, then DEFAULT_PATHS.')
    ap.add_argument('--allow-generate', action='store_true',
                     help='Sentinel — must be set together with --probe-connection '
                          'to enable downstream agent generation. Right now the '
                          'agent integration is NOT wired; flag is reserved for '
                          'the next iteration after SF access lands.')
    args = ap.parse_args()

    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    eng_filter = args.engine if args.engine != 'all' else None
    subset = None
    if args.subset and args.subset != args.engine and args.engine != 'all':
        # subset/engine mismatch: prefer subset
        eng_filter = args.subset
    elif args.subset and args.engine == 'all':
        eng_filter = args.subset

    # 1. find dataset
    jsonl = find_dataset(args.dataset_path)
    if jsonl is None:
        print('FAIL: spider2-lite.jsonl not found. Tried (in order):')
        if args.dataset_path: print(f'  - --dataset-path: {args.dataset_path}')
        if os.environ.get("SPIDER2_LITE_JSONL"):
            print(f'  - $SPIDER2_LITE_JSONL: {os.environ["SPIDER2_LITE_JSONL"]}')
        for p in DEFAULT_PATHS: print(f'  - {p}')
        print('\nTo unblock locally:')
        print('  1) pass --dataset-path <path>, OR')
        print('  2) export SPIDER2_LITE_JSONL=<path>, OR')
        print('  3) place the file at one of the DEFAULT_PATHS above.')
        return 2
    print(f'DATASET: {jsonl}')

    # 2. select
    selected = select_tasks(jsonl, engine_filter=eng_filter,
                              limit=args.limit)
    print(f'SELECTED: {len(selected)} items '
          f'(engine={eng_filter or "all"}, limit={args.limit})')

    # Coverage stats over the full file (no limit)
    full = select_tasks(jsonl, engine_filter=None)
    from collections import Counter
    by_eng = Counter(it.get('_engine', '?') for it in full)
    print(f'TOTAL_BY_ENGINE: {dict(by_eng)}')

    # 3. write selection
    sel_path = out_dir / 'tasks_selected.jsonl'
    write_jsonl(selected, sel_path)
    print(f'WROTE: {sel_path}')

    meta = {
        'benchmark': args.benchmark,
        'engine': args.engine,
        'subset': args.subset,
        'limit': args.limit,
        'selected_n': len(selected),
        'total_by_engine': dict(by_eng),
        'dataset_path': str(jsonl),
        'tasks_selected_path': str(sel_path),
        'generated_at': utcnow(),
        'probe_connection': bool(args.probe_connection),
        'allow_generate': bool(args.allow_generate),
    }

    # 4. optional connection probe
    if args.probe_connection:
        print('\nPROBING SF CONNECTION…')
        probe = probe_snowflake()
        probe_path = out_dir / 'connection_probe.json'
        probe_path.write_text(json.dumps(probe, indent=2), encoding='utf-8')
        meta['probe'] = {k: probe.get(k) for k in
                          ('ok', 'reason', 'current_version', 'current_role',
                            'current_warehouse', 'current_database',
                            'current_schema', 'connect_ms')}
        print(f'WROTE: {probe_path} ok={probe.get("ok")} reason={probe.get("reason","-")}')
        if not probe.get('ok'):
            print('SF connection probe FAILED — agent generation will NOT run. '
                  'Fix env / creds and re-probe.')

    # 5. agent generation (gated)
    if args.allow_generate:
        if not args.probe_connection:
            print('REFUSED: --allow-generate requires --probe-connection.')
            meta['generation_status'] = 'refused_no_probe'
        elif not (meta.get('probe') or {}).get('ok'):
            print('REFUSED: SF probe did not pass; agent generation skipped.')
            meta['generation_status'] = 'refused_probe_failed'
        else:
            # Placeholder: the actual agent invocation will be added once
            # the SF executor lands in a future module. For now, refuse to
            # invent SQL without the full pipeline.
            print('NOT_IMPLEMENTED: SF agent integration is the next step. '
                  'Selection JSONL ready; do not run heavy generation yet.')
            meta['generation_status'] = 'not_implemented_yet'

    meta_path = out_dir / 'run_metadata.json'
    meta_path.write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print(f'WROTE: {meta_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
