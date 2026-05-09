# Final consolidation v2: master matrix + scientific findings + plot.

import csv
import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'

ROWS = []
for p in sorted((OUTPUTS/'metrics').glob('*_metrics.csv')):
    try:
        row = next(csv.DictReader(p.open(encoding='utf-8')))
    except Exception:
        continue
    ROWS.append({
        'baseline': row.get('run_id','').split('_')[0],
        'run_id': row.get('run_id',''),
        'model': row.get('model',''),
        'subset': row.get('subset',''),
        'n': row.get('n',''),
        'EX': row.get('ex',''),
        'executable_count': row.get('executable_count',''),
        'plan_valid_count': row.get('plan_valid_count',''),
        'avg_reduction': row.get('avg_reduction_ratio',''),
        'fallback_policy': row.get('fallback_policy',''),
    })

mcsv = OUTPUTS/'tables'/'final_experiment_master_matrix.csv'
with mcsv.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(ROWS[0].keys()) if ROWS else
                       ['baseline','run_id','model','subset','n','EX','executable_count','plan_valid_count','avg_reduction','fallback_policy'])
    w.writeheader()
    for r in ROWS: w.writerow(r)

# Markdown master
def fmt_ex(x):
    try: return f'{float(x):.4f}'
    except: return '—'
def fmt_n(x): return str(x) if x else '—'

mmd = OUTPUTS/'tables'/'final_experiment_master_matrix.md'
hdr = ['Run','Baseline','Model','Subset','n','EX','Executable','Plan-valid','Avg-red','Fallback']
lines = ['# Final Experiment Master Matrix',
         f'Generated: {dt.datetime.now(dt.timezone.utc).isoformat()}',
         '',
         '|'+'|'.join(hdr)+'|',
         '|'+'|'.join(['---']*len(hdr))+'|']
for r in ROWS:
    lines.append('|' + '|'.join([
        r['run_id'], r['baseline'], r['model'].replace('Qwen/','').replace('-Instruct',''),
        r['subset'], fmt_n(r['n']), fmt_ex(r['EX']),
        r['executable_count'] or '—', r['plan_valid_count'] or '—',
        r['avg_reduction'] or '—', r['fallback_policy'] or '—',
    ]) + '|')
mmd.write_text('\n'.join(lines)+'\n', encoding='utf-8')

# Plot
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    by_subset = {'smoke_10':{}, 'smoke_25':{}, 'multidb_30':{}}
    for r in ROWS:
        if r['model'] != 'Qwen/Qwen2.5-Coder-7B-Instruct': continue
        sub = r['subset']
        if sub not in by_subset: continue
        b = r['baseline']
        try: by_subset[sub][b] = float(r['EX'])
        except: pass

    baseline_order = ['B0','B1','B2','B2v1','B3','B3v1','B3v2','B4','B4v2','B4final']
    fig, ax = plt.subplots(figsize=(13, 5.5))
    width = 0.27
    xs = np.arange(len(baseline_order))
    colors = {'smoke_10':'#3b78a7','smoke_25':'#7fa75d','multidb_30':'#c75b3d'}
    for offset, sub in zip([-width, 0.0, +width], ['smoke_10','smoke_25','multidb_30']):
        ys = [by_subset[sub].get(b, 0) for b in baseline_order]
        bars = ax.bar(xs + offset, ys, width, label=sub, color=colors[sub])
        for x, y, b in zip(xs+offset, ys, bars):
            if y > 0:
                ax.text(x, y + 0.01, f'{y:.2f}', ha='center', fontsize=7)
    ax.set_xticks(xs)
    ax.set_xticklabels(baseline_order)
    ax.set_ylabel('Execution Match (EX)')
    ax.set_ylim(0, 1.10)
    ax.set_title('Final master matrix — EX by baseline × subset (Qwen2.5-Coder-7B)')
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(axis='y', linestyle=':', alpha=0.4)
    fig.tight_layout()
    plot_path = OUTPUTS/'plots'/'final_experiment_master_overview.png'
    fig.savefig(plot_path, dpi=130)
    plt.close(fig)
except Exception as exc:
    plot_path = f'(plot_error: {exc})'

# Scientific findings
findings = OUTPUTS/'logs'/'final_scientific_findings.md'

def best_for(subset, predicate=lambda r: True):
    cands = [r for r in ROWS if r['subset']==subset and r['model']=='Qwen/Qwen2.5-Coder-7B-Instruct' and predicate(r)]
    cands = [r for r in cands if r['EX']]
    if not cands: return None
    cands.sort(key=lambda r: -float(r['EX']))
    return cands[0]

best_direct_s10 = best_for('smoke_10', lambda r: r['baseline'] in ('B0','B1'))
best_struct_s10 = best_for('smoke_10', lambda r: r['baseline'] not in ('B0','B1'))
best_direct_md = best_for('multidb_30', lambda r: r['baseline'] in ('B0','B1'))
best_struct_md = best_for('multidb_30', lambda r: r['baseline'] not in ('B0','B1'))

def line(r):
    return f'`{r["run_id"]}` EX={float(r["EX"]):.4f} (n={r["n"]})' if r else '—'

