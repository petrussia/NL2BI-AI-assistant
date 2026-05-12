"""build_dev_holdout_split.py — stratified smoke / dev_20 / holdout_30 / reserve.

Reads:
    outputs/spider2_dbt/task_taxonomy.csv (with floor markers)
    outputs/spider2_dbt/floor_baseline.json (optional)

Writes:
    outputs/spider2_dbt/dev_holdout_split.json

Stratification rules (per spider2_dbt_task_taxonomy_plan.md):
- smoke = fixed 6 tasks
- dev_20 = 20 tasks, exclude smoke, stratified across primary_bucket
  - >=1 per non-empty bucket if possible
  - >=2 per bucket with >=4 items in full set
  - avoid upstream_already_produces_gold and upstream_project_issue
    UNLESS we need them as negative controls (we'll keep at most 1 of
    each as a labeled negative)
- holdout_30 = 30 tasks, exclude smoke and dev_20
  - similar stratification; preserve >=50% bucket coverage of dev_20
- reserve = remaining

Deterministic order: alphabetic instance_id within each bucket bucket
to keep selection reproducible without random seed.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TAX = REPO / 'outputs' / 'spider2_dbt' / 'task_taxonomy.csv'
OUT = REPO / 'outputs' / 'spider2_dbt' / 'dev_holdout_split.json'

SMOKE = ['asana001', 'playbook001', 'retail001',
          'recharge002', 'xero001', 'lever001']
DEV_TARGET = 20
HOLDOUT_TARGET = 30
NEG_CONTROL_PER_BUCKET = 1   # how many upstream_* items to keep as negative


def _bucket_counts(rows: list[dict], bucket_field='primary_bucket') -> Counter:
    return Counter(r.get(bucket_field, '') for r in rows)


def _pick(rows: list[dict], n: int, *, exclude: set[str],
            allowed_buckets: set[str] | None = None) -> list[str]:
    """Stratified selection: round-robin over buckets sorted by current
    underrepresentation. Deterministic by alphabetic iid within bucket."""
    by_bucket: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        iid = r['instance_id']
        if iid in exclude: continue
        b = r.get('primary_bucket', '')
        if allowed_buckets is not None and b not in allowed_buckets:
            continue
        by_bucket[b].append(iid)
    for b in by_bucket: by_bucket[b].sort()

    chosen: list[str] = []
    used: dict[str, int] = defaultdict(int)
    while len(chosen) < n:
        # pick the bucket with the smallest used/total ratio that still has tasks
        best = None; best_ratio = 1e9
        for b, members in by_bucket.items():
            remaining = len(members) - used[b]
            if remaining <= 0: continue
            total = len(members)
            ratio = used[b] / max(1, total)
            if ratio < best_ratio:
                best_ratio = ratio; best = b
        if best is None: break
        chosen.append(by_bucket[best][used[best]])
        used[best] += 1
    return chosen


def main() -> int:
    if not TAX.exists():
        print(f'FAIL: {TAX} missing'); return 2
    rows: list[dict] = []
    with TAX.open(encoding='utf-8') as f:
        for r in csv.DictReader(f): rows.append(r)
    print(f'taxonomy rows: {len(rows)}')

    smoke = SMOKE[:]
    smoke_set = set(smoke)

    # Separate negative-control buckets from the main pool
    neg_buckets = {'upstream_already_produces_gold', 'upstream_project_issue'}
    rows_main = [r for r in rows
                   if r.get('primary_bucket', '') not in neg_buckets]
    rows_neg = [r for r in rows
                  if r.get('primary_bucket', '') in neg_buckets]

    # Pick dev_20: from main pool first, then 1 negative-control if available
    dev_main = _pick(rows_main, DEV_TARGET - 2, exclude=smoke_set)
    # Add up to NEG_CONTROL_PER_BUCKET items from each negative bucket
    dev_neg: list[str] = []
    for nb in sorted(neg_buckets):
        neg_iids = sorted(r['instance_id'] for r in rows_neg
                            if r.get('primary_bucket', '') == nb
                            and r['instance_id'] not in smoke_set)
        if neg_iids:
            dev_neg.extend(neg_iids[:NEG_CONTROL_PER_BUCKET])
    dev_20 = sorted(set(dev_main + dev_neg))[:DEV_TARGET]
    # Pad if short
    if len(dev_20) < DEV_TARGET:
        extra = _pick(rows_main, DEV_TARGET, exclude=smoke_set | set(dev_20))
        for x in extra:
            if len(dev_20) >= DEV_TARGET: break
            if x not in dev_20: dev_20.append(x)
    dev_20 = dev_20[:DEV_TARGET]
    dev_set = set(dev_20)

    # holdout_30: 30 from remaining (any bucket); preserve coverage
    excluded = smoke_set | dev_set
    holdout = _pick(rows_main, HOLDOUT_TARGET - 2,
                      exclude=excluded)
    # Add a couple of negative-control items if available
    holdout_neg: list[str] = []
    for nb in sorted(neg_buckets):
        neg_iids = sorted(r['instance_id'] for r in rows_neg
                            if r.get('primary_bucket', '') == nb
                            and r['instance_id'] not in excluded)
        if neg_iids:
            holdout_neg.extend(neg_iids[:NEG_CONTROL_PER_BUCKET])
    holdout = sorted(set(holdout + holdout_neg))[:HOLDOUT_TARGET]
    # Pad
    if len(holdout) < HOLDOUT_TARGET:
        extra = _pick(rows_main + rows_neg, HOLDOUT_TARGET,
                        exclude=smoke_set | dev_set | set(holdout))
        for x in extra:
            if len(holdout) >= HOLDOUT_TARGET: break
            if x not in holdout: holdout.append(x)
    holdout = holdout[:HOLDOUT_TARGET]
    holdout_set = set(holdout)

    # Reserve = the rest
    all_iids = {r['instance_id'] for r in rows}
    reserve = sorted(all_iids - smoke_set - dev_set - holdout_set)

    # Stratification check
    by_iid_bucket = {r['instance_id']: r.get('primary_bucket', '') for r in rows}
    by_iid_marker = {r['instance_id']: r.get('floor_marker', '') for r in rows}

    def split_stats(iids: list[str]) -> dict:
        return {
            'bucket_counts': dict(Counter(by_iid_bucket[i] for i in iids)),
            'floor_marker_counts': dict(Counter(by_iid_marker[i] for i in iids)),
        }

    rationale_dev = {iid: f'bucket={by_iid_bucket.get(iid, "?")} marker={by_iid_marker.get(iid, "?")}'
                       for iid in dev_20}
    rationale_holdout = {iid: f'bucket={by_iid_bucket.get(iid, "?")} marker={by_iid_marker.get(iid, "?")}'
                            for iid in holdout}

    payload = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'source_taxonomy': str(TAX.relative_to(REPO).as_posix()),
        'source_floor': 'outputs/spider2_dbt/floor_baseline.json',
        'sets': {
            'smoke': smoke,
            'dev_20': dev_20,
            'holdout_30': holdout,
            'reserve': reserve,
        },
        'stratification_check': {
            'full_68': split_stats(sorted(all_iids)),
            'smoke': split_stats(smoke),
            'dev_20': split_stats(dev_20),
            'holdout_30': split_stats(holdout),
            'reserve': split_stats(reserve),
        },
        'selection_rationale': {
            'dev_20': rationale_dev,
            'holdout_30': rationale_holdout,
        },
        'leakage_policy': {
            'holdout_rule': 'holdout_30 must not be used for prompt iteration',
            'gold_usage': 'gold used only for offline taxonomy/floor diagnostics, not generation',
        },
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'WROTE {OUT}')
    print(f'  smoke={len(smoke)} dev_20={len(dev_20)} '
          f'holdout_30={len(holdout)} reserve={len(reserve)}')
    print(f'  total={len(smoke)+len(dev_20)+len(holdout)+len(reserve)}')

    # Sanity assertions
    assert len(smoke) == 6, f'smoke must be 6; got {len(smoke)}'
    assert len(dev_20) == DEV_TARGET, f'dev_20 must be {DEV_TARGET}'
    assert len(holdout) == HOLDOUT_TARGET, f'holdout_30 must be {HOLDOUT_TARGET}'
    assert smoke_set.isdisjoint(dev_set), 'smoke ∩ dev_20 must be empty'
    assert smoke_set.isdisjoint(holdout_set), 'smoke ∩ holdout_30 must be empty'
    assert dev_set.isdisjoint(holdout_set), 'dev_20 ∩ holdout_30 must be empty'
    assert (smoke_set | dev_set | holdout_set | set(reserve)) == all_iids, 'union must cover full 68'
    return 0


if __name__ == '__main__':
    sys.exit(main())
