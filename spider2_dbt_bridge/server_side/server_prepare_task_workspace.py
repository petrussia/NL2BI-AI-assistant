#!/usr/bin/env python3
"""server_prepare_task_workspace.py — rsync the upstream example dir into
the task's workspace under outputs/colab_bridge/tasks/<TASK_ID>/workspace/.
Idempotent: refuses to clobber an active workspace.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

EXAMPLES = Path('/home/denis/dbt/vendor/Spider2/spider2-dbt/examples')
WORKSPACE_ROOT = Path('/home/denis/dbt/outputs/colab_bridge/tasks')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--force', action='store_true',
                     help='Reset workspace even if it has .duckdb_wal files.')
    args = ap.parse_args()
    iid = args.task_id

    src = EXAMPLES / iid
    if not src.is_dir():
        print(f'FAIL: example dir missing: {src}')
        return 2

    dst = WORKSPACE_ROOT / iid / 'workspace'
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Refuse to clobber an active workspace
    if dst.exists() and not args.force:
        wal = list(dst.rglob('*.duckdb_wal'))
        if wal:
            print(f'BUSY: workspace has active dbt-duckdb WAL files; '
                  f'refusing to clobber. Pass --force to override.')
            return 3
        # If workspace already has dbt_project.yml, treat as "already prepared"
        if (dst / 'dbt_project.yml').exists():
            print(f'OK already_prepared: {dst}')
            return 0

    # Use `cp -R` (rsync may be absent on minimal servers). Refresh by
    # removing dst first when force/initial.
    if dst.exists():
        shutil.rmtree(dst)
    res = subprocess.run(['cp', '-R', str(src), str(dst)],
                           capture_output=True, text=True)
    if res.returncode != 0:
        print(f'FAIL cp -R: {res.stderr[:300]}')
        return 4
    # Drop heavy/state dirs that should never be in a workspace.
    for sub in ('dbt_packages', 'target', 'logs'):
        p = dst / sub
        if p.exists(): shutil.rmtree(p, ignore_errors=True)
    print(f'OK prepared: {dst}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
