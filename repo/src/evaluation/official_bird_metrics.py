"""Wrapper around the BIRD Mini-Dev official evaluation scripts (when present).

The mini_dev repo ships:
- evaluation/evaluation_ex.py  — Execution Match
- evaluation/evaluation_f1.py  — Soft F1
- evaluation/evaluation_ves.py — R-VES (relative valid efficiency score)

These scripts read predictions in a specific format (text file, one SQL per line,
1-indexed). We adapt our JSONL predictions, write the temp file, invoke the
official scripts, and parse stdout.
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

EVAL_DIR = Path('/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/bird_mini_dev/raw/minidev/evaluation')
DATA_DIR = Path('/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/bird_mini_dev/raw/minidev/minidev/MINIDEV')


def predictions_jsonl_to_bird_text(jsonl_path: Path, out_txt: Path,
                                    bird_data: list[dict]) -> int:
    """Convert our JSONL predictions to BIRD's expected predicted SQL text file.
    BIRD format: one line per index, format `<sql>\\t----- bird -----\\t<db_id>`.
    We map our records by item idx (0-based) onto the same idx in `bird_data`.
    Returns number of items written."""
    preds = []
    for line in open(jsonl_path, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try: preds.append(json.loads(line))
        except Exception: pass
    n = min(len(preds), len(bird_data))
    lines = []
    for i in range(n):
        sql = (preds[i].get('generated_sql') or '').strip().replace('\n', ' ')
        if not sql.endswith(';'): sql += ';'
        sql = sql.rstrip(';')
        db_id = bird_data[i].get('db_id') or preds[i].get('db_id', '')
        lines.append(f"{sql}\t----- bird -----\t{db_id}")
    out_txt.write_text('\n'.join(lines), encoding='utf-8')
    return n


def run_bird_official_ex(jsonl_path: str | Path,
                          slice_path: str | Path = DATA_DIR/'mini_dev_sqlite.json',
                          db_root: str | Path = DATA_DIR/'dev_databases',
                          ground_truth_path: str | Path = DATA_DIR/'mini_dev_sqlite_gold.sql',
                          ) -> dict:
    """Try to run the official BIRD EX evaluator. Returns dict with score and
    raw stdout, or {'available': False, 'reason': ...} on failure."""
    if not EVAL_DIR.exists():
        return {'available': False, 'reason': f'eval dir missing: {EVAL_DIR}'}
    eval_script = EVAL_DIR / 'evaluation_ex.py'
    if not eval_script.exists():
        return {'available': False, 'reason': f'evaluation_ex.py missing in {EVAL_DIR}'}
    bird_data = json.loads(Path(slice_path).read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        pred_txt = tdp / 'predicted_sql.txt'
        n = predictions_jsonl_to_bird_text(Path(jsonl_path), pred_txt, bird_data)
        # The official script CLI varies between BIRD versions; we try the most
        # common arg names. Always fall back to capturing stderr for diagnostics.
        cmd = [sys.executable, str(eval_script),
               '--predicted_sql_path', str(pred_txt),
               '--ground_truth_path', str(ground_truth_path),
               '--db_root_path', str(db_root),
               '--num_cpus', '1',
               '--meta_time_out', '30.0']
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=900,
                                cwd=str(EVAL_DIR))
        except subprocess.TimeoutExpired as exc:
            return {'available': False, 'reason': f'eval timeout: {exc}', 'cmd': cmd}
        score = None
        # Try to find a numeric score in stdout
        m = re.search(r'(?i)(?:execution\s+accuracy|EX|accuracy)\s*[:=]?\s*([0-9]+\.[0-9]+)', r.stdout)
        if m:
            try: score = float(m.group(1))
            except: pass
        if score is None:
            m2 = re.search(r'([0-9]+\.[0-9]+)', r.stdout)
            if m2:
                try: score = float(m2.group(1))
                except: pass
        return {'available': True, 'returncode': r.returncode, 'n_items': n,
                'score': score, 'stdout_tail': r.stdout[-2000:],
                'stderr_tail': r.stderr[-1000:], 'cmd': cmd}
