# Phase A consolidation:
# - Joins 2 new cells (b1_v5, b2_v5 × Spider+BIRD) with v11 B0 anchor JSONLs.
# - Computes:
#     * master matrix v12 (per-cell EX, Wilson CI, exec/safe/lat/fb/red ratios)
#     * paired stats (B0 anchor vs B1_v5; B0 vs B2_v5; B1_v5 vs B2_v5;
#       on Spider AND BIRD; report Δpp, McNemar exact, paired bootstrap CI)
#     * retrieval gain analysis (helpful/harm/neutral vs anchor)
#     * error taxonomy refresh (joins old + new)
#     * Spider2-Lite NOT covered in Phase A (no spider2 baselines run)
# - Writes:
#     outputs/tables/final_experiment_master_matrix_fullbench_v1.{csv,md}
#     outputs/tables/paired_significance_fullbench_v1.csv
#     outputs/tables/error_taxonomy_fullbench_v1.csv
#     outputs/logs/retrieval_gain_analysis_fullbench_v1.md
#     outputs/logs/fullbench_readiness.md          (Phase-A-only "what's done so far")
#     outputs/plots/retrieval_ablation_fullbench.png
#     outputs/plots/fullbench_overview.png         (rebuilds with new cells)
from __future__ import annotations
import json, math, os, csv, time, glob
from pathlib import Path
from collections import Counter, defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
PRED = ROOT / 'outputs' / 'predictions'
TBL = ROOT / 'outputs' / 'tables'
LOG = ROOT / 'outputs' / 'logs'
PLT = ROOT / 'outputs' / 'plots'
TBL.mkdir(parents=True, exist_ok=True); LOG.mkdir(parents=True, exist_ok=True); PLT.mkdir(parents=True, exist_ok=True)

CELLS = [
    ('B0',    'spider_dev', 'b0_qwen2p5_coder_7b_spider_dev_full',   1034, 'v11_anchor'),
    ('B1_v5', 'spider_dev', 'b1v5_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_a'),
    ('B2_v5', 'spider_dev', 'b2v5_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_a'),
    ('B0',    'bird_full',  'b0_qwen2p5_coder_7b_bird_full',          500, 'v11_anchor'),
    ('B1_v5', 'bird_full',  'b1v5_qwen2p5_coder_7b_bird_full',        500, 'phase_a'),
    ('B2_v5', 'bird_full',  'b2v5_qwen2p5_coder_7b_bird_full',        500, 'phase_a'),
]


def wilson(p, n, z=1.96):
    if n == 0: return (0.0, 0.0)
    den = 1 + z*z/n; centre = p + z*z/(2*n)
    adj = z * ((p*(1-p)/n + z*z/(4*n*n)) ** 0.5)
    return ((centre - adj)/den, (centre + adj)/den)


