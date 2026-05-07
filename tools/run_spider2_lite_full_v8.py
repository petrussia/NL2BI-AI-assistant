"""run_spider2_lite_full_v8.py — Spider2-Lite full benchmark runner (v8 agent).

Lane-aware: BigQuery (~205) + Snowflake (~207) + SQLite stub (~135) → 547.

Each lane writes its own metrics block; SQLite is flagged
`non_comparable=True` and is NOT mixed into the official EX number.

Usage:
  python tools/run_spider2_lite_full_v8.py --limit 1
  python tools/run_spider2_lite_full_v8.py --limit-bq 3 --limit-sf 3 --limit-sqlite 3
  python tools/run_spider2_lite_full_v8.py --limit 0      # FULL 547

Outputs land under outputs/spider2_lite/runs/<RUN_ID>/.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'repo' / 'src' / 'evaluation'))

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


# Reuse the bridge LLM from the Snow runner
from run_spider2_snow_full_v8 import (  # type: ignore
    bridge_url, bridge_exec, ensure_model, gen_remote, ensure_db_schema,
)


def _ensure_bq_db_schema(db: str) -> Path | None:
    """Pull a BQ db schema dir from Drive into local cache."""
    target = REPO / 'data' / 'spider2_lite' / 'resource' / 'databases' / 'bigquery' / db
    if target.exists() and any(target.glob('**/*.json')):
        return target
    target.mkdir(parents=True, exist_ok=True)
    code = ('import os, base64, json, glob\n'
            f'SRC = "/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/bigquery/{db}"\n'
            'if not os.path.isdir(SRC):\n'
            '    print(json.dumps({"ok": False, "error": "no_src"}))\n'
            'else:\n'
            '    files = []\n'
            '    for p in glob.glob(SRC + "/**/*.json", recursive=True):\n'
            '        rel = os.path.relpath(p, SRC)\n'
            '        with open(p, "rb") as f:\n'
            '            files.append([rel, base64.b64encode(f.read()).decode()])\n'
            '    print(json.dumps({"ok": True, "files": files}))\n')
    r = bridge_exec(code, timeout=180)
    out = (r.get('stdout') or '').strip()
    try:
        obj = json.loads(out.split('\n')[-1])
    except Exception:
        return None
    if not obj.get('ok'):
        return None
    import base64
    for rel, b64 in obj['files']:
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(base64.b64decode(b64))
    return target


def select_tasks(jsonl: Path, *, limit: int,
                   limit_bq: int = 0, limit_sf: int = 0,
                   limit_sqlite: int = 0) -> list[dict]:
    rows = [json.loads(l) for l in jsonl.open(encoding='utf-8') if l.strip()]
    # Per-lane limits take precedence when any are non-zero.
    if limit_bq or limit_sf or limit_sqlite:
        bq = [r for r in rows if not str(r['instance_id']).startswith(('sf', 'local'))]
        sf = [r for r in rows if str(r['instance_id']).startswith('sf')]
        lc = [r for r in rows if str(r['instance_id']).startswith('local')]
        if limit_bq: bq = bq[:limit_bq]
        if limit_sf: sf = sf[:limit_sf]
        if limit_sqlite: lc = lc[:limit_sqlite]
        return bq + sf + lc
    # Otherwise apply --limit equally; 0 = FULL
    if limit and limit > 0:
        return rows[:limit]
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dataset', default=str(REPO / 'data' / 'spider2_lite' / 'raw' / 'spider2-lite.jsonl'))
    ap.add_argument('--limit', type=int, default=1,
                     help='Apply equally to all lanes; 0 = FULL.')
    ap.add_argument('--limit-bq', type=int, default=0)
    ap.add_argument('--limit-sf', type=int, default=0)
    ap.add_argument('--limit-sqlite', type=int, default=0)
    ap.add_argument('--no-execute', action='store_true')
    ap.add_argument('--max-rows', type=int, default=1000)
    ap.add_argument('--max-repair-rounds', type=int, default=1)
    ap.add_argument('--run-id', default=None)
    ap.add_argument('--skip-sqlite', action='store_true',
                     help='Do not even attempt SQLite stub items.')
    args = ap.parse_args()

    ds = Path(args.dataset)
    items = select_tasks(ds, limit=args.limit, limit_bq=args.limit_bq,
                            limit_sf=args.limit_sf, limit_sqlite=args.limit_sqlite)
    print(f'TASKS: {len(items)}')

    run_id = args.run_id or f'lite_v8_lim{args.limit}_{int(time.time())}'
    out_dir = REPO / 'outputs' / 'spider2_lite' / 'runs' / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    print('Bootstrapping LLM on Colab...')
    ensure_model()

    print('Building executors...')
    from spider2_lite_tools_v8 import build_bq_executor, build_sf_executor
    from spider2_lite_tools_v8 import build_sqlite_executor as _make_sqlite

    bq_executor = build_bq_executor(timeout_s=120)
    sf_executor = build_sf_executor(query_tag=f'spider2_lite_v8/{run_id}',
                                       timeout_s=120, max_rows=args.max_rows)

    # Schema loaders (lazy + cached)
    sf_idx_cache: dict[str, object] = {}
    bq_idx_cache: dict[str, object] = {}
    sqlite_exec_cache: dict[str, object] = {}

    def sf_idx_loader(db: str):
        if db in sf_idx_cache: return sf_idx_cache[db]
        ddir = ensure_db_schema(db)
        if ddir is None:
            sf_idx_cache[db] = None
            return None
        from spider2_sf_schema_index_v8 import build_index_from_db_dir
        try:
            idx = build_index_from_db_dir(db, ddir)
        except Exception:
            idx = None
        sf_idx_cache[db] = idx
        return idx

    def bq_idx_loader(db: str):
        if db in bq_idx_cache: return bq_idx_cache[db]
        ddir = _ensure_bq_db_schema(db)
        if ddir is None:
            bq_idx_cache[db] = None
            return None
        from spider2_bq_schema_index_v8 import build_index_from_db_dir
        try:
            idx = build_index_from_db_dir(db, ddir)
        except Exception:
            idx = None
        bq_idx_cache[db] = idx
        return idx

    def sqlite_exec_for(db: str):
        if db in sqlite_exec_cache: return sqlite_exec_cache[db]
        ex = _make_sqlite(db, max_rows=args.max_rows, timeout_s=30)
        sqlite_exec_cache[db] = ex
        return ex

    from spider2_lite_agent_v8 import run_lite_step_dispatch

    pred_path = out_dir / 'predictions.jsonl'
    cand_path = out_dir / 'candidates.jsonl'
    err_tax_by_lane: dict[str, Counter] = defaultdict(Counter)
    src_break_by_lane: dict[str, Counter] = defaultdict(Counter)
    metrics_by_lane: dict[str, Counter] = defaultdict(Counter)
    cost_rows: list[dict] = []

    for i, it in enumerate(items, 1):
        iid = it['instance_id']; db = it['db']
        prefix = ('sf' if iid.startswith('sf')
                    else ('local' if iid.startswith('local') else 'bq'))
        if args.skip_sqlite and prefix == 'local':
            continue
        t0 = time.time()
        print(f'[{i}/{len(items)}] {iid} ({prefix}) db={db} ...', flush=True)
        sqlite_executor_inst = (sqlite_exec_for(db) if prefix == 'local' else None)
        try:
            res = run_lite_step_dispatch(
                it, gen=gen_remote,
                bq_executor=bq_executor, sf_executor=sf_executor,
                sqlite_executor=sqlite_executor_inst,
                bq_idx_loader=bq_idx_loader, sf_idx_loader=sf_idx_loader,
                max_repair_rounds=args.max_repair_rounds,
                max_rows=args.max_rows,
            )
        except Exception as exc:
            res = {'instance_id': iid, 'db': db, 'lane': f'A_{prefix}',
                   'sql': '', 'parses': False, 'executable': False,
                   'error_type': 'agent_exception',
                   'error_message': f'{type(exc).__name__}: {exc}'[:300],
                   'wall_time_s': round(time.time() - t0, 2),
                   'candidate_count': 0, 'candidates_summary': []}

        lane = res.get('lane', f'A_{prefix}')
        non_comp = res.get('non_comparable', False)
        metrics_by_lane[lane]['n'] += 1
        if res.get('parses'): metrics_by_lane[lane]['parse_ok'] += 1
        if res.get('executable'): metrics_by_lane[lane]['execute_ok'] += 1
        et = res.get('error_type') or 'none'
        err_tax_by_lane[lane][et] += 1
        src_break_by_lane[lane][res.get('final_source') or 'none'] += 1

        slim = {
            'instance_id': iid, 'db': db, 'lane': lane,
            'non_comparable': non_comp,
            'sql': res.get('sql', ''), 'final_source': res.get('final_source', ''),
            'parses': res.get('parses'), 'executable': res.get('executable'),
            'rows_count': res.get('rows_count', 0),
            'error_type': res.get('error_type', ''),
            'error_message': res.get('error_message', ''),
            'wall_time_s': res.get('wall_time_s', round(time.time() - t0, 2)),
            'utc': now(),
        }
        with pred_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(slim, ensure_ascii=False) + '\n')
        with cand_path.open('a', encoding='utf-8') as f:
            for cs in res.get('candidates_summary', []):
                f.write(json.dumps({**cs, 'instance_id': iid, 'lane': lane},
                                   ensure_ascii=False) + '\n')
        cost_rows.append({'instance_id': iid, 'lane': lane, 'db': db,
                            'wall_time_s': slim['wall_time_s']})
        print(f'  lane={lane} parse={res.get("parses")} '
              f'exec={res.get("executable")} non_comp={non_comp} '
              f'err={res.get("error_type","-")} wall={slim["wall_time_s"]}s')

    # Lane metrics CSV
    with (out_dir / 'lane_metrics.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['lane', 'n', 'parse_ok', 'execute_ok',
                      'parse_rate', 'execute_rate', 'non_comparable'])
        for lane, m in metrics_by_lane.items():
            n = m['n']; po = m['parse_ok']; eo = m['execute_ok']
            non_c = (lane == 'C_sqlite_stub')
            w.writerow([lane, n, po, eo,
                          f'{(po/max(1,n))*100:.2f}',
                          f'{(eo/max(1,n))*100:.2f}', non_c])

    with (out_dir / 'error_taxonomy.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['lane', 'error_type', 'count'])
        for lane, c in err_tax_by_lane.items():
            for k, v in c.most_common(): w.writerow([lane, k, v])

    with (out_dir / 'source_breakdown.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['lane', 'final_source', 'count'])
        for lane, c in src_break_by_lane.items():
            for k, v in c.most_common(): w.writerow([lane, k, v])

    with (out_dir / 'cost_runtime.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['instance_id', 'lane', 'db', 'wall_time_s'])
        w.writeheader()
        for r in cost_rows: w.writerow(r)

    # Readout
    md = [
        f'# Spider2-Lite v8 — run `{run_id}`', '',
        f'_Generated: {now()} | dataset: `{ds.relative_to(REPO).as_posix()}`_',
        '',
        '## Lane metrics (do NOT average across lanes — they are not comparable)',
        '',
        '| lane | n | parse_ok | execute_ok | parse_rate | execute_rate | non_comparable |',
        '|---|---:|---:|---:|---:|---:|:---:|',
    ]
    for lane, m in metrics_by_lane.items():
        n = m['n']; po = m['parse_ok']; eo = m['execute_ok']
        non_c = (lane == 'C_sqlite_stub')
        md.append(f'| `{lane}` | {n} | {po} | {eo} | '
                    f'{(po/max(1,n))*100:.1f}% | {(eo/max(1,n))*100:.1f}% | '
                    f'{"YES" if non_c else "no"} |')
    md.append('')
    md.append('## Notes')
    md.append('- `A_bq` lane uses official BQ live execute (capped 1 GB billed).')
    md.append('- `A_sf` lane uses official Snowflake live execute (PARTICIPANT/COMPUTE_WH_PARTICIPANT).')
    md.append('- `C_sqlite_stub` lane runs against Spider2 sample-rows SQLite databases. '
                'Results are NOT comparable to official EX — flagged `non_comparable=True`.')
    (out_dir / 'readout.md').write_text('\n'.join(md), encoding='utf-8')

    canon = REPO / 'outputs' / 'predictions'
    canon.mkdir(parents=True, exist_ok=True)
    (canon / f'spider2_lite_agent_v8_{run_id}_predictions.jsonl').write_text(
        pred_path.read_text(encoding='utf-8'), encoding='utf-8')

    print(f'\nDONE. {out_dir.relative_to(REPO).as_posix()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
