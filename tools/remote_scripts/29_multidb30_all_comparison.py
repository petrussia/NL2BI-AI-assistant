# Stage 6: comparison of B0, B1, B2_v1, B1R, B2R on multidb_30.

import csv
import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
for sub in ['plots','tables']: (OUTPUTS / sub).mkdir(parents=True, exist_ok=True)

def load_jsonl(p): return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
def load_csv_one(p): return list(csv.DictReader(p.open(encoding='utf-8')))[0]
def short(s, n=200):
    s = (s or '').replace('|','\\|').replace('\n',' ')
    return s if len(s) <= n else s[:n-3] + '...'

baselines = {
    'B0':    'b0_multidb30',
    'B1':    'b1_multidb30',
    'B2_v1': 'b2_v1_multidb30',
    'B1R':   'b1r_multidb30',
    'B2R':   'b2r_multidb30',
}

m = {}
preds = {}
for label, prefix in baselines.items():
    p = OUTPUTS / 'metrics' / f'{prefix}_metrics.csv'
    m[label] = load_csv_one(p) if p.exists() else None
    pj = OUTPUTS / 'predictions' / f'{prefix}_predictions.jsonl'
    preds[label] = load_jsonl(pj) if pj.exists() else []

def f(d, k):
    if not d or d.get(k) in (None, ''): return None
    try: return float(d[k])
    except Exception: return d.get(k)

def i(d, k):
    if not d or d.get(k) in (None, ''): return None
    try: return int(float(d[k]))
    except Exception: return d.get(k)

# CSV
csv_path = OUTPUTS / 'tables' / 'multidb30_all_baselines_comparison.csv'
with csv_path.open('w', newline='', encoding='utf-8') as f_:
    w = csv.writer(f_)
    w.writerow(['baseline', 'EX', 'executable_count', 'plan_valid_count', 'avg_reduction_ratio', 'retrieval_hit_count', 'n'])
    for label in baselines:
        d = m[label]
        if d is None:
            w.writerow([label, 'missing', '', '', '', '', '']); continue
        w.writerow([label,
                    f"{f(d,'ex'):.4f}" if f(d,'ex') is not None else '',
                    i(d,'executable_count'),
                    i(d,'plan_valid_count') if 'plan_valid_count' in d else '',
                    d.get('avg_reduction_ratio',''),
                    i(d,'retrieval_hit_count') if 'retrieval_hit_count' in d else '',
                    i(d,'n')])

# Winner
ex_map = {label: f(m[label], 'ex') for label in baselines if m[label]}
top = max(v for v in ex_map.values() if v is not None) if ex_map else None
winners = [k for k, v in ex_map.items() if v == top]
winner = winners[0] if len(winners) == 1 else 'tie ({})'.format(' = '.join(winners))

md_lines = [
    '# All Baselines on multidb_30',
    '',
    f'Checked at: {dt.datetime.now(dt.timezone.utc).isoformat()}',
    'Subset: multidb_30 (n=30, 6 unique DBs, no concert_singer).',
    'Model: Qwen/Qwen2.5-Coder-7B-Instruct (4-bit nf4 bitsandbytes), greedy decode.',
    '',
    '| Baseline | EX | Executable | Plan valid | Avg reduction | Retrieval hit | n |',
    '|---|---|---|---|---|---|---|',
]
for label in baselines:
    d = m[label]
    if d is None:
        md_lines.append(f'| {label} | missing | — | — | — | — | — |'); continue
    ex_v = f(d,'ex')
    md_lines.append(
        f"| {label} | {ex_v:.4f} | {i(d,'executable_count')} / {i(d,'n')} | "
        f"{(str(i(d,'plan_valid_count'))+' / '+str(i(d,'n'))) if 'plan_valid_count' in d else '—'} | "
        f"{d.get('avg_reduction_ratio','—')} | "
        f"{(str(i(d,'retrieval_hit_count'))+' / '+str(i(d,'n'))) if 'retrieval_hit_count' in d else '—'} | "
        f"{i(d,'n')} |"
    )
