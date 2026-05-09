# Phase C consolidation:
# - Joins b4_v5 cells with v11 B0 + Phase A b1_v5/b2_v5 + Phase B b3_v5.
# - Computes:
#     * master matrix v14 (all baselines through Phase C)
#     * paired stats: B0 vs B4_v5; B2_v5 vs B4_v5 (key: does B4_v5 close Phase B gap?);
#       B3_v5 vs B4_v5 (key: does verifier+repair help over plan-then-compile alone?)
#     * controller-source breakdown (which candidate was picked and how often)
#     * verifier impact analysis (anchor wins via tie-break vs verifier wins by score)
#     * repair impact analysis
# - Writes:
#     outputs/tables/final_experiment_master_matrix_fullbench_v3.{csv,md}
#     outputs/tables/paired_significance_fullbench_v3.csv
#     outputs/tables/controller_source_breakdown_fullbench_v1.csv
#     outputs/tables/verifier_repair_impact_fullbench_v1.csv
#     outputs/logs/controller_analysis_fullbench_v1.md
#     outputs/plots/controller_overview_fullbench.png
from __future__ import annotations
import json, math, csv, time
from pathlib import Path
from collections import Counter, defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
PRED = ROOT/'outputs'/'predictions'; TBL = ROOT/'outputs'/'tables'
LOG = ROOT/'outputs'/'logs'; PLT = ROOT/'outputs'/'plots'
TBL.mkdir(parents=True, exist_ok=True); LOG.mkdir(parents=True, exist_ok=True); PLT.mkdir(parents=True, exist_ok=True)

