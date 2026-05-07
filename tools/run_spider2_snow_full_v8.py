"""run_spider2_snow_full_v8.py — Spider2-Snow benchmark runner (v8 agent).

This runner is honest about what it does:

  - Spider2-Snow is the Snowflake-only track.
  - On this Drive copy we only have the SF subset (207) of Spider2-Lite's
    spider2-lite.jsonl. If a separate `spider2-snow.jsonl` (547) becomes
    available locally, point `--dataset` at it.
  - Schema metadata is pulled lazily from Drive via the Colab bridge,
    cached locally at `data/spider2_lite/resource/databases/snowflake/<DB>/`.
  - LLM inference goes through the Colab bridge.
  - Snowflake EXPLAIN dry_run + execution use creds from snowflake_setup/.env.

Outputs land under `outputs/spider2_snow/runs/<RUN_ID>/`:
  predictions.jsonl, candidates.jsonl, traces.jsonl,
  metrics.csv, error_taxonomy.csv, source_breakdown.csv,
  cost_runtime.csv, readout.md.

Usage:
  python tools/run_spider2_snow_full_v8.py --limit 1
  python tools/run_spider2_snow_full_v8.py --limit 3
  python tools/run_spider2_snow_full_v8.py --limit 10
  python tools/run_spider2_snow_full_v8.py --limit 0   # FULL (all sf*)

Use `--no-execute` to dry-run-only (no Snowflake credit usage beyond EXPLAIN).
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

# Force UTF-8 stdout
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


# --- Bridge LLM gen ---------------------------------------------------------

def bridge_url() -> str:
    return (REPO / 'tools' / '.bridge_url').read_text(encoding='utf-8').strip().rstrip('/')


def bridge_exec(code: str, timeout: int = 120) -> dict:
    payload = json.dumps({'code': code}).encode('utf-8')
    req = urllib.request.Request(bridge_url() + '/exec', data=payload,
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


_GEN_BOOTSTRAP = '''
import os, json
if not globals().get("_GEN_READY"):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch
    MODEL_ID = os.environ.get("SPIDER2_GEN_MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct")
    print("LOADING_MODEL=", MODEL_ID, flush=True)
    tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    mdl = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, torch_dtype=torch.bfloat16,
        device_map="auto", trust_remote_code=True)
    mdl.eval()
    globals()["_TOK"] = tok
    globals()["_MDL"] = mdl
    globals()["_GEN_READY"] = True
    print("MODEL_READY", flush=True)
'''


def ensure_model() -> None:
    """Idempotent bootstrap: load model on Colab once."""
    r = bridge_exec(_GEN_BOOTSTRAP, timeout=600)
    print(f'  bridge_exec model_load: ok={r.get("ok")} '
          f'tail={(r.get("stdout") or "")[-200:]}')


def gen_remote(prompt: str, max_new: int = 800) -> str:
    """Sends prompt through bridge, returns generated text."""
    code = (
        'import json\n'
        f'_PROMPT = {json.dumps(prompt)}\n'
        f'_MAX_NEW = {max_new}\n'
        'msgs = [{"role":"user","content":_PROMPT}]\n'
        'enc = _TOK.apply_chat_template(msgs, return_tensors="pt", add_generation_prompt=True, return_dict=True)\n'
        'enc = {k: v.to(_MDL.device) for k, v in enc.items()}\n'
        'import torch\n'
        'with torch.no_grad():\n'
        '    out = _MDL.generate(**enc, max_new_tokens=_MAX_NEW, do_sample=False, pad_token_id=_TOK.eos_token_id)\n'
        'gen = out[0][enc["input_ids"].shape[1]:]\n'
        'txt = _TOK.decode(gen, skip_special_tokens=True)\n'
        'print("===GEN_START===")\n'
        'print(txt)\n'
        'print("===GEN_END===")\n'
    )
    r = bridge_exec(code, timeout=240)
    out = (r.get('stdout') or '')
    if '===GEN_START===' in out and '===GEN_END===' in out:
        return out.split('===GEN_START===\n', 1)[1].split('\n===GEN_END===', 1)[0]
    return ''


# --- Schema fetch (lazy from Drive) ----------------------------------------

LOCAL_SF_RES = REPO / 'data' / 'spider2_lite' / 'resource' / 'databases' / 'snowflake'


def ensure_db_schema(db: str) -> Path | None:
    """Pull `<DB>` schema dir from Drive into local cache. Returns local path."""
    target = LOCAL_SF_RES / db
    if target.exists() and any(target.glob('**/*.json')):
        return target
    target.mkdir(parents=True, exist_ok=True)

    code = ('import os, base64, json, glob\n'
            f'SRC = "/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/snowflake/{db}"\n'
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


# --- Per-task processing ---------------------------------------------------

def select_tasks(jsonl_path: Path, *, limit: int) -> list[dict]:
    rows = [json.loads(l) for l in jsonl_path.open(encoding='utf-8') if l.strip()]
    sf = [r for r in rows if str(r.get('instance_id', '')).lower().startswith('sf')]
    if limit and limit > 0:
        return sf[:limit]
    return sf


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dataset', default=str(REPO / 'data' / 'spider2_lite' / 'raw' / 'spider2-lite.jsonl'))
    ap.add_argument('--limit', type=int, default=1,
                     help='0 = FULL (all sf-prefixed items)')
    ap.add_argument('--no-execute', action='store_true',
                     help='Skip live Snowflake execute; only EXPLAIN dry_run.')
    ap.add_argument('--run-id', default=None)
    ap.add_argument('--max-repair-rounds', type=int, default=1)
    ap.add_argument('--include-tool-loop', action='store_true')
    ap.add_argument('--max-rows', type=int, default=1000)
    args = ap.parse_args()

    ds = Path(args.dataset)
    if not ds.exists():
        print(f'FAIL: dataset {ds} missing'); return 2
    items = select_tasks(ds, limit=args.limit)
    print(f'TASKS: {len(items)} (limit={args.limit})')
    if not items:
        return 0

    run_id = args.run_id or f'snow_v8_lim{args.limit}_{int(time.time())}'
    out_dir = REPO / 'outputs' / 'spider2_snow' / 'runs' / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f'RUN_ID: {run_id}\nOUT: {out_dir}')

    # Bootstrap model on Colab
    print('\nLoading model on Colab (one-time)...')
    ensure_model()

    # Build SF executor
    from spider2_sf_executor_v8 import build_sf_executor
    print('Building SF executor (lazy connect on first call)...')
    sf_executor = build_sf_executor(query_tag=f'spider2_snow_v8/{run_id}',
                                       timeout_s=120, max_rows=args.max_rows)

    from spider2_snow_agent_v8 import run_snow_agent_step
    from spider2_snow_schema_retrieval_v8 import build_index_from_db_dir

    # Iterate
    pred_path = out_dir / 'predictions.jsonl'
    cand_path = out_dir / 'candidates.jsonl'
    trace_path = out_dir / 'traces.jsonl'
    metrics: dict[str, Counter] = defaultdict(Counter)
    err_tax = Counter()
    src_break = Counter()
    rep_helpful = rep_harmful = rep_neutral = 0
    cost_rows: list[dict] = []
    schemas_cache: dict[str, object] = {}

    for i, it in enumerate(items, 1):
        iid = it['instance_id']; db = it['db']
        question = it['question']
        t_task = time.time()
        print(f'\n[{i}/{len(items)}] {iid} db={db} ...', flush=True)

        # Lazy fetch schema
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
        if idx is None or not idx.tables:
            print(f'  SKIP: schema missing for {db}')
            row = {'instance_id': iid, 'db': db, 'lane': 'A_sf',
                    'mode': 'blocked_no_schema',
                    'sql': '', 'final_source': '', 'parses': False,
                    'executable': False, 'error_type': 'schema_missing',
                    'wall_time_s': round(time.time() - t_task, 2)}
            with pred_path.open('a', encoding='utf-8') as f:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
            continue

        try:
            result = run_snow_agent_step(
                question, idx,
                gen=gen_remote, sf_executor=sf_executor,
                include_tool_loop=args.include_tool_loop,
                max_repair_rounds=args.max_repair_rounds,
                execute_chosen_query=not args.no_execute,
                max_rows_exec=args.max_rows,
            )
        except Exception as exc:
            result = {'sql': '', 'final_source': '', 'parses': False,
                       'executable': False, 'error_type': 'agent_exception',
                       'error_message': f'{type(exc).__name__}: {exc}'[:300],
                       'wall_time_s': round(time.time() - t_task, 2),
                       'candidates_summary': [], 'candidate_count': 0}

        # Aggregates
        metrics['totals']['n'] += 1
        if result.get('parses'): metrics['totals']['parse_ok'] += 1
        if result.get('executable'): metrics['totals']['execute_ok'] += 1
        et = result.get('error_type') or 'none'
        err_tax[et] += 1
        src_break[result.get('final_source') or 'none'] += 1
        rr = result.get('repair_record')
        if rr:
            if rr.get('success'): rep_helpful += 1
            elif (result.get('parses') is False): rep_harmful += 0  # neutral if no chosen
            else: rep_neutral += 1

        # Predictions row (slim)
        pred_row = {
            'instance_id': iid, 'db': db, 'lane': 'A_sf',
            'sql': result['sql'], 'final_source': result['final_source'],
            'parses': result['parses'], 'executable': result['executable'],
            'rows_count': result.get('rows_count', 0),
            'error_type': result.get('error_type', ''),
            'error_message': result.get('error_message', ''),
            'wall_time_s': result['wall_time_s'],
            'utc': now(),
        }
        with pred_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(pred_row, ensure_ascii=False) + '\n')

        # Candidates audit
        with cand_path.open('a', encoding='utf-8') as f:
            for cs in result.get('candidates_summary', []):
                f.write(json.dumps({**cs, 'instance_id': iid}, ensure_ascii=False) + '\n')

        # Trace
        with trace_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps({
                'instance_id': iid, 'db': db,
                'repair_record': result.get('repair_record'),
                'selector_audit': result.get('selector_audit'),
                'utc': now(),
            }, ensure_ascii=False) + '\n')

        cost_rows.append({
            'instance_id': iid, 'db': db,
            'wall_time_s': result['wall_time_s'],
            'elapsed_ms_chosen': result.get('elapsed_ms') or 0,
            'candidate_count': result.get('candidate_count', 0),
        })
        print(f'  parse={result.get("parses")} exec={result.get("executable")} '
              f'rows={result.get("rows_count",0)} err={result.get("error_type","-")} '
              f'wall={result.get("wall_time_s")}s')

    # Summary CSVs
    with (out_dir / 'metrics.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['metric', 'value'])
        w.writerow(['n_total', metrics['totals']['n']])
        w.writerow(['parse_ok', metrics['totals']['parse_ok']])
        w.writerow(['execute_ok', metrics['totals']['execute_ok']])
        w.writerow(['repair_helpful', rep_helpful])
        w.writerow(['repair_neutral', rep_neutral])
        w.writerow(['repair_harmful', rep_harmful])

    with (out_dir / 'error_taxonomy.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['error_type', 'count'])
        for k, v in err_tax.most_common(): w.writerow([k, v])

    with (out_dir / 'source_breakdown.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['final_source', 'count'])
        for k, v in src_break.most_common(): w.writerow([k, v])

    with (out_dir / 'cost_runtime.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(cost_rows[0].keys()) if cost_rows
                              else ['instance_id', 'wall_time_s'])
        w.writeheader()
        for r in cost_rows: w.writerow(r)

    # Readout
    md = [
        f'# Spider2-Snow v8 — run `{run_id}`', '',
        f'_Generated: {now()} | dataset: `{ds.relative_to(REPO).as_posix()}` | '
        f'limit: {args.limit} | execute_chosen: {not args.no_execute}_',
        '',
        '## Aggregate metrics',
        '',
        '| metric | value |',
        '|---|---:|',
        f"| n_total | {metrics['totals']['n']} |",
        f"| parse_ok | {metrics['totals']['parse_ok']} "
        f"({100 * metrics['totals']['parse_ok'] / max(1, metrics['totals']['n']):.1f}%) |",
        f"| execute_ok | {metrics['totals']['execute_ok']} "
        f"({100 * metrics['totals']['execute_ok'] / max(1, metrics['totals']['n']):.1f}%) |",
        f"| repair_helpful | {rep_helpful} |",
        f"| repair_neutral | {rep_neutral} |",
        '',
        '## Error taxonomy',
        '',
        '| error_type | count |',
        '|---|---:|',
    ]
    for k, v in err_tax.most_common(15):
        md.append(f'| `{k}` | {v} |')
    md += ['',
            '## Source breakdown (chosen candidate)',
            '',
            '| source | count |',
            '|---|---:|']
    for k, v in src_break.most_common():
        md.append(f'| `{k}` | {v} |')
    md.append('')
    (out_dir / 'readout.md').write_text('\n'.join(md), encoding='utf-8')

    # Manifest at canonical paths
    canon = REPO / 'outputs' / 'predictions'
    canon.mkdir(parents=True, exist_ok=True)
    (canon / f'spider2_snow_agent_v8_{run_id}_predictions.jsonl').write_text(
        pred_path.read_text(encoding='utf-8'), encoding='utf-8')

    print(f'\nDONE. Artifacts under: {out_dir.relative_to(REPO).as_posix()}')
    print(f'  predictions: {pred_path.relative_to(REPO).as_posix()}')
    print(f'  readout: {(out_dir / "readout.md").relative_to(REPO).as_posix()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
