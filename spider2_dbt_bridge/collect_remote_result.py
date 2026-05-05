"""collect_remote_result.py — pull result.json + logs + dbt artifacts from
the per-task workspace into data/spider2_dbt/tasks/<TASK_ID>/result/.
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
import tarfile
from pathlib import Path

from ssh_utils import (
    load_config, ssh_run, scp_from_remote, task_workspace_path, local_task_path,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--config', default=None)
    args = ap.parse_args()
    cfg = load_config(args.config)
    iid = args.task_id

    remote_root = task_workspace_path(cfg, iid)
    out_dir = local_task_path(cfg, iid) / 'result'
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. result.json
    cp = scp_from_remote(cfg, f'{remote_root}/result.json',
                            out_dir / 'result.json')
    if cp.returncode == 0:
        print(f'  WROTE {out_dir / "result.json"}')
    else:
        print(f'WARN: result.json not present on server: {cp.stderr[:200]}')

    # 2. Logs
    logs_local = out_dir / 'logs'
    logs_local.mkdir(exist_ok=True)
    for f in ('dbt_deps.log', 'dbt_run.log', 'dbt_test.log'):
        cp = scp_from_remote(cfg, f'{remote_root}/logs/{f}', logs_local / f)
        if cp.returncode == 0:
            print(f'  WROTE {logs_local / f}')

    # 3. dbt target/run_results.json + manifest.json (small JSON, not the big artifacts)
    target_local = out_dir / 'target'
    target_local.mkdir(exist_ok=True)
    for f in ('run_results.json', 'manifest.json', 'sources.json'):
        cp = scp_from_remote(cfg,
                              f'{remote_root}/workspace/target/{f}',
                              target_local / f)
        if cp.returncode == 0:
            print(f'  WROTE {target_local / f}')

    # 4. Tar of the workspace (excluding bulky stuff) for full audit
    snap_remote = f'{remote_root}/workspace_snapshot.tgz'
    tar_cmd = (f'cd {shlex.quote(remote_root)} && '
                 f'tar -czf {shlex.quote(snap_remote)} '
                 f'   --exclude=workspace/dbt_packages --exclude=workspace/target '
                 f'   --exclude="*.duckdb_wal" '
                 f'   workspace 2>/dev/null || true')
    ssh_run(cfg, tar_cmd, timeout=60)
    cp = scp_from_remote(cfg, snap_remote, out_dir / 'workspace_snapshot.tgz')
    if cp.returncode == 0:
        print(f'  WROTE {out_dir / "workspace_snapshot.tgz"}')

    # 5. Compose a local summary
    summary_path = out_dir / 'summary.json'
    res = {}
    if (out_dir / 'result.json').exists():
        try:
            res = json.loads((out_dir / 'result.json').read_text(encoding='utf-8'))
        except Exception:
            res = {'parse_fail': True}
    summary = {
        'task_id': iid,
        'remote_root': remote_root,
        'local_dir': str(out_dir),
        'has_result_json': (out_dir / 'result.json').exists(),
        'has_run_results_json': (target_local / 'run_results.json').exists(),
        'dbt_run_rc': res.get('dbt_run_rc'),
        'dbt_test_rc': res.get('dbt_test_rc'),
        'overall_ok': res.get('overall_ok'),
        'eval_status': res.get('eval_status', 'not_implemented'),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                              encoding='utf-8')
    print(f'WROTE: {summary_path}')
    return 0 if summary.get('overall_ok') else 1


if __name__ == '__main__':
    sys.exit(main())
