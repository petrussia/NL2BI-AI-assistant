# Phase 8 (S1_v7) consolidation:
# - Joins S1_v7 cell with the full ladder (B0..B6_v7).
# - Computes:
#     * master matrix v19
#     * paired stats: S1_v7 vs B6_v7 (key: does demo retrieval beat 76.79?);
#       S1_v7 vs B4_v5; S1_v7 vs B0
#     * source breakdown (judge picks for S1_v7)
#     * helpful/harmful via demo retrieval
# - Writes:
#     outputs/tables/final_experiment_master_matrix_fullbench_v8.{csv,md}
#     outputs/tables/paired_significance_s1_v7.csv
#     outputs/tables/spider_demo_retrieval_ablation_v7.csv
#     outputs/tables/controller_source_breakdown_s1_v7.csv
#     outputs/logs/spider_specific_design_v7.md
#     outputs/plots/s1v7_overview.png
from __future__ import annotations
import json, math, csv, time
from pathlib import Path
from collections import Counter, defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
PRED = ROOT/'outputs'/'predictions'; TBL = ROOT/'outputs'/'tables'
LOG = ROOT/'outputs'/'logs'; PLT = ROOT/'outputs'/'plots'
TBL.mkdir(parents=True, exist_ok=True); LOG.mkdir(parents=True, exist_ok=True); PLT.mkdir(parents=True, exist_ok=True)

CELLS = [
    ('B0',    'spider_dev', 'b0_qwen2p5_coder_7b_spider_dev_full',   1034, 'v11_anchor'),
    ('B1_v5', 'spider_dev', 'b1v5_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_a'),
    ('B2_v5', 'spider_dev', 'b2v5_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_a'),
    ('B4_v5', 'spider_dev', 'b4v5_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_c'),
    ('B6_v7', 'spider_dev', 'b6v7_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_six'),
    ('S1_v7', 'spider_dev', 's1v7_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_eight'),
]

def wilson(p, n, z=1.96):
    if n == 0: return (0,0)
    den = 1 + z*z/n; centre = p + z*z/(2*n)
    adj = z * ((p*(1-p)/n + z*z/(4*n*n))**0.5)
    return ((centre-adj)/den, (centre+adj)/den)

def load(prefix):
    p = PRED/f'{prefix}_predictions.jsonl'
    if not p.exists(): return []
    return [json.loads(l) for l in p.open(encoding='utf-8') if l.strip()]

def percentile(xs, q):
    if not xs: return 0
    xs = sorted(xs); k = (len(xs)-1)*q; lo, hi = math.floor(k), math.ceil(k)
    return xs[int(k)] if lo == hi else xs[lo]*(hi-k)+xs[hi]*(k-lo)

data = {}
for bl, bench, prefix, expected, source in CELLS:
    rows = load(prefix)
    data[(bl, bench)] = {'baseline':bl,'bench':bench,'prefix':prefix,
                          'expected':expected,'rows':rows,'source':source,
                          'n':len(rows),'complete':len(rows)>=expected}
    print(f'  {prefix}: {len(rows)}/{expected} {"OK" if len(rows)>=expected else "PARTIAL"} ({source})')

def cell_metrics(d):
    rows = d['rows']; n = len(rows)
    if n == 0: return {'N':0,'EX':None}
    em = sum(1 for r in rows if r.get('execution_match'))
    exec_ok = sum(1 for r in rows if r.get('executable'))
    safe = sum(1 for r in rows if r.get('safe_select'))
    j_inv = sum(1 for r in rows if r.get('judge_invoked'))
    j_ovr = sum(1 for r in rows if r.get('judge_overrode'))
    demo_chars = [int(r.get('demo_chars_rendered',0) or 0) for r in rows]
    lats = [float(r.get('latency_ms',0) or 0) for r in rows]
    cts = [int(r.get('completion_tokens',0) or 0) for r in rows]
    lm_avg = (sum(int(r.get('lm_calls',1) or 1) for r in rows) / n)
    ex_rate = em/n; lo, hi = wilson(ex_rate, n)
    return {'N':n,'EX':ex_rate,'EX_lo':lo,'EX_hi':hi,
            'exec_pct':exec_ok/n,'safe_pct':safe/n,
            'judge_invoked_pct':j_inv/n,'judge_overrode_pct':j_ovr/n,
            'demo_chars_avg': (sum(demo_chars)/len(demo_chars)) if demo_chars else 0,
            'lat_p50':percentile(lats,0.5),'lat_p95':percentile(lats,0.95),
            'completion_tokens_p50':percentile(cts,0.5),'lm_calls_avg':lm_avg}

