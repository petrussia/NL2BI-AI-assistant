"""run_spider2_snow_full_v10.py — Phase 12 H1-fix runner for Spider2-Snow.

Differences from v9:
  - Uses `spider2_snow_agent_v10.run_snow_agent_step_v10`
  - Logs per-candidate `applied_dialect_fixes` AND
    `applied_identifier_fixes` in candidates.jsonl.
  - readout.md includes a v10-specific identifier-fix breakdown.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter
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


# Reuse bridge plumbing + Snow canonical schema fetch from the v9 runner
from run_spider2_snow_full_v9 import (  # type: ignore
    bridge_url, bridge_exec, ensure_model, gen_remote, ensure_db_schema,
    select_tasks,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dataset', default=str(REPO / 'data' / 'spider2_snow' / 'raw' / 'spider2-snow.jsonl'))
    ap.add_argument('--limit', type=int, default=10)
    ap.add_argument('--no-execute', action='store_true')
    ap.add_argument('--max-rows', type=int, default=1000)
    ap.add_argument('--max-repair-rounds', type=int, default=1)
    ap.add_argument('--run-id', default=None)
    args = ap.parse_args()

    ds = Path(args.dataset)
    if not ds.exists():
        print(f'FAIL: dataset {ds} missing'); return 2
    items = select_tasks(ds, limit=args.limit)
    print(f'TASKS: {len(items)} (limit={args.limit})')
    if not items: return 0

    run_id = args.run_id or f'snow_v10_lim{args.limit}_{int(time.time())}'
    out_dir = REPO / 'outputs' / 'spider2_snow' / 'runs' / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f'RUN_ID: {run_id}')

    print('\nLoading model on Colab (idempotent)...')
    ensure_model()

    from spider2_sf_executor_v8 import build_sf_executor
    sf_executor = build_sf_executor(query_tag=f'spider2_snow_v10/{run_id}',
                                       timeout_s=120, max_rows=args.max_rows)

    from spider2_snow_agent_v10 import run_snow_agent_step_v10
    from spider2_snow_schema_retrieval_v8 import build_index_from_db_dir

    pred_path = out_dir / 'predictions.jsonl'
    cand_path = out_dir / 'candidates.jsonl'
    trace_path = out_dir / 'traces.jsonl'
    metrics: Counter = Counter()
    err_tax = Counter()
    src_break = Counter()
    dialect_fix_break = Counter()
    ident_fix_total = Counter()
    cost_rows: list[dict] = []
    rep_helpful = 0
    schemas_cache: dict[str, object] = {}

    for i, it in enumerate(items, 1):
        iid = it['instance_id']; db = it['db']; question = it['question']
        t_task = time.time()
        print(f'\n[{i}/{len(items)}] {iid} db={db} ...', flush=True)

        if db not in schemas_cache:
            ddir = ensure_db_schema(db)
            if ddir is None:
                schemas_cache[db] = None
            else:
                try:
                    schemas_cache[db] = build_index_from_db_dir(db, ddir)
                except Exception as exc:
                    print(f'  schema_build_err: {exc}')
                    schemas_cache[db] = None
        idx = schemas_cache.get(db)
        if idx is None or not getattr(idx, 'tables', []):
            print(f'  SKIP: schema missing for {db}')
            row = {'instance_id': iid, 'db': db, 'lane': 'A_sf',
                    'mode': 'blocked_no_schema',
                    'sql': '', 'final_source': '', 'parses': False,
                    'executable': False, 'error_type': 'schema_missing',
                    'wall_time_s': round(time.time() - t_task, 2)}
            with pred_path.open('a', encoding='utf-8') as f:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
            metrics['n'] += 1
            err_tax['schema_missing'] += 1
            continue

        try:
            result = run_snow_agent_step_v10(
                question, idx, gen=gen_remote, sf_executor=sf_executor,
                max_repair_rounds=args.max_repair_rounds,
                execute_chosen_query=not args.no_execute,
                max_rows_exec=args.max_rows,
            )
        except Exception as exc:
            result = {'sql': '', 'original_sql': '', 'final_source': '',
                       'parses': False, 'executable': False,
                       'error_type': 'agent_exception',
                       'error_message': f'{type(exc).__name__}: {exc}'[:300],
                       'wall_time_s': round(time.time() - t_task, 2),
                       'candidates_summary': [], 'candidate_count': 0,
                       'applied_dialect_fixes': [], 'applied_identifier_fixes': {},
                       'repair_record': None}

        metrics['n'] += 1
        if result.get('parses'): metrics['parse_ok'] += 1
        if result.get('executable'): metrics['execute_ok'] += 1
        et = result.get('error_type') or 'none'
        err_tax[et] += 1
        src_break[result.get('final_source') or 'none'] += 1
        for cs in result.get('candidates_summary', []):
            for fix in cs.get('applied_dialect_fixes', []) or []:
                dialect_fix_break[fix] += 1
            ifx = cs.get('applied_identifier_fixes') or {}
            ident_fix_total['n_4part_collapsed'] += ifx.get('n_4part_collapsed', 0)
            ident_fix_total['n_quoted_blob_unwrapped'] += ifx.get('n_quoted_blob_unwrapped', 0)
        rr = result.get('repair_record')
        if rr and rr.get('success'): rep_helpful += 1

        pred_row = {
            'instance_id': iid, 'db': db, 'lane': 'A_sf',
            'sql': result['sql'], 'original_sql': result.get('original_sql', ''),
            'final_source': result['final_source'],
            'parses': result['parses'], 'executable': result['executable'],
            'rows_count': result.get('rows_count', 0),
            'error_type': result.get('error_type', ''),
            'error_message': result.get('error_message', ''),
            'applied_dialect_fixes': result.get('applied_dialect_fixes', []),
            'applied_identifier_fixes': result.get('applied_identifier_fixes', {}),
            'wall_time_s': result['wall_time_s'],
            'utc': now(),
        }
        with pred_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(pred_row, ensure_ascii=False) + '\n')
        with cand_path.open('a', encoding='utf-8') as f:
            for cs in result.get('candidates_summary', []):
                f.write(json.dumps({**cs, 'instance_id': iid},
                                    ensure_ascii=False) + '\n')
        with trace_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps({
                'instance_id': iid, 'db': db,
                'repair_record': result.get('repair_record'),
                'selector_audit': result.get('selector_audit'),
                'utc': now(),
            }, ensure_ascii=False) + '\n')
        cost_rows.append({'instance_id': iid, 'db': db,
                            'wall_time_s': result['wall_time_s'],
                            'elapsed_ms_chosen': result.get('elapsed_ms') or 0,
                            'candidate_count': result.get('candidate_count', 0)})
        ident_str = (f"4p={result['applied_identifier_fixes'].get('n_4part_collapsed', 0)} "
                       f"qb={result['applied_identifier_fixes'].get('n_quoted_blob_unwrapped', 0)}"
                       if result.get('applied_identifier_fixes') else '·')
        print(f'  parse={result.get("parses")} exec={result.get("executable")} '
              f'rows={result.get("rows_count",0)} '
              f'err={result.get("error_type","-")} ident={ident_str} '
              f'wall={result.get("wall_time_s")}s')

    # CSVs
    with (out_dir / 'metrics.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['metric', 'value'])
        w.writerow(['n_total', metrics['n']])
        w.writerow(['parse_ok', metrics['parse_ok']])
        w.writerow(['execute_ok', metrics['execute_ok']])
        w.writerow(['repair_helpful', rep_helpful])
        w.writerow(['ident_4part_collapsed_total',
                       ident_fix_total['n_4part_collapsed']])
        w.writerow(['ident_quoted_blob_unwrapped_total',
                       ident_fix_total['n_quoted_blob_unwrapped']])
    with (out_dir / 'error_taxonomy.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['error_type', 'count'])
        for k, v in err_tax.most_common(): w.writerow([k, v])
    with (out_dir / 'source_breakdown.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['final_source', 'count'])
        for k, v in src_break.most_common(): w.writerow([k, v])
    with (out_dir / 'dialect_fix_breakdown.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['fix_name', 'candidate_count'])
        for k, v in dialect_fix_break.most_common(): w.writerow([k, v])
    with (out_dir / 'cost_runtime.csv').open('w', newline='', encoding='utf-8') as f:
        if cost_rows:
            w = csv.DictWriter(f, fieldnames=list(cost_rows[0].keys()))
            w.writeheader()
            for r in cost_rows: w.writerow(r)

    n = max(1, metrics['n'])
    md = [f'# Spider2-Snow v10 — run `{run_id}` (Phase 12, H1 fix)', '',
            f'_Generated: {now()}_', '',
            '## Aggregate metrics (CANONICAL Spider2-Snow 547)', '',
            '| metric | value | rate |',
            '|---|---:|---:|',
            f"| n_total | {metrics['n']} | — |",
            f"| parse_ok | {metrics['parse_ok']} | "
            f"{(metrics['parse_ok']/n)*100:.1f}% |",
            f"| execute_ok | {metrics['execute_ok']} | "
            f"{(metrics['execute_ok']/n)*100:.1f}% |",
            f"| repair_helpful | {rep_helpful} | — |",
            f"| ident_4part_collapsed_total | {ident_fix_total['n_4part_collapsed']} | — |",
            f"| ident_quoted_blob_unwrapped_total | {ident_fix_total['n_quoted_blob_unwrapped']} | — |",
            '', '## Dialect-fix breakdown', '',
            '| fix | applied to N candidates |',
            '|---|---:|']
    for k, v in dialect_fix_break.most_common(): md.append(f'| `{k}` | {v} |')
    md += ['', '## Error taxonomy', '', '| error_type | count |',
            '|---|---:|']
    for k, v in err_tax.most_common(15): md.append(f'| `{k}` | {v} |')
    md += ['', '## Source breakdown (chosen candidate)', '',
            '| source | count |', '|---|---:|']
    for k, v in src_break.most_common(): md.append(f'| `{k}` | {v} |')
    (out_dir / 'readout.md').write_text('\n'.join(md), encoding='utf-8')

    canon = REPO / 'outputs' / 'predictions'
    canon.mkdir(parents=True, exist_ok=True)
    (canon / f'spider2_snow_agent_v10_{run_id}_predictions.jsonl').write_text(
        pred_path.read_text(encoding='utf-8'), encoding='utf-8')

    print(f'\nDONE. {out_dir.relative_to(REPO).as_posix()}')
    print(f'  parse_ok={metrics["parse_ok"]}/{metrics["n"]} '
          f'execute_ok={metrics["execute_ok"]}/{metrics["n"]}')
    print(f'  ident_fixes: 4part={ident_fix_total["n_4part_collapsed"]} '
          f'quoted_blob={ident_fix_total["n_quoted_blob_unwrapped"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