CELLS = [
    ('B0',    'spider_dev', 'b0_qwen2p5_coder_7b_spider_dev_full',   1034, 'v11_anchor'),
    ('B1_v5', 'spider_dev', 'b1v5_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_a'),
    ('B2_v5', 'spider_dev', 'b2v5_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_a'),
    ('B3_v5', 'spider_dev', 'b3v5_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_b'),
    ('B4_v5', 'spider_dev', 'b4v5_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_c'),
    ('B0',    'bird_full',  'b0_qwen2p5_coder_7b_bird_full',          500, 'v11_anchor'),
    ('B1_v5', 'bird_full',  'b1v5_qwen2p5_coder_7b_bird_full',        500, 'phase_a'),
    ('B2_v5', 'bird_full',  'b2v5_qwen2p5_coder_7b_bird_full',        500, 'phase_a'),
    ('B3_v5', 'bird_full',  'b3v5_qwen2p5_coder_7b_bird_full',        500, 'phase_b'),
    ('B4_v5', 'bird_full',  'b4v5_qwen2p5_coder_7b_bird_full',        500, 'phase_c'),
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
    fb = sum(1 for r in rows if r.get('fallback_used'))
    pl = sum(1 for r in rows if r.get('planner_used'))
    pv = sum(1 for r in rows if r.get('plan_valid'))
    rep = sum(1 for r in rows if r.get('repair_used'))
    cand_avg = (sum(int(r.get('candidate_count',1) or 1) for r in rows) / n)
    cons_avg = (sum(int(r.get('consensus_size',0) or 0) for r in rows) / n)
    lats = [float(r.get('latency_ms',0) or 0) for r in rows]
    cts = [int(r.get('completion_tokens',0) or 0) for r in rows]
    lm_avg = (sum(int(r.get('lm_calls',1) or 1) for r in rows) / n)
    ex_rate = em/n; lo, hi = wilson(ex_rate, n)
    return {'N':n,'EX':ex_rate,'EX_lo':lo,'EX_hi':hi,
            'exec_pct':exec_ok/n,'safe_pct':safe/n,'fallback_pct':fb/n,
            'planner_used_pct':pl/n,'plan_valid_pct':pv/n,'repair_used_pct':rep/n,
            'candidate_avg':cand_avg,'consensus_avg':cons_avg,
            'lat_p50':percentile(lats,0.5),'lat_p95':percentile(lats,0.95),
            'completion_tokens_p50':percentile(cts,0.5),'lm_calls_avg':lm_avg}

mm_rows = []
for (b, bench), d in data.items():
    m = cell_metrics(d)
    mm_rows.append({'cell':d['prefix'],'baseline':b,'benchmark':bench,
                    'N':m.get('N',0),'expected':d['expected'],'complete':d['complete'],
                    'source':d['source'], **m})

with (TBL/'final_experiment_master_matrix_fullbench_v3.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(mm_rows[0].keys()))
    w.writeheader(); [w.writerow(r) for r in mm_rows]

def pct(x): return f'{x*100:.2f}%' if x is not None else '—'
def ci(lo,hi): return f'[{lo*100:.1f}, {hi*100:.1f}]' if lo is not None else '—'

md = ['# Master matrix v14 — Phase A+B+C (full benchmarks)', '',
      'B0 from v11 commit 684a818. B1_v5/B2_v5 from Phase A d2cf0b4. B3_v5 from Phase B 98d39e1.',
      'B4_v5 from Phase C (this run) — controller with verifier+repair on top of multi-candidate pool.',
      '',
      '| Baseline | Bench | N | EX | 95% CI | Exec | Safe | Fallback | Planner used | Plan valid | Repair used | Cand avg | Consensus avg | Avg LM calls | Lat p50 | Lat p95 |',
      '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in mm_rows:
    md.append(f'| {r["baseline"]} | {r["benchmark"]} | {r["N"]} | {pct(r.get("EX"))} | {ci(r.get("EX_lo"),r.get("EX_hi"))} | '
              f'{pct(r.get("exec_pct"))} | {pct(r.get("safe_pct"))} | {pct(r.get("fallback_pct"))} | '
              f'{pct(r.get("planner_used_pct"))} | {pct(r.get("plan_valid_pct"))} | {pct(r.get("repair_used_pct"))} | '
              f'{r.get("candidate_avg",0):.2f} | {r.get("consensus_avg",0):.2f} | {r.get("lm_calls_avg",0):.2f} | '
              f'{(r.get("lat_p50") or 0):.0f} | {(r.get("lat_p95") or 0):.0f} |')
(TBL/'final_experiment_master_matrix_fullbench_v3.md').write_text('\n'.join(md)+'\n', encoding='utf-8')

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
    ('Spider','B0','B4_v5','spider_dev'),
    ('Spider','B2_v5','B4_v5','spider_dev'),
    ('Spider','B3_v5','B4_v5','spider_dev'),
    ('BIRD','B0','B4_v5','bird_full'),
    ('BIRD','B2_v5','B4_v5','bird_full'),
    ('BIRD','B3_v5','B4_v5','bird_full'),
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
with (TBL/'paired_significance_fullbench_v3.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(ps_rows[0].keys()))
    w.writeheader(); [w.writerow(r) for r in ps_rows]

# ---------- controller source breakdown ----------
sb_rows = []
for bench in ('spider_dev','bird_full'):
    rows = data.get(('B4_v5', bench), {}).get('rows', [])
    if not rows: continue
    cnt = Counter(r.get('selected_candidate_source','?') for r in rows)
    em_by_src = defaultdict(int); n_by_src = defaultdict(int)
    for r in rows:
        s = r.get('selected_candidate_source','?')
        n_by_src[s] += 1
        if r.get('execution_match'): em_by_src[s] += 1
    for src, n in cnt.most_common():
        sb_rows.append({'benchmark':bench,'source':src,'count':n,
                         'pct':round(n/len(rows),4),
                         'em':em_by_src[src],'em_rate':round(em_by_src[src]/max(1,n),4)})
with (TBL/'controller_source_breakdown_fullbench_v1.csv').open('w', newline='', encoding='utf-8') as f:
    if sb_rows:
        w = csv.DictWriter(f, fieldnames=list(sb_rows[0].keys()))
        w.writeheader(); [w.writerow(r) for r in sb_rows]

# ---------- verifier+repair impact ----------
imp_rows = []
for bench in ('spider_dev','bird_full'):
    rows = data.get(('B4_v5', bench), {}).get('rows', [])
    if not rows: continue
    n = len(rows)
    n_repair = sum(1 for r in rows if r.get('repair_used'))
    em_rep = sum(1 for r in rows if r.get('repair_used') and r.get('execution_match'))
    n_norep = n - n_repair
    em_norep = sum(1 for r in rows if not r.get('repair_used') and r.get('execution_match'))
    n_fallback = sum(1 for r in rows if r.get('fallback_used'))
    em_fb = sum(1 for r in rows if r.get('fallback_used') and r.get('execution_match'))
    imp_rows.append({'benchmark':bench,
                      'n_total':n,'em_total':sum(1 for r in rows if r.get('execution_match')),
                      'n_repair':n_repair,'em_repair':em_rep,
                      'em_repair_rate':round(em_rep/max(1,n_repair),4),
                      'n_norepair':n_norep,'em_norepair':em_norep,
                      'em_norepair_rate':round(em_norep/max(1,n_norep),4),
                      'n_fallback_to_anchor':n_fallback,'em_fallback':em_fb})
with (TBL/'verifier_repair_impact_fullbench_v1.csv').open('w', newline='', encoding='utf-8') as f:
    if imp_rows:
        w = csv.DictWriter(f, fieldnames=list(imp_rows[0].keys()))
        w.writeheader(); [w.writerow(r) for r in imp_rows]

# ---------- analysis markdown ----------
def m_for(b, bench):
    return next((r for r in mm_rows if r['baseline']==b and r['benchmark']==bench), {})

ca_lines = ['# Controller analysis (Phase C b4_v5 = candidate pool + verifier + bounded repair)', '',
    f'_Generated: {time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}._',
    '',
    '## Headline EX', '',
    '| Bench | B0 | B1_v5 | B2_v5 | B3_v5 | **B4_v5** |',
    '|---|---:|---:|---:|---:|---:|']
for bench, label in [('spider_dev','Spider dev'),('bird_full','BIRD Mini-Dev')]:
    ca_lines.append(f'| {label} | {pct(m_for("B0",bench).get("EX"))} | {pct(m_for("B1_v5",bench).get("EX"))} | '
                     f'{pct(m_for("B2_v5",bench).get("EX"))} | {pct(m_for("B3_v5",bench).get("EX"))} | '
                     f'**{pct(m_for("B4_v5",bench).get("EX"))}** |')

ca_lines += ['', '## Paired stats (key questions)', '',
    '| Bench | A | B | n | EX(A) | EX(B) | Δ pp | 95% CI pp | McNemar p | helpful | harmful |',
    '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in ps_rows:
    if r['n']==0: continue
    ca_lines.append(f'| {r["bench"]} | {r["A"]} | {r["B"]} | {r["n"]} | {r["A_em"]*100:.2f}% | {r["B_em"]*100:.2f}% | '
                     f'{r["diff_pp"]:+.2f} | [{r["boot_lo_pp"]:+.2f}, {r["boot_hi_pp"]:+.2f}] | '
                     f'{r["mcnemar_p"]:.4f} | {r["helpful"]} | {r["harmful"]} |')

ca_lines += ['', '## Controller-source breakdown (B4_v5 final pick distribution)', '']
for bench, label in [('spider_dev','Spider dev'),('bird_full','BIRD Mini-Dev')]:
    rs = [r for r in sb_rows if r['benchmark']==bench]
    if not rs: continue
    ca_lines.append(f'### {label}')
    ca_lines.append('| source | count | pct | EX | EX rate |')
    ca_lines.append('|---|---:|---:|---:|---:|')
    for r in rs:
        ca_lines.append(f'| {r["source"]} | {r["count"]} | {r["pct"]*100:.1f}% | {r["em"]} | {r["em_rate"]*100:.2f}% |')
    ca_lines.append('')

ca_lines += ['## Verifier + repair impact', '',
    '| Bench | N | total EX | repair n | repair EX | repair EX rate | no-repair n | no-repair EX rate | fallback-to-anchor n | fallback EX |',
    '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in imp_rows:
    ca_lines.append(f'| {r["benchmark"]} | {r["n_total"]} | {r["em_total"]} | {r["n_repair"]} | {r["em_repair"]} | {r["em_repair_rate"]*100:.2f}% | '
                     f'{r["n_norepair"]} | {r["em_norepair_rate"]*100:.2f}% | {r["n_fallback_to_anchor"]} | {r["em_fallback"]} |')

# Verdicts
ca_lines += ['', '## Verdicts', '']
def verdict(r):
    if r['mcnemar_p'] is None: return 'inconclusive'
    if r['mcnemar_p'] >= 0.05: return f'no significant difference (p={r["mcnemar_p"]:.4f})'
    if r['diff_pp'] > 0: return f'**{r["B"]} significantly beats {r["A"]}** (Δ {r["diff_pp"]:+.2f} pp, p={r["mcnemar_p"]:.4f})'
    return f'**{r["B"]} significantly worse than {r["A"]}** (Δ {r["diff_pp"]:+.2f} pp, p={r["mcnemar_p"]:.4f})'
for r in ps_rows:
    if r['n']==0: continue
    ca_lines.append(f'- {r["bench"]} {r["A"]} → {r["B"]}: {verdict(r)} (helpful {r["helpful"]} / harmful {r["harmful"]})')

(LOG/'controller_analysis_fullbench_v1.md').write_text('\n'.join(ca_lines)+'\n', encoding='utf-8')

# ---------- plots ----------
fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
for ax, bench, ttl in zip(axes, ['spider_dev','bird_full'],
                            ['Spider dev (1034)','BIRD Mini-Dev (500)']):
    cells = [r for r in mm_rows if r['benchmark']==bench and r.get('EX') is not None]
    cells.sort(key=lambda r: ['B0','B1_v5','B2_v5','B3_v5','B4_v5'].index(r['baseline']) if r['baseline'] in ['B0','B1_v5','B2_v5','B3_v5','B4_v5'] else 99)
    xs = [r['baseline'] for r in cells]
    ys = [r['EX']*100 for r in cells]
    err_lo = [r['EX']*100 - r['EX_lo']*100 for r in cells]
    err_hi = [r['EX_hi']*100 - r['EX']*100 for r in cells]
    cmap = {'B0':'#3a82f6','B1_v5':'#f59e0b','B2_v5':'#a855f7','B3_v5':'#ef4444','B4_v5':'#22c55e'}
    bars = ax.bar(xs, ys, yerr=[err_lo, err_hi], capsize=5,
                   color=[cmap.get(b,'#888') for b in xs], edgecolor='black', linewidth=0.6)
    for bar, y in zip(bars, ys):
        ax.text(bar.get_x()+bar.get_width()/2, y+0.5, f'{y:.1f}%', ha='center', fontsize=10, fontweight='bold')
    ax.set_title(ttl); ax.set_ylabel('Execution Match (%)'); ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(0, max(ys)*1.25 if ys else 100)
fig.suptitle('Phase A+B+C ladder — Wilson 95% CI', fontsize=13, fontweight='bold')
fig.tight_layout()
fig.savefig(PLT/'controller_overview_fullbench.png', dpi=140, bbox_inches='tight')
plt.close(fig)

print('Phase C consolidation done.')
print()
for r in mm_rows:
    print(f'  {r["baseline"]:6s} {r["benchmark"]:12s} N={r["N"]:5d} EX={pct(r.get("EX")):>8s} CI={ci(r.get("EX_lo"),r.get("EX_hi")):>14s}')
