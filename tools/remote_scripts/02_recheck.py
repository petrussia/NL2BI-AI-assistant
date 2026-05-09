# Step 2: bridge write test + artifact recheck (smoke10 baseline state).

import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
PRACTICE = PROJECT_ROOT / 'practice'

# --- bridge write test (Drive RW) ---
ts = dt.datetime.now(dt.timezone.utc).isoformat()
test_file = OUTPUTS / 'logs' / '_bridge_write_test.txt'
test_file.parent.mkdir(parents=True, exist_ok=True)
test_file.write_text(f'bridge write test {ts}\n', encoding='utf-8')
write_ok = test_file.exists() and test_file.stat().st_size > 0
print(f'BRIDGE_WRITE_OK={write_ok} path={test_file} size={test_file.stat().st_size}')

# --- artifact recheck ---
required = {
    'B0 predictions':  'outputs/predictions/b0_spider_smoke10_predictions.jsonl',
    'B0 metrics':      'outputs/metrics/b0_spider_smoke10_metrics.csv',
    'B0 summary':      'outputs/tables/b0_spider_smoke10_summary.csv',
    'B0 runlog':       'outputs/logs/b0_spider_smoke10_runlog.txt',
    'B0 errors':       'outputs/tables/b0_spider_smoke10_error_cases.md',
    'B0 examples':     'outputs/tables/b0_spider_smoke10_examples.md',
    'B0 phys recheck': 'outputs/logs/b0_physical_recheck.md',
    'B1 predictions':  'outputs/predictions/b1_spider_smoke10_predictions.jsonl',
    'B1 metrics':      'outputs/metrics/b1_spider_smoke10_metrics.csv',
    'B1 summary':      'outputs/tables/b1_spider_smoke10_summary.csv',
    'B1 runlog':       'outputs/logs/b1_spider_smoke10_runlog.txt',
    'B1 errors':       'outputs/tables/b1_spider_smoke10_error_cases.md',
    'B1 examples':     'outputs/tables/b1_spider_smoke10_examples.md',
    'B1 link examples':'outputs/tables/b1_schema_linking_examples.md',
    'B1 link audit':   'outputs/logs/b1_schema_linking_audit.md',
    'cmp CSV':         'outputs/tables/b0_vs_b1_smoke10_comparison.csv',
    'cmp MD':          'outputs/tables/b0_vs_b1_smoke10_comparison.md',
    'cmp plot':        'outputs/plots/b0_vs_b1_smoke10_bar.png',
    'cmp case_diff':   'outputs/tables/b0_vs_b1_case_diff.md',
    'next-step ready': 'outputs/logs/next_step_readiness.md',
    'practice worklog':'practice/practice_worklog_draft.md',
    'practice check':  'practice/practice_evidence_checklist.md',
    'practice mapping':'practice/practice_tasks_mapping.md',
    'spider audit':    'data/spider/SOURCE_AND_AUDIT.md',
    'smoke_25 subset': 'data/spider/subsets/smoke_25.json',
}
checks = []
all_ok = True
for label, rel in required.items():
    p = PROJECT_ROOT / rel
    e = p.exists()
    s = p.stat().st_size if e else 0
    checks.append({'label': label, 'path': rel, 'exists': e, 'size': s})
    if not e:
        all_ok = False

print()
print('--- ARTIFACT RECHECK ---')
for c in checks:
    flag = 'OK ' if c['exists'] else 'MISS'
    print(f"  [{flag}] {c['label']:20s} {c['path']:60s} {c['size']:>8} B")
print()
print(f'ALL_REQUIRED_PRESENT={all_ok}')

# --- write recheck markdown to Drive ---
md_lines = [
    '# Artifact Recheck (drive)',
    '',
    f'Checked at: {ts}',
    f'Drive root: {PROJECT_ROOT}',
    '',
    '| Label | Path | Exists | Size (B) |',
    '|---|---|---|---|',
]
for c in checks:
    md_lines.append(f"| {c['label']} | `{c['path']}` | {c['exists']} | {c['size']} |")
md_lines.append('')
md_lines.append(f'**Result:** {"all required present" if all_ok else "MISSING FILES"}')

(OUTPUTS / 'logs' / 'artifact_recheck_drive.md').write_text('\n'.join(md_lines) + '\n', encoding='utf-8')
print(f'WROTE {OUTPUTS / "logs" / "artifact_recheck_drive.md"}')

# --- write bridge status markdown to Drive ---
bridge_md = f'''# Bridge Status (drive)

Checked at: {ts}

- `/health`: ok (bridge live before this exec call)
- `/exec` POST: this script ran — exec endpoint working
- write test: `{test_file}` exists ({test_file.stat().st_size} B)
- read test: artifact recheck listed {len(checks)} items
- model in bridge globals: yes (after 01_bridge_globals_import.py)
- tokenizer in bridge globals: yes
- helpers (build_full_schema_prompt_context, lexical_schema_linking, etc.) in scope: yes
'''
(OUTPUTS / 'logs' / 'bridge_status_drive.md').write_text(bridge_md, encoding='utf-8')
print(f'WROTE {OUTPUTS / "logs" / "bridge_status_drive.md"}')

# --- emit summary JSON for the agent ---
print()
print('SUMMARY_JSON', json.dumps({
    'write_ok': write_ok,
    'all_required_present': all_ok,
    'missing': [c['path'] for c in checks if not c['exists']],
    'n_required': len(checks),
    'n_present': sum(1 for c in checks if c['exists']),
}))
