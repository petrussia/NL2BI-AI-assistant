# Stage 2 (c): B2_v0 vs B2_v1 comparison on smoke10.

import csv
import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
for sub in ['plots','tables']: (OUTPUTS / sub).mkdir(parents=True, exist_ok=True)

def load_jsonl(p): return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
def load_csv_one(p): return list(csv.DictReader(p.open(encoding='utf-8')))[0]

v0_preds = load_jsonl(OUTPUTS / 'predictions' / 'b2_spider_smoke10_predictions.jsonl')
v1_preds = load_jsonl(OUTPUTS / 'predictions' / 'b2_v1_spider_smoke10_predictions.jsonl')
assert len(v0_preds) == len(v1_preds) == 10, f'{len(v0_preds)} vs {len(v1_preds)}'

v0_m = load_csv_one(OUTPUTS / 'metrics' / 'b2_spider_smoke10_metrics.csv')
v1_m = load_csv_one(OUTPUTS / 'metrics' / 'b2_v1_spider_smoke10_metrics.csv')

def f(d, k):
    try: return float(d[k])
    except Exception: return d.get(k, '')

ex_v0 = float(v0_m['ex']); ex_v1 = float(v1_m['ex'])
exec_v0 = int(v0_m['executable_count']); exec_v1 = int(v1_m['executable_count'])
pv_v0 = int(v0_m['plan_valid_count']); pv_v1 = int(v1_m['plan_valid_count'])
pf_v0 = int(v0_m['plan_parse_failures']); pf_v1 = int(v1_m['plan_parse_failures'])

# CSV
csv_path = OUTPUTS / 'tables' / 'b2_v0_vs_b2_v1_smoke10_comparison.csv'
with csv_path.open('w', newline='', encoding='utf-8') as f_:
    w = csv.writer(f_)
    w.writerow(['metric','b2_v0','b2_v1','delta'])
    w.writerow(['EX', f'{ex_v0:.4f}', f'{ex_v1:.4f}', f'{ex_v1-ex_v0:+.4f}'])
    w.writerow(['executable_count', exec_v0, exec_v1, exec_v1-exec_v0])
    w.writerow(['plan_valid_count', pv_v0, pv_v1, pv_v1-pv_v0])
    w.writerow(['plan_parse_failures', pf_v0, pf_v1, pf_v1-pf_v0])

fixed = []
broken = []
unchanged_correct = []
unchanged_wrong = []
for r0, r1 in zip(v0_preds, v1_preds):
    if r0['execution_match'] and r1['execution_match']: unchanged_correct.append((r0, r1))
    elif (not r0['execution_match']) and (not r1['execution_match']): unchanged_wrong.append((r0, r1))
    elif r1['execution_match'] and not r0['execution_match']: fixed.append((r0, r1))
    else: broken.append((r0, r1))

winner = 'B2_v1' if ex_v1 > ex_v0 else ('B2_v0' if ex_v0 > ex_v1 else 'tie')

md_path = OUTPUTS / 'tables' / 'b2_v0_vs_b2_v1_smoke10_comparison.md'
md_lines = [
    '# B2_v0 vs B2_v1 Comparison on Spider smoke10',
    '',
    f'Checked at: {dt.datetime.now(dt.timezone.utc).isoformat()}',
    'Subset: spider/smoke_10 (n=10). Same model, same schema linker; only planner prompt + plan schema were patched in v1.',
    '',
    '| Metric | B2_v0 | B2_v1 | Δ |',
    '|---|---|---|---|',
    f'| EX | {ex_v0:.4f} | {ex_v1:.4f} | {ex_v1-ex_v0:+.4f} |',
    f'| executable_count | {exec_v0} / 10 | {exec_v1} / 10 | {exec_v1-exec_v0:+d} |',
    f'| plan_valid_count | {pv_v0} / 10 | {pv_v1} / 10 | {pv_v1-pv_v0:+d} |',
    f'| plan_parse_failures | {pf_v0} / 10 | {pf_v1} / 10 | {pf_v1-pf_v0:+d} |',
    '',
    f'**Winner on smoke10:** {winner}',
    '',
    '## Per-case transitions',
    '',
    f'- Fixed by v1 (v0 wrong, v1 right): **{len(fixed)}** cases',
    f'- Broken by v1 (v0 right, v1 wrong): **{len(broken)}** cases',
    f'- Unchanged correct: {len(unchanged_correct)} cases',
    f'- Unchanged wrong: {len(unchanged_wrong)} cases',
    '',
]

def short(s, n=200):
    s = (s or '').replace('|', '\\|').replace('\n', ' ')
    return s if len(s) <= n else s[:n-3] + '...'

if fixed:
    md_lines += ['### Cases fixed by v1', '']
    for r0, r1 in fixed:
        md_lines.append(f"- **idx {r0['idx']}** ({r0['db_id']}): {short(r0['question'])}")
        md_lines.append(f"  - v0 SQL: `{short(r0['generated_sql'])}` (err: {r0['error_type']})")
        md_lines.append(f"  - v1 SQL: `{short(r1['generated_sql'])}` ✓")

if broken:
    md_lines += ['', '### Cases broken by v1', '']
    for r0, r1 in broken:
        md_lines.append(f"- **idx {r0['idx']}** ({r0['db_id']}): {short(r0['question'])}")
        md_lines.append(f"  - v0 SQL: `{short(r0['generated_sql'])}` ✓")
        md_lines.append(f"  - v1 SQL: `{short(r1['generated_sql'])}` (err: {r1['error_type']})")

if unchanged_wrong:
    md_lines += ['', '### Still wrong (unchanged)', '']
    for r0, r1 in unchanged_wrong:
        md_lines.append(f"- **idx {r0['idx']}** ({r0['db_id']}): {short(r0['question'])}")
        md_lines.append(f"  - v0 err: {r0['error_type']}; v1 err: {r1['error_type']}")
        md_lines.append(f"  - v0 SQL: `{short(r0['generated_sql'])}`")
        md_lines.append(f"  - v1 SQL: `{short(r1['generated_sql'])}`")

md_path.write_text('\n'.join(md_lines) + '\n', encoding='utf-8')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(6,4))
bars = ax.bar(['B2_v0', 'B2_v1'], [ex_v0, ex_v1], color=['#C44E52', '#8172B2'])
for bar, v in zip(bars, [ex_v0, ex_v1]):
    ax.text(bar.get_x()+bar.get_width()/2, v+0.02, f'{v:.2f}', ha='center', va='bottom', fontsize=11)
ax.set_ylim(0, 1.15)
ax.set_ylabel('EX (Execution Match)')
ax.set_title('B2_v0 vs B2_v1 on Spider smoke10 (n=10)')
plt.tight_layout()
plt.savefig(OUTPUTS / 'plots' / 'b2_v0_vs_b2_v1_smoke10_bar.png', dpi=140)
plt.close(fig)

print(f'EX v0={ex_v0:.4f}  EX v1={ex_v1:.4f}  Δ={ex_v1-ex_v0:+.4f}  winner={winner}')
print(f'fixed={len(fixed)}  broken={len(broken)}  unchanged_correct={len(unchanged_correct)}  unchanged_wrong={len(unchanged_wrong)}')
print(f'WROTE {csv_path}')
print(f'WROTE {md_path}')
print(f'WROTE {OUTPUTS / "plots" / "b2_v0_vs_b2_v1_smoke10_bar.png"}')
print(f'V1_AT_LEAST_AS_GOOD={ex_v1 >= ex_v0}')
print('STATUS=DONE')
