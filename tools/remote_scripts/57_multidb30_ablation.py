# Multidb_30 ablation: read all per-baseline metrics + build comparison.

import csv
import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
ts = dt.datetime.now(dt.timezone.utc).isoformat()


def load_metrics(prefix):
    p = OUTPUTS / 'metrics' / f'{prefix}_metrics.csv'
    if not p.exists(): return None
    return list(csv.DictReader(p.open(encoding='utf-8')))[0]


def f(d, k):
    if not d or d.get(k) in (None, ''): return None
    try: return float(d[k])
    except Exception: return d.get(k)


def i(d, k):
    if not d or d.get(k) in (None, ''): return None
    try: return int(float(d[k]))
    except Exception: return d.get(k)


labels = [
    ('B0', 'b0_multidb30_v2'),
    ('B1', 'b1_multidb30_v2'),
    ('B2_v1', 'b2v1_multidb30'),
    ('B3_v1', 'b3v1_multidb30'),
    ('B4_final', 'b4_final_multidb30'),
]
m = {label: load_metrics(prefix) for label, prefix in labels}

# CSV
csv_path = OUTPUTS / 'tables' / 'multidb30_ablation.csv'
with csv_path.open('w', newline='', encoding='utf-8') as fh:
    w = csv.writer(fh)
    w.writerow(['baseline', 'EX', 'executable_count', 'plan_valid_count', 'avg_reduction_ratio', 'n', 'notes'])
    for label, prefix in labels:
        d = m[label]
        if d is None:
            w.writerow([label, 'missing', '', '', '', '', f'no metrics file at outputs/metrics/{prefix}_metrics.csv'])
            continue
        notes = ''
        if 'plan_parse_failures' in d: notes = f"plan_parse_fail={d['plan_parse_failures']}"
        if 'repaired_count' in d: notes = (notes + ' ' if notes else '') + f"repaired={d['repaired_count']}"
        w.writerow([label, f(d,'ex'), i(d,'executable_count'),
                    i(d,'plan_valid_count') if 'plan_valid_count' in d else '',
                    d.get('avg_reduction_ratio',''),
                    i(d,'n'), notes])

# MD narrative
ex_map = {label: f(m[label],'ex') for label,_ in labels if m[label]}
top = max(v for v in ex_map.values() if v is not None) if ex_map else None
winners = [k for k,v in ex_map.items() if v == top]
winner = winners[0] if len(winners)==1 else 'tie ({})'.format(' = '.join(winners))

md = ['# Multi-DB Ablation (multidb_30)', '',
      f'Generated at: {ts}',
      'Subset: multidb_30 (n=30, 6 unique DBs).',
      'Model: Qwen2.5-Coder-7B-Instruct (4-bit nf4 bitsandbytes).',
      '',
      '| Baseline | EX | Executable | Plan valid | Avg reduction | n | Notes |',
      '|---|---|---|---|---|---|---|']
for label, prefix in labels:
    d = m[label]
    if d is None:
        md.append(f'| {label} | — | — | — | — | — | (run missing) |'); continue
    ex_v = f(d,'ex')
    pv = f"{i(d,'plan_valid_count')}/{i(d,'n')}" if 'plan_valid_count' in d else '—'
    notes = []
    if 'plan_parse_failures' in d: notes.append(f"parse_fail={d['plan_parse_failures']}")
    if 'repaired_count' in d: notes.append(f"repaired={d['repaired_count']}")
    if 'rejected_unsafe_total' in d: notes.append(f"rejected_unsafe={d['rejected_unsafe_total']}")
    md.append(f"| {label} | {ex_v:.4f} | {i(d,'executable_count')}/{i(d,'n')} | {pv} | {d.get('avg_reduction_ratio','—')} | {i(d,'n')} | {' '.join(notes) or '—'} |")
md += ['', f'**Winner on multidb_30:** {winner}', '',
       '## Interpretation',
       '- B0 has access to gold db_id (so it does not perform retrieval). Same for B1/B2_v1/B3_v1/B4_final on this subset.',
       '- Multi-DB benchmark stresses the schema-linker and (partially) the planner: questions span 6 different DBs.',
       '- If B1 keeps EX close to B0, the linker is information-equivalent (not harmful).',
       '- If B3_v1 EX > B2_v1 EX, the dual-retrieval channel is contributing on multi-DB.',
       '- If B4_final EX > B3_v1 EX, the multi-candidate + safety + repair stack is paying off.',
       '']

(OUTPUTS / 'tables' / 'multidb30_ablation.md').write_text('\n'.join(md) + '\n', encoding='utf-8')

# Plot
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
present = [(L, f(m[L],'ex')) for L,_ in labels if m[L] and f(m[L],'ex') is not None]
fig, ax = plt.subplots(figsize=(8, 4.5))
if present:
    L = [a for a,_ in present]; V = [b for _,b in present]
    colors = ['#4C72B0','#55A868','#8172B2','#CCB974','#C44E52'][:len(L)]
    bars = ax.bar(L, V, color=colors)
    for bar, v in zip(bars, V):
        ax.text(bar.get_x()+bar.get_width()/2, v+0.02, f'{v:.2f}', ha='center', va='bottom', fontsize=11)
    ax.set_ylim(0, 1.15)
ax.set_ylabel('EX (Execution Match)')
ax.set_title('Multi-DB ablation on multidb_30 (Qwen2.5-Coder-7B-Instruct)')
plt.tight_layout()
plt.savefig(OUTPUTS / 'plots' / 'multidb30_ablation.png', dpi=140)
plt.close(fig)

print(f'winner={winner}')
for L, _ in labels:
    d = m[L]
    print(f"  {L}: EX={f(d,'ex')}  exec={i(d,'executable_count')}/{i(d,'n')}")
print(f'WROTE {csv_path}')
print(f'WROTE {OUTPUTS / "tables" / "multidb30_ablation.md"}')
print(f'WROTE {OUTPUTS / "plots" / "multidb30_ablation.png"}')
print('STATUS=DONE')
