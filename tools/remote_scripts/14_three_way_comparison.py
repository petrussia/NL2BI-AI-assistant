# Step 14: B0 vs B1 vs B2 three-way comparison on smoke10. CSV + MD + PNG + case_diff.

import csv
import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
for sub in ['plots', 'tables']:
    (OUTPUTS / sub).mkdir(parents=True, exist_ok=True)


def load_jsonl(p):
    return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]


def load_csv_one(p):
    return list(csv.DictReader(p.open(encoding='utf-8')))[0]


def short(s, n=240):
    s = (s or '').replace('|', '\\|').replace('\n', ' ')
    return s if len(s) <= n else s[:n - 3] + '...'


b0 = load_jsonl(OUTPUTS / 'predictions' / 'b0_spider_smoke10_predictions.jsonl')
b1 = load_jsonl(OUTPUTS / 'predictions' / 'b1_spider_smoke10_predictions.jsonl')
b2 = load_jsonl(OUTPUTS / 'predictions' / 'b2_spider_smoke10_predictions.jsonl')
assert len(b0) == len(b1) == len(b2) and len(b0) > 0, f'misaligned: {len(b0)}/{len(b1)}/{len(b2)}'
n = len(b0)

ex_b0 = sum(1 for r in b0 if r['execution_match']) / n
ex_b1 = sum(1 for r in b1 if r['execution_match']) / n
ex_b2 = sum(1 for r in b2 if r['execution_match']) / n
exe_b0 = sum(1 for r in b0 if r['executable'])
exe_b1 = sum(1 for r in b1 if r['executable'])
exe_b2 = sum(1 for r in b2 if r['executable'])
plan_valid = sum(1 for r in b2 if r.get('plan_valid'))
plan_parse_fail = sum(1 for r in b2 if r.get('plan_parsed') is None)
b1_avg_red = (sum(r.get('schema_reduction_ratio', 0) for r in b1) / n) if any('schema_reduction_ratio' in r for r in b1) else None
b2_avg_red = (sum(r.get('schema_reduction_ratio', 0) for r in b2) / n) if any('schema_reduction_ratio' in r for r in b2) else None

# CSV
csv_path = OUTPUTS / 'tables' / 'b0_b1_b2_smoke10_comparison.csv'
with csv_path.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['metric', 'b0', 'b1', 'b2'])
    w.writerow(['EX', f'{ex_b0:.4f}', f'{ex_b1:.4f}', f'{ex_b2:.4f}'])
    w.writerow(['executable_count', exe_b0, exe_b1, exe_b2])
    w.writerow(['n', n, n, n])
    w.writerow(['avg_reduction_ratio', '', f'{b1_avg_red:.4f}' if b1_avg_red is not None else '', f'{b2_avg_red:.4f}' if b2_avg_red is not None else ''])
    w.writerow(['plan_valid_count', '', '', plan_valid])
    w.writerow(['plan_parse_failures', '', '', plan_parse_fail])

# Winner
ex_map = {'B0': ex_b0, 'B1': ex_b1, 'B2': ex_b2}
top = max(ex_map.values())
winners = [k for k, v in ex_map.items() if v == top]
winner = winners[0] if len(winners) == 1 else 'tie ({})'.format(' = '.join(winners))

# Markdown
md_path = OUTPUTS / 'tables' / 'b0_b1_b2_smoke10_comparison.md'
md_path.write_text(f'''# B0 vs B1 vs B2 Comparison (Spider smoke10)

Checked at: {dt.datetime.now(dt.timezone.utc).isoformat()}
Subset: spider/smoke_10 (n={n})
Model: Qwen/Qwen2.5-Coder-7B-Instruct (4-bit nf4 bitsandbytes), greedy decode

| Metric | B0 (full schema) | B1 (reduced schema) | B2 (Plan->SQL) |
|---|---|---|---|
| EX | {ex_b0:.4f} | {ex_b1:.4f} | {ex_b2:.4f} |
| executable_count | {exe_b0} / {n} | {exe_b1} / {n} | {exe_b2} / {n} |
| avg_reduction_ratio | — | {b1_avg_red:.4f} | {b2_avg_red:.4f} |
| plan_valid_count | — | — | {plan_valid} / {n} |
| plan_parse_failures | — | — | {plan_parse_fail} / {n} |

Winner on smoke10: **{winner}**

## Notes
- B2 schema strategy: lexical schema linking (reused from B1) + planner producing JSON Plan validated against `repo/docs/plan_schema.json` + plan->SQL prompt.
- B2 schema reduction ratio reuses the same lexical linker as B1 — they should match closely on the same questions.
- B2 EX upper bound is `plan_valid_count / n` (questions whose plan failed validation are recorded as `error_type=plan_invalid` and skip SQL generation).
''', encoding='utf-8')

