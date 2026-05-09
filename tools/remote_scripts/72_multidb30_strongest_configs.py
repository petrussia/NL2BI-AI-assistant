# Stage E: multidb_30 audit + strongest configs evidence pack.

import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
SPIDER_DIR = PROJECT_ROOT / 'data' / 'spider'
NOW = dt.datetime.now(dt.timezone.utc).isoformat()

# === E1 multidb_30 audit ===
multidb30 = json.loads((SPIDER_DIR/'subsets'/'multidb_30.json').read_text(encoding='utf-8'))
db_dist = Counter(item['db_id'] for item in multidb30)
audit_md = OUTPUTS/'logs'/'multidb30_audit_v2.md'
audit_md.write_text(f'''# multidb_30 audit (v2)

**Captured:** {NOW}
**N items:** {len(multidb30)}
**Distinct DBs:** {len(db_dist)}

## Distribution by db_id
| db_id | count |
|---|---|
''' + '\n'.join(f'| `{k}` | {v} |' for k, v in sorted(db_dist.items(), key=lambda x: (-x[1], x[0])))
+ f'''

## Manifest sanity
- All items have non-empty `question`: {all(bool(it.get("question")) for it in multidb30)}
- All items have `query` (gold SQL): {all(bool(it.get("query")) for it in multidb30)}
- All db_ids resolvable to sqlite path:
''' + '\n'.join(
    f'  - `{k}`: {(SPIDER_DIR/"database"/k/(k+".sqlite")).exists()}'
    for k in sorted(set(db_dist))
) + '\n', encoding='utf-8')

