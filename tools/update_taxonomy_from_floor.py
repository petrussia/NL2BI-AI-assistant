"""update_taxonomy_from_floor.py — fold floor_baseline.json into task_taxonomy.csv.

Mode B (offline diagnostic): adds floor_marker / floor_score fields to the
taxonomy CSV and may upgrade primary_bucket to upstream_already_produces_gold
or upstream_project_issue based on floor evidence.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TAX = REPO / 'outputs' / 'spider2_dbt' / 'task_taxonomy.csv'
FLOOR_JSON = REPO / 'outputs' / 'spider2_dbt' / 'floor_baseline.json'
FLOOR_JSONL = REPO / 'outputs' / 'dbt_ablation' / 'floor' / 'per_task.jsonl'


def _floor_marker(row: dict) -> str:
    sc = row.get('official_score') or {}
    matched = (sc or {}).get('matched', 0) or 0
    deps_rc = row.get('dbt_deps_rc')
    run_rc = row.get('dbt_run_rc')
    off_rc = row.get('official_rc')
    status = row.get('status', '')
    if status != 'done':
        return 'evaluator_error'
    if matched > 0:
        return 'upstream_already_produces_gold'
    if deps_rc not in (0, None) or (deps_rc == 0 and run_rc is not None and run_rc not in (0, 1, 2)):
        return 'upstream_broken'
    if off_rc not in (0, None):
        return 'evaluator_error'
    return 'normal_floor_miss'


def main() -> int:
    if not TAX.exists():
        print(f'FAIL: {TAX} missing — run tools/build_task_taxonomy.py first'); return 2
    if not FLOOR_JSONL.exists():
        print(f'FAIL: {FLOOR_JSONL} missing — run V0 floor first'); return 2

    floor_rows = [json.loads(l) for l in FLOOR_JSONL.open(encoding='utf-8') if l.strip()]
    floor_by_iid = {r['instance_id']: r for r in floor_rows
                       if r.get('variant') == 'v0_floor'}
    print(f'floor rows: {len(floor_by_iid)}')

    # Load existing taxonomy
    rows: list[dict] = []
    fields: list[str] = []
    with TAX.open(encoding='utf-8') as f:
        rdr = csv.DictReader(f)
        fields = rdr.fieldnames or []
        for r in rdr:
            rows.append(r)
    print(f'taxonomy rows: {len(rows)}')

    # Update + collect aggregates
    n_marker_change = 0; n_bucket_change = 0
    aggregates = {
        'official_matched_count': 0,
        'official_total_count': 0,
        'floor_win_count': 0,
        'dbt_run_rc_zero_count': 0,
        'dbt_deps_rc_zero_count': 0,
        'dbt_test_rc_zero_count': 0,
        'upstream_broken_count': 0,
        'evaluator_error_count': 0,
        'normal_floor_miss_count': 0,
    }
    floor_per_task: dict[str, dict] = {}

    for r in rows:
        iid = r['instance_id']
        floor = floor_by_iid.get(iid)
        if floor is None:
            r['floor_marker'] = 'no_floor_run'
            continue
        sc = floor.get('official_score') or {}
        matched = (sc or {}).get('matched', 0) or 0
        total = (sc or {}).get('total', 0) or 0
        rate = (sc or {}).get('rate')
        marker = _floor_marker(floor)

        prior_primary = r.get('primary_bucket', '')
        if marker == 'upstream_already_produces_gold' and prior_primary != 'upstream_already_produces_gold':
            r['secondary_buckets'] = (
                (r.get('secondary_buckets', '') or '') + (';' if r.get('secondary_buckets') else '')
                + prior_primary)
            r['primary_bucket'] = 'upstream_already_produces_gold'
            n_bucket_change += 1
        elif marker == 'upstream_broken' and prior_primary != 'upstream_project_issue':
            r['secondary_buckets'] = (
                (r.get('secondary_buckets', '') or '') + (';' if r.get('secondary_buckets') else '')
                + prior_primary)
            r['primary_bucket'] = 'upstream_project_issue'
            n_bucket_change += 1
        if r.get('floor_marker') != marker: n_marker_change += 1

        r['floor_marker'] = marker
        r['floor_score_rate'] = rate if rate is not None else ''
        r['floor_score_matched'] = matched
        r['floor_score_total'] = total
        r['upstream_compile_ok'] = (floor.get('dbt_run_rc') in (0, 1))
        r['upstream_run_ok'] = (floor.get('dbt_run_rc') == 0)
        r['upstream_test_pass'] = floor.get('pass_n', 0)
        r['upstream_test_fail'] = floor.get('err_n', 0)
        r['upstream_test_error'] = floor.get('err_n', 0)

        # Aggregates
        aggregates['official_total_count'] += total
        aggregates['official_matched_count'] += matched
        if matched > 0: aggregates['floor_win_count'] += 1
        if floor.get('dbt_deps_rc') == 0: aggregates['dbt_deps_rc_zero_count'] += 1
        if floor.get('dbt_run_rc') == 0: aggregates['dbt_run_rc_zero_count'] += 1
        if floor.get('dbt_test_rc') == 0: aggregates['dbt_test_rc_zero_count'] += 1
        if marker == 'upstream_broken': aggregates['upstream_broken_count'] += 1
        if marker == 'evaluator_error': aggregates['evaluator_error_count'] += 1
        if marker == 'normal_floor_miss': aggregates['normal_floor_miss_count'] += 1

        floor_per_task[iid] = {
            'official_score': sc,
            'dbt_deps_rc': floor.get('dbt_deps_rc'),
            'dbt_run_rc': floor.get('dbt_run_rc'),
            'dbt_test_rc': floor.get('dbt_test_rc'),
            'pass_n': floor.get('pass_n', 0),
            'err_n': floor.get('err_n', 0),
            'floor_marker': marker,
            'notes': '',
        }

    # Re-write CSV with same fields
    with TAX.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows: w.writerow(r)

    # Write floor_baseline.json
    payload = {
        'mode': 'mode_b_offline_floor_diagnostic',
        'created_at': '__set_externally__',  # commit hash is captured by run manifest
        'source_run_dir': 'outputs/dbt_ablation/floor',
        'n_tasks': len(floor_by_iid),
        'aggregates': aggregates,
        'tasks': floor_per_task,
    }
    FLOOR_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                            encoding='utf-8')
    print(f'WROTE {FLOOR_JSON}')
    print(f'WROTE updated {TAX} (markers changed: {n_marker_change}, '
          f'primary_bucket changed: {n_bucket_change})')
    print(f'AGGREGATES: {aggregates}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
