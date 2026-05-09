# Phase B consolidation:
# - Joins b3_v5 cells (Spider/BIRD) with v11 B0 anchor and Phase A b1_v5/b2_v5.
# - Computes:
#     * master matrix v13 (Phase A + Phase B together)
#     * paired stats: B0 vs B3_v5; B2_v5 vs B3_v5 (best Phase A); B1_v5 vs B3_v5
#     * planner harm analysis (helpful/harmful/neutral, breakdown by easy/hard,
#       breakdown by selected_candidate_source, by compiler_status)
#     * compiler family success matrix
# - Writes:
#     outputs/tables/final_experiment_master_matrix_fullbench_v2.{csv,md}
#     outputs/tables/paired_significance_fullbench_v2.csv
#     outputs/tables/planner_harm_breakdown_fullbench_v1.csv
#     outputs/tables/compiler_family_success_fullbench_v1.csv
#     outputs/logs/planner_harm_analysis_fullbench_v1.md
#     outputs/plots/planner_vs_anchor_fullbench.png
from __future__ import annotations
import json, math, os, csv, time
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
    ('B0',    'bird_full',  'b0_qwen2p5_coder_7b_bird_full',          500, 'v11_anchor'),
    ('B1_v5', 'bird_full',  'b1v5_qwen2p5_coder_7b_bird_full',        500, 'phase_a'),
    ('B2_v5', 'bird_full',  'b2v5_qwen2p5_coder_7b_bird_full',        500, 'phase_a'),
    ('B3_v5', 'bird_full',  'b3v5_qwen2p5_coder_7b_bird_full',        500, 'phase_b'),
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
    xs = sorted(xs); k = (len(xs)-1)*q
    lo, hi = math.floor(k), math.ceil(k)
    return xs[int(k)] if lo == hi else xs[lo]*(hi-k)+xs[hi]*(k-lo)

data = {}
for bl, bench, prefix, expected, source in CELLS:
    rows = load(prefix)
    data[(bl, bench)] = {'baseline':bl,'bench':bench,'prefix':prefix,
                          'expected':expected,'rows':rows,'source':source,
                          'n':len(rows),'complete':len(rows)>=expected}
    print(f'  {prefix}: {len(rows)}/{expected} {"OK" if len(rows)>=expected else "PARTIAL"} ({source})')

# ---------- master matrix v13 ----------
def cell_metrics(d):
    rows = d['rows']; n = len(rows)
    if n == 0: return {'N':0,'EX':None}
    em = sum(1 for r in rows if r.get('execution_match'))
    exec_ok = sum(1 for r in rows if r.get('executable'))
    safe = sum(1 for r in rows if r.get('safe_select'))
    fb = sum(1 for r in rows if r.get('fallback_used'))
    pl_used = sum(1 for r in rows if r.get('planner_used'))
    pl_valid = sum(1 for r in rows if r.get('plan_valid'))
    lats = [float(r.get('latency_ms',0) or 0) for r in rows]
    cts = [int(r.get('completion_tokens',0) or 0) for r in rows]
    ex_rate = em/n; lo, hi = wilson(ex_rate, n)
    return {'N':n,'EX':ex_rate,'EX_lo':lo,'EX_hi':hi,
            'exec_pct':exec_ok/n,'safe_pct':safe/n,'fallback_pct':fb/n,
            'planner_used_pct':pl_used/n,'plan_valid_pct':pl_valid/n,
            'lat_p50':percentile(lats,0.5),'lat_p95':percentile(lats,0.95),
            'completion_tokens_p50':percentile(cts,0.5),
            'lm_calls_avg': (sum(int(r.get('lm_calls',1) or 1) for r in rows) / n)}

mm_rows = []
for (b, bench), d in data.items():
    m = cell_metrics(d)
    mm_rows.append({'cell':d['prefix'],'baseline':b,'benchmark':bench,
                    'N':m.get('N',0),'expected':d['expected'],'complete':d['complete'],
                    'source':d['source'], **m})

