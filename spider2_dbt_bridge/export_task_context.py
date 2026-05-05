"""export_task_context.py — fetch a single Spider2-DBT task's context from
the server into `data/spider2_dbt/tasks/<TASK_ID>/context/`.

Captures: task instruction, dbt_project.yml, profiles.yml, all model SQL/YAML
files, and a list of `.duckdb` files (with their tables, fetched via a small
remote DuckDB query). Skips secrets/gold paths.
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
import tarfile
from pathlib import Path

from ssh_utils import (
    load_config, ssh_run, scp_from_remote, ensure_remote_dir, local_task_path,
)


def _remote_task_files(cfg, instance_id: str) -> list[str]:
    """Return list of files of interest under the example dir."""
    base = f'{cfg.remote_spider2_dbt}/examples/{instance_id}'
    cmd = (
        f'cd {shlex.quote(base)} && '
        f'find . -maxdepth 4 \\('
        f'   -name dbt_project.yml -o -name profiles.yml -o -name packages.yml '
        f' -o -name "*.sql" -o -name "*.yml" -o -name "*.md" -o -name README* '
        f' -o -name "schema.yml" \\) '
        f' -not -path "./dbt_packages/*" -not -path "./target/*" '
        f' -not -path "./logs/*" 2>/dev/null'
    )
    r = ssh_run(cfg, cmd, timeout=30)
    return [ln.strip().lstrip('./') for ln in r.stdout.splitlines() if ln.strip()]


def _remote_duckdb_tables(cfg, instance_id: str) -> dict[str, list[dict]]:
    """For each .duckdb file in the example dir, list its tables + columns
    via the deployed probe script. Skipped silently if duckdb python is
    not available there.
    """
    base = f'{cfg.remote_spider2_dbt}/examples/{instance_id}'
    probe_path = f'{cfg.remote_bridge_root}/probe_duckdb.py'
    cmd = (f'source /home/denis/dbt/.venv/bin/activate && '
            f'python {shlex.quote(probe_path)} {shlex.quote(base)}')
    r = ssh_run(cfg, cmd, timeout=60)
    try:
        return json.loads(r.stdout.strip() or '{}')
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--config', default=None)
    args = ap.parse_args()
    cfg = load_config(args.config)
    iid = args.task_id

    # 1. Read task record from the jsonl
    jsonl = f'{cfg.remote_spider2_dbt}/examples/spider2-dbt.jsonl'
    cmd = f'grep -F {shlex.quote(json.dumps(iid))} {shlex.quote(jsonl)} | head -1'
    r = ssh_run(cfg, cmd, timeout=20)
    task_rec = None
    if r.returncode == 0 and r.stdout.strip():
        try:
            task_rec = json.loads(r.stdout.strip())
        except Exception:
            pass
    if task_rec is None:
        print(f'FAIL: task_id {iid!r} not found in {jsonl}')
        return 2

    # 2. Confirm example dir exists
    base = f'{cfg.remote_spider2_dbt}/examples/{iid}'
    r = ssh_run(cfg, f'test -d {shlex.quote(base)} && echo OK', timeout=10)
    if 'OK' not in r.stdout:
        print(f'FAIL: example dir missing: {base}')
        return 3

    # 3. Local context dir
    out = local_task_path(cfg, iid) / 'context'
    out.mkdir(parents=True, exist_ok=True)
    print(f'EXPORT  task_id={iid}  ->  {out}')

    # 4. Tar the relevant files (no dbt_packages, no target, no logs, no .duckdb)
    files = _remote_task_files(cfg, iid)
    if not files:
        print('WARN: no source files matched the file filter')
    snapshot_remote = (f'{cfg.remote_workspace_root.rstrip("/")}/{iid}/'
                         f'snapshot.tgz')
    ensure_remote_dir(cfg, f'{cfg.remote_workspace_root.rstrip("/")}/{iid}')
    if files:
        tar_cmd = (f'cd {shlex.quote(base)} && '
                     f'tar -czf {shlex.quote(snapshot_remote)} '
                     f'{" ".join(shlex.quote(f) for f in files)}')
        r = ssh_run(cfg, tar_cmd, timeout=60)
        if r.returncode != 0:
            print(f'WARN: tar failed: {r.stderr[:200]}')
        else:
            local_tar = out / 'snapshot.tgz'
            cp = scp_from_remote(cfg, snapshot_remote, local_tar)
            if cp.returncode == 0 and local_tar.exists():
                print(f'  WROTE {local_tar}')
                # Extract for easy reading
                extr = out / 'task_files'
                extr.mkdir(parents=True, exist_ok=True)
                with tarfile.open(local_tar, 'r:gz') as t:
                    t.extractall(extr)
                print(f'  EXTRACTED -> {extr}')

    # 5. Probe DuckDB tables (small JSON; never the row data)
    duck = _remote_duckdb_tables(cfg, iid)
    if duck:
        (out / 'duckdb_tables.json').write_text(
            json.dumps(duck, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f'  WROTE duckdb_tables.json ({len(duck)} db files)')

    # 6. context.json
    context = {
        'task_id': iid,
        'instance_id': iid,
        'instruction': task_rec.get('instruction', ''),
        'type': task_rec.get('type', ''),
        'remote_example_dir': base,
        'remote_workspace_dir': f'{cfg.remote_workspace_root.rstrip("/")}/{iid}',
        'snapshot_remote': snapshot_remote,
        'files_in_snapshot': files,
        'duckdb_files': sorted(duck.keys()) if duck else [],
        'step_idx': 0,
        'mode': 'single_shot',
        'notes': ('Server holds the dbt project + DuckDB. Bridge does NOT '
                   'transfer .duckdb files (large/binary). The model uses '
                   'duckdb_tables.json as schema knowledge.'),
    }
    (out / 'context.json').write_text(
        json.dumps(context, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'  WROTE context.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
