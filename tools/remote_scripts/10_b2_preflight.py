# Step 10: B2 preflight. Verify everything B2 will depend on is present.

import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
PRACTICE = PROJECT_ROOT / 'practice'
REPO = PROJECT_ROOT / 'repo'

# Required for B2
required = {
    # Baselines (all four must already exist for the 3-way / 4-way comparisons later)
    'B0 smoke10 preds':  'outputs/predictions/b0_spider_smoke10_predictions.jsonl',
    'B0 smoke10 metrics':'outputs/metrics/b0_spider_smoke10_metrics.csv',
    'B1 smoke10 preds':  'outputs/predictions/b1_spider_smoke10_predictions.jsonl',
    'B1 smoke10 metrics':'outputs/metrics/b1_spider_smoke10_metrics.csv',
    'B0 smoke25 preds':  'outputs/predictions/b0_spider_smoke25_predictions.jsonl',
    'B0 smoke25 metrics':'outputs/metrics/b0_spider_smoke25_metrics.csv',
    'B1 smoke25 preds':  'outputs/predictions/b1_spider_smoke25_predictions.jsonl',
    'B1 smoke25 metrics':'outputs/metrics/b1_spider_smoke25_metrics.csv',
    # Evidence pack
    'practice worklog':  'practice/practice_worklog_draft.md',
    'practice checklist':'practice/practice_evidence_checklist.md',
    'practice mapping':  'practice/practice_tasks_mapping.md',
    'thesis inventory':  'outputs/logs/thesis_experiment_inventory.md',
    # B2 readiness docs
    'b2 readiness':      'outputs/logs/b2_readiness_after_smoke25.md',
    'b2 plan':           'outputs/logs/b2_implementation_plan.md',
    # Spider data
    'smoke10 subset':    'data/spider/subsets/smoke_10.json',
    'smoke25 subset':    'data/spider/subsets/smoke_25.json',
    'spider tables':     'data/spider/tables.json',
    'spider audit':      'data/spider/SOURCE_AND_AUDIT.md',
    # B1 helpers reused by B2
    'baselines module':  'repo/src/evaluation/baselines.py',
}

# Check repo/docs/ for plan_schema and output_contract
candidates_plan = ['repo/docs/plan_schema.json', 'docs/plan_schema.json',
                   'repo/contracts/plan_schema.json', 'contracts/plan_schema.json',
                   'repo/plan_schema.json', 'plan_schema.json']
candidates_out = ['repo/docs/output_contract.json', 'docs/output_contract.json',
                  'repo/contracts/output_contract.json', 'contracts/output_contract.json',
                  'repo/output_contract.json', 'output_contract.json']

found_plan_schema = None
for rel in candidates_plan:
    if (PROJECT_ROOT / rel).exists():
        found_plan_schema = rel; break
found_output_contract = None
for rel in candidates_out:
    if (PROJECT_ROOT / rel).exists():
        found_output_contract = rel; break

# Hunt for any plan_schema.json anywhere under repo/ if not found
if not found_plan_schema and REPO.exists():
    for p in REPO.rglob('plan_schema.json'):
        found_plan_schema = str(p.relative_to(PROJECT_ROOT))
        break
if not found_output_contract and REPO.exists():
    for p in REPO.rglob('output_contract.json'):
        found_output_contract = str(p.relative_to(PROJECT_ROOT))
        break

# Walk repo/src/evaluation/ to see what helpers are already there
eval_dir = REPO / 'src' / 'evaluation'
eval_listing = []
if eval_dir.exists():
    for p in sorted(eval_dir.iterdir()):
        if p.is_file():
            eval_listing.append({'name': p.name, 'size': p.stat().st_size})

checks = []
all_ok = True
missing = []
for label, rel in required.items():
    p = PROJECT_ROOT / rel
    e = p.exists(); s = p.stat().st_size if e else 0
    checks.append({'label': label, 'path': rel, 'exists': e, 'size': s})
    if not e:
        all_ok = False
        missing.append(rel)

if not found_plan_schema:
    all_ok = False
    missing.append('plan_schema.json (searched repo/docs/, docs/, contracts/, repo/, root)')

ts = dt.datetime.now(dt.timezone.utc).isoformat()
print('--- artifact recheck ---')
for c in checks:
    flag = 'OK ' if c['exists'] else 'MISS'
    print(f"  [{flag}] {c['label']:24s} {c['path']:60s} {c['size']:>8} B")
print(f'  plan_schema.json found at: {found_plan_schema or "MISSING"}')
print(f'  output_contract.json found at: {found_output_contract or "(not strictly required)"}')
print(f'  repo/src/evaluation/ listing: {eval_listing}')
print(f'ALL_REQUIRED_PRESENT={all_ok}')

# Also dump plan_schema.json content if found (the agent needs to know its shape)
plan_schema_obj = None
if found_plan_schema:
    try:
        plan_schema_obj = json.loads((PROJECT_ROOT / found_plan_schema).read_text(encoding='utf-8'))
        print('--- plan_schema.json (parsed) ---')
        print(json.dumps(plan_schema_obj, ensure_ascii=False, indent=2)[:3000])
    except Exception as exc:
        print(f'plan_schema.json parse failed: {exc!r}')

# Markdown dump on Drive
md_lines = ['# B2 Preflight (drive)', '', f'Checked at: {ts}', '', '| Label | Path | Exists | Size |', '|---|---|---|---|']
for c in checks:
    md_lines.append(f"| {c['label']} | `{c['path']}` | {c['exists']} | {c['size']} |")
md_lines += ['', f'- plan_schema.json: `{found_plan_schema}`',
             f'- output_contract.json: `{found_output_contract}`',
             f'- repo/src/evaluation/ listing: `{eval_listing}`',
             '', f'**Result:** {"PASS" if all_ok else "PRECHECK BLOCKED"}']
if missing:
    md_lines += ['', '## Missing'] + [f'- `{m}`' for m in missing]
(OUTPUTS / 'logs' / 'b2_preflight_drive.md').write_text('\n'.join(md_lines) + '\n', encoding='utf-8')
print(f'\nWROTE {OUTPUTS / "logs" / "b2_preflight_drive.md"}')

# JSON for the agent
print('\nSUMMARY_JSON', json.dumps({
    'all_ok': all_ok, 'missing': missing,
    'plan_schema_path': found_plan_schema,
    'output_contract_path': found_output_contract,
    'eval_dir_files': [e['name'] for e in eval_listing],
    'plan_schema_keys': list(plan_schema_obj.keys()) if isinstance(plan_schema_obj, dict) else None,
}))
