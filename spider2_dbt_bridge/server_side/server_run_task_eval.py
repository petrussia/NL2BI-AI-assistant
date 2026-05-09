#!/usr/bin/env python3
"""server_run_task_eval.py — run dbt deps + dbt run + dbt test in the
task's workspace. Stand-alone helper for manual debugging on the server.
The local-side `run_remote_evaluation.py` does the same over SSH.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

WORKSPACE_ROOT = Path('/home/denis/dbt/outputs/colab_bridge/tasks')
VENV_PY = '/home/denis/dbt/.venv/bin/python'
VENV_BIN = '/home/denis/dbt/.venv/bin'


def _run(cmd, cwd, log_path: Path, timeout: int) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('w', encoding='utf-8') as f:
        try:
            res = subprocess.run(cmd, cwd=str(cwd),
                                   stdout=f, stderr=subprocess.STDOUT,
                                   timeout=timeout, env={**os.environ,
                                                            'PATH': f'{VENV_BIN}:{os.environ.get("PATH","")}',
                                                            'DBT_PROFILES_DIR': str(cwd)})
            return res.returncode
        except subprocess.TimeoutExpired:
            f.write(f'\nTIMEOUT after {timeout}s\n')
            return 124


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--skip-deps', action='store_true')
    ap.add_argument('--skip-test', action='store_true')
    ap.add_argument('--timeout', type=int, default=300)
    args = ap.parse_args()
    iid = args.task_id
    ws = WORKSPACE_ROOT / iid / 'workspace'
    if not (ws / 'dbt_project.yml').exists():
        print(f'FAIL: {ws}/dbt_project.yml missing. Prepare workspace first.')
        return 2
    logs = WORKSPACE_ROOT / iid / 'logs'
    logs.mkdir(parents=True, exist_ok=True)

    deps_rc = run_rc = test_rc = None
    t0 = time.time()
    if not args.skip_deps:
        deps_rc = _run(['dbt', 'deps'], ws, logs / 'dbt_deps.log', args.timeout)
    run_rc = _run(['dbt', 'run'], ws, logs / 'dbt_run.log', args.timeout)
    if not args.skip_test:
        test_rc = _run(['dbt', 'test'], ws, logs / 'dbt_test.log', args.timeout)
    elapsed = time.time() - t0

    summary = {
        'task_id': iid,
        'workspace': str(ws),
        'logs_dir': str(logs),
        'dbt_deps_rc': deps_rc,
        'dbt_run_rc': run_rc,
        'dbt_test_rc': test_rc,
        'elapsed_s': round(elapsed, 1),
        'has_run_results_json': (ws / 'target' / 'run_results.json').exists(),
        'eval_status': 'not_implemented',
        'overall_ok': (run_rc == 0) and (test_rc in (0, None)),
    }
    out = WORKSPACE_ROOT / iid / 'result.json'
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                     encoding='utf-8')
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary['overall_ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
