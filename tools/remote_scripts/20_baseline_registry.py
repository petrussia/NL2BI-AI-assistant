# Stage 0: freeze baseline state. Author baseline_registry.md + .csv on Drive.

import csv
import datetime as dt
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'

def load_csv_one(p):
    if not p.exists(): return None
    return list(csv.DictReader(p.open(encoding='utf-8')))[0]

b0_10 = load_csv_one(OUTPUTS / 'metrics' / 'b0_spider_smoke10_metrics.csv')
b1_10 = load_csv_one(OUTPUTS / 'metrics' / 'b1_spider_smoke10_metrics.csv')
b0_25 = load_csv_one(OUTPUTS / 'metrics' / 'b0_spider_smoke25_metrics.csv')
b1_25 = load_csv_one(OUTPUTS / 'metrics' / 'b1_spider_smoke25_metrics.csv')
b2_10 = load_csv_one(OUTPUTS / 'metrics' / 'b2_spider_smoke10_metrics.csv')

ts = dt.datetime.now(dt.timezone.utc).isoformat()
rows = [
    {'baseline_name': 'B0',    'version': 'v0', 'subset': 'smoke10',
     'ex': b0_10.get('ex'), 'executable_count': b0_10.get('executable_count'),
     'special_fields': '',
     'status': 'completed',
     'comment': 'Single-shot full-schema NL->SQL prompt; reference baseline.'},
    {'baseline_name': 'B1',    'version': 'v0', 'subset': 'smoke10',
     'ex': b1_10.get('ex'), 'executable_count': b1_10.get('executable_count'),
     'special_fields': f"avg_reduction_ratio={b1_10.get('avg_reduction_ratio')}",
     'status': 'completed',
     'comment': 'Reduced schema via lexical schema linking (table x2, col x1, min_score=0.5).'},
    {'baseline_name': 'B0',    'version': 'v0', 'subset': 'smoke25',
     'ex': b0_25.get('ex'), 'executable_count': b0_25.get('executable_count'),
     'special_fields': '',
     'status': 'completed',
     'comment': 'Single error idx 16 (wrong_aggregation), shared with B1.'},
    {'baseline_name': 'B1',    'version': 'v0', 'subset': 'smoke25',
     'ex': b1_25.get('ex'), 'executable_count': b1_25.get('executable_count'),
     'special_fields': f"avg_reduction_ratio={b1_25.get('avg_reduction_ratio')}",
     'status': 'completed',
     'comment': 'Identical EX to B0; same error idx 16. ~58% schema retained.'},
    {'baseline_name': 'B2',    'version': 'v0', 'subset': 'smoke10',
     'ex': b2_10.get('ex'), 'executable_count': b2_10.get('executable_count'),
     'special_fields': f"plan_valid_count={b2_10.get('plan_valid_count')},plan_parse_failures={b2_10.get('plan_parse_failures')},avg_reduction_ratio={b2_10.get('avg_reduction_ratio')}",
     'status': 'completed (regressed)',
     'comment': 'Plan->SQL minimal pipeline. Regressed: 2 result_mismatch (idx 6,7 youngest-singer), 1 plan_invalid (idx 8 distinct+filter).'},
]

# CSV
csv_path = OUTPUTS / 'tables' / 'baseline_registry.csv'
with csv_path.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['baseline_name','version','subset','ex','executable_count','special_fields','status','comment'])
    w.writeheader()
    for r in rows: w.writerow(r)

# MD
md_lines = [
    '# Baseline Registry',
    '',
    f'Frozen at: {ts}',
    'Single source of truth for completed baseline runs. Append-only; new versions get a new row, never overwrite an existing one.',
    '',
    '| Baseline | Ver | Subset | EX | Executable | Special fields | Status | Comment |',
    '|---|---|---|---|---|---|---|---|',
]
for r in rows:
    md_lines.append(f"| {r['baseline_name']} | {r['version']} | {r['subset']} | {r['ex']} | {r['executable_count']} | {r['special_fields']} | {r['status']} | {r['comment']} |")
md_lines += ['',
             '## Conventions',
             '',
             '- `baseline_name` is the family (B0, B1, B2, B1R, B2R...).',
             '- `version` is `v0`, `v1`, ... within the family. Original B0/B1 do not need a version bump because the underlying prompt has not changed.',
             '- `subset` matches the file in `data/spider/subsets/`.',
             '- `special_fields` lists baseline-specific columns from the metrics CSV (avg_reduction_ratio, plan_valid_count, etc.).',
             '- New runs MUST register a new row before being analysed.',
             '']
md_path = OUTPUTS / 'logs' / 'baseline_registry.md'
md_path.write_text('\n'.join(md_lines), encoding='utf-8')
print(f'WROTE {csv_path}')
print(f'WROTE {md_path}')
print(f'rows={len(rows)}')