# Plot
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(7, 4))
labels = ['B0\nfull schema', 'B1\nreduced schema', 'B2\nPlan->SQL']
vals = [ex_b0, ex_b1, ex_b2]
colors = ['#4C72B0', '#55A868', '#C44E52']
bars = ax.bar(labels, vals, color=colors)
for bar, v in zip(bars, vals):
    ax.text(bar.get_x() + bar.get_width() / 2, v + 0.02, f'{v:.2f}', ha='center', va='bottom', fontsize=11)
ax.set_ylim(0, 1.15)
ax.set_ylabel('EX (Execution Match)')
ax.set_title(f'B0 vs B1 vs B2 on Spider smoke10 (n={n})')
plt.tight_layout()
plt.savefig(OUTPUTS / 'plots' / 'b0_b1_b2_smoke10_bar.png', dpi=140)
plt.close(fig)

# Case diff (>= 5)
case_lines = ['# B0 vs B1 vs B2 Case Diff (smoke10)\n']
# Pick interesting cases: any with disagreement first, then unchanged_correct
disagree = []
agree = []
for i in range(n):
    if (b0[i]['execution_match'], b1[i]['execution_match'], b2[i]['execution_match']) in [(True, True, True), (False, False, False)]:
        agree.append(i)
    else:
        disagree.append(i)
selected = disagree + agree
selected = selected[:max(5, len(disagree) + 2)]

for i in selected[:max(5, len(disagree))]:
    bb0, bb1, bb2 = b0[i], b1[i], b2[i]
    case_lines.append(f"## Case {i} (db: {bb0['db_id']})\n")
    case_lines.append(f"- **Question:** {short(bb0['question'])}\n")
    case_lines.append(f"- **B0:** match={bb0['execution_match']} executable={bb0['executable']} error={bb0.get('error_type', '')!r}\n")
    case_lines.append(f"  - SQL: `{short(bb0['generated_sql'])}`\n")
    case_lines.append(f"- **B1:** match={bb1['execution_match']} executable={bb1['executable']} error={bb1.get('error_type', '')!r} selected_tables={bb1.get('selected_tables', [])}\n")
    case_lines.append(f"  - SQL: `{short(bb1['generated_sql'])}`\n")
    case_lines.append(f"- **B2:** match={bb2['execution_match']} executable={bb2['executable']} plan_valid={bb2.get('plan_valid', False)} error={bb2.get('error_type', '')!r}\n")
    case_lines.append(f"  - Plan parsed: `{json.dumps(bb2.get('plan_parsed'), ensure_ascii=False)[:200]}`\n")
    case_lines.append(f"  - SQL: `{short(bb2['generated_sql'])}`\n")
    if (bb0['execution_match'], bb1['execution_match'], bb2['execution_match']) == (True, True, True):
        comment = 'all three baselines correct'
    elif (bb0['execution_match'], bb1['execution_match'], bb2['execution_match']) == (False, False, False):
        comment = 'all three failed; planner did not rescue'
    elif bb2['execution_match'] and not (bb0['execution_match'] and bb1['execution_match']):
        comment = 'B2 rescued where simpler baselines were wrong'
    elif (bb0['execution_match'] or bb1['execution_match']) and not bb2['execution_match']:
        comment = 'B2 regressed vs simpler baseline (planner introduced an error)'
    else:
        comment = 'mixed outcome'
    case_lines.append(f"- **Comment:** {comment}\n")

(OUTPUTS / 'tables' / 'b0_b1_b2_smoke10_case_diff.md').write_text('\n'.join(case_lines), encoding='utf-8')

print(f'three-way: EX_B0={ex_b0:.4f} EX_B1={ex_b1:.4f} EX_B2={ex_b2:.4f} winner={winner}')
print(f'B2 plan_valid={plan_valid}/{n} parse_fail={plan_parse_fail}/{n}')
print(f'WROTE {csv_path}')
print(f'WROTE {md_path}')
print(f'WROTE {OUTPUTS / "plots" / "b0_b1_b2_smoke10_bar.png"}')
print(f'WROTE {OUTPUTS / "tables" / "b0_b1_b2_smoke10_case_diff.md"}')
print('STATUS=DONE')