text = f'''# Final scientific findings

**Generated:** {dt.datetime.now(dt.timezone.utc).isoformat()}

## 1. Best direct baseline (B0/B1)
- smoke_10: {line(best_direct_s10)}
- multidb_30: {line(best_direct_md)}

## 2. Best retrieval/planning baseline (B2*/B3*/B4*)
- smoke_10: {line(best_struct_s10)}
- multidb_30: {line(best_struct_md)}

## 3. Where schema linking helps / hurts
- On smoke_10/25 with Qwen-Coder-7B: B0 = B1 = 1.0 / 0.96. Schema linking is
  information-equivalent: the lex linker reduces the prompt by ~50% with no
  EX cost on small Spider DBs.
- On multidb_30 (6 distinct DBs, more diverse schemas): B0 = 0.93, B1 = 0.77.
  The lex linker over-prunes when the question vocabulary does not lexically
  match column or table names. **Schema linking actively hurts on
  schema-diverse benchmarks.**

## 4. Where the planner helps / hurts
- The B2/B3/B4 family **never beats B0** on any subset evaluated.
- B3 and B4-lite catastrophically regressed (EX = 0.20 on smoke_10) because the
  synthesised "knowledge channel" inflated the planner prompt without adding
  signal beyond what schema linking already carried.
- B3_v1 / B4_final partially fixed this with adaptive policy, but the planner
  itself remained a bottleneck: when the JSON was malformed, the entire
  pipeline failed for that item.
- B3_v2 / B4_v2 add an unconditional **B1 fallback** at the planner-failure
  boundary, which guarantees that the layered baseline cannot regress *below*
  B1. This is a structural fix, not an accuracy improvement.

## 5. What multidb_30 reveals
The multi-DB subset is the hardest test in this evaluation slice.
On it, B0 (full schema, single-shot) **dominates everything else by 0.16+ EX
points**. This is the cleanest evidence in the project that, for a benchmark
where the base model can already read the full schema and write correct SQL,
no amount of schema linking, planning, or repair recovers lost ground —
they each remove information or add failure modes.

## 6. How to interpret the negative results
The diploma's experimental contribution is therefore TWO-FOLD:

1. **Positive contribution (engineering):** A complete NL→SQL pipeline with
   query analysis, lex schema linking, JSON-validated plan generation, dual
   retrieval, multi-candidate sampling with consistency selection, bounded
   repair, AST-level safety guard, post-processing and analytics handoff.
   Every layer is implemented and exercised.

2. **Negative contribution (scientific):** On Spider with a strong code-aware
   base model (Qwen-Coder-7B-Instruct in 4-bit), every layer above B0/B1
   either *does not improve* EX or *actively reduces* it. The right
   architecture for this task on this hardware is **B0 with full schema
   prompt, single-shot SQL, with a SELECT-only AST guard and execution
   sandbox**. The planner stack only pays off on tasks where single-shot
   SQL is already failing, which is *not* the case on Spider for this model.

## 7. What can be claimed at defense
- "The proposed pipeline is fully implemented and reproducible." ✅
- "On Spider+Qwen-Coder, the simplest direct baseline saturates the
  benchmark. The retrieval/planner stack adds engineering safety (validation,
  repair, fallback) but does not improve EX, and on harder schema-diverse
  subsets it can hurt." ✅
- "The mandatory model block is partially closed: Qwen-Coder fully evaluated
  across 3 subsets, Qwen-Instruct cross-model on 1 subset; Llama-3.1-8B
  blocked by HF_TOKEN absence; DeepSeek-V2-Lite blocked by transformers
  version mismatch in the trust-remote-code modeling file." ✅
- We can NOT honestly claim "the planner stack improves accuracy on this
  benchmark." That would be a misrepresentation. Defense narrative must own
  the negative result and frame it as a finding about benchmark difficulty
  vs base-model capability.
'''
findings.write_text(text, encoding='utf-8')

# System status
status = OUTPUTS/'logs'/'final_system_status.md'
status.write_text(textwrap.dedent(f'''
# Final system status — v2

Generated: {dt.datetime.now(dt.timezone.utc).isoformat()}

- Total experiment rows: {len(ROWS)}
- Master matrix CSV: `{mcsv.relative_to(PROJECT_ROOT)}`
- Master matrix MD: `{mmd.relative_to(PROJECT_ROOT)}`
- Master plot: `{Path(plot_path).relative_to(PROJECT_ROOT) if isinstance(plot_path, Path) else plot_path}`
- Findings: `{findings.relative_to(PROJECT_ROOT)}`
''').strip()+'\n' if False else '', encoding='utf-8')

import textwrap
status_text = textwrap.dedent(f'''
# Final system status — v2

Generated: {dt.datetime.now(dt.timezone.utc).isoformat()}

- Total experiment rows: {len(ROWS)}
- Master matrix CSV: `{mcsv.relative_to(PROJECT_ROOT)}`
- Master matrix MD: `{mmd.relative_to(PROJECT_ROOT)}`
- Master plot: `outputs/plots/final_experiment_master_overview.png`
- Findings: `{findings.relative_to(PROJECT_ROOT)}`
- Negative result analysis: `outputs/logs/final_negative_result_analysis.md`
- DeepSeek blocker: `outputs/logs/deepseek_blocker_final.md`
- Llama blocker: `outputs/logs/llama_blocker_final.md`
''').strip()+'\n'
status.write_text(status_text, encoding='utf-8')

print(f'WROTE {mcsv}')
print(f'WROTE {mmd}')
print(f'WROTE {findings}')
print(f'WROTE {status}')
print(f'PLOT={plot_path}')
print(f'rows={len(ROWS)}')
