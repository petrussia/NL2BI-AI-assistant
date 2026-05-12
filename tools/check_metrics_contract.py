"""check_metrics_contract.py — validate per_task.jsonl files for Phase 0+.

Required-field contract is the freezing reference for the variant-row
schema. v0_floor variants get the strictest rule on apply_kind /
pushed_files / inference_used / prompt_used.

Usage:
    python tools/check_metrics_contract.py \
        --path outputs/dbt_ablation/floor/per_task.jsonl \
        --path outputs/dbt_ablation/v4_vs_floor_dev20/per_task.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict


REQUIRED = (
    'instance_id', 'variant', 'status', 'apply_kind',
    'pushed_files',
    'dbt_deps_rc', 'dbt_run_rc', 'dbt_test_rc',
    'official_score', 'official_rc', 'wall_time_s',
)

# Optional fields that we WARN on if absent (not fatal)
EXPECTED_OPTIONAL = (
    'pass_n', 'err_n',
)


def check_row(row: dict, line_no: int, errors: list, warnings: list) -> None:
    iid = row.get('instance_id', '<no-iid>')
    var = row.get('variant', '<no-variant>')
    tag = f'L{line_no} {iid}/{var}'

    for f in REQUIRED:
        if f not in row:
            errors.append(f'{tag}: missing required field {f!r}')
    for f in EXPECTED_OPTIONAL:
        if f not in row:
            warnings.append(f'{tag}: missing optional field {f!r}')

    # variant-specific checks
    if var == 'v0_floor':
        if row.get('apply_kind') != 'none':
            errors.append(f'{tag}: v0_floor must have apply_kind="none", '
                            f'got {row.get("apply_kind")!r}')
        if row.get('pushed_files') not in ([], None):
            errors.append(f'{tag}: v0_floor must have pushed_files=[], '
                            f'got {row.get("pushed_files")!r}')
        if row.get('inference_used') not in (False, None):
            errors.append(f'{tag}: v0_floor must have inference_used=false')
        if row.get('prompt_used') not in (False, None):
            errors.append(f'{tag}: v0_floor must have prompt_used=false')

    # official_score — if present must be dict with rate/matched/total OR null
    sc = row.get('official_score')
    if sc is not None:
        if not isinstance(sc, dict):
            errors.append(f'{tag}: official_score should be dict or null')
        else:
            for sub in ('rate', 'matched', 'total'):
                if sub not in sc:
                    errors.append(f'{tag}: official_score missing {sub!r}')

    # If status=='done' and official_score is None, allow only when official_rc != 0
    if row.get('status') == 'done' and sc is None:
        if row.get('official_rc') in (0, None):
            warnings.append(f'{tag}: status=done with null official_score and official_rc not failure')


def summarize(rows: list[dict]) -> dict:
    by_var: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        v = r.get('variant', '?')
        by_var[v]['total'] += 1
        by_var[v][f"status={r.get('status', '?')}"] += 1
        by_var[v][f"apply_kind={r.get('apply_kind', '?')}"] += 1
        sc = r.get('official_score') or {}
        if sc.get('matched', 0) > 0: by_var[v]['matched'] += 1
        if r.get('dbt_run_rc') == 0: by_var[v]['dbt_run_rc_zero'] += 1
    return {v: dict(c) for v, c in by_var.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--path', action='append', required=True)
    args = ap.parse_args()

    overall_errors: list[str] = []
    overall_warnings: list[str] = []
    summaries: dict[str, dict] = {}

    for p in args.path:
        path = Path(p)
        if not path.exists():
            overall_errors.append(f'{p}: file not found')
            continue
        rows = []
        for ln_no, line in enumerate(path.open(encoding='utf-8'), start=1):
            line = line.rstrip()
            if not line: continue
            try:
                row = json.loads(line)
            except Exception as exc:
                overall_errors.append(f'{p}:L{ln_no}: JSON parse error: {exc}')
                continue
            rows.append(row)
            check_row(row, ln_no, overall_errors, overall_warnings)
        summaries[p] = summarize(rows)

    print('check_metrics_contract')
    print('=' * 60)
    for p, s in summaries.items():
        print(f'\n{p}:')
        for v, c in s.items():
            print(f'  variant={v}: {c}')
    if overall_warnings:
        print('\nWARNINGS:')
        for w in overall_warnings[:20]:
            print(f'  - {w}')
        if len(overall_warnings) > 20:
            print(f'  ...and {len(overall_warnings)-20} more')
    if overall_errors:
        print('\nFAIL — errors:')
        for e in overall_errors[:30]:
            print(f'  - {e}')
        if len(overall_errors) > 30:
            print(f'  ...and {len(overall_errors)-30} more')
        return 1
    print('\nPASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
