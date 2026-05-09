"""run_spider2_lite_sf_agent.py — readiness-gated runner for Spider2-Lite
A_sf lane.

Defaults to manual inference mode (model_response.txt drop). Will only
issue Snowflake queries if `spider2_sf_readiness_v8.check_readiness()`
returns `can_execute_real_sql=True` for the selected items' databases.

Output (per --run-id):
    outputs/snowflake/runs/<RUN_ID>/
        predictions.jsonl
        execution_results.jsonl
        metrics.json
        run_metadata.json
        errors_top.md
        readout.md

Usage:
    python snowflake_setup/run_spider2_lite_sf_agent.py \
        --benchmark spider2-lite --engine snowflake \
        --limit 1 --inference manual --execute false

The default is `--execute false` so the pipeline NEVER hits Snowflake
unless you explicitly opt in. With `--execute true`, the readiness gate
is consulted; if any required db is missing, the runner refuses to
execute and writes blocked records.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'repo' / 'src' / 'evaluation'))


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _select(jsonl_path: Path, *, limit: int) -> list[dict]:
    out: list[dict] = []
    for ln in jsonl_path.open(encoding='utf-8'):
        try:
            it = json.loads(ln)
        except Exception: continue
        iid = str(it.get('instance_id') or '').lower()
        if iid.startswith('sf'):
            out.append(it)
            if len(out) >= limit: break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--benchmark', default='spider2-lite',
                     choices=['spider2-lite'])
    ap.add_argument('--engine', default='snowflake', choices=['snowflake'])
    ap.add_argument('--limit', type=int, default=1,
                     help='1 / 3 / 10 — never run full without confirmation.')
    ap.add_argument('--run-id', default=None, help='Default: derived timestamp.')
    ap.add_argument('--inference', default='manual',
                     choices=['manual', 'none'],
                     help='manual = wait for model_response.txt files; '
                          'none = skip generation, only readiness + selection.')
    ap.add_argument('--execute', default='false', choices=['false', 'true'],
                     help='Whether to actually run generated SQL on SF. '
                          'Default false; even when true, the readiness gate '
                          'must pass.')
    ap.add_argument('--dataset-path', default=None,
                     help='Override path to spider2-lite.jsonl.')
    ap.add_argument('--max-bytes-confirm', action='store_true',
                     help='Confirm you accept SF credit usage.')
    args = ap.parse_args()

    # 1. Locate dataset
    dataset = (Path(args.dataset_path).expanduser() if args.dataset_path
                 else REPO / 'external_benchmarks' / 'spider2_lite' / 'raw' /
                       'Spider2' / 'spider2-lite' / 'spider2-lite.jsonl')
    if not dataset.exists():
        print(f'FAIL: dataset not found: {dataset}'); return 2
    print(f'DATASET: {dataset}')

    items = _select(dataset, limit=args.limit)
    print(f'SELECTED: {len(items)} SF items (limit={args.limit})')
    if not items:
        print('No SF items found — exiting.'); return 0

    # 2. Build run_id + outputs dir
    run_id = args.run_id or f'sf_limit{args.limit}_{int(time.time())}'
    out_dir = REPO / 'outputs' / 'snowflake' / 'runs' / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f'RUN_ID: {run_id}  OUT: {out_dir}')

    # 3. Readiness check
    required_dbs = sorted({str(it.get('db') or '') for it in items if it.get('db')})
    print(f'\nREQUIRED DBS for this slice: {required_dbs}')
    from spider2_sf_readiness_v8 import check_readiness
    rd = check_readiness(required_dbs)
    print(f'READINESS: connection_ok={rd.connection_ok} role_ok={rd.role_ok} '
          f'warehouse_ok={rd.warehouse_ok} can_execute_real_sql={rd.can_execute_real_sql}')
    if rd.missing_databases:
        print(f'  missing dbs: {rd.missing_databases[:10]}')
    if rd.error:
        print(f'  error: {rd.error}')

    # Save readiness snapshot for this run
    (out_dir / 'readiness.json').write_text(
        json.dumps(rd.to_dict(), indent=2, ensure_ascii=False), encoding='utf-8')

    # 4. Decide path
    will_execute = (args.execute == 'true' and rd.can_execute_real_sql)
    if args.execute == 'true' and not rd.can_execute_real_sql:
        print('\n*** EXECUTE refused: readiness gate failed. Writing blocked '
              'records instead. See readiness.json + spider2_sf_self_host_plan.md ***')
    elif args.execute == 'false':
        print('\n--execute false (default). No Snowflake queries will run; '
              'this is selection + readiness only.')

    # 5. Build prediction skeleton (one row per item)
    pred_path = out_dir / 'predictions.jsonl'
    blocked_n = 0
    written = 0
    with pred_path.open('w', encoding='utf-8') as f:
        for it in items:
            iid = it.get('instance_id', '')
            db = it.get('db', '')
            base = {
                'instance_id': iid, 'db': db, 'lane': 'A_sf',
                'benchmark': args.benchmark, 'engine': args.engine,
                'question': it.get('question', ''),
                'external_knowledge': it.get('external_knowledge', ''),
                'run_id': run_id, 'utc': utcnow(),
            }
            if not will_execute:
                row = {**base,
                        'mode': 'blocked_missing_snowflake_database'
                                  if rd.missing_databases else 'execute_disabled',
                        'blocked_reason': rd.reason or 'execute=false',
                        'generated_sql': '', 'executable': False,
                        'execution_match': None,
                        'error_type': 'blocked', 'error_message': '',
                        'final_source': '', 'parses': False,
                }
                blocked_n += 1
            else:
                # Real execution path is reserved for the next step (when shares
                # are attached). The agent module is already wired; the runner
                # would call run_sf_agent_step here. For the gated default we
                # write a "ready_but_no_inference" record.
                if args.inference == 'none':
                    row = {**base, 'mode': 'ready_no_inference',
                            'generated_sql': '', 'executable': None,
                            'execution_match': None,
                            'error_type': '', 'error_message': '',
                            'final_source': '', 'parses': None,
                    }
                else:
                    row = {**base, 'mode': 'manual_pending_response',
                            'generated_sql': '',
                            'executable': None, 'execution_match': None,
                            'error_type': '', 'error_message': '',
                            'final_source': '', 'parses': None,
                            'note': ('Drop a model_response.txt for this iid '
                                     'and re-invoke with the agent path.'),
                    }
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
            written += 1
    print(f'WROTE {pred_path} rows={written} blocked={blocked_n}')

    # 6. Run metadata + readout
    metadata = {
        'run_id': run_id, 'utc': utcnow(),
        'benchmark': args.benchmark, 'engine': args.engine,
        'limit': args.limit, 'inference': args.inference,
        'execute_flag': args.execute,
        'will_execute': will_execute,
        'readiness_can_execute_real_sql': rd.can_execute_real_sql,
        'readiness_missing_dbs_n': len(rd.missing_databases),
        'readiness_reason': rd.reason,
        'required_dbs': required_dbs,
        'visible_dbs_count': len(rd.visible_databases),
        'self_host_eligible': rd.self_host_eligible,
        'cloud': rd.cloud, 'region': rd.region,
        'predictions_path': str(pred_path),
        'rows_written': written, 'rows_blocked': blocked_n,
    }
    (out_dir / 'run_metadata.json').write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding='utf-8')

    metrics = {
        'n_total': written, 'n_blocked': blocked_n,
        'n_executed_ok': 0, 'n_em': 0,
        'note': ('No queries issued: '
                  + ('readiness blocked' if rd.missing_databases
                     else ('--execute false' if args.execute == 'false'
                            else 'inference=none'))),
    }
    (out_dir / 'metrics.json').write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding='utf-8')

    readout = [
        f'# Run {run_id}', '',
        f'_Generated: {utcnow()}_', '',
        f'- benchmark: `{args.benchmark}`',
        f'- engine: `{args.engine}`',
        f'- limit: {args.limit}',
        f'- inference: `{args.inference}`',
        f'- execute flag: `{args.execute}`',
        f'- will_execute: **{will_execute}**',
        '',
        '## Readiness',
        '',
        f'- connection_ok: {rd.connection_ok}',
        f'- role_ok: {rd.role_ok}',
        f'- warehouse_ok: {rd.warehouse_ok}',
        f'- can_execute_real_sql: **{rd.can_execute_real_sql}**',
        f'- reason: `{rd.reason}`',
        f'- visible dbs: {len(rd.visible_databases)}; required: '
        f'{len(required_dbs)}; missing: {len(rd.missing_databases)}',
        f'- self_host_eligible: {rd.self_host_eligible} (cloud={rd.cloud} '
        f'region={rd.region})',
        '',
        '## Selected items',
        '',
        '| instance_id | db | mode |',
        '|---|---|---|',
    ]
    for r in [json.loads(l) for l in pred_path.open(encoding='utf-8')]:
        readout.append(f'| `{r["instance_id"]}` | `{r["db"]}` | {r["mode"]} |')
    readout += ['',
                 '## Next step',
                 ('Real Spider2-Lite SF execution requires the missing databases. '
                  'See `outputs/logs/spider2_sf_self_host_plan.md` for the '
                  'Marketplace-share / self-host plan. Until then this runner '
                  'records `blocked_missing_snowflake_database` per item.'
                  if rd.missing_databases else
                  'Add `--execute true` once you have model output to run real '
                  'queries; the readiness gate will let you through.'),
                 '']
    (out_dir / 'readout.md').write_text('\n'.join(readout), encoding='utf-8')

    # errors_top.md placeholder
    (out_dir / 'errors_top.md').write_text(
        '# Top errors\n\n_No queries issued in this run._\n', encoding='utf-8')

    print(f'\nALL artifacts in: {out_dir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
