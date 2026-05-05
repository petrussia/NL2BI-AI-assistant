"""run_remote_evaluation.py — execute dbt run + dbt test inside the per-task
workspace on the server. NEVER touches the upstream example dir.

Output (written on the server, fetched by collect_remote_result.py):
  outputs/colab_bridge/tasks/<TASK_ID>/logs/dbt_deps.log
  outputs/colab_bridge/tasks/<TASK_ID>/logs/dbt_run.log
  outputs/colab_bridge/tasks/<TASK_ID>/logs/dbt_test.log
  outputs/colab_bridge/tasks/<TASK_ID>/logs/timing.json
  outputs/colab_bridge/tasks/<TASK_ID>/result.json (status summary)
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from ssh_utils import (
    load_config, ssh_run, ensure_remote_dir, task_workspace_path,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--config', default=None)
    ap.add_argument('--skip-deps', action='store_true',
                     help='Skip `dbt deps` step.')
    ap.add_argument('--skip-test', action='store_true',
                     help='Skip `dbt test` step (run only `dbt run`).')
    args = ap.parse_args()
    cfg = load_config(args.config)
    iid = args.task_id

    ws = f'{task_workspace_path(cfg, iid)}/workspace'
    logs = f'{task_workspace_path(cfg, iid)}/logs'
    res_path = f'{task_workspace_path(cfg, iid)}/result.json'

    # 0. Sanity: workspace must be initialized
    r = ssh_run(cfg, f'test -f {shlex.quote(ws)}/dbt_project.yml && echo OK', timeout=10)
    if 'OK' not in r.stdout:
        print(f'FAIL: workspace dbt_project.yml missing at {ws}. '
              f'Run apply_model_output.py first.')
        return 2

    ensure_remote_dir(cfg, logs)

    activate = 'source /home/denis/dbt/.venv/bin/activate'
    run_dbt_deps = (cfg.run_dbt_deps and not args.skip_deps)

    cmd_pieces = [
        f'{activate}',
        f'cd {shlex.quote(ws)}',
        # Use task workspace as profiles dir (profiles.yml lives there)
        f'export DBT_PROFILES_DIR={shlex.quote(ws)}',
    ]
    inner = []
    if run_dbt_deps:
        inner.append(f'dbt deps 2>&1 | tee {shlex.quote(logs)}/dbt_deps.log')
    inner.append(f'timeout {cfg.dbt_timeout_s} dbt run 2>&1 '
                  f'| tee {shlex.quote(logs)}/dbt_run.log; '
                  f'echo "DBT_RUN_RC=${{PIPESTATUS[0]}}" >> {shlex.quote(logs)}/dbt_run.log')
    if not args.skip_test:
        inner.append(f'timeout {cfg.dbt_timeout_s} dbt test 2>&1 '
                      f'| tee {shlex.quote(logs)}/dbt_test.log; '
                      f'echo "DBT_TEST_RC=${{PIPESTATUS[0]}}" >> {shlex.quote(logs)}/dbt_test.log')
    cmd_pieces.append(' && '.join(inner))
    full_cmd = ' && '.join(cmd_pieces)

    print(f'RUNNING (workspace={ws}, deps={run_dbt_deps}, test={not args.skip_test})')
    r = ssh_run(cfg, f'bash -lc {shlex.quote(full_cmd)}',
                  timeout=cfg.dbt_timeout_s + 60)
    print(f'rc={r.returncode}')
    print(f'stdout tail:\n{r.stdout[-1500:]}')
    if r.stderr:
        print(f'stderr tail:\n{r.stderr[-800:]}')

    # Parse return codes from log tails
    def _grep_rc(path: str, key: str) -> int | None:
        cmd = f'grep -h {shlex.quote(key)} {shlex.quote(path)} 2>/dev/null | tail -1'
        rr = ssh_run(cfg, cmd, timeout=10)
        for ln in rr.stdout.splitlines():
            if key in ln:
                try: return int(ln.split('=')[1].strip())
                except Exception: return None
        return None

    run_rc = _grep_rc(f'{logs}/dbt_run.log', 'DBT_RUN_RC')
    test_rc = _grep_rc(f'{logs}/dbt_test.log', 'DBT_TEST_RC') if not args.skip_test else None
    target_dir = f'{ws}/target'
    has_run_results = ssh_run(cfg, f'test -f {shlex.quote(target_dir)}/run_results.json && echo OK',
                                 timeout=5).stdout.strip() == 'OK'

    summary = {
        'task_id': iid,
        'workspace': ws,
        'logs_dir': logs,
        'dbt_deps_skipped': not run_dbt_deps,
        'dbt_test_skipped': bool(args.skip_test),
        'dbt_run_rc': run_rc,
        'dbt_test_rc': test_rc,
        'has_run_results_json': has_run_results,
        'eval_status': 'not_implemented',  # filled by future evaluator integration
        'overall_ok': (run_rc == 0) and (test_rc in (0, None)),
    }
    write_summary_cmd = (f'echo {shlex.quote(json.dumps(summary, indent=2))} '
                          f'> {shlex.quote(res_path)}')
    ssh_run(cfg, write_summary_cmd, timeout=10)
    print(f'WROTE remote {res_path}: {summary}')
    return 0 if summary['overall_ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
