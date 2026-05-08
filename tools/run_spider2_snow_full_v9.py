"""run_spider2_snow_full_v9.py — Spider2-Snow CANONICAL 547 runner (v9 agent).

Differences from v8:
  - Uses CANONICAL Spider2-Snow dataset (xlang-ai/Spider2 spider2-snow.jsonl,
    547 rows). Field schema is `instance_id / instruction / db_id /
    external_knowledge` — NOT the Spider2-Lite `db / question` schema.
    The runner adapts on read.
  - Uses `spider2_snow_agent_v9.run_snow_agent_step_v9` which applies
    the dialect normalizer (backticks → unquoted, SAFE_CAST → TRY_CAST,
    UNNEST → LATERAL FLATTEN, DATE_DIFF arg-order, REGEXP_CONTAINS
    → REGEXP_LIKE, sqlglot transpile fallback) before SF EXPLAIN.
  - Per-candidate audit logs `original_sql` + `final_sql` +
    `applied_fixes`, so dialect-fix impact is quantifiable.

Usage:
  python tools/run_spider2_snow_full_v9.py --limit 10            # pilot
  python tools/run_spider2_snow_full_v9.py --limit 0             # FULL 547

Outputs:
  outputs/spider2_snow/runs/<RUN_ID>/
      predictions.jsonl, candidates.jsonl, traces.jsonl,
      metrics.csv, error_taxonomy.csv, source_breakdown.csv,
      cost_runtime.csv, dialect_fix_breakdown.csv, readout.md
  outputs/predictions/spider2_snow_agent_v9_<RUN_ID>_predictions.jsonl
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
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


# Reuse bridge LLM from the v8 runner; OVERRIDE schema fetch to use the
# canonical Snow path (resource/databases/<DB>/<SCHEMA>/<TABLE>.json on
# /content extract) — different from Lite's snowflake/<DB>/... layout.
from run_spider2_snow_full_v8 import (  # type: ignore
    bridge_url, bridge_exec, ensure_model, gen_remote,
)


LOCAL_SF_RES = REPO / 'data' / 'spider2_snow' / 'resource' / 'databases'


def ensure_db_schema(db: str, *, max_tables: int = 60) -> Path | None:
    """Pull the canonical Spider2-Snow `resource/databases/<DB>` dir from
    Colab local extract via bridge. Caches at
    `data/spider2_snow/resource/databases/<DB>`. Limits to first
    `max_tables` files per schema to keep prompt + retrieval fast."""
    target = LOCAL_SF_RES / db
    if target.exists() and any(target.glob('**/*.json')):
        return target
    target.mkdir(parents=True, exist_ok=True)

    code = ('import os, base64, json, glob\n'
            f'SRC = "/content/spider2_snow_extract/spider2-snow/resource/databases/{db}"\n'
            f'MAX = {int(max_tables)}\n'
            'if not os.path.isdir(SRC):\n'
            '    print(json.dumps({"ok": False, "error": "no_src", "src": SRC}))\n'
            'else:\n'
            '    files = []\n'
            '    by_sch = {}\n'
            '    for p in glob.glob(SRC + "/**/*.json", recursive=True):\n'
            '        rel = os.path.relpath(p, SRC)\n'
            '        sch = rel.split("/", 1)[0] if "/" in rel else rel.split("\\\\", 1)[0]\n'
            '        by_sch.setdefault(sch, []).append((rel, p))\n'
            '    # take first MAX/len(schemas) per schema to keep prompt small\n'
            '    n_sch = max(1, len(by_sch))\n'
            '    per_sch = max(5, MAX // n_sch)\n'
            '    for sch, lst in by_sch.items():\n'
            '        lst.sort()\n'
            '        for rel, p in lst[:per_sch]:\n'
            '            with open(p, "rb") as f:\n'
            '                files.append([rel, base64.b64encode(f.read()).decode()])\n'
            '    print(json.dumps({"ok": True, "files": files,\n'
            '                       "n_schemas": len(by_sch),\n'
            '                       "per_schema_limit": per_sch}))\n')
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
        # rel may use forward or back slashes from the Colab side; normalize
        rel = rel.replace('\\', '/')
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(base64.b64decode(b64))
    return target


def select_tasks(jsonl_path: Path, *, limit: int) -> list[dict]:
    """Adapter: returns rows in v9-uniform shape:
        {instance_id, db, question, external_knowledge, raw_keys}
    where v8 readers expect `db` and `question`. This handles BOTH
    canonical Snow (`db_id`/`instruction`) and Lite (`db`/`question`).
    """
    rows: list[dict] = []
    for ln in jsonl_path.open(encoding='utf-8'):
        if not ln.strip(): continue
        d = json.loads(ln)
        adapted = {
            'instance_id': d.get('instance_id', ''),
            'db': d.get('db_id') or d.get('db') or '',
            'question': d.get('instruction') or d.get('question') or '',
            'external_knowledge': d.get('external_knowledge', ''),
            'raw_keys': sorted(list(d.keys())),
        }
        rows.append(adapted)
    if limit and limit > 0:
        return rows[:limit]
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dataset', default=str(REPO / 'data' / 'spider2_snow' / 'raw' / 'spider2-snow.jsonl'),
                     help='Canonical Spider2-Snow jsonl. Default: local data/spider2_snow/raw/.')
    ap.add_argument('--limit', type=int, default=10,
                     help='0 = FULL 547')
    ap.add_argument('--no-execute', action='store_true',
                     help='Skip live execute; only EXPLAIN dry_run.')
    ap.add_argument('--max-rows', type=int, default=1000)
    ap.add_argument('--max-repair-rounds', type=int, default=1)
    ap.add_argument('--include-tool-loop', action='store_true')
    ap.add_argument('--run-id', default=None)
    args = ap.parse_args()

    ds = Path(args.dataset)
    if not ds.exists():
        print(f'FAIL: dataset {ds} missing'); return 2

    items = select_tasks(ds, limit=args.limit)
    print(f'TASKS: {len(items)} (limit={args.limit}) dataset={ds.name}')
    if items:
        print(f'sample iid={items[0]["instance_id"]} db={items[0]["db"]} '
              f'raw_keys={items[0]["raw_keys"]}')
    if not items:
        return 0

    run_id = args.run_id or f'snow_v9_lim{args.limit}_{int(time.time())}'
    out_dir = REPO / 'outputs' / 'spider2_snow' / 'runs' / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f'RUN_ID: {run_id}\nOUT: {out_dir.relative_to(REPO).as_posix()}')

    print('\nLoading model on Colab (idempotent)...')
    ensure_model()

    from spider2_sf_executor_v8 import build_sf_executor
    sf_executor = build_sf_executor(query_tag=f'spider2_snow_v9/{run_id}',
                                       timeout_s=120, max_rows=args.max_rows)

    from spider2_snow_agent_v9 import run_snow_agent_step_v9
    from spider2_snow_schema_retrieval_v8 import build_index_from_db_dir

    pred_path = out_dir / 'predictions.jsonl'
    cand_path = out_dir / 'candidates.jsonl'
    trace_path = out_dir / 'traces.jsonl'
    metrics: Counter = Counter()
    err_tax = Counter()
    src_break = Counter()
    fix_break = Counter()
    cost_rows: list[dict] = []
    rep_helpful = rep_unsuccessful = 0
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
            result = run_snow_agent_step_v9(
                question, idx, gen=gen_remote, sf_executor=sf_executor,
                include_tool_loop=args.include_tool_loop,
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
                       'dialect_fix': None, 'repair_record': None}

        metrics['n'] += 1
        if result.get('parses'): metrics['parse_ok'] += 1
        if result.get('executable'): metrics['execute_ok'] += 1
        et = result.get('error_type') or 'none'
        err_tax[et] += 1
        src_break[result.get('final_source') or 'none'] += 1
        for cs in result.get('candidates_summary', []):
            df = cs.get('dialect_fix')
            if df and df.get('applied_fixes'):
                for fix in df['applied_fixes']:
                    fix_break[fix] += 1
        rr = result.get('repair_record')
        if rr:
            if rr.get('success'): rep_helpful += 1
            else: rep_unsuccessful += 1

        pred_row = {
            'instance_id': iid, 'db': db, 'lane': 'A_sf',
            'sql': result['sql'], 'original_sql': result.get('original_sql', ''),
            'final_source': result['final_source'],
            'parses': result['parses'], 'executable': result['executable'],
            'rows_count': result.get('rows_count', 0),
            'error_type': result.get('error_type', ''),
            'error_message': result.get('error_message', ''),
            'dialect_fix_applied': bool(result.get('dialect_fix')),
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
        df_ind = '✓' if result.get('dialect_fix') else '·'
        print(f'  parse={result.get("parses")} exec={result.get("executable")} '
              f'rows={result.get("rows_count",0)} '
              f'err={result.get("error_type","-")} fix={df_ind} '
              f'wall={result.get("wall_time_s")}s')

    # Summary CSVs
    with (out_dir / 'metrics.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['metric', 'value'])
        w.writerow(['n_total', metrics['n']])
        w.writerow(['parse_ok', metrics['parse_ok']])
        w.writerow(['execute_ok', metrics['execute_ok']])
        w.writerow(['repair_helpful', rep_helpful])
        w.writerow(['repair_unsuccessful', rep_unsuccessful])

    with (out_dir / 'error_taxonomy.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['error_type', 'count'])
        for k, v in err_tax.most_common(): w.writerow([k, v])
    with (out_dir / 'source_breakdown.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['final_source', 'count'])
        for k, v in src_break.most_common(): w.writerow([k, v])
    with (out_dir / 'dialect_fix_breakdown.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['fix_name', 'candidate_count'])
        for k, v in fix_break.most_common(): w.writerow([k, v])
    with (out_dir / 'cost_runtime.csv').open('w', newline='', encoding='utf-8') as f:
        if cost_rows:
            w = csv.DictWriter(f, fieldnames=list(cost_rows[0].keys()))
            w.writeheader()
            for r in cost_rows: w.writerow(r)

    n = max(1, metrics['n'])
    md = [
        f'# Spider2-Snow v9 — run `{run_id}`', '',
        f'_Generated: {now()} | dataset: `{ds.relative_to(REPO).as_posix()}` | '
        f'limit: {args.limit} | execute_chosen: {not args.no_execute}_',
        '',
        '## Aggregate metrics (CANONICAL Spider2-Snow 547 dataset)',
        '',
        '| metric | value | rate |',
        '|---|---:|---:|',
        f"| n_total | {metrics['n']} | — |",
        f"| parse_ok | {metrics['parse_ok']} | "
        f"{(metrics['parse_ok']/n)*100:.1f}% |",
        f"| execute_ok | {metrics['execute_ok']} | "
        f"{(metrics['execute_ok']/n)*100:.1f}% |",
        f"| repair_helpful | {rep_helpful} | — |",
        '',
        '## Dialect-fix breakdown',
        '',
        '| fix | applied to N candidates |',
        '|---|---:|',
    ]
    for k, v in fix_break.most_common():
        md.append(f'| `{k}` | {v} |')
    md.append('')
    md.append('## Error taxonomy')
    md.append('')
    md.append('| error_type | count |')
    md.append('|---|---:|')
    for k, v in err_tax.most_common(15):
        md.append(f'| `{k}` | {v} |')
    md.append('')
    md.append('## Source breakdown (chosen candidate)')
    md.append('')
    md.append('| source | count |')
    md.append('|---|---:|')
    for k, v in src_break.most_common():
        md.append(f'| `{k}` | {v} |')
    (out_dir / 'readout.md').write_text('\n'.join(md), encoding='utf-8')

    canon = REPO / 'outputs' / 'predictions'
    canon.mkdir(parents=True, exist_ok=True)
    (canon / f'spider2_snow_agent_v9_{run_id}_predictions.jsonl').write_text(
        pred_path.read_text(encoding='utf-8'), encoding='utf-8')

    print(f'\nDONE. {out_dir.relative_to(REPO).as_posix()}')
    print(f'  parse_ok={metrics["parse_ok"]}/{metrics["n"]} '
          f'execute_ok={metrics["execute_ok"]}/{metrics["n"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
