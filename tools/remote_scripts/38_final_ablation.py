# Stage 7 (a): final ablation summary table + plot.

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


# ---- Qwen Coder 7B baselines ----
qwen = {
    'B0': load_metrics('b0_spider_smoke10'),
    'B1': load_metrics('b1_spider_smoke10'),
    'B2_v0': load_metrics('b2_spider_smoke10'),
    'B2_v1': load_metrics('b2_v1_spider_smoke10'),
    'B3': load_metrics('b3_spider_smoke10'),
    'B4-lite': load_metrics('b4_spider_smoke10'),
}

qwen25 = {
    'B0': load_metrics('b0_spider_smoke25'),
    'B1': load_metrics('b1_spider_smoke25'),
    'B2_v1': load_metrics('b2_v1_spider_smoke25'),
}

# ---- Cross-model baselines (whatever loaded successfully) ----
import os
import re
crossm = {}
for p in (OUTPUTS / 'metrics').iterdir():
    name = p.stem  # e.g. b0_qwen_qwen2.5_7b_instruct_smoke10_metrics
    m = re.match(r'^(b[01])_(.+?)_smoke10_metrics$', name) if name.endswith('_metrics') else None
    if m:
        prefix_baseline = m.group(1).upper()
        model_slug = m.group(2)
        if model_slug in ('spider',):
            continue
        # exclude our main Qwen Coder runs (they're captured above as "spider")
        crossm.setdefault(model_slug, {})[prefix_baseline] = load_metrics(f'{prefix_baseline.lower()}_{model_slug}_smoke10')


def f(d, k):
    if not d or d.get(k) in (None, ''): return None
    try: return float(d[k])
    except Exception: return d.get(k)


# ---- CSV: Qwen Coder ablation on smoke10 ----
csv_path = OUTPUTS / 'tables' / 'final_ablation_summary.csv'
with csv_path.open('w', newline='', encoding='utf-8') as fh:
    w = csv.writer(fh)
    w.writerow(['model','baseline','subset','EX','executable_count','plan_valid_count','avg_reduction_ratio','n','notes'])
    for label, m in qwen.items():
        if m is None:
            w.writerow(['Qwen2.5-Coder-7B-Instruct',label,'smoke_10','missing','','','','','run not present'])
            continue
        notes = ''
        if 'avg_reduction_ratio' in m: notes = f"reduction={m['avg_reduction_ratio']}"
        w.writerow(['Qwen2.5-Coder-7B-Instruct', label, 'smoke_10',
                    f(m,'ex'), m.get('executable_count',''),
                    m.get('plan_valid_count',''),
                    m.get('avg_reduction_ratio',''),
                    m.get('n',''), notes])
    for label, m in qwen25.items():
        if m is None:
            w.writerow(['Qwen2.5-Coder-7B-Instruct',label,'smoke_25','missing','','','','','run not present'])
            continue
        w.writerow(['Qwen2.5-Coder-7B-Instruct', label, 'smoke_25',
                    f(m,'ex'), m.get('executable_count',''),
                    m.get('plan_valid_count',''),
                    m.get('avg_reduction_ratio',''),
                    m.get('n',''), ''])
    for model_slug, by_baseline in crossm.items():
        for label, m in by_baseline.items():
            if m is None: continue
            w.writerow([m.get('model', model_slug), label, 'smoke_10',
                        f(m,'ex'), m.get('executable_count',''),
                        m.get('plan_valid_count',''),
                        m.get('avg_reduction_ratio',''),
                        m.get('n',''), 'cross-model comparator'])

# ---- MD: human-readable ----
md = ['# Final Ablation Summary', '',
      f'Generated at: {ts}', '',
      '## Qwen2.5-Coder-7B-Instruct (primary model) on smoke10',
      '',
      '| Baseline | EX | Executable | Plan valid | Avg reduction | Notes |',
      '|---|---|---|---|---|---|']
for label, m in qwen.items():
    if m is None:
        md.append(f'| {label} | — | — | — | — | not run |'); continue
    ex = f(m,'ex'); ex_str = f'{ex:.4f}' if isinstance(ex,float) else str(ex)
    pv = m.get('plan_valid_count','—'); ar = m.get('avg_reduction_ratio','—')
    md.append(f"| {label} | {ex_str} | {m.get('executable_count','—')} / {m.get('n','—')} | {pv} | {ar} | |")

md += ['', '## Qwen2.5-Coder-7B-Instruct on smoke25',
       '',
       '| Baseline | EX | Executable | Plan valid | Avg reduction | Notes |',
       '|---|---|---|---|---|---|']
for label, m in qwen25.items():
    if m is None:
        md.append(f'| {label} | — | — | — | — | not run (deferred / lost-bridge incident) |'); continue
    ex = f(m,'ex'); ex_str = f'{ex:.4f}' if isinstance(ex,float) else str(ex)
    md.append(f"| {label} | {ex_str} | {m.get('executable_count','—')} / {m.get('n','—')} | {m.get('plan_valid_count','—')} | {m.get('avg_reduction_ratio','—')} | |")

md += ['', '## Cross-model comparator(s) on smoke10', '']
if not crossm:
    md.append('_No cross-model comparator runs are present yet. The model-swap stage may be queued or skipped._')
else:
    md.append('| Model | Baseline | EX | Executable | Notes |')
    md.append('|---|---|---|---|---|')
    for model_slug, by_baseline in crossm.items():
        for label, m in by_baseline.items():
            if m is None: continue
            ex = f(m,'ex'); ex_str = f'{ex:.4f}' if isinstance(ex,float) else str(ex)
            md.append(f"| `{m.get('model', model_slug)}` | {label} | {ex_str} | {m.get('executable_count','—')} / {m.get('n','—')} | comparator |")

(OUTPUTS / 'tables' / 'final_ablation_summary.md').write_text('\n'.join(md) + '\n', encoding='utf-8')

# ---- Plot: Qwen Coder ablation on smoke10 ----
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
labels = []
vals = []
for L, m in qwen.items():
    if m is None: continue
    v = f(m,'ex')
    if v is None: continue
    labels.append(L); vals.append(v)
fig, ax = plt.subplots(figsize=(8,4.5))
colors = ['#4C72B0','#55A868','#C44E52','#8172B2','#CCB974','#64B5CD']
bars = ax.bar(labels, vals, color=colors[:len(labels)])
for bar, v in zip(bars, vals):
    ax.text(bar.get_x()+bar.get_width()/2, v+0.02, f'{v:.2f}', ha='center', va='bottom', fontsize=11)
ax.set_ylim(0, 1.15)
ax.set_ylabel('EX (Execution Match)')
ax.set_title('Final ablation on Spider smoke10 (Qwen2.5-Coder-7B-Instruct)')
plt.tight_layout()
plt.savefig(OUTPUTS / 'plots' / 'final_ablation_overview.png', dpi=140)
plt.close(fig)

print(f'WROTE {csv_path}')
print(f'WROTE {OUTPUTS / "tables" / "final_ablation_summary.md"}')
print(f'WROTE {OUTPUTS / "plots" / "final_ablation_overview.png"}')
print(f'qwen labels included: {labels}')
print(f'cross-model models seen: {sorted(crossm.keys())}')
print('STATUS=DONE')
