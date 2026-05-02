# Phase 9-10 add-on: plots + Spider2-Lite structural metrics + final export pack.
# Should be run AFTER 109_full_benchmark_consolidation.py.
from __future__ import annotations
import json, os, math, glob, time, csv, re, tarfile, shutil
from pathlib import Path
from collections import Counter, defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
PRED = ROOT / 'outputs' / 'predictions'
TBL = ROOT / 'outputs' / 'tables'
LOG = ROOT / 'outputs' / 'logs'
PLT = ROOT / 'outputs' / 'plots'
EXP = ROOT / 'outputs' / 'exports'
PLT.mkdir(parents=True, exist_ok=True)
EXP.mkdir(parents=True, exist_ok=True)

# -------- Load master matrix --------
mm = []
with (TBL / 'full_benchmark_master_matrix.csv').open(encoding='utf-8') as f:
    for r in csv.DictReader(f):
        for k in ('EX','EX_lo','EX_hi','exec_pct','safe_pct','lat_p50','lat_p95',
                  'fallback_pct','planner_used_pct','plan_valid_pct','repair_used_pct',
                  'prompt_chars_p50','completion_tokens_p50','total_runtime_s'):
            v = r.get(k)
            r[k] = float(v) if v not in ('', None) else None
        r['N'] = int(r.get('N') or 0)
        mm.append(r)

ps = []
with (TBL / 'full_benchmark_paired_stats.csv').open(encoding='utf-8') as f:
    for r in csv.DictReader(f):
        for k in ('A_em','B_em','diff_pp','mcnemar_p','boot_lo_pp','boot_hi_pp'):
            v = r.get(k)
            r[k] = float(v) if v not in ('', None) else None
        for k in ('n','a_only','b_only','both','neither'):
            r[k] = int(r[k])
        ps.append(r)

# -------- PLOT 1: per-cell EX bar chart with Wilson CI --------
fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
for ax, bench, ttl in zip(axes, ['spider_dev','bird_full'],
                           ['Spider dev (1034)','BIRD Mini-Dev (500)']):
    cells = [r for r in mm if r['benchmark']==bench and r['EX'] is not None]
    cells.sort(key=lambda r: ['B0','B1_v3','B3_v4','B2_v4'].index(r['baseline']) if r['baseline'] in ['B0','B1_v3','B3_v4','B2_v4'] else 99)
    xs = [r['baseline'] for r in cells]
    ys = [r['EX']*100 for r in cells]
    err_lo = [r['EX']*100 - r['EX_lo']*100 for r in cells]
    err_hi = [r['EX_hi']*100 - r['EX']*100 for r in cells]
    colors = {'B0':'#3a82f6','B1_v3':'#f6a93a','B3_v4':'#22c55e','B2_v4':'#ef4444'}
    bars = ax.bar(xs, ys, yerr=[err_lo, err_hi], capsize=5,
                   color=[colors.get(b,'#aaaaaa') for b in xs], edgecolor='black', linewidth=0.6)
    for bar, y in zip(bars, ys):
        ax.text(bar.get_x()+bar.get_width()/2, y+0.5, f'{y:.1f}%', ha='center', fontsize=10, fontweight='bold')
    ax.set_title(ttl); ax.set_ylabel('Execution Match (%)'); ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(0, max(ys)*1.25 if ys else 100)
fig.suptitle('Full-benchmark Execution Match — Qwen2.5-Coder-7B (Wilson 95% CI)', fontsize=13, fontweight='bold')
fig.tight_layout()
p1 = PLT / 'full_benchmark_ex_per_cell.png'
fig.savefig(p1, dpi=140, bbox_inches='tight')
plt.close(fig)
print(f'wrote {p1}')

# -------- PLOT 2: paired diff with bootstrap CI (forest plot) --------
fig, ax = plt.subplots(figsize=(10, max(4, 0.45*len(ps))))
ps_plot = [r for r in ps if r['n']>0]
ps_plot = list(reversed(ps_plot))  # so first row is on top
labels = [f'{r["bench"]}: {r["B"]} − {r["A"]}' for r in ps_plot]
diffs = [r['diff_pp'] for r in ps_plot]
los = [r['boot_lo_pp'] for r in ps_plot]
his = [r['boot_hi_pp'] for r in ps_plot]
ys = list(range(len(ps_plot)))
ax.errorbar(diffs, ys, xerr=[[d-l for d,l in zip(diffs,los)], [h-d for d,h in zip(diffs,his)]],
             fmt='o', color='#1e293b', ecolor='#64748b', capsize=4, markersize=8)
