"""run_spider2_lite_sqlite_v10_pilot.py — SQLite-only pilot10 with v10 materializer.

Uses `spider2_lite_sqlite_materializer_v10.resolve_sqlite_db` to build
a real .sqlite from row-level JSONs (Spider2-Lite ships JSON stubs, not
binaries). All results are flagged `non_comparable=True`.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'repo' / 'src' / 'evaluation'))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=10)
    ap.add_argument('--run-id', default=None)
    args = ap.parse_args()

    ds = REPO / 'data' / 'spider2_lite' / 'raw' / 'spider2-lite.jsonl'
    rows = [json.loads(l) for l in ds.open(encoding='utf-8') if l.strip()]
    locals_ = [r for r in rows if r['instance_id'].startswith('local')][:args.limit]
    print(f'TASKS: {len(locals_)} (sqlite stub only, NON-COMPARABLE)')

    run_id = args.run_id or f'lite_sqlite_v10_pilot{args.limit}_{int(time.time())}'
    out_dir = REPO / 'outputs' / 'spider2_lite' / 'runs' / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    from spider2_lite_sqlite_materializer_v10 import resolve_sqlite_db
    from run_spider2_snow_full_v8 import ensure_model, gen_remote
    print('Bootstrapping LLM...')
    ensure_model()

    audit_rows: list[dict] = []
    pred_rows: list[dict] = []
    err = Counter()
    n_parse = n_exec = 0

    from spider2_agent_v7 import _extract_sql

    for i, it in enumerate(locals_, 1):
        iid = it['instance_id']; db = it['db']; q = it['question']
        print(f'\n[{i}/{len(locals_)}] {iid} db={db} ...', flush=True)
        t0 = time.time()
        rr = resolve_sqlite_db(db)
        audit_rows.append({'iid': iid, 'dataset_db': db,
                            'disk_db': rr.disk_db,
                            'local_sqlite': str(rr.local_sqlite) if rr.local_sqlite else '',
                            'n_tables': rr.n_tables, 'n_rows': rr.n_rows_total,
                            'error': rr.error})
        if not rr.local_sqlite:
            err['materializer_failed'] += 1
            pred_rows.append({'instance_id': iid, 'db': db, 'lane': 'C_sqlite_stub',
                                'non_comparable': True,
                                'sql': '', 'parses': False, 'executable': False,
                                'error_type': 'materializer_failed',
                                'error_message': rr.error,
                                'wall_time_s': round(time.time() - t0, 2)})
            print(f'  MATERIALIZER FAIL: {rr.error}')
            continue

        # Generate SQL
        prompt = (f"Generate a SQLite SELECT for the question.\n"
                    f"DATABASE: {db}\nQUESTION: {q}\n"
                    f"Reply with SQL inside ```sql ... ``` fence.")
        try:
            raw = gen_remote(prompt, max_new=600)
            sql = _extract_sql(raw) or ''
        except Exception as exc:
            sql = ''
            err['gen_error'] += 1
        # Run against materialized .sqlite
        import sqlite3
        parse_ok = False; exec_ok = False; rows_count = 0
        et = ''; em = ''
        if not sql.strip():
            et = 'empty_sql'
            err['empty_sql'] += 1
        else:
            try:
                conn = sqlite3.connect(str(rr.local_sqlite),
                                          check_same_thread=False)
                cur = conn.cursor()
                cur.execute(sql)
                got = cur.fetchmany(100)
                exec_ok = True; parse_ok = True
                rows_count = len(got)
                conn.close()
                n_parse += 1; n_exec += 1
            except Exception as exc:
                em = str(exc)[:200]
                if 'no such table' in em.lower() or 'no such column' in em.lower():
                    et = 'object_not_found'
                elif 'syntax error' in em.lower() or 'near' in em.lower():
                    et = 'syntax'
                else:
                    et = 'sqlite_error'
                err[et] += 1

        pred_rows.append({'instance_id': iid, 'db': db, 'lane': 'C_sqlite_stub',
                            'non_comparable': True,
                            'sql': sql, 'parses': parse_ok, 'executable': exec_ok,
                            'rows_count': rows_count,
                            'error_type': et, 'error_message': em,
                            'wall_time_s': round(time.time() - t0, 2)})
        print(f'  parse={parse_ok} exec={exec_ok} rows={rows_count} err={et}'
              f' wall={round(time.time() - t0, 2)}s')

    # Write outputs
    pred_path = out_dir / 'predictions.jsonl'
    with pred_path.open('w', encoding='utf-8') as f:
        for r in pred_rows: f.write(json.dumps(r, ensure_ascii=False) + '\n')

    audit_path = REPO / 'outputs' / 'tables' / 'spider2_lite_sqlite_resolver_v10_audit.csv'
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open('w', newline='', encoding='utf-8') as f:
        if audit_rows:
            w = csv.DictWriter(f, fieldnames=list(audit_rows[0].keys()))
            w.writeheader()
            for r in audit_rows: w.writerow(r)

    n = max(1, len(locals_))
    md = [f'# Spider2-Lite SQLite v10 — run `{run_id}`', '',
            f'_NON-COMPARABLE — sample-rows stub. Only parse/exec smoke._', '',
            '## Aggregate metrics (NON-COMPARABLE)', '',
            '| metric | value | rate |', '|---|---:|---:|',
            f'| n | {len(locals_)} | — |',
            f'| parse_ok | {n_parse} | {(n_parse/n)*100:.1f}% |',
            f'| executable | {n_exec} | {(n_exec/n)*100:.1f}% |',
            '', '## Error taxonomy', '', '| error_type | count |',
            '|---|---:|']
    for k, v in err.most_common(): md.append(f'| `{k}` | {v} |')
    md += ['', '## Resolver audit',
            'See `outputs/tables/spider2_lite_sqlite_resolver_v10_audit.csv`.']
    (out_dir / 'readout.md').write_text('\n'.join(md), encoding='utf-8')

    canon = REPO / 'outputs' / 'predictions'
    canon.mkdir(parents=True, exist_ok=True)
    (canon / f'spider2_lite_sqlite_v10_{run_id}_predictions.jsonl').write_text(
        pred_path.read_text(encoding='utf-8'), encoding='utf-8')

    print(f'\nDONE. {out_dir.relative_to(REPO).as_posix()}')
    print(f'  parse_ok={n_parse}/{len(locals_)} exec_ok={n_exec}/{len(locals_)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