md_lines += ['',
             f'**Winner on multidb_30:** {winner}',
             '',
             '## Notes',
             '- B0 / B1 / B2_v1 use the gold `db_id` and only differ in how the schema is presented to the model.',
             '- B1R / B2R do NOT see the gold `db_id`; they retrieve over all 166 Spider DBs by lexical token overlap (db_id x3, table x2, column x1) and use the top-1 candidate.',
             '- "Retrieval hit" = top-1 retrieved DB equals gold `db_id`.',
             '- B2_v1 and B2R add a planner stage producing a JSON plan validated against `plan_schema_v1.json`. `plan_valid_count` is the upper bound of B2_v1 / B2R EX.',
             '']

(OUTPUTS / 'tables' / 'multidb30_all_baselines_comparison.md').write_text('\n'.join(md_lines), encoding='utf-8')

# Plot
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
labels = list(baselines.keys())
vals = [(f(m[L],'ex') or 0) for L in labels]
colors = ['#4C72B0','#55A868','#8172B2','#CCB974','#64B5CD']
fig, ax = plt.subplots(figsize=(8,4.5))
bars = ax.bar(labels, vals, color=colors)
for bar, v in zip(bars, vals):
    ax.text(bar.get_x()+bar.get_width()/2, v+0.02, f'{v:.2f}', ha='center', va='bottom', fontsize=11)
ax.set_ylim(0, 1.15)
ax.set_ylabel('EX (Execution Match)')
ax.set_title(f'All baselines on multidb_30 (n=30, 6 DBs)')
plt.tight_layout()
plt.savefig(OUTPUTS / 'plots' / 'multidb30_all_baselines_bar.png', dpi=140)
plt.close(fig)

# Case diff: pick interesting cases (any baseline differs from any other in match)
all_idxs = sorted({r['idx'] for label in baselines for r in preds[label]})
case_lines = ['# Case diff (multidb_30, all baselines)\n']
selected = []
for idx in all_idxs:
    by = {label: next((r for r in preds[label] if r['idx']==idx), None) for label in baselines}
    matches = tuple((b, (by[b]['execution_match'] if by[b] else None)) for b in baselines)
    distinct = len({m for _,m in matches if m is not None})
    if distinct > 1:
        selected.append((idx, by, matches))
    if len(selected) >= 8:
        break

for idx, by, matches in selected[:6]:
    sample = next((r for r in by.values() if r), None)
    if not sample: continue
    case_lines.append(f"## Case {idx} (gold db: {sample['db_id']})\n")
    case_lines.append(f"- **Question:** {short(sample['question'])}")
    case_lines.append(f"- **Gold SQL:** `{short(sample['gold_sql'])}`")
    for label in baselines:
        r = by[label]
        if r is None: continue
        extra = []
        if 'retrieved_db_id' in r: extra.append(f"retrieved={r['retrieved_db_id']}")
        if 'plan_valid' in r: extra.append(f"plan_valid={r['plan_valid']}")
        extras = ' '.join(extra)
        case_lines.append(f"- **{label}:** match={r['execution_match']} executable={r['executable']} err={r.get('error_type','')!r} {extras}")
        case_lines.append(f"  - SQL: `{short(r['generated_sql'])}`")
    case_lines.append('')

(OUTPUTS / 'tables' / 'multidb30_case_diff.md').write_text('\n'.join(case_lines) + '\n', encoding='utf-8')

print(f'winner={winner}')
for label in baselines:
    d = m[label]
    print(f"  {label}: EX={f(d,'ex')}  exec={i(d,'executable_count')}/{i(d,'n')}")
print(f'WROTE {csv_path}')
print(f'WROTE {OUTPUTS / "tables" / "multidb30_all_baselines_comparison.md"}')
print(f'WROTE {OUTPUTS / "plots" / "multidb30_all_baselines_bar.png"}')
print(f'WROTE {OUTPUTS / "tables" / "multidb30_case_diff.md"}')
print('STATUS=DONE')