for y, d, p in zip(ys, diffs, [r['mcnemar_p'] for r in ps_plot]):
    sig = 'p<0.001' if p<0.001 else f'p={p:.3f}'
    ax.text(d + (1.3 if d>=0 else -1.3), y,
             f'{d:+.2f}pp ({sig})', va='center', fontsize=9,
             color=('#16a34a' if d>0 and p<0.05 else ('#dc2626' if d<0 and p<0.05 else '#475569')))
ax.axvline(0, color='#222', linewidth=1)
ax.set_yticks(ys); ax.set_yticklabels(labels, fontsize=10)
ax.set_xlabel('Δ (pp) of B − A — paired bootstrap 95% CI; McNemar two-sided exact')
ax.set_title('Paired comparisons across baselines (Qwen2.5-Coder-7B, full benchmarks)', fontsize=12, fontweight='bold')
ax.grid(axis='x', alpha=0.3)
fig.tight_layout()
p2 = PLT / 'full_benchmark_paired_diff_forest.png'
fig.savefig(p2, dpi=140, bbox_inches='tight')
plt.close(fig)
print(f'wrote {p2}')

# -------- PLOT 3: failure taxonomy stacked bar --------
tax = []
with (TBL / 'full_benchmark_failure_taxonomy.csv').open(encoding='utf-8') as f:
    for r in csv.DictReader(f):
        r['count'] = int(r['count']); r['pct'] = float(r['pct'])
        tax.append(r)
cells = [(r['baseline'], r['benchmark']) for r in mm]
cell_keys = [f'{b}\n{bn}' for b,bn in cells]
all_cats = sorted({r['category'] for r in tax})
cat_color = {
    'success':'#22c55e','result_mismatch':'#f97316','op_no_such_table':'#dc2626',
    'op_no_such_column':'#b91c1c','op_other':'#7f1d1d','op_syntax_error':'#991b1b',
    'op_ambiguous_column':'#a16207','runtime_type_error':'#7c3aed',
    'runtime_timeout':'#1d4ed8','spider2_no_planner':'#9ca3af',
    'spider2_structural_only':'#cbd5e1','no_error_no_match':'#d4d4d8',
    'gold_missing':'#000000',
}
fig, ax = plt.subplots(figsize=(13, 6))
import numpy as np
counts = np.zeros((len(all_cats), len(cell_keys)))
for r in tax:
    ci = cell_keys.index(f'{r["baseline"]}\n{r["benchmark"]}')
    ki = all_cats.index(r['category'])
    counts[ki, ci] = r['pct'] * 100
bottoms = np.zeros(len(cell_keys))
for ki, cat in enumerate(all_cats):
    ax.bar(cell_keys, counts[ki], bottom=bottoms, label=cat,
            color=cat_color.get(cat, '#999999'), edgecolor='white', linewidth=0.4)
    bottoms += counts[ki]
ax.legend(bbox_to_anchor=(1.02,1), loc='upper left', fontsize=9)
ax.set_ylabel('% of cell rows'); ax.set_title('Failure taxonomy — distribution per cell')
ax.set_ylim(0, 100); ax.grid(axis='y', alpha=0.3)
plt.xticks(rotation=0, fontsize=9)
fig.tight_layout()
p3 = PLT / 'full_benchmark_failure_taxonomy.png'
fig.savefig(p3, dpi=140, bbox_inches='tight')
plt.close(fig)
print(f'wrote {p3}')

