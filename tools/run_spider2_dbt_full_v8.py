"""run_spider2_dbt_full_v8.py — Spider2-DBT v8 full benchmark runner.

Spider2-DBT is a code-generation agent task on 68 examples. The pipeline
(local-generate / server-evaluate via SSH bridge) is implemented in
`spider2_dbt_bridge.run_dbt_ablation`; this v8 runner uses the V4
(diff-form) variant — winner of the n=6 ablation in commit 8f57eea.

Usage:
  python tools/run_spider2_dbt_full_v8.py --limit 1
  python tools/run_spider2_dbt_full_v8.py --limit 3
  python tools/run_spider2_dbt_full_v8.py --limit 10
  python tools/run_spider2_dbt_full_v8.py --limit 0    # FULL 68

Outputs land under outputs/spider2_dbt/runs_v8/<RUN_ID>/.
"""
from __future__ import annotations

import argparse
import csv
import json
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


def list_tasks() -> list[str]:
    """Pull the 68 task IDs from outputs/spider2_dbt/_task_inventory.json
    or fall back to task_taxonomy.csv."""
    inv = REPO / 'outputs' / 'spider2_dbt' / '_task_inventory.json'
    if inv.exists():
        d = json.loads(inv.read_text(encoding='utf-8'))
        if isinstance(d, list):
            return [t['instance_id'] for t in d]
        if isinstance(d, dict) and 'tasks' in d:
            return [t['instance_id'] for t in d['tasks']]
    tax = REPO / 'outputs' / 'spider2_dbt' / 'task_taxonomy.csv'
    if tax.exists():
        import csv as _csv
        return [row['instance_id'] for row in _csv.DictReader(tax.open(encoding='utf-8'))]
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--limit', type=int, default=1,
                     help='0 = FULL 68')
    ap.add_argument('--variant', default='v4',
                     choices=['v0_floor', 'v1', 'v2', 'v4'])
    ap.add_argument('--max-new', type=int, default=1500)
    ap.add_argument('--run-id', default=None)
    args = ap.parse_args()

    iids = list_tasks()
    if not iids:
        print('FAIL: no task inventory found'); return 2
    if args.limit and args.limit > 0:
        iids = iids[:args.limit]

    run_id = args.run_id or f'dbt_v8_{args.variant}_lim{args.limit}_{int(time.time())}'
    out_dir = REPO / 'outputs' / 'spider2_dbt' / 'runs_v8' / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f'TASKS: {len(iids)} variant={args.variant} run_id={run_id}')

    from spider2_dbt_agent_v8 import run_dbt_v8
    from spider2_dbt_evaluator_v8 import task_success

    pred_path = out_dir / 'predictions.jsonl'
    metrics = Counter()
    err_tax = Counter()
    src_break = Counter()  # apply_kind breakdown
    cost_rows: list[dict] = []
    successes: list[str] = []

    for i, iid in enumerate(iids, 1):
        print(f'[{i}/{len(iids)}] {iid} variant={args.variant} ...', flush=True)
        t0 = time.time()
        try:
            res = run_dbt_v8(iid, variant=args.variant, max_new=args.max_new)
        except Exception as exc:
            res = {'instance_id': iid, 'variant': args.variant,
                    'status': 'agent_exception',
                    'error': f'{type(exc).__name__}: {exc}'[:300],
                    'wall_time_s': round(time.time() - t0, 2)}

        # Aggregate
        metrics['n'] += 1
        if res.get('status') == 'done':
            metrics['done'] += 1
            if res.get('dbt_deps_rc') == 0: metrics['dbt_deps_ok'] += 1
            if res.get('dbt_run_rc') == 0: metrics['dbt_run_ok'] += 1
            if res.get('dbt_test_rc') == 0: metrics['dbt_test_ok'] += 1
            if task_success(res.get('official_score')):
                metrics['task_success'] += 1
                successes.append(iid)
        err_tax[res.get('status', 'unknown')] += 1
        src_break[res.get('apply_kind', 'none')] += 1

        with pred_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(res, ensure_ascii=False) + '\n')

        cost_rows.append({'instance_id': iid,
                            'wall_time_s': res.get('wall_time_s', 0),
                            'status': res.get('status', '?')})
        print(f'  status={res.get("status")} '
              f'dbt_run_rc={res.get("dbt_run_rc")} '
              f'score={(res.get("official_score") or {}).get("matched","-")}/'
              f'{(res.get("official_score") or {}).get("total","-")} '
              f'wall={res.get("wall_time_s")}s')

    # Write metrics CSV
    with (out_dir / 'metrics.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['metric', 'value'])
        for k in ('n', 'done', 'dbt_deps_ok', 'dbt_run_ok', 'dbt_test_ok',
                    'task_success'):
            w.writerow([k, metrics[k]])

    with (out_dir / 'error_taxonomy.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['status', 'count'])
        for k, v in err_tax.most_common(): w.writerow([k, v])

    with (out_dir / 'source_breakdown.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['apply_kind', 'count'])
        for k, v in src_break.most_common(): w.writerow([k, v])

    with (out_dir / 'cost_runtime.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['instance_id', 'wall_time_s', 'status'])
        w.writeheader()
        for r in cost_rows: w.writerow(r)

    n = max(1, metrics['n'])
    md = [
        f'# Spider2-DBT v8 — run `{run_id}`', '',
        f'_Generated: {now()} | variant: `{args.variant}` | '
        f'tasks: {metrics["n"]}_',
        '',
        '## Aggregate metrics',
        '',
        '| metric | value | rate |',
        '|---|---:|---:|',
        f"| n | {metrics['n']} | — |",
        f"| done | {metrics['done']} | {(metrics['done']/n)*100:.1f}% |",
        f"| dbt_deps_ok | {metrics['dbt_deps_ok']} | {(metrics['dbt_deps_ok']/n)*100:.1f}% |",
        f"| dbt_run_ok | {metrics['dbt_run_ok']} | {(metrics['dbt_run_ok']/n)*100:.1f}% |",
        f"| dbt_test_ok | {metrics['dbt_test_ok']} | {(metrics['dbt_test_ok']/n)*100:.1f}% |",
        f"| task_success (matched>0) | {metrics['task_success']} | "
        f"**{(metrics['task_success']/n)*100:.1f}%** |",
        '',
        f'## Successes',
        '',
        ', '.join(f'`{s}`' for s in successes) if successes else '_(none)_',
        '',
        '## Error taxonomy',
        '',
        '| status | count |',
        '|---|---:|',
    ]
    for k, v in err_tax.most_common():
        md.append(f'| `{k}` | {v} |')
    (out_dir / 'readout.md').write_text('\n'.join(md), encoding='utf-8')

    canon = REPO / 'outputs' / 'predictions'
    canon.mkdir(parents=True, exist_ok=True)
    (canon / f'spider2_dbt_agent_v8_{run_id}_predictions.jsonl').write_text(
        pred_path.read_text(encoding='utf-8'), encoding='utf-8')

    print(f'\nDONE. {out_dir.relative_to(REPO).as_posix()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
