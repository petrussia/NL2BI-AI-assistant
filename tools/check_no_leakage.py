"""check_no_leakage.py — fail fast if submission-flow code reads gold.

Scans:
- spider2_dbt_bridge/*.py  (excluding server_side/*)
- tools/*.py
- configs/*.yaml
- prompt files under data/spider2_dbt/tasks/*/prompt*.txt

Allowed: gold references inside docs and explicit Mode B / offline
diagnostic scripts. Forbidden: gold references in submission-flow code
paths or in materialized prompts.

Exit code 0 = pass, 1 = leak detected.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Patterns we consider gold-leakage in submission code paths
BAD_TOKENS = (
    'evaluation_suite/gold',
    'spider2_eval.jsonl',
    'condition_tabs',
    'condition_cols',
    'gold_target_table',
    'gold_db_path',
    'load_gold_csv',
    'BEGIN PRIVATE KEY',
    'BEGIN OPENSSH PRIVATE KEY',
    'BEGIN RSA PRIVATE KEY',
)

# Files/directories where references are allowed (docs, Mode B explicit)
ALLOWED_PATH_PARTS = (
    # docs that DESCRIBE the policy
    'outputs/logs/spider2_dbt_no_leakage_policy.md',
    'outputs/logs/spider2_dbt_next_implementation_prompt.md',
    'outputs/logs/spider2_dbt_experiment_strategy_vNext.md',
    'outputs/logs/spider2_dbt_experiment_matrix_vNext.md',
    'outputs/logs/spider2_dbt_metrics_contract.md',
    'outputs/logs/spider2_dbt_task_taxonomy_plan.md',
    'outputs/logs/spider2_dbt_first_real_model_run.md',
    # Mode B explicit (offline labeling/diagnostics)
    'tools/build_task_taxonomy.py',
    'tools/update_taxonomy_from_floor.py',
    'tools/check_no_leakage.py',
    'tools/check_metrics_contract.py',
    # server-side analyzer (Mode B)
    'spider2_dbt_bridge/server_side/build_task_inventory.py',
    'spider2_dbt_bridge/server_side/server_official_eval.py',
    'spider2_dbt_bridge/server_side/analyze_tasks.py',
    'spider2_dbt_bridge/server_side/colab_bridge_README.md',
    # offline data files
    'outputs/spider2_dbt/',
    # Strategy / config / registry
    'configs/spider2_dbt_experiments.yaml',
    'reports/spider2_dbt_first_real_model_run.md',
    'reports/spider2_dbt_bridge_final_report.md',
    'reports/spider2_dbt_bridge_dry_run.md',
)


def is_allowed(p: Path) -> bool:
    rel = p.relative_to(REPO).as_posix()
    return any(rel.startswith(allowed) or rel == allowed
                 for allowed in ALLOWED_PATH_PARTS)


def scan_file(p: Path) -> list[tuple[int, str, str]]:
    """Return list of (line_no, token, line_text) for unallowed matches."""
    if is_allowed(p): return []
    try:
        text = p.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return []
    hits: list[tuple[int, str, str]] = []
    for ln_no, line in enumerate(text.splitlines(), start=1):
        # Tolerate comments in code files
        stripped = line.lstrip()
        is_comment = stripped.startswith(('#', '//', '--'))
        for tok in BAD_TOKENS:
            if tok in line and not is_comment:
                hits.append((ln_no, tok, line[:200]))
                break
    return hits


def collect_targets() -> list[Path]:
    out: list[Path] = []
    # spider2_dbt_bridge/*.py (top-level only — server_side has Mode B helpers)
    bridge_dir = REPO / 'spider2_dbt_bridge'
    if bridge_dir.exists():
        for p in bridge_dir.glob('*.py'):
            out.append(p)
    # tools/*.py
    tools_dir = REPO / 'tools'
    if tools_dir.exists():
        for p in tools_dir.rglob('*.py'):
            out.append(p)
    # configs/*.yaml
    cfg_dir = REPO / 'configs'
    if cfg_dir.exists():
        for p in cfg_dir.rglob('*.yaml'):
            out.append(p)
        for p in cfg_dir.rglob('*.yml'):
            out.append(p)
    # materialized prompts
    data_dir = REPO / 'data' / 'spider2_dbt' / 'tasks'
    if data_dir.exists():
        for p in data_dir.rglob('prompt*.txt'):
            out.append(p)
    return out


def main() -> int:
    targets = collect_targets()
    print(f'check_no_leakage: scanning {len(targets)} files')
    total_hits: list[tuple[Path, list[tuple[int, str, str]]]] = []
    for p in targets:
        hits = scan_file(p)
        if hits:
            total_hits.append((p, hits))
    if not total_hits:
        print('PASS — no gold-leakage patterns in submission-flow files.')
        return 0
    print('FAIL — gold-leakage candidates detected:')
    for p, hits in total_hits:
        print(f'\n  {p.relative_to(REPO).as_posix()}')
        for ln, tok, txt in hits[:5]:
            print(f'    L{ln} matches {tok!r}: {txt.strip()[:120]}')
        if len(hits) > 5:
            print(f'    ...and {len(hits)-5} more matches in this file')
    return 1


if __name__ == '__main__':
    sys.exit(main())
