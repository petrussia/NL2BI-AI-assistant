import json
import uuid
from pathlib import Path

NB = Path(r"D:\HSE\Диплом\NL2BI-AI-assistant\notebooks\example.ipynb")

CELL_F_SOURCE = '''# B1_FINAL_INDEX
from __future__ import annotations
import csv
import datetime as dt
from pathlib import Path

MARKER = 'B1_FINAL_INDEX'
PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS_DIR = PROJECT_ROOT / 'outputs'
PRACTICE_DIR = PROJECT_ROOT / 'practice'

critical = {
    'B0 predictions': 'outputs/predictions/b0_spider_smoke10_predictions.jsonl',
    'B0 metrics': 'outputs/metrics/b0_spider_smoke10_metrics.csv',
    'B0 summary': 'outputs/tables/b0_spider_smoke10_summary.csv',
    'B0 runlog': 'outputs/logs/b0_spider_smoke10_runlog.txt',
    'B0 errors': 'outputs/tables/b0_spider_smoke10_error_cases.md',
    'B0 examples': 'outputs/tables/b0_spider_smoke10_examples.md',
    'B0 physical recheck': 'outputs/logs/b0_physical_recheck.md',
    'B1 predictions': 'outputs/predictions/b1_spider_smoke10_predictions.jsonl',
    'B1 metrics': 'outputs/metrics/b1_spider_smoke10_metrics.csv',
    'B1 summary': 'outputs/tables/b1_spider_smoke10_summary.csv',
    'B1 runlog': 'outputs/logs/b1_spider_smoke10_runlog.txt',
    'B1 errors': 'outputs/tables/b1_spider_smoke10_error_cases.md',
    'B1 examples': 'outputs/tables/b1_spider_smoke10_examples.md',
    'B1 schema linking examples': 'outputs/tables/b1_schema_linking_examples.md',
    'B1 schema linking audit': 'outputs/logs/b1_schema_linking_audit.md',
    'comparison CSV': 'outputs/tables/b0_vs_b1_smoke10_comparison.csv',
    'comparison MD': 'outputs/tables/b0_vs_b1_smoke10_comparison.md',
    'comparison plot': 'outputs/plots/b0_vs_b1_smoke10_bar.png',
    'comparison case diff': 'outputs/tables/b0_vs_b1_case_diff.md',
    'next step readiness': 'outputs/logs/next_step_readiness.md',
    'practice worklog': 'practice/practice_worklog_draft.md',
    'practice checklist': 'practice/practice_evidence_checklist.md',
    'practice mapping': 'practice/practice_tasks_mapping.md',
}

print(MARKER)
print(f'Drive root: {PROJECT_ROOT}')
print(f'Checked at: {dt.datetime.now(dt.timezone.utc).isoformat()}')
print()
print('=== Critical artifacts ===')
missing = []
for label, rel in critical.items():
    p = PROJECT_ROOT / rel
    if p.exists():
        print(f'  [OK] {label:38s}  {rel:60s}  ({p.stat().st_size:>9} B)')
    else:
        print(f'  [MISSING] {label:33s}  {rel}')
        missing.append(rel)

print()
print('=== Full outputs/ tree ===')
for sub in ['predictions', 'metrics', 'tables', 'logs', 'plots']:
    d = OUTPUTS_DIR / sub
    print(f'  outputs/{sub}/:')
    if d.exists():
        for p in sorted(d.iterdir()):
            if p.is_file():
                print(f'    {p.name:60s}  {p.stat().st_size:>9} B')
    else:
        print(f'    (does not exist)')

print()
print('=== Practice/ tree ===')
if PRACTICE_DIR.exists():
    for p in sorted(PRACTICE_DIR.iterdir()):
        if p.is_file():
            print(f'  {p.name:60s}  {p.stat().st_size:>9} B')

print()
print('=== Final status ===')
try:
    b0 = list(csv.DictReader((OUTPUTS_DIR / 'metrics' / 'b0_spider_smoke10_metrics.csv').open(encoding='utf-8')))[0]
    b1 = list(csv.DictReader((OUTPUTS_DIR / 'metrics' / 'b1_spider_smoke10_metrics.csv').open(encoding='utf-8')))[0]
    ex_b0 = float(b0['ex'])
    ex_b1 = float(b1['ex'])
    winner = 'B1' if ex_b1 > ex_b0 else 'B0' if ex_b0 > ex_b1 else 'tie'
    print(f'  EX B0 = {ex_b0:.4f}  ({b0["execution_match_count"]}/{b0["n"]} matches, {b0["executable_count"]}/{b0["n"]} executable)')
    print(f'  EX B1 = {ex_b1:.4f}  ({b1["execution_match_count"]}/{b1["n"]} matches, {b1["executable_count"]}/{b1["n"]} executable)')
    print(f'  Winner on smoke10: {winner}')
    print(f'  B1 schema strategy: {b1["schema_strategy"]} (avg reduction = {b1["avg_reduction_ratio"]})')
    if not missing:
        print('  >>> B1 PIPELINE COMPLETED <<<')
    else:
        print(f'  >>> B1 PIPELINE COMPLETED WITH MISSING ARTIFACTS: {missing} <<<')
except Exception as exc:
    print(f'  COULD NOT LOAD METRICS: {exc!r}')
    print('  >>> B1 PIPELINE INCOMPLETE <<<')
'''

nb = json.loads(NB.read_text(encoding="utf-8"))

# Check if cell already exists
exists = any("B1_FINAL_INDEX" in "".join(c["source"]) for c in nb["cells"])
if exists:
    print("Cell B1_FINAL_INDEX already present, skipping")
else:
    new_cell = {
        "cell_type": "code",
        "id": uuid.uuid4().hex[:8],
        "metadata": {},
        "outputs": [],
        "execution_count": None,
        "source": CELL_F_SOURCE.splitlines(keepends=True),
    }
    nb["cells"].append(new_cell)
    NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Inserted cell at end with id {new_cell['id']}")
    print(f"Total cells now: {len(nb['cells'])}")