# -------- PLOT 4: linker fallback split EX --------
fig, ax = plt.subplots(figsize=(10, 5))
splits = []
for prefix, label in [
    ('b1v3_qwen2p5_coder_7b_spider_dev_full',  'B1_v3 Spider'),
    ('b3v4_qwen2p5_coder_7b_spider_dev_full',  'B3_v4 Spider'),
    ('b1v3_qwen2p5_coder_7b_bird_full',         'B1_v3 BIRD'),
    ('b3v4_qwen2p5_coder_7b_bird_full',         'B3_v4 BIRD'),
    ('b2v4_qwen2p5_coder_7b_bird_full',         'B2_v4 BIRD'),
]:
    p = PRED / f'{prefix}_predictions.jsonl'
    if not p.exists(): continue
    rows = [json.loads(l) for l in p.open()]
    fb = [r for r in rows if r.get('fallback_used')]
    nofb = [r for r in rows if not r.get('fallback_used')]
    fb_em = (sum(1 for r in fb if r.get('execution_match'))/len(fb)*100) if fb else 0
    nofb_em = (sum(1 for r in nofb if r.get('execution_match'))/len(nofb)*100) if nofb else 0
    splits.append((label, len(fb), len(nofb), fb_em, nofb_em))
labels = [s[0] for s in splits]
fb_ys = [s[3] for s in splits]
nofb_ys = [s[4] for s in splits]
x = np.arange(len(labels))
w = 0.35
ax.bar(x-w/2, fb_ys, w, color='#94a3b8', label='EX in fallback (full schema)')
ax.bar(x+w/2, nofb_ys, w, color='#22c55e', label='EX no-fallback (reduced schema)')
for xi, (lab, fbn, nofbn, fb_em, nofb_em) in enumerate(splits):
    ax.text(xi-w/2, fb_em+0.5, f'{fb_em:.1f}%\nn={fbn}', ha='center', fontsize=8)
    ax.text(xi+w/2, nofb_em+0.5, f'{nofb_em:.1f}%\nn={nofbn}', ha='center', fontsize=8)
ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=10)
ax.set_ylabel('Execution Match (%)')
ax.set_title('Linker / retrieval: EX split by fallback (full benchmarks)')
ax.legend(); ax.grid(axis='y', alpha=0.3)
fig.tight_layout()
p4 = PLT / 'full_benchmark_linker_fallback_split.png'
fig.savefig(p4, dpi=140, bbox_inches='tight')
plt.close(fig)
print(f'wrote {p4}')

# -------- Spider2-Lite structural metrics --------
def parse_struct(sql):
    s = (sql or '').lower()
    return {
        'has_select': bool(re.search(r'\bselect\b', s)),
        'joins': len(re.findall(r'\bjoin\b', s)),
        'where_clauses': len(re.findall(r'\bwhere\b', s)),
        'group_by': len(re.findall(r'\bgroup by\b', s)),
        'order_by': len(re.findall(r'\border by\b', s)),
        'aggregates': len(re.findall(r'\b(sum|avg|min|max|count)\s*\(', s)),
        'subqueries': s.count('select') - 1 if s.count('select') > 0 else 0,
        'cte': s.count('with ') if 'with ' in s else 0,
        'length_chars': len(sql or ''),
    }

s2_summary = []
for prefix in ['b0_qwen2p5_coder_7b_spider2lite_full',
                'b3v4_qwen2p5_coder_7b_spider2lite_full']:
    p = PRED / f'{prefix}_predictions.jsonl'
    if not p.exists(): continue
    rows = [json.loads(l) for l in p.open()]
    n = len(rows)
    metrics = [parse_struct(r.get('generated_sql','')) for r in rows]
    safe_pct = sum(1 for r in rows if r.get('safe_select')) / n
    avg = lambda k: sum(m[k] for m in metrics)/n
    summary = {
        'cell': prefix, 'n': n, 'safe_pct': round(safe_pct, 4),
        'has_select_pct': round(sum(1 for m in metrics if m['has_select'])/n, 4),
        'avg_joins': round(avg('joins'), 3),
        'avg_where': round(avg('where_clauses'), 3),
        'avg_group_by': round(avg('group_by'), 3),
        'avg_order_by': round(avg('order_by'), 3),
        'avg_aggregates': round(avg('aggregates'), 3),
        'avg_subqueries': round(avg('subqueries'), 3),
        'avg_length_chars': round(avg('length_chars'), 1),
    }
    s2_summary.append(summary)

