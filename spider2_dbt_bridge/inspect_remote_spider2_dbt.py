"""inspect_remote_spider2_dbt.py — list available task_ids and key paths.

Pulls the spider2-dbt.jsonl, checks example dirs exist for each instance_id,
and writes `reports/spider2_dbt_tasks_index.json` locally.
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from ssh_utils import load_config, ssh_run


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default=None)
    ap.add_argument('--out', default='reports/spider2_dbt_tasks_index.json')
    args = ap.parse_args()
    cfg = load_config(args.config)

    jsonl_path = f'{cfg.remote_spider2_dbt}/examples/spider2-dbt.jsonl'
    cmd = f'cat {shlex.quote(jsonl_path)}'
    res = ssh_run(cfg, cmd, timeout=30)
    if res.returncode != 0:
        print(f'FAIL reading {jsonl_path}: {res.stderr[:300]}')
        return 1

    items: list[dict] = []
    for ln in res.stdout.splitlines():
        ln = ln.strip()
        if not ln: continue
        try:
            items.append(json.loads(ln))
        except Exception:
            continue
    print(f'TASKS read from {jsonl_path}: {len(items)}')

    # Build manifest: which instance_ids have an example dir?
    iids = [it.get('instance_id', '') for it in items]
    iids_quoted = ' '.join(shlex.quote(i) for i in iids if i)
    cmd = (f'cd {shlex.quote(cfg.remote_spider2_dbt)}/examples && '
            f'for d in {iids_quoted}; do '
            f'if [ -d "$d" ]; then echo "OK $d"; else echo "MISSING $d"; fi; '
            f'done')
    res = ssh_run(cfg, cmd, timeout=60)
    status: dict[str, bool] = {}
    for ln in res.stdout.splitlines():
        if ln.startswith('OK '): status[ln[3:].strip()] = True
        elif ln.startswith('MISSING '): status[ln[8:].strip()] = False

    enriched = []
    for it in items:
        iid = it.get('instance_id', '')
        enriched.append({
            'instance_id': iid,
            'instruction': it.get('instruction', ''),
            'type': it.get('type', ''),
            'has_example_dir': bool(status.get(iid)),
        })
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        'remote_jsonl': jsonl_path,
        'remote_examples_root': f'{cfg.remote_spider2_dbt}/examples',
        'n_tasks': len(enriched),
        'n_with_example_dir': sum(1 for e in enriched if e['has_example_dir']),
        'tasks': enriched,
    }, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'WROTE: {out_path}')
    print(f'  n_tasks={len(enriched)} '
          f'with_example_dir={sum(1 for e in enriched if e["has_example_dir"])}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