mm_rows = []
for (b, bench), d in data.items():
    m = cell_metrics(d)
    mm_rows.append({'cell':d['prefix'],'baseline':b,'benchmark':bench,
                    'N':m.get('N',0),'expected':d['expected'],'complete':d['complete'],
                    'source':d['source'], **m})

with (TBL/'final_experiment_master_matrix_fullbench_v8.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(mm_rows[0].keys()))
    w.writeheader(); [w.writerow(r) for r in mm_rows]

def pct(x): return f'{x*100:.2f}%' if x is not None else '—'
def ci(lo,hi): return f'[{lo*100:.1f}, {hi*100:.1f}]' if lo is not None else '—'

md = ['# Master matrix v19 — Phase 8 (S1_v7 demo retrieval on FULL Spider)', '',
      'B0/B1_v5/B2_v5/B4_v5/B6_v7 from prior phases. S1_v7 = B6_v7 controller +',
      'DAIL-style demonstration retrieval (top-3 same-db demos prepended to anchor).',
      '',
      '| Baseline | Bench | N | EX | 95% CI | Exec | Judge inv | Judge ovr | Demo chars avg | Avg LM calls |',
      '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in mm_rows:
    md.append(f'| {r["baseline"]} | {r["benchmark"]} | {r["N"]} | {pct(r.get("EX"))} | {ci(r.get("EX_lo"),r.get("EX_hi"))} | '
              f'{pct(r.get("exec_pct"))} | {pct(r.get("judge_invoked_pct",0))} | {pct(r.get("judge_overrode_pct",0))} | '
              f'{r.get("demo_chars_avg",0):.0f} | {r.get("lm_calls_avg",0):.2f} |')
(TBL/'final_experiment_master_matrix_fullbench_v8.md').write_text('\n'.join(md)+'\n', encoding='utf-8')

# ---------- paired stats ----------
def aligned(a, b):
    am = {r['idx']: r for r in a}; bm = {r['idx']: r for r in b}
    common = sorted(set(am) & set(bm))
    return [(am[i], bm[i]) for i in common]

def mcnemar_exact(b, c):
    if b+c==0: return 1.0
    from math import comb
    n = b+c; k = min(b,c)
    p = sum(comb(n,i) for i in range(0,k+1)) / (2**n)
    return min(1.0, 2*p)

def boot_ci(diffs, n_iter=2000, seed=42):
    import random; random.seed(seed)
    n = len(diffs)
    if n == 0: return (0,0)
    samples = []
    for _ in range(n_iter):
        idx = [random.randrange(n) for _ in range(n)]
        samples.append(sum(diffs[i] for i in idx)/n)
    samples.sort()
    return (samples[int(0.025*n_iter)], samples[int(0.975*n_iter)])

paired = [
    ('Spider','B0','S1_v7','spider_dev'),
    ('Spider','B2_v5','S1_v7','spider_dev'),
    ('Spider','B4_v5','S1_v7','spider_dev'),
    ('Spider','B6_v7','S1_v7','spider_dev'),
]
ps_rows = []
for label, A, B, bench in paired:
    a = data.get((A,bench),{}).get('rows',[])
    b = data.get((B,bench),{}).get('rows',[])
    pairs = aligned(a, b)
    if not pairs:
        ps_rows.append({'bench':label,'A':A,'B':B,'n':0,'A_em':0,'B_em':0,
                        'a_only':0,'b_only':0,'both':0,'neither':0,
                        'diff_pp':None,'mcnemar_p':None,'boot_lo_pp':None,'boot_hi_pp':None,
                        'helpful':0,'harmful':0,'neutral':0})
        continue
    a_only = sum(1 for x,y in pairs if x.get('execution_match') and not y.get('execution_match'))
    b_only = sum(1 for x,y in pairs if not x.get('execution_match') and y.get('execution_match'))
    both = sum(1 for x,y in pairs if x.get('execution_match') and y.get('execution_match'))
    neither = sum(1 for x,y in pairs if not x.get('execution_match') and not y.get('execution_match'))
    n = len(pairs); a_em = (both+a_only)/n; b_em = (both+b_only)/n
    diffs = [int(bool(y.get('execution_match'))) - int(bool(x.get('execution_match'))) for x,y in pairs]
    diff_pp = (b_em-a_em)*100; p = mcnemar_exact(a_only, b_only)
    lo, hi = boot_ci(diffs)
    ps_rows.append({'bench':label,'A':A,'B':B,'n':n,
                    'A_em':round(a_em,4),'B_em':round(b_em,4),
                    'a_only':a_only,'b_only':b_only,'both':both,'neither':neither,
                    'diff_pp':round(diff_pp,2),'mcnemar_p':round(p,5),
                    'boot_lo_pp':round(lo*100,2),'boot_hi_pp':round(hi*100,2),
                    'helpful':b_only,'harmful':a_only,'neutral':both+neither})
with (TBL/'paired_significance_s1_v7.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(ps_rows[0].keys()))
    w.writeheader(); [w.writerow(r) for r in ps_rows]

# ---------- demo retrieval ablation summary ----------
da_rows = []
s1 = data.get(('S1_v7','spider_dev'), {}).get('rows', [])
b6 = data.get(('B6_v7','spider_dev'), {}).get('rows', [])
if s1:
    n = len(s1); em = sum(1 for r in s1 if r.get('execution_match'))
    demo_chars = [int(r.get('demo_chars_rendered',0) or 0) for r in s1]
    demo_n = [int(r.get('demo_n',0) or 0) for r in s1]
    src = Counter(r.get('selected_candidate_source','?') for r in s1)
    da_rows.append({'cell':'S1_v7','n':n,'em':em,'em_rate':round(em/n,4),
                     'demo_chars_avg':sum(demo_chars)/n,
                     'demo_n_avg':sum(demo_n)/n,
                     'C0_anchor':src.get('C0_anchor',0),
                     'C1_retrieval':src.get('C1_retrieval_direct',0),
                     'C2_evidence':src.get('C2_retrieval_evidence',0),
                     'C3_planner':src.get('C3_planner_compiled',0)})
if b6:
    n = len(b6); em = sum(1 for r in b6 if r.get('execution_match'))
    src = Counter(r.get('selected_candidate_source','?') for r in b6)
    da_rows.append({'cell':'B6_v7 (no demos)','n':n,'em':em,'em_rate':round(em/n,4),
                     'demo_chars_avg':0,'demo_n_avg':0,
                     'C0_anchor':src.get('C0_anchor',0),
                     'C1_retrieval':src.get('C1_retrieval_direct',0),
                     'C2_evidence':src.get('C2_retrieval_evidence',0),
                     'C3_planner':src.get('C3_planner_compiled',0)})
with (TBL/'spider_demo_retrieval_ablation_v7.csv').open('w', newline='', encoding='utf-8') as f:
    if da_rows:
        w = csv.DictWriter(f, fieldnames=list(da_rows[0].keys()))
        w.writeheader(); [w.writerow(r) for r in da_rows]

# ---------- source breakdown (s1 vs b6) ----------
sb_rows = []
for cell_label in ('S1_v7','B6_v7'):
    rows = data.get((cell_label,'spider_dev'), {}).get('rows', [])
    if not rows: continue
    cnt = Counter(r.get('selected_candidate_source','?') for r in rows)
    em_by = {}
    for r in rows:
        s = r.get('selected_candidate_source','?')
        em_by[s] = em_by.get(s, 0) + (1 if r.get('execution_match') else 0)
    for src, n in cnt.most_common():
        sb_rows.append({'cell':cell_label,'source':src,'count':n,
                         'pct':round(n/len(rows),4),
                         'em':em_by.get(src,0),
                         'em_rate':round(em_by.get(src,0)/max(1,n),4)})
with (TBL/'controller_source_breakdown_s1_v7.csv').open('w', newline='', encoding='utf-8') as f:
    if sb_rows:
        w = csv.DictWriter(f, fieldnames=list(sb_rows[0].keys()))
        w.writeheader(); [w.writerow(r) for r in sb_rows]

# ---------- design memo ----------
def m_for(b, bench='spider_dev'):
    return next((r for r in mm_rows if r['baseline']==b and r['benchmark']==bench), {})

design = ['# Spider-specific design memo v7 (S1 demo retrieval)', '',
    f'_Generated: {time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}._',
    '',
    'Architecture: B6_v7 controller (Phase 6 LLM-as-judge selector) + DAIL-style',
    'demonstration retrieval. Top-3 train demos retrieved per dev question via',
    'BM25 over question text + structural-feature jaccard + +0.5 same-db boost.',
    'Demos are prepended only to the C0_anchor prompt (other candidates unchanged).',
    '',
    '## Train pool',
    '- train_spider.json (7000) + train_others.json (1659) = 8659 examples',
    '- Per-db BM25 indices for fast same-db lookup',
    '- Structural-feature jaccard (16 features inferred from gold SQL skeleton)',
    '',
    '## Headline EX (FULL Spider 1034)', '',
    '| Cell | EX | 95% CI | demo chars avg |',
    '|---|---:|---:|---:|']
for bl in ['B0','B2_v5','B4_v5','B6_v7','S1_v7']:
    r = m_for(bl)
    if not r: continue
    design.append(f'| {bl} | {pct(r.get("EX"))} | {ci(r.get("EX_lo"),r.get("EX_hi"))} | {r.get("demo_chars_avg",0):.0f} |')

design += ['', '## Paired stats', '',
           '| Bench | A | B | n | EX(A) | EX(B) | Δ pp | 95% CI pp | McNemar p | helpful | harmful |',
           '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in ps_rows:
    if r['n']==0: continue
    design.append(f'| {r["bench"]} | {r["A"]} | {r["B"]} | {r["n"]} | {r["A_em"]*100:.2f}% | {r["B_em"]*100:.2f}% | '
                   f'{r["diff_pp"]:+.2f} | [{r["boot_lo_pp"]:+.2f}, {r["boot_hi_pp"]:+.2f}] | '
                   f'{r["mcnemar_p"]:.4f} | {r["helpful"]} | {r["harmful"]} |')

design += ['', '## Source breakdown', '',
           '| Cell | source | count | pct | EX rate |',
           '|---|---|---:|---:|---:|']
for r in sb_rows:
    design.append(f'| {r["cell"]} | {r["source"]} | {r["count"]} | {r["pct"]*100:.1f}% | {r["em_rate"]*100:.2f}% |')

design += ['', '## Verdicts', '']
def verdict(r):
    if r['mcnemar_p'] is None: return 'inconclusive'
    if r['mcnemar_p'] >= 0.05: return f'no significant difference (p={r["mcnemar_p"]:.4f})'
    if r['diff_pp'] > 0: return f'**{r["B"]} significantly beats {r["A"]}** (Δ {r["diff_pp"]:+.2f} pp, p={r["mcnemar_p"]:.4f})'
    return f'**{r["B"]} significantly worse than {r["A"]}** (Δ {r["diff_pp"]:+.2f} pp, p={r["mcnemar_p"]:.4f})'
for r in ps_rows:
    if r['n']==0: continue
    design.append(f'- {r["bench"]} {r["A"]} → {r["B"]}: {verdict(r)} (helpful {r["helpful"]} / harmful {r["harmful"]})')

(LOG/'spider_specific_design_v7.md').write_text('\n'.join(design)+'\n', encoding='utf-8')

# ---------- plot ----------
fig, ax = plt.subplots(figsize=(11, 5.5))
order = ['B0','B1_v5','B2_v5','B4_v5','B6_v7','S1_v7']
cmap = {'B0':'#3a82f6','B1_v5':'#f59e0b','B2_v5':'#a855f7','B4_v5':'#22c55e',
        'B6_v7':'#e879f9','S1_v7':'#0ea5e9'}
cells = [r for r in mm_rows if r.get('EX') is not None and r['baseline'] in order]
cells.sort(key=lambda r: order.index(r['baseline']))
xs = [r['baseline'] for r in cells]
ys = [r['EX']*100 for r in cells]
err_lo = [r['EX']*100 - r['EX_lo']*100 for r in cells]
err_hi = [r['EX_hi']*100 - r['EX']*100 for r in cells]
bars = ax.bar(xs, ys, yerr=[err_lo, err_hi], capsize=5,
               color=[cmap.get(b,'#888') for b in xs], edgecolor='black', linewidth=0.6)
for bar, y in zip(bars, ys):
    ax.text(bar.get_x()+bar.get_width()/2, y+0.5, f'{y:.1f}%', ha='center', fontsize=10, fontweight='bold')
ax.set_title('Phase 8 — Spider FULL with demo retrieval', fontsize=13, fontweight='bold')
ax.set_ylabel('Execution Match (%)'); ax.grid(axis='y', alpha=0.3)
ax.set_ylim(0, max(ys)*1.25 if ys else 100)
fig.tight_layout()
fig.savefig(PLT/'s1v7_overview.png', dpi=140, bbox_inches='tight')
plt.close(fig)

print('Phase 8 consolidation done.')
print()
for r in mm_rows:
    print(f'  {r["baseline"]:8s} N={r["N"]:5d} EX={pct(r.get("EX")):>8s}')