with (TBL / 'spider2lite_structural_summary.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(s2_summary[0].keys()))
    w.writeheader(); [w.writerow(r) for r in s2_summary]
print(f'wrote spider2lite_structural_summary.csv')

# Markdown
md = ['# Spider2-Lite structural quality summary (Qwen2.5-Coder-7B)', '',
      'Spider2-Lite was run **structural-only** (no BigQuery/Snowflake creds).',
      'These columns describe the syntactic / structural features of generated SQL,',
      '**not accuracy**.', '',
      '| Cell | N | safe% | SELECT% | avg joins | avg WHERE | avg GROUP | avg ORDER | avg AGG | avg subq | avg len (chars) |',
      '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for s in s2_summary:
    md.append(f'| {s["cell"]} | {s["n"]} | {s["safe_pct"]*100:.1f}% | {s["has_select_pct"]*100:.1f}% | {s["avg_joins"]} | {s["avg_where"]} | {s["avg_group_by"]} | {s["avg_order_by"]} | {s["avg_aggregates"]} | {s["avg_subqueries"]} | {s["avg_length_chars"]} |')
md += ['',
    '## Reading',
    '',
    '- `safe%` = passed the SELECT-only AST guard. 100% means all generations were syntactically read-only SQL.',
    '- Use these for "the model produces plausible-looking SQL on a held-out enterprise benchmark", not "the model is X% accurate on Spider2-Lite".',
    '- Comparison between B0 and B3_v4 here tells you whether retrieval changes SQL shape (e.g. fewer joins because retrieved schema is smaller).',
]
(LOG / 'full_benchmark_spider2lite_structural.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
print(f'wrote full_benchmark_spider2lite_structural.md')

# -------- Build export pack --------
pack_dir = ROOT / 'outputs' / 'full_benchmark_export_pack_v1'
if pack_dir.exists(): shutil.rmtree(pack_dir)
pack_dir.mkdir(parents=True)
(pack_dir / 'predictions').mkdir(); (pack_dir / 'tables').mkdir()
(pack_dir / 'logs').mkdir(); (pack_dir / 'plots').mkdir(); (pack_dir / 'docs').mkdir()

import shutil as sh
for p in PRED.glob('*qwen2p5_coder_7b*full*.jsonl'):
    sh.copy2(p, pack_dir/'predictions'/p.name)
for p in TBL.glob('full_benchmark_*'):
    sh.copy2(p, pack_dir/'tables'/p.name)
for p in TBL.glob('spider2lite_structural_*'):
    sh.copy2(p, pack_dir/'tables'/p.name)
for p in LOG.glob('full_benchmark_*'):
    sh.copy2(p, pack_dir/'logs'/p.name)
for p in PLT.glob('full_benchmark_*'):
    sh.copy2(p, pack_dir/'plots'/p.name)
sh.copy2(ROOT/'outputs'/'REPORT_FULL_BENCHMARK.md', pack_dir/'REPORT_FULL_BENCHMARK.md')

# Manifest
manifest = {
    'pack_version': 'full_benchmark_v1',
    'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    'model': 'Qwen/Qwen2.5-Coder-7B-Instruct',
    'precision': 'bf16',
    'gpu': 'A100 80GB',
    'cells': sorted([p.name for p in (pack_dir/'predictions').iterdir()]),
    'tables': sorted([p.name for p in (pack_dir/'tables').iterdir()]),
    'logs': sorted([p.name for p in (pack_dir/'logs').iterdir()]),
    'plots': sorted([p.name for p in (pack_dir/'plots').iterdir()]),
    'totals': {
        'predictions_rows': sum(sum(1 for _ in open(p)) for p in (pack_dir/'predictions').iterdir()),
        'predictions_files': len(list((pack_dir/'predictions').iterdir())),
    },
}
(pack_dir / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
print(f'pack: predictions_rows={manifest["totals"]["predictions_rows"]}')

# Tarball
tar_path = EXP / 'full_benchmark_export_pack_v1.tar.gz'
with tarfile.open(tar_path, 'w:gz') as tar:
    tar.add(pack_dir, arcname=pack_dir.name)
print(f'wrote tarball {tar_path} ({tar_path.stat().st_size//1024} KB)')

print()
print('done — phase 9-10 plots+structural+export.')
