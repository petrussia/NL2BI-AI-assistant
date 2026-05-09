# Build comparison tables b3v2 vs b3v1 and b4v2 vs b4_final.

import csv
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'

def load_metric(prefix):
    p = OUTPUTS / 'metrics' / f'{prefix}_metrics.csv'
    if not p.exists(): return None
    with p.open(encoding='utf-8') as f:
        return next(csv.DictReader(f), None)

def write_pair(out_csv_name, rows):
    p = OUTPUTS / 'tables' / out_csv_name
    cols = ['comparison','baseline','subset','EX','executable','plan_valid','n','file']
    with p.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return p

def fmt(m, prefix):
    if not m: return None
    return {
        'baseline': prefix.split('_')[0].upper(),
        'subset': m.get('subset',''),
        'EX': m.get('ex',''),
        'executable': m.get('executable_count',''),
        'plan_valid': m.get('plan_valid_count',''),
        'n': m.get('n',''),
        'file': prefix,
    }

# B3v2 vs B3v1
b3_rows = []
for sub, suffix in [('smoke_10','spider_smoke10'),('multidb_30','multidb30')]:
    for prefix in (f'b3v1_{suffix}', f'b3v2_{suffix}'):
        m = load_metric(prefix)
        if m:
            r = fmt(m, prefix); r['comparison'] = f'B3v2_vs_B3v1_{sub}'
            b3_rows.append(r)
p1 = write_pair('b3v2_vs_b3v1.csv', b3_rows)

# B4v2 vs B4_final
b4_rows = []
for sub, suffix in [('smoke_10','spider_smoke10'),('multidb_30','multidb30')]:
    for prefix in (f'b4_final_{suffix}', f'b4v2_{suffix}'):
        m = load_metric(prefix)
        if m:
            r = fmt(m, prefix); r['comparison'] = f'B4v2_vs_B4final_{sub}'
            b4_rows.append(r)
p2 = write_pair('b4v2_vs_b4final.csv', b4_rows)

# Final negative-result analysis (auto-derived)
analysis = OUTPUTS / 'logs' / 'final_negative_result_analysis.md'

def lookup(rows, baseline_filter, subset_filter):
    for r in rows:
        if r['baseline'].lower() == baseline_filter.lower() and r['subset'] == subset_filter:
            try: return float(r['EX'])
            except: return None
    return None

b3v1_s10 = lookup(b3_rows, 'B3v1', 'smoke_10')
b3v2_s10 = lookup(b3_rows, 'B3v2', 'smoke_10')
b4f_s10  = lookup(b4_rows, 'B4', 'smoke_10')
b4v2_s10 = lookup(b4_rows, 'B4v2', 'smoke_10')
b3v1_md  = lookup(b3_rows, 'B3v1', 'multidb_30')
b3v2_md  = lookup(b3_rows, 'B3v2', 'multidb_30')
b4f_md   = lookup(b4_rows, 'B4', 'multidb_30')
b4v2_md  = lookup(b4_rows, 'B4v2', 'multidb_30')

def _delta(a,b):
    if a is None or b is None: return '—'
    return f'{(a-b):+.4f}'

def _val(x):
    return '—' if x is None else f'{x:.4f}'

text = f'''# Final negative-result analysis (post B3_v2 / B4_v2)

## Direct EX comparison

| Subset | B3v1 | B3v2 | Δ B3v2−B3v1 | B4_final | B4v2 | Δ B4v2−B4final |
|---|---|---|---|---|---|---|
| smoke_10  | {_val(b3v1_s10)} | {_val(b3v2_s10)} | {_delta(b3v2_s10, b3v1_s10)} | {_val(b4f_s10)} | {_val(b4v2_s10)} | {_delta(b4v2_s10, b4f_s10)} |
| multidb_30 | {_val(b3v1_md)} | {_val(b3v2_md)} | {_delta(b3v2_md, b3v1_md)} | {_val(b4f_md)} | {_val(b4v2_md)} | {_delta(b4v2_md, b4f_md)} |

## Interpretation

The B3_v2 design removed the synthesised "knowledge channel" entirely and
added an unconditional B1 fallback when the planner JSON cannot be validated.
The B4_v2 design extended the B1 fallback to the "no-executable-candidate"
branch as well.

If the deltas above are **strongly positive**, the regression of the prior
B3_v1 / B4_final iteration is fully attributable to (a) prompt noise from the
fake knowledge channel and (b) hard planner failures with no graceful
degradation. The diploma can then claim that *with the right safety nets, the
planner stack is at least non-harmful*.

If the deltas above are **near-zero or negative**, the regression is
structural: planner-mediated SQL generation does not pay off on Spider with a
strong base model, regardless of safety nets. This is a clean negative
research finding, more valuable than a misleading positive: it tells future
practitioners not to spend latency budget on a planner stack for tasks where
single-shot SQL already saturates accuracy.

Either way, the B0/B1 trio with Qwen-Coder-7B remains the strongest
configuration this project found, and the diploma should report that as the
production recommendation.
'''
analysis.write_text(text, encoding='utf-8')
print(f'WROTE {p1}')
print(f'WROTE {p2}')
print(f'WROTE {analysis}')