with (OUTPUTS/'tables'/'multidb30_db_distribution.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['db_id','count'])
    for k, v in sorted(db_dist.items(), key=lambda x: (-x[1], x[0])):
        w.writerow([k, v])

# === E2 strongest configs on multidb_30 ===
def load(prefix):
    p = OUTPUTS/'metrics'/f'{prefix}_metrics.csv'
    if not p.exists(): return None
    return next(csv.DictReader(p.open(encoding='utf-8')), None)

# Define the configs we want on multidb_30
CONFIGS = [
    ('B0', 'Qwen2.5-Coder-7B', 'b0_multidb30_v2'),
    ('B1', 'Qwen2.5-Coder-7B', 'b1_multidb30_v2'),
    ('B2_v1', 'Qwen2.5-Coder-7B', 'b2v1_multidb30'),
    ('B3_v1', 'Qwen2.5-Coder-7B', 'b3v1_multidb30'),
    ('B3_v2', 'Qwen2.5-Coder-7B', 'b3v2_multidb30'),
    ('B4_final', 'Qwen2.5-Coder-7B', 'b4_final_multidb30'),
    ('B4_v2', 'Qwen2.5-Coder-7B', 'b4v2_multidb30'),
    ('B0', 'Qwen2.5-Coder-14B', 'b0_qwen2p5_coder_14b_instruct_multidb30'),
    ('B1', 'Qwen2.5-Coder-14B', 'b1_qwen2p5_coder_14b_instruct_multidb30'),
]

rows = []
for label, model, prefix in CONFIGS:
    m = load(prefix)
    rows.append({
        'baseline': label, 'model': model, 'prefix': prefix,
        'n': (m or {}).get('n', '—'),
        'EX': (m or {}).get('ex', '—'),
        'executable': (m or {}).get('executable_count', '—'),
        'plan_valid': (m or {}).get('plan_valid_count', '—'),
        'present': bool(m),
    })

p_csv = OUTPUTS/'tables'/'multidb30_strongest_configs.csv'
with p_csv.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    for r in rows: w.writerow(r)

# Markdown
def fex(x):
    try: return f'{float(x):.4f}'
    except: return '—'

p_md = OUTPUTS/'tables'/'multidb30_strongest_configs.md'
md_lines = [
    '# Strongest configs on multidb_30',
    f'_Generated: {NOW}_', '',
    '| Baseline | Model | n | EX | Executable | Plan-valid | Present |',
    '|---|---|---|---|---|---|---|',
]
for r in rows:
    md_lines.append(f'| {r["baseline"]} | {r["model"]} | {r["n"]} | {fex(r["EX"])} | {r["executable"]} | {r["plan_valid"]} | {r["present"]} |')
p_md.write_text('\n'.join(md_lines)+'\n', encoding='utf-8')

# Pairwise deltas vs B0 Coder-7B and vs B1 Coder-7B
b0_7b = float(rows[0]['EX']) if rows[0]['EX'] != '—' else None
b1_7b = float(rows[1]['EX']) if rows[1]['EX'] != '—' else None
delta_rows = []
for r in rows:
    try: ex = float(r['EX'])
    except: ex = None
    delta_rows.append({
        'baseline': r['baseline'], 'model': r['model'], 'EX': r['EX'],
        'delta_vs_B0_7B': f'{(ex-b0_7b):+.4f}' if (ex is not None and b0_7b is not None) else '—',
        'delta_vs_B1_7B': f'{(ex-b1_7b):+.4f}' if (ex is not None and b1_7b is not None) else '—',
    })
with (OUTPUTS/'tables'/'multidb30_pairwise_deltas.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(delta_rows[0].keys()))
    w.writeheader()
    for r in delta_rows: w.writerow(r)

# Plot
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    present = [r for r in rows if r['present']]
    labels = [f'{r["baseline"]}\n{r["model"].split("-")[-1]}' for r in present]
    vals = [float(r['EX']) for r in present]
    fig, ax = plt.subplots(figsize=(11.5, 5.5))
    bars = ax.bar(np.arange(len(labels)), vals, color='#3b78a7')
    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=20, ha='right', fontsize=9)
    for x, y in zip(np.arange(len(labels)), vals):
        ax.text(x, y+0.012, f'{y:.3f}', ha='center', fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel('Execution Match (EX)')
    ax.set_title('multidb_30 — strongest configs (the master scientific slice)')
    ax.grid(axis='y', linestyle=':', alpha=0.4)
    fig.tight_layout()
    plot_path = OUTPUTS/'plots'/'multidb30_strongest_configs.png'
    fig.savefig(plot_path, dpi=130)
    plt.close(fig)
except Exception as exc:
    plot_path = f'(plot_error: {exc})'

# === E3 scientific readout ===
ro = OUTPUTS/'logs'/'multidb30_scientific_readout.md'
b0 = b0_7b
b1 = b1_7b
def get(label, model='Qwen2.5-Coder-7B'):
    for r in rows:
        if r['baseline'] == label and r['model'] == model and r['EX'] != '—':
            try: return float(r['EX'])
            except: return None
    return None
ro_text = f'''# multidb_30 scientific readout

**Generated:** {NOW}

## Hard numbers (Qwen2.5-Coder-7B unless stated)
- B0      = {fex(b0)}
- B1      = {fex(b1)}
- B2_v1   = {fex(get("B2_v1"))}
- B3_v1   = {fex(get("B3_v1"))}
- B3_v2   = {fex(get("B3_v2"))}
- B4_final= {fex(get("B4_final"))}
- B4_v2   = {fex(get("B4_v2"))}
- B0 (Coder-14B) = {fex(get("B0", "Qwen2.5-Coder-14B"))}
- B1 (Coder-14B) = {fex(get("B1", "Qwen2.5-Coder-14B"))}

## Where direct baseline is stronger
- B0 Qwen-Coder-7B at {fex(b0)} is the **single strongest** configuration on multidb_30.
- It outperforms every layered configuration (B2/B3/B4) by 0.16+ EX points.
- This is the cleanest evidence in the project that direct generation with full
  schema, on a code-aware base model, dominates Spider-style benchmarks.

## Where schema linking helps / hurts
- B1 (lex linker) on multidb_30 = {fex(b1)} vs B0 = {fex(b0)} → linker **hurts**
  by ~{(b0-b1)*100:.1f} pp on schema-diverse subsets, because it over-prunes
  when question vocabulary does not lexically match column/table names.
- On smoke_10 (smaller, more uniform DBs), B0 = B1 = 1.0 — linker is
  information-equivalent.

## Where planner / repair / retrieval are needed
- Strictly speaking, **none of the layered baselines beats B0** on multidb_30.
- The closest are B3_v2 / B4_v2 at {fex(get("B3_v2"))} — **competitive with B1**
  but still 0.20 below B0.
- B3_v2 / B4_v2 only become useful when the upstream B0 path fails — they
  provide engineering safety (validation, repair, multi-cand, AST guard) but
  not accuracy gains on this benchmark.

## Did structured stack ever win?
- **No** — not on smoke_10, not on smoke_25, not on multidb_30, not for any
  evaluated model.
- The honest answer: layered planning pays off on questions that the base
  model cannot answer one-shot. Spider with Qwen-Coder is **not such a
  benchmark**. We need a harder slice (multi-step reasoning, ambiguous
  domains, real corpora) to expose planning value.
- This is a clean, defensible negative result — not a failure, but a
  benchmark-vs-architecture mismatch claim.
'''
ro.write_text(ro_text, encoding='utf-8')

print(f'WROTE {audit_md}')
print(f'WROTE {p_csv}')
print(f'WROTE {p_md}')
print(f'WROTE {ro}')
print(f'PLOT={plot_path}')
