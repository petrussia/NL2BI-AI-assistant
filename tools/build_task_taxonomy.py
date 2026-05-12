"""build_task_taxonomy.py — local taxonomy classifier (Mode B offline labeling).

Reads the server-pulled inventory at outputs/spider2_dbt/_task_inventory.json
and emits:
    outputs/spider2_dbt/task_inventory.jsonl  (one JSON per task, cleaner format)
    outputs/spider2_dbt/task_taxonomy.csv     (CSV with primary/secondary buckets,
                                                 floor fields blank until V0 run)
    outputs/spider2_dbt/task_taxonomy_readout.md (bucket distribution table)

Bucket rule chain — first match wins for primary_bucket; secondaries are
appended as ;-delimited list. Buckets per the strategy doc.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INV = REPO / 'outputs' / 'spider2_dbt' / '_task_inventory.json'
OUT_JSONL = REPO / 'outputs' / 'spider2_dbt' / 'task_inventory.jsonl'
OUT_CSV = REPO / 'outputs' / 'spider2_dbt' / 'task_taxonomy.csv'
OUT_MD = REPO / 'outputs' / 'spider2_dbt' / 'task_taxonomy_readout.md'


# Keyword detectors used in rule chain
_DATE_KW = re.compile(r'\b(daily|weekly|monthly|quarterly|annual|yearly|year|month|week|day|hour|date|time|period|since|until|recent|last\s+\d+\s+days|first\s+visit|days\s+open|date_diff|dateadd|date_trunc|extract)\b', re.I)
_GRAIN_KW = re.compile(r'\b(per\s+\w+|for\s+each|by\s+(team|user|customer|account|product|day|month|year|category|country|region|state|city)|group(ed)?\s+by|aggregate|total|sum\s+of|count\s+of|average|number\s+of\s+(unique|distinct))', re.I)
_JOIN_KW = re.compile(r'\b(combin\w+|join\w+|merge\w+|including\s+\w+\s+(and|or)\s+\w+|along\s+with|together\s+with|enrich|exclude\s+\w+|but\s+not|where\s+also|regardless\s+of|in\s+addition\s+to)\b', re.I)
_NESTED_KW = re.compile(r'\b(unnest|flatten|json|array|struct|nested|hits\b|items\b|event_params)\b', re.I)
_SCHEMA_KW = re.compile(r'\b(schema\.yml|tests|column\s+test|unique\s+constraint|not_null|relationships)\b', re.I)
_MACRO_KW = re.compile(r'\b(macro|jinja|dbt_project\.yml|var\(|materialization|incremental)\b', re.I)
_FIXREF_KW = re.compile(r'\b(missing\s+ref|broken\s+ref|wrong\s+source|dependency\s+(error|chain)|fix\s+the\s+ref)\b', re.I)


def classify(it: dict) -> tuple[str, list[str], dict]:
    """Return (primary, secondaries, debug_dict)."""
    inv = it.get('inventory') or {}
    instr = (it.get('instruction') or '').strip()
    target_existed = bool(it.get('target_file_existed_in_upstream'))
    bodies = it.get('target_bodies') or []
    likely = it.get('likely_target_files') or []
    gold_targets = it.get('gold_target_tables') or []

    secondaries: list[str] = []
    dbg = {'rules_fired': []}

    # Rule 0: project missing pieces -> upstream_project_issue
    if not inv.get('exists') or not inv.get('has_dbt_project_yml'):
        dbg['rules_fired'].append('missing_project_root')
        return ('upstream_project_issue', secondaries, dbg)

    # Rule 1: stub model present (target file exists, body short / placeholder)
    stub_match = False
    for b in bodies:
        if not b.get('readable'): continue
        if b.get('is_empty') or b.get('chars', 9999) < 60 or b.get('has_todo'):
            stub_match = True; break
        if b.get('has_select') is False and b.get('chars', 9999) < 200:
            stub_match = True; break
    if stub_match and target_existed:
        dbg['rules_fired'].append('stub_target')
        primary = 'fill_stub_model'
    # Rule 2: target file with substantive body present -> patch_existing_model
    elif target_existed and any(b.get('has_select') for b in bodies):
        dbg['rules_fired'].append('substantive_target')
        primary = 'patch_existing_model'
    # Rule 3: gold target named, no plausible upstream file -> create_new_model
    elif gold_targets and not target_existed:
        dbg['rules_fired'].append('no_upstream_target')
        primary = 'create_new_model'
    elif not gold_targets:
        dbg['rules_fired'].append('no_gold_target')
        primary = 'unclear'
    else:
        primary = 'unclear'

    # Secondary tags from instruction
    if _GRAIN_KW.search(instr): secondaries.append('grain_aggregation')
    if _JOIN_KW.search(instr): secondaries.append('join_semantics')
    if _DATE_KW.search(instr): secondaries.append('date_time_semantics')
    if _NESTED_KW.search(instr): secondaries.append('nested_json_list_struct')
    if _SCHEMA_KW.search(instr): secondaries.append('schema_yml_contract')
    if _MACRO_KW.search(instr): secondaries.append('macro_or_config')
    if _FIXREF_KW.search(instr): secondaries.append('fix_ref_source')

    # Promote a secondary to primary if primary was unclear
    if primary == 'unclear' and secondaries:
        primary = secondaries[0]
        secondaries = secondaries[1:]

    return (primary, secondaries, dbg)


def main() -> int:
    if not INV.exists():
        print(f'FAIL: inventory missing: {INV}'); return 2
    inv_rows = json.loads(INV.read_text(encoding='utf-8'))
    print(f'inventory rows: {len(inv_rows)}')

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        'instance_id', 'mode_tag', 'instruction_short',
        'gold_target_table', 'primary_bucket', 'secondary_buckets',
        'target_file_existed_in_upstream', 'likely_target_files',
        'model_sql_count', 'yml_count', 'has_macros', 'has_seeds',
        'has_snapshots',
        # floor fields filled later
        'upstream_compile_ok', 'upstream_run_ok',
        'upstream_test_pass', 'upstream_test_fail', 'upstream_test_error',
        'floor_score_rate', 'floor_score_matched', 'floor_score_total',
        'floor_marker',
        # v4 from prior runs (filled later when known)
        'v4_score_rate_if_known', 'v4_score_matched_if_known',
        'v4_score_total_if_known', 'v4_known_from_run_id',
        'notes',
    ]

    # Pull V4 prior scores from ablation_main if available
    v4_known: dict[str, dict] = {}
    main_run = REPO / 'outputs' / 'dbt_ablation' / 'ablation_main' / 'per_task.jsonl'
    if main_run.exists():
        for ln in main_run.open(encoding='utf-8'):
            r = json.loads(ln)
            if r.get('variant') == 'v4':
                sc = r.get('official_score') or {}
                v4_known[r.get('instance_id', '')] = {
                    'rate': sc.get('rate'),
                    'matched': sc.get('matched'),
                    'total': sc.get('total'),
                    'run_id': 'ablation_main',
                }

    # Write JSONL + CSV
    bucket_counts: dict[str, int] = {}
    secondary_total: dict[str, int] = {}
    csv_rows = []
    with OUT_JSONL.open('w', encoding='utf-8') as fjsonl:
        for it in inv_rows:
            primary, secondaries, dbg = classify(it)
            bucket_counts[primary] = bucket_counts.get(primary, 0) + 1
            for s in secondaries: secondary_total[s] = secondary_total.get(s, 0) + 1
            iid = it['instance_id']
            v4 = v4_known.get(iid) or {}
            inv = it.get('inventory') or {}
            row = {
                'instance_id': iid,
                'mode_tag': 'mode_b_offline_labeling',
                'instruction_short': it.get('instruction_short', '')[:120],
                'gold_target_table': (it.get('gold_target_tables') or [''])[0],
                'primary_bucket': primary,
                'secondary_buckets': ';'.join(secondaries),
                'target_file_existed_in_upstream': bool(it.get('target_file_existed_in_upstream')),
                'likely_target_files': ';'.join(it.get('likely_target_files') or []),
                'model_sql_count': inv.get('model_sql_count', 0),
                'yml_count': inv.get('yml_count', 0),
                'has_macros': inv.get('has_macros_dir', False),
                'has_seeds': inv.get('has_seeds_dir', False),
                'has_snapshots': inv.get('has_snapshots_dir', False),
                'upstream_compile_ok': '',
                'upstream_run_ok': '',
                'upstream_test_pass': '',
                'upstream_test_fail': '',
                'upstream_test_error': '',
                'floor_score_rate': '',
                'floor_score_matched': '',
                'floor_score_total': '',
                'floor_marker': '',
                'v4_score_rate_if_known': v4.get('rate', ''),
                'v4_score_matched_if_known': v4.get('matched', ''),
                'v4_score_total_if_known': v4.get('total', ''),
                'v4_known_from_run_id': v4.get('run_id', ''),
                'notes': ';'.join(dbg.get('rules_fired', [])),
            }
            csv_rows.append(row)
            full = {**row, 'inventory': inv,
                     'gold_target_tables': it.get('gold_target_tables', []),
                     'target_bodies': it.get('target_bodies', [])}
            fjsonl.write(json.dumps(full, ensure_ascii=False) + '\n')

    with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in csv_rows: w.writerow(r)

    print(f'WROTE {OUT_JSONL}')
    print(f'WROTE {OUT_CSV} ({len(csv_rows)} rows)')

    # MD readout
    md = ['# Task taxonomy readout (Phase 0, pre-floor)', '',
            f'_n_total = {len(csv_rows)}_', '',
            '## Primary bucket distribution', '',
            '| bucket | count |', '|---|---:|']
    for b, c in sorted(bucket_counts.items(), key=lambda x: -x[1]):
        md.append(f'| {b} | {c} |')
    md += ['',
            '## Secondary bucket presence', '',
            '| secondary | count |', '|---|---:|']
    for s, c in sorted(secondary_total.items(), key=lambda x: -x[1]):
        md.append(f'| {s} | {c} |')
    md += ['',
            '## Notes',
            '- floor_marker / floor_score fields blank until V0 run completes;',
            '- after V0 run, taxonomy is updated by '
            '`tools/update_taxonomy_from_floor.py`;',
            '- mode_tag is `mode_b_offline_labeling` for every row — gold is used '
            'only for taxonomy/floor diagnostics, never for prompt building.',
            '']
    OUT_MD.write_text('\n'.join(md), encoding='utf-8')
    print(f'WROTE {OUT_MD}')

    print('\nbuckets:')
    for b, c in sorted(bucket_counts.items(), key=lambda x: -x[1]):
        print(f'  {b:32s} {c}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