with (TBL/'final_experiment_master_matrix_fullbench_v2.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(mm_rows[0].keys()))
    w.writeheader(); [w.writerow(r) for r in mm_rows]

def pct(x): return f'{x*100:.2f}%' if x is not None else '—'
def ci(lo,hi): return f'[{lo*100:.1f}, {hi*100:.1f}]' if lo is not None else '—'

md = ['# Master matrix v13 — Phase A+B (full benchmarks)', '',
      'B0 from v11 commit 684a818. B1_v5/B2_v5 from Phase A commit d2cf0b4. B3_v5 from Phase B (this run).',
      '',
      '| Baseline | Bench | N | EX | 95% CI | Exec | Safe | Fallback | Planner used | Plan valid | Avg LM calls | Lat p50 | Lat p95 |',
      '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in mm_rows:
    md.append(f'| {r["baseline"]} | {r["benchmark"]} | {r["N"]} | {pct(r.get("EX"))} | {ci(r.get("EX_lo"),r.get("EX_hi"))} | '
              f'{pct(r.get("exec_pct"))} | {pct(r.get("safe_pct"))} | {pct(r.get("fallback_pct"))} | '
              f'{pct(r.get("planner_used_pct"))} | {pct(r.get("plan_valid_pct"))} | {r.get("lm_calls_avg",0):.2f} | '
              f'{(r.get("lat_p50") or 0):.0f} | {(r.get("lat_p95") or 0):.0f} |')
(TBL/'final_experiment_master_matrix_fullbench_v2.md').write_text('\n'.join(md)+'\n', encoding='utf-8')

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
    ('Spider','B0','B3_v5','spider_dev'),
    ('Spider','B1_v5','B3_v5','spider_dev'),
    ('Spider','B2_v5','B3_v5','spider_dev'),
    ('BIRD','B0','B3_v5','bird_full'),
    ('BIRD','B1_v5','B3_v5','bird_full'),
    ('BIRD','B2_v5','B3_v5','bird_full'),
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
with (TBL/'paired_significance_fullbench_v2.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(ps_rows[0].keys()))
    w.writeheader(); [w.writerow(r) for r in ps_rows]

# ---------- planner harm breakdown ----------
def harm_breakdown(b3_rows, anchor_rows):
    """Per-row: helpful (b3 right, anchor wrong), harmful (b3 wrong, anchor right), neutral."""
    am = {r['idx']: r for r in anchor_rows}
    out = []
    for r in b3_rows:
        a = am.get(r['idx'])
        if a is None: continue
        b3_em = bool(r.get('execution_match')); b0_em = bool(a.get('execution_match'))
        cls = 'neutral'
        if b3_em and not b0_em: cls = 'helpful'
        elif b0_em and not b3_em: cls = 'harmful'
        out.append({
            'idx': r['idx'], 'class': cls,
            'difficulty': r.get('difficulty',''),
            'difficulty_score': r.get('difficulty_score',0.0),
            'planner_used': r.get('planner_used', False),
            'plan_valid': r.get('plan_valid', False),
            'compiler_status': r.get('compiler_status',''),
            'selected_candidate_source': r.get('selected_candidate_source',''),
            'fallback_used': r.get('fallback_used', False),
            'fallback_reason': r.get('fallback_reason',''),
            'lm_calls': r.get('lm_calls', 1),
        })
    return out

ph_rows = []
for bench in ('spider_dev','bird_full'):
    b3 = data.get(('B3_v5', bench), {}).get('rows', [])
    b0 = data.get(('B0', bench), {}).get('rows', [])
    if not b3 or not b0: continue
    bd = harm_breakdown(b3, b0)
    for r in bd:
        ph_rows.append({'benchmark': bench, **r})

with (TBL/'planner_harm_breakdown_fullbench_v1.csv').open('w', newline='', encoding='utf-8') as f:
    if ph_rows:
        w = csv.DictWriter(f, fieldnames=list(ph_rows[0].keys()))
        w.writeheader(); [w.writerow(r) for r in ph_rows]

# Aggregate harm breakdown
def aggregate_harm(rows):
    groups = defaultdict(lambda: {'helpful':0,'harmful':0,'neutral':0})
    for r in rows:
        key = (r['benchmark'], r.get('difficulty','?'),
               r.get('selected_candidate_source','?'),
               r.get('compiler_status','?'),
               'plan_valid=True' if r.get('plan_valid') else 'plan_valid=False')
        groups[key][r['class']] += 1
    return groups

agg = aggregate_harm(ph_rows)
agg_rows = [{'benchmark':k[0],'difficulty':k[1],'src':k[2],'compiler_status':k[3],'plan_valid':k[4],
              'helpful':v['helpful'],'harmful':v['harmful'],'neutral':v['neutral'],
              'n':v['helpful']+v['harmful']+v['neutral'],
              'net':v['helpful']-v['harmful']}
             for k,v in sorted(agg.items())]
agg_rows.sort(key=lambda r: -r['net'])
# Save aggregated breakdown
agg_path = TBL/'planner_harm_aggregate_fullbench_v1.csv'
with agg_path.open('w', newline='', encoding='utf-8') as f:
    if agg_rows:
        w = csv.DictWriter(f, fieldnames=list(agg_rows[0].keys()))
        w.writeheader(); [w.writerow(r) for r in agg_rows]

# Compiler family success
fam_counts = defaultdict(lambda: {'total':0,'em':0})
for r in data.get(('B3_v5','spider_dev'),{}).get('rows',[]) + data.get(('B3_v5','bird_full'),{}).get('rows',[]):
    fams = r.get('compile_families') or ['skipped']
    if r.get('selected_candidate_source','').startswith('b0_anchor'): fams = ['anchor_only']
    for fam in fams:
        fam_counts[fam]['total'] += 1
        if r.get('execution_match'): fam_counts[fam]['em'] += 1
fam_rows = [{'family':k,'total':v['total'],'em':v['em'],'em_rate':round(v['em']/max(1,v['total']),4)}
            for k,v in sorted(fam_counts.items(), key=lambda kv: -kv[1]['total'])]
with (TBL/'compiler_family_success_fullbench_v1.csv').open('w', newline='', encoding='utf-8') as f:
    if fam_rows:
        w = csv.DictWriter(f, fieldnames=list(fam_rows[0].keys()))
        w.writeheader(); [w.writerow(r) for r in fam_rows]

# ---------- planner harm analysis markdown ----------
def m_for(b, bench):
    return next((r for r in mm_rows if r['baseline']==b and r['benchmark']==bench), {})

ha_lines = ['# Planner harm analysis (Phase B b3_v5 vs anchor and Phase A best)', '',
    f'_Generated: {time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}._',
    '',
    '## Headline EX', '',
    '| Bench | B0 anchor | B1_v5 retr | B2_v5 retr+ev | B3_v5 planner+compiler |',
    '|---|---:|---:|---:|---:|']
for bench, label in [('spider_dev','Spider dev (1034)'), ('bird_full','BIRD Mini-Dev (500)')]:
    ha_lines.append(f'| {label} | {pct(m_for("B0", bench).get("EX"))} | {pct(m_for("B1_v5", bench).get("EX"))} | '
                     f'{pct(m_for("B2_v5", bench).get("EX"))} | {pct(m_for("B3_v5", bench).get("EX"))} |')
ha_lines += ['', '## Paired comparisons', '',
    '| Bench | A | B | n | EX(A) | EX(B) | Δ pp | 95% CI pp | McNemar p | helpful | harmful | neutral |',
    '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in ps_rows:
    if r['n']==0: continue
    ha_lines.append(f'| {r["bench"]} | {r["A"]} | {r["B"]} | {r["n"]} | {r["A_em"]*100:.2f}% | {r["B_em"]*100:.2f}% | '
                     f'{r["diff_pp"]:+.2f} | [{r["boot_lo_pp"]:+.2f}, {r["boot_hi_pp"]:+.2f}] | '
                     f'{r["mcnemar_p"]:.4f} | {r["helpful"]} | {r["harmful"]} | {r["neutral"]} |')

ha_lines += ['', '## Selected-candidate breakdown (Phase B b3_v5)', '']
src_per_bench = defaultdict(lambda: Counter())
for r in data.get(('B3_v5','spider_dev'),{}).get('rows',[]):
    src_per_bench['spider'][r.get('selected_candidate_source','?')] += 1
for r in data.get(('B3_v5','bird_full'),{}).get('rows',[]):
    src_per_bench['bird'][r.get('selected_candidate_source','?')] += 1
for bench, c in src_per_bench.items():
    total = sum(c.values()) or 1
    ha_lines.append(f'### {bench}')
    ha_lines.append('| source | count | pct |')
    ha_lines.append('|---|---:|---:|')
    for k, v in c.most_common():
        ha_lines.append(f'| {k} | {v} | {v/total*100:.1f}% |')
    ha_lines.append('')

# Compiler family success
ha_lines += ['## Compiler family success (Phase B b3_v5, both benchmarks combined)', '',
             '| family | total | EX | EX rate |',
             '|---|---:|---:|---:|']
for fr in fam_rows:
    ha_lines.append(f'| {fr["family"]} | {fr["total"]} | {fr["em"]} | {fr["em_rate"]*100:.2f}% |')

# Verdicts
ha_lines += ['', '## Verdicts', '']
def verdict(r):
    if r['mcnemar_p'] is None: return 'inconclusive'
    if r['mcnemar_p'] >= 0.05: return f'no significant difference (p={r["mcnemar_p"]:.4f})'
    if r['diff_pp'] > 0: return f'**{r["B"]} significantly beats {r["A"]}** (Δ {r["diff_pp"]:+.2f} pp, p={r["mcnemar_p"]:.4f})'
    return f'**{r["B"]} significantly worse than {r["A"]}** (Δ {r["diff_pp"]:+.2f} pp, p={r["mcnemar_p"]:.4f})'
for r in ps_rows:
    if r['n']==0: continue
    ha_lines.append(f'- {r["bench"]} {r["A"]} → {r["B"]}: {verdict(r)} (helpful {r["helpful"]} / harmful {r["harmful"]})')

(LOG/'planner_harm_analysis_fullbench_v1.md').write_text('\n'.join(ha_lines)+'\n', encoding='utf-8')

# ---------- planner_vs_anchor plot ----------
fig, ax = plt.subplots(figsize=(11, 4.5))
ps_plot = [r for r in ps_rows if r['n']>0]
ps_plot = list(reversed(ps_plot))
labels = [f'{r["bench"]}: {r["B"]} − {r["A"]}' for r in ps_plot]
diffs = [r['diff_pp'] for r in ps_plot]
los = [r['boot_lo_pp'] for r in ps_plot]; his = [r['boot_hi_pp'] for r in ps_plot]
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
ax.set_xlabel('Δ pp of B − A — paired bootstrap 95% CI; McNemar two-sided exact')
ax.set_title('Phase B planner vs anchor and Phase A best — paired comparisons')
ax.grid(axis='x', alpha=0.3)
fig.tight_layout()
fig.savefig(PLT/'planner_vs_anchor_fullbench.png', dpi=140, bbox_inches='tight'); plt.close(fig)

print('Phase B consolidation done.')
print()
for r in mm_rows:
    print(f'  {r["baseline"]:6s} {r["benchmark"]:12s} N={r["N"]:5d} EX={pct(r.get("EX")):>8s} CI={ci(r.get("EX_lo"),r.get("EX_hi")):>14s}')