def percentile(xs, q):
    if not xs: return 0
    xs = sorted(xs); k = (len(xs)-1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return xs[int(k)] if lo == hi else xs[lo]*(hi-k) + xs[hi]*(k-lo)


def load(prefix):
    p = PRED / f'{prefix}_predictions.jsonl'
    if not p.exists(): return []
    return [json.loads(l) for l in p.open(encoding='utf-8') if l.strip()]


# -------- master matrix --------
data = {}
for bl, bench, prefix, expected, source in CELLS:
    rows = load(prefix)
    data[(bl, bench)] = {'baseline': bl, 'bench': bench, 'prefix': prefix,
                          'expected': expected, 'rows': rows, 'source': source,
                          'n': len(rows), 'complete': len(rows) >= expected}
    print(f'  {prefix}: {len(rows)}/{expected} {"OK" if len(rows)>=expected else "PARTIAL"} ({source})')


def cell_metrics(d):
    rows = d['rows']; n = len(rows)
    if n == 0: return {'N': 0, 'EX': None}
    em = sum(1 for r in rows if r.get('execution_match'))
    exec_ok = sum(1 for r in rows if r.get('executable'))
    safe = sum(1 for r in rows if r.get('safe_select'))
    fb = sum(1 for r in rows if r.get('fallback_used'))
    lats = [float(r.get('latency_ms',0) or 0) for r in rows]
    pcs = [int(r.get('prompt_chars',0) or 0) for r in rows]
    cts = [int(r.get('completion_tokens',0) or 0) for r in rows]
    reds = [float(r.get('selected_schema_ratio') or 1.0) for r in rows
             if r.get('selected_schema_ratio') is not None]
    ex_rate = em / n
    lo, hi = wilson(ex_rate, n)
    return {'N': n, 'EX': ex_rate, 'EX_lo': lo, 'EX_hi': hi,
            'exec_pct': exec_ok/n, 'safe_pct': safe/n,
            'fallback_pct': fb/n,
            'lat_p50': percentile(lats, 0.5), 'lat_p95': percentile(lats, 0.95),
            'prompt_chars_p50': percentile(pcs, 0.5),
            'completion_tokens_p50': percentile(cts, 0.5),
            'avg_reduction_ratio': (sum(reds)/len(reds)) if reds else None}


mm_rows = []
for (b, bench), d in data.items():
    m = cell_metrics(d)
    mm_rows.append({'cell': d['prefix'], 'baseline': b, 'benchmark': bench,
                    'N': m.get('N',0), 'expected': d['expected'], 'complete': d['complete'],
                    'source': d['source'], **m})

with (TBL / 'final_experiment_master_matrix_fullbench_v1.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(mm_rows[0].keys()))
    w.writeheader(); [w.writerow(r) for r in mm_rows]


def fmt_pct(x): return f'{x*100:.2f}%' if x is not None else '—'
def fmt_ci(lo, hi): return f'[{lo*100:.1f}, {hi*100:.1f}]' if lo is not None else '—'


md = ['# Master matrix v12 — Phase A (full benchmarks, Qwen2.5-Coder-7B)', '',
      'B0 numbers reused from v11 closure (committed). B1_v5/B2_v5 are new.', '',
      '| Baseline | Bench | N | EX | 95% Wilson CI | Exec | Safe | Lat p50 | Lat p95 | Fallback | Avg reduction |',
      '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in mm_rows:
    md.append(f'| {r["baseline"]} | {r["benchmark"]} | {r["N"]} | {fmt_pct(r.get("EX"))} | '
              f'{fmt_ci(r.get("EX_lo"), r.get("EX_hi"))} | {fmt_pct(r.get("exec_pct"))} | '
              f'{fmt_pct(r.get("safe_pct"))} | {(r.get("lat_p50") or 0):.0f} | {(r.get("lat_p95") or 0):.0f} | '
              f'{fmt_pct(r.get("fallback_pct"))} | {fmt_pct(r.get("avg_reduction_ratio"))} |')
(TBL / 'final_experiment_master_matrix_fullbench_v1.md').write_text('\n'.join(md) + '\n', encoding='utf-8')


# -------- paired stats --------
def aligned(a, b):
    am = {r['idx']: r for r in a}; bm = {r['idx']: r for r in b}
    common = sorted(set(am) & set(bm))
    return [(am[i], bm[i]) for i in common]


def mcnemar_exact(b, c):
    if b + c == 0: return 1.0
    from math import comb
    n = b + c; k = min(b, c)
    p = sum(comb(n, i) for i in range(0, k+1)) / (2**n)
    return min(1.0, 2*p)


def boot_ci(diffs, n_iter=2000, seed=42):
    import random
    random.seed(seed)
    n = len(diffs)
    if n == 0: return (0, 0)
    samples = []
    for _ in range(n_iter):
        idx = [random.randrange(n) for _ in range(n)]
        s = sum(diffs[i] for i in idx) / n
        samples.append(s)
    samples.sort()
    return (samples[int(0.025*n_iter)], samples[int(0.975*n_iter)])


paired = [
    ('Spider', 'B0', 'B1_v5', 'spider_dev'),
    ('Spider', 'B0', 'B2_v5', 'spider_dev'),
    ('Spider', 'B1_v5', 'B2_v5', 'spider_dev'),
    ('BIRD',   'B0', 'B1_v5', 'bird_full'),
    ('BIRD',   'B0', 'B2_v5', 'bird_full'),
    ('BIRD',   'B1_v5', 'B2_v5', 'bird_full'),
]
ps_rows = []
for label, A, B, bench in paired:
    a = data.get((A, bench), {}).get('rows', [])
    b = data.get((B, bench), {}).get('rows', [])
    pairs = aligned(a, b)
    if not pairs:
        ps_rows.append({'bench':label,'A':A,'B':B,'n':0,'A_em':0,'B_em':0,
                        'a_only':0,'b_only':0,'both':0,'neither':0,
                        'diff_pp':None,'mcnemar_p':None,
                        'boot_lo_pp':None,'boot_hi_pp':None,
                        'helpful':0,'harmful':0,'neutral':0})
        continue
    a_only = sum(1 for x,y in pairs if x.get('execution_match') and not y.get('execution_match'))
    b_only = sum(1 for x,y in pairs if not x.get('execution_match') and y.get('execution_match'))
    both = sum(1 for x,y in pairs if x.get('execution_match') and y.get('execution_match'))
    neither = sum(1 for x,y in pairs if not x.get('execution_match') and not y.get('execution_match'))
    n = len(pairs)
    a_em = (both + a_only) / n
    b_em = (both + b_only) / n
    diffs = [int(bool(y.get('execution_match'))) - int(bool(x.get('execution_match'))) for x,y in pairs]
    diff_pp = (b_em - a_em) * 100
    p = mcnemar_exact(a_only, b_only)
    lo, hi = boot_ci(diffs)
    helpful = b_only; harmful = a_only; neutral = both + neither
    ps_rows.append({'bench':label,'A':A,'B':B,'n':n,
                    'A_em':round(a_em,4),'B_em':round(b_em,4),
                    'a_only':a_only,'b_only':b_only,'both':both,'neither':neither,
                    'diff_pp':round(diff_pp,2),'mcnemar_p':round(p,5),
                    'boot_lo_pp':round(lo*100,2),'boot_hi_pp':round(hi*100,2),
                    'helpful':helpful,'harmful':harmful,'neutral':neutral})

with (TBL / 'paired_significance_fullbench_v1.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(ps_rows[0].keys()))
    w.writeheader(); [w.writerow(r) for r in ps_rows]

# -------- error taxonomy --------
def categorize(r):
    et = (r.get('error_type') or '').strip()
    em = (r.get('error_message') or '').strip()
    if r.get('execution_match'): return 'success'
    if not r.get('safe_select', True) and not et.startswith('unsafe'): pass
    if et == 'no_gold': return 'gold_missing'
    if et == 'result_mismatch': return 'result_mismatch'
    if et == 'OperationalError':
        if 'no such table' in em: return 'op_no_such_table'
        if 'no such column' in em: return 'op_no_such_column'
        if 'syntax' in em.lower(): return 'op_syntax_error'
        if 'ambiguous' in em: return 'op_ambiguous_column'
        return 'op_other'
    if et == 'TypeError': return 'runtime_type_error'
    if et == 'timeout': return 'runtime_timeout'
    if et.startswith('unsafe'): return 'unsafe_sql_blocked'
    if et.startswith('pipeline_exception'): return 'pipeline_exception'
    if et == 'no_schema_ir': return 'pipeline_no_ir'
    if et == '': return 'no_error_no_match'
    return f'other:{et}'


tax_rows = []
for (b, bench), d in data.items():
    cnt = Counter(categorize(r) for r in d['rows'])
    n = len(d['rows']) or 1
    for cat, c in sorted(cnt.items(), key=lambda x: -x[1]):
        tax_rows.append({'baseline': b, 'benchmark': bench, 'category': cat,
                          'count': c, 'pct': round(c/n, 4)})
with (TBL / 'error_taxonomy_fullbench_v1.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['baseline','benchmark','category','count','pct'])
    w.writeheader(); [w.writerow(r) for r in tax_rows]


# -------- retrieval gain analysis (markdown) --------
def m_for(b, bench):
    return next((r for r in mm_rows if r['baseline']==b and r['benchmark']==bench), {})

sp_b0 = m_for('B0','spider_dev'); sp_b1 = m_for('B1_v5','spider_dev'); sp_b2 = m_for('B2_v5','spider_dev')
bd_b0 = m_for('B0','bird_full'); bd_b1 = m_for('B1_v5','bird_full'); bd_b2 = m_for('B2_v5','bird_full')

def ps_for(label, A, B):
    return next((r for r in ps_rows if r['bench']==label and r['A']==A and r['B']==B), None)

ra_lines = ['# Retrieval gain analysis (full benchmarks v1)', '',
    f'_Generated: {time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}._',
    '',
    'B0 (full schema anchor) reused from v11. B1_v5 = retrieval-only direct.',
    'B2_v5 = retrieval + benchmark evidence direct.',
    '',
    '## Headline EX', '',
    '| Bench | B0 (anchor) | B1_v5 (retrieval) | B2_v5 (retrieval+evidence) |',
    '|---|---:|---:|---:|',
    f'| Spider dev (1034) | {fmt_pct(sp_b0.get("EX"))} | {fmt_pct(sp_b1.get("EX"))} | {fmt_pct(sp_b2.get("EX"))} |',
    f'| BIRD Mini-Dev (500) | {fmt_pct(bd_b0.get("EX"))} | {fmt_pct(bd_b1.get("EX"))} | {fmt_pct(bd_b2.get("EX"))} |',
    '',
    '## Paired diff vs anchor (helpful = B fixes A; harmful = B breaks A)', '',
    '| Bench | A | B | n | EX(A) | EX(B) | Δ pp | 95% CI pp | McNemar p | helpful | harmful | neutral |',
    '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
]
for r in ps_rows:
    if r['n'] == 0: continue
    ra_lines.append(
        f'| {r["bench"]} | {r["A"]} | {r["B"]} | {r["n"]} | {r["A_em"]*100:.2f}% | {r["B_em"]*100:.2f}% | '
        f'{r["diff_pp"]:+.2f} | [{r["boot_lo_pp"]:+.2f}, {r["boot_hi_pp"]:+.2f}] | {r["mcnemar_p"]:.4f} | '
        f'{r["helpful"]} | {r["harmful"]} | {r["neutral"]} |')

# Verdict logic
def verdict(p, A, B):
    p_val = p['mcnemar_p']
    if p_val is None: return 'inconclusive'
    if p_val >= 0.05: return 'no significant difference (p ≥ 0.05)'
    if p['diff_pp'] > 0: return f'**{B} significantly beats {A}** (Δ {p["diff_pp"]:+.2f} pp, p={p_val:.4f})'
    return f'**{B} significantly worse than {A}** (Δ {p["diff_pp"]:+.2f} pp, p={p_val:.4f})'

ra_lines += ['', '## Verdicts', '']
for r in ps_rows:
    if r['n'] == 0: continue
    ra_lines.append(f'- {r["bench"]} {r["A"]} → {r["B"]}: {verdict(r, r["A"], r["B"])} (helpful {r["helpful"]} / harmful {r["harmful"]})')

(LOG / 'retrieval_gain_analysis_fullbench_v1.md').write_text('\n'.join(ra_lines) + '\n', encoding='utf-8')


# -------- fullbench_readiness.md --------
ready_lines = ['# Phase A readiness (Phase B/C/D deferred)', '',
    f'_Generated: {time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}._',
    '',
    '## What is closed', '',
    f'- Phase A retrieval ablation: B0 (v11) vs B1_v5 vs B2_v5, '
    f'Qwen2.5-Coder-7B, full Spider dev (1034) + full BIRD Mini-Dev (500).',
    '',
    '## What is NOT closed (deferred to next sessions)', '',
    '- Phase B: planner_v2 + sql_compiler_v2 + b3_v5 (gated planner+compiler) — code not yet written.',
    '- Phase C: candidate_generator_v2 + verifier_ranker_v2 + repair_v2 + b4_v5 (full controller); model scaling across Gemma-3-12b / Qwen-Coder-32B/30B / SQLCoder.',
    '- Phase D: planner-model swap (Qwen3-8B vs Gemma-3-12b as planner/verifier).',
    '- Spider2-Lite v2: Phase A skipped Spider2-Lite (no execution engine; structural-only B0/B3_v4 closed in v11).',
    '- BIRD official R-VES + Soft-F1: still blocked by official CLI drift.',
    '- Premium retrieval lane R2 (Qwen3-Embedding + Qwen3-Reranker): not yet implemented; FAST lane (BM25 + char n-gram) is what Phase A used.',
    '',
    '## Cells in this readout', '',
    '| Cell | N | source | EX | 95% CI |',
    '|---|---:|---|---:|---:|',
]
for r in mm_rows:
    ready_lines.append(f'| {r["cell"]} | {r["N"]} | {r["source"]} | {fmt_pct(r.get("EX"))} | {fmt_ci(r.get("EX_lo"), r.get("EX_hi"))} |')
(LOG / 'fullbench_readiness.md').write_text('\n'.join(ready_lines) + '\n', encoding='utf-8')


# -------- plots --------
def colors_for(b):
    return {'B0':'#3a82f6','B1_v5':'#22c55e','B2_v5':'#a855f7',
             'B1_v3':'#f59e0b','B3_v4':'#10b981','B2_v4':'#ef4444'}.get(b,'#888888')

# 1) per-cell EX with Wilson CI (overview)
fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
for ax, bench, ttl in zip(axes, ['spider_dev','bird_full'],
                            ['Spider dev (1034)','BIRD Mini-Dev (500)']):
    cells = [r for r in mm_rows if r['benchmark']==bench and r.get('EX') is not None]
    cells.sort(key=lambda r: ['B0','B1_v5','B2_v5'].index(r['baseline']) if r['baseline'] in ['B0','B1_v5','B2_v5'] else 99)
    xs = [r['baseline'] for r in cells]
    ys = [r['EX']*100 for r in cells]
    err_lo = [r['EX']*100 - r['EX_lo']*100 for r in cells]
    err_hi = [r['EX_hi']*100 - r['EX']*100 for r in cells]
    bars = ax.bar(xs, ys, yerr=[err_lo, err_hi], capsize=5,
                   color=[colors_for(b) for b in xs], edgecolor='black', linewidth=0.6)
    for bar, y in zip(bars, ys):
        ax.text(bar.get_x()+bar.get_width()/2, y+0.5, f'{y:.1f}%', ha='center', fontsize=10, fontweight='bold')
    ax.set_title(ttl); ax.set_ylabel('Execution Match (%)'); ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(0, max(ys)*1.25 if ys else 100)
fig.suptitle('Phase A — Retrieval ablation (Wilson 95% CI)', fontsize=13, fontweight='bold')
fig.tight_layout()
fig.savefig(PLT / 'fullbench_overview.png', dpi=140, bbox_inches='tight'); plt.close(fig)

# 2) Retrieval ablation forest
fig, ax = plt.subplots(figsize=(11, 4))
ps_plot = [r for r in ps_rows if r['n'] > 0]
ps_plot = list(reversed(ps_plot))
labels = [f'{r["bench"]}: {r["B"]} − {r["A"]}' for r in ps_plot]
diffs = [r['diff_pp'] for r in ps_plot]; los = [r['boot_lo_pp'] for r in ps_plot]; his = [r['boot_hi_pp'] for r in ps_plot]
ys = list(range(len(ps_plot)))
ax.errorbar(diffs, ys, xerr=[[d-l for d,l in zip(diffs,los)], [h-d for d,h in zip(diffs,his)]],
             fmt='o', color='#1e293b', ecolor='#64748b', capsize=4, markersize=8)
for y, d, p in zip(ys, diffs, [r['mcnemar_p'] for r in ps_plot]):
    sig = 'p<0.001' if p<0.001 else f'p={p:.3f}'
    ax.text(d + (1.0 if d>=0 else -1.0), y,
             f'{d:+.2f}pp ({sig})', va='center', fontsize=9,
             color=('#16a34a' if d>0 and p<0.05 else ('#dc2626' if d<0 and p<0.05 else '#475569')))
ax.axvline(0, color='#222', linewidth=1)
ax.set_yticks(ys); ax.set_yticklabels(labels, fontsize=10)
ax.set_xlabel('Δ (pp) of B − A — paired bootstrap 95% CI; McNemar two-sided exact')
ax.set_title('Phase A retrieval ablation — paired comparisons')
ax.grid(axis='x', alpha=0.3)
fig.tight_layout()
fig.savefig(PLT / 'retrieval_ablation_fullbench.png', dpi=140, bbox_inches='tight'); plt.close(fig)

print('Phase A consolidation done.')
print()
for r in mm_rows:
    print(f'  {r["baseline"]:6s} {r["benchmark"]:12s} N={r["N"]:5d} EX={fmt_pct(r.get("EX")):>8s} CI={fmt_ci(r.get("EX_lo"), r.get("EX_hi")):>14s}')
