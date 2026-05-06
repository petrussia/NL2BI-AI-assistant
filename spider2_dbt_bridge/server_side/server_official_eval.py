#!/usr/bin/env python3
"""server_official_eval.py — run Spider2-DBT official evaluator for a SINGLE
task and emit a structured result.json.

Reads:
  /home/denis/dbt/vendor/Spider2/spider2-dbt/evaluation_suite/gold/spider2_eval.jsonl
  /home/denis/dbt/vendor/Spider2/spider2-dbt/evaluation_suite/gold/<TASK_ID>/...

Builds a temporary `result_dir/` containing:
  results_metadata.jsonl  -> single entry for <TASK_ID>
  <TASK_ID>/<artifacts>   -> copies of the post-dbt-run output (.duckdb, .csv)

Then invokes:
  python evaluate.py --result_dir <tmp> --gold_dir <gold>
captures stdout/stderr/score, and updates the task's result.json.

Defaults are conservative: only one --task-id at a time; refuses to run
on the upstream evaluation_suite without an explicit isolation copy.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

VENDOR = Path('/home/denis/dbt/vendor/Spider2/spider2-dbt')
EVAL_SUITE = VENDOR / 'evaluation_suite'
EVAL_PY = EVAL_SUITE / 'evaluate.py'
GOLD_DIR = EVAL_SUITE / 'gold'
GOLD_JSONL = GOLD_DIR / 'spider2_eval.jsonl'
WORKSPACE_ROOT = Path('/home/denis/dbt/outputs/colab_bridge/tasks')
VENV_BIN = '/home/denis/dbt/.venv/bin'


def _read_gold_entry(task_id: str) -> dict | None:
    if not GOLD_JSONL.exists(): return None
    with GOLD_JSONL.open(encoding='utf-8') as f:
        for ln in f:
            try:
                e = json.loads(ln.strip())
                if e.get('instance_id') == task_id: return e
            except Exception: continue
    return None


def _infer_answer_path(task_id: str, gold_entry: dict, workspace: Path) -> tuple[str, str]:
    """Decide what to copy from the workspace into result_dir.
    Returns (answer_type, answer_or_path) for the results_metadata entry.
    """
    eval_md = gold_entry.get('evaluation') or {}
    evals = eval_md if isinstance(eval_md, list) else [eval_md]
    for em in evals:
        func = em.get('func', '')
        params = em.get('parameters', {}) or {}
        if func == 'duckdb_match':
            gold_path = params.get('gold', '')
            # Copy our workspace's matching .duckdb file
            for cand in [workspace / gold_path, *workspace.glob(gold_path)]:
                if cand.is_file():
                    return ('file', cand.name)
            # Fallback: any .duckdb in the workspace
            ducks = list(workspace.glob('*.duckdb'))
            if ducks:
                return ('file', ducks[0].name)
        elif func in ('table_match', 'tables_match'):
            return ('file', params.get('gold', 'pred.csv'))
        elif func in ('string_match', 'number_match'):
            # Look for `output.txt` or similar
            for n in ('output.txt', 'answer.txt'):
                if (workspace / n).exists(): return ('answer', (workspace / n).read_text()[:1000])
            return ('answer', '')
    return ('file', 'asana.duckdb')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--workspace', default=None,
                     help='Override workspace dir; default '
                          '/home/denis/dbt/outputs/colab_bridge/tasks/<task>/workspace')
    ap.add_argument('--write-result', action='store_true',
                     help='Update tasks/<task>/result.json with eval results.')
    args = ap.parse_args()
    iid = args.task_id

    if not EVAL_PY.exists():
        print(f'FAIL: {EVAL_PY} not found'); return 2

    gold = _read_gold_entry(iid)
    if gold is None:
        print(f'FAIL: no gold entry for {iid}'); return 3

    workspace = Path(args.workspace) if args.workspace \
        else WORKSPACE_ROOT / iid / 'workspace'
    if not workspace.exists():
        print(f'FAIL: workspace missing: {workspace}'); return 4

    answer_type, answer_path = _infer_answer_path(iid, gold, workspace)
    print(f'GOLD entry: {gold}')
    print(f'Inferred answer_type={answer_type} answer_or_path={answer_path}')

    # Build a temp result_dir (not inside vendor/Spider2/)
    with tempfile.TemporaryDirectory(prefix=f'spider2_eval_{iid}_') as tmp:
        rd = Path(tmp)
        # 1. results_metadata.jsonl
        meta_entry = {'instance_id': iid, 'answer_type': answer_type,
                       'answer_or_path': answer_path}
        (rd / 'results_metadata.jsonl').write_text(
            json.dumps(meta_entry, ensure_ascii=False) + '\n', encoding='utf-8')

        # 2. Per-task artifacts
        per = rd / iid; per.mkdir(parents=True, exist_ok=True)
        if answer_type == 'file' and answer_path:
            src = workspace / answer_path
            if src.exists():
                shutil.copy2(src, per / answer_path)
            else:
                # find the .duckdb that exists in workspace
                ducks = list(workspace.glob('*.duckdb'))
                if ducks:
                    shutil.copy2(ducks[0], per / answer_path)

        # 3. Run evaluate.py
        cmd = [f'{VENV_BIN}/python', str(EVAL_PY),
                '--result_dir', str(rd), '--gold_dir', str(GOLD_DIR)]
        env = {**os.environ, 'PATH': f'{VENV_BIN}:{os.environ.get("PATH","")}'}
        t0 = time.time()
        try:
            res = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=180, env=env, cwd=str(EVAL_SUITE))
            stdout, stderr, rc = res.stdout, res.stderr, res.returncode
        except subprocess.TimeoutExpired:
            stdout = ''; stderr = 'TIMEOUT_180s'; rc = 124
        elapsed = time.time() - t0

        # 4. Parse score from stdout — last "X / Y" line is the summary
        score = None
        for ln in (stdout or '').splitlines()[::-1]:
            parts = ln.strip().split()
            # The official evaluator prints "<rate> <num_match> <num_total>"
            if len(parts) == 3:
                try:
                    rate = float(parts[0])
                    matched = int(parts[1])
                    total = int(parts[2])
                    score = {'rate': rate, 'matched': matched, 'total': total}
                    break
                except ValueError: continue

    summary = {
        'task_id': iid,
        'eval_command': ' '.join(cmd),
        'elapsed_s': round(elapsed, 2),
        'rc': rc,
        'eval_status': 'ok' if rc == 0 else 'eval_error',
        'official_score': score,
        'stdout_tail': (stdout or '')[-1500:],
        'stderr_tail': (stderr or '')[-500:],
        'gold_entry': gold,
        'answer_type': answer_type,
        'answer_or_path': answer_path,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.write_result:
        rj_path = WORKSPACE_ROOT / iid / 'result.json'
        rj = {}
        if rj_path.exists():
            try: rj = json.loads(rj_path.read_text(encoding='utf-8'))
            except Exception: rj = {}
        rj['eval_status'] = summary['eval_status']
        rj['official_score'] = score
        rj['official_eval_rc'] = rc
        rj['official_stdout_tail'] = summary['stdout_tail']
        rj['official_stderr_tail'] = summary['stderr_tail']
        rj['official_eval_command'] = summary['eval_command']
        rj_path.write_text(json.dumps(rj, indent=2, ensure_ascii=False),
                              encoding='utf-8')
        print(f'\nUPDATED {rj_path}')

    return 0 if rc == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
