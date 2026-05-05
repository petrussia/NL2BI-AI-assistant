#!/usr/bin/env python3
"""server_list_tasks.py — list Spider2-DBT tasks on stdout as JSON."""
import json
import os
import sys
from pathlib import Path

ROOT = Path('/home/denis/dbt/vendor/Spider2/spider2-dbt')
JSONL = ROOT / 'examples' / 'spider2-dbt.jsonl'
EX = ROOT / 'examples'


def main() -> int:
    if not JSONL.exists():
        print(json.dumps({'error': f'{JSONL} not found'}))
        return 2
    out = []
    for ln in JSONL.read_text(encoding='utf-8').splitlines():
        ln = ln.strip()
        if not ln: continue
        try:
            it = json.loads(ln)
        except Exception:
            continue
        iid = it.get('instance_id', '')
        out.append({
            'instance_id': iid,
            'instruction': it.get('instruction', ''),
            'type': it.get('type', ''),
            'has_example_dir': (EX / iid).is_dir(),
        })
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
