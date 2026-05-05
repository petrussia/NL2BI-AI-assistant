"""run_one_task_pipeline.py — orchestrator for a single Spider2-DBT task.

Modes:
  manual          — export → prompt → wait for human/Colab to drop
                     `data/spider2_dbt/tasks/<TASK_ID>/model_response.txt`,
                     then continue with apply → eval → collect.
  local_function  — call a Python callable (passed via --inference-fn) that
                     receives the prompt string and returns the model response.
  hf_local        — load a HF model locally to do inference (placeholder; not
                     wired here — keep `manual` for now).
  colab_file      — alias for `manual`; the human/Colab drops the file.

Usage:
  python spider2_dbt_bridge/run_one_task_pipeline.py --task-id asana001 --mode manual
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from ssh_utils import load_config, local_task_path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / 'spider2_dbt_bridge'


def _run(cmd: list[str], *, timeout: int = 300) -> int:
    print(f'\n$ {" ".join(cmd)}')
    p = subprocess.run(cmd, timeout=timeout)
    return p.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--config', default=None)
    ap.add_argument('--mode', default='manual',
                     choices=['manual', 'colab_file', 'local_function', 'hf_local'])
    ap.add_argument('--wait-seconds', type=int, default=300,
                     help='Manual mode: how long to poll for model_response.txt.')
    ap.add_argument('--skip-eval', action='store_true',
                     help='Stop after apply (no dbt run/test).')
    args = ap.parse_args()
    cfg = load_config(args.config)
    iid = args.task_id

    py = sys.executable
    base = [py]
    here = str(SCRIPTS) + '/'

    # 1. Export task context
    rc = _run(base + [here + 'export_task_context.py', '--task-id', iid])
    if rc != 0: return rc

    # 2. Build prompt
    rc = _run(base + [here + 'build_model_prompt.py', '--task-id', iid])
    if rc != 0: return rc

    response_path = local_task_path(cfg, iid) / 'model_response.txt'
    print(f'\nMODE: {args.mode}')
    print(f'Drop the model output at: {response_path}')

    if args.mode in ('manual', 'colab_file'):
        # Poll for the file (so the human/Colab has time to act)
        deadline = time.time() + args.wait_seconds
        while time.time() < deadline:
            if response_path.exists():
                size = response_path.stat().st_size
                if size > 10:
                    print(f'  detected: size={size}; continuing.')
                    break
            time.sleep(2)
        else:
            print('  timed out waiting for model_response.txt — exiting.')
            return 4
    elif args.mode == 'local_function':
        print('  local_function mode is not wired here — supply --inference-fn.')
        return 5
    elif args.mode == 'hf_local':
        print('  hf_local mode is a placeholder — drop a file manually for now.')
        return 5

    # 3. Apply model output
    rc = _run(base + [here + 'apply_model_output.py', '--task-id', iid])
    if rc != 0: return rc
    if args.skip_eval:
        print('SKIPPED EVAL (per --skip-eval). Workspace ready on server.')
        return 0

    # 4. Run remote evaluation
    rc = _run(base + [here + 'run_remote_evaluation.py', '--task-id', iid])
    eval_rc = rc

    # 5. Collect result (always, even if eval failed — to capture logs)
    _run(base + [here + 'collect_remote_result.py', '--task-id', iid])

    return eval_rc


if __name__ == '__main__':
    sys.exit(main())
