# Phase D consolidation:
# - Compares B4_v5 with planner-model swap (Qwen3-8B vs Gemma-3-12b) against
#   Phase C B4_v5 baseline (planner = Coder-7B as part of single-model setup).
# - Writes:
#     outputs/tables/final_experiment_master_matrix_fullbench_v5.{csv,md}
#     outputs/tables/paired_significance_phase_d_v1.csv
#     outputs/tables/planner_swap_source_breakdown_v1.csv
#     outputs/logs/planner_swap_analysis_fullbench_v1.md
#     outputs/plots/phase_d_planner_swap.png
from __future__ import annotations
import json, math, csv, time
from pathlib import Path
from collections import Counter

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
PRED = ROOT/'outputs'/'predictions'; TBL = ROOT/'outputs'/'tables'
LOG = ROOT/'outputs'/'logs'; PLT = ROOT/'outputs'/'plots'
TBL.mkdir(parents=True, exist_ok=True); LOG.mkdir(parents=True, exist_ok=True); PLT.mkdir(parents=True, exist_ok=True)

CELLS = [
    # Anchor / best-of-each from prior phases
    ('B0',    'spider_dev', 'b0_qwen2p5_coder_7b_spider_dev_full',   1034, 'v11_anchor'),
    ('B2_v5', 'spider_dev', 'b2v5_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_a'),
    ('B4_v5', 'spider_dev', 'b4v5_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_c'),
    ('B0',    'bird_full',  'b0_qwen2p5_coder_7b_bird_full',          500, 'v11_anchor'),
    ('B2_v5', 'bird_full',  'b2v5_qwen2p5_coder_7b_bird_full',        500, 'phase_a'),
    ('B4_v5', 'bird_full',  'b4v5_qwen2p5_coder_7b_bird_full',        500, 'phase_c'),
    # Phase D — planner swap
    ('B4_v5_planner_qwen3_8b',  'spider_dev', 'b4v5_planner_qwen3_8b_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_d'),
    ('B4_v5_planner_qwen3_8b',  'bird_full',  'b4v5_planner_qwen3_8b_qwen2p5_coder_7b_bird_full',        500, 'phase_d'),
    ('B4_v5_planner_gemma_12b', 'spider_dev', 'b4v5_planner_gemma_12b_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_d'),
    ('B4_v5_planner_gemma_12b', 'bird_full',  'b4v5_planner_gemma_12b_qwen2p5_coder_7b_bird_full',        500, 'phase_d'),
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
    pl = sum(1 for r in rows if r.get('planner_used'))
    pv = sum(1 for r in rows if r.get('plan_valid'))
    rep = sum(1 for r in rows if r.get('repair_used'))
    lats = [float(r.get('latency_ms',0) or 0) for r in rows]
    cts = [int(r.get('completion_tokens',0) or 0) for r in rows]
    lm_avg = (sum(int(r.get('lm_calls',1) or 1) for r in rows) / n)
    ex_rate = em/n; lo, hi = wilson(ex_rate, n)
    return {'N':n,'EX':ex_rate,'EX_lo':lo,'EX_hi':hi,
            'exec_pct':exec_ok/n,'safe_pct':safe/n,
            'planner_used_pct':pl/n,'plan_valid_pct':pv/n,'repair_used_pct':rep/n,
            'lat_p50':percentile(lats,0.5),'lat_p95':percentile(lats,0.95),
            'completion_tokens_p50':percentile(cts,0.5),'lm_calls_avg':lm_avg}

mm_rows = []
for (b, bench), d in data.items():
    m = cell_metrics(d)
    mm_rows.append({'cell':d['prefix'],'baseline':b,'benchmark':bench,
                    'N':m.get('N',0),'expected':d['expected'],'complete':d['complete'],
                    'source':d['source'], **m})

with (TBL/'final_experiment_master_matrix_fullbench_v5.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(mm_rows[0].keys()))
    w.writeheader(); [w.writerow(r) for r in mm_rows]

def pct(x): return f'{x*100:.2f}%' if x is not None else '—'
def ci(lo,hi): return f'[{lo*100:.1f}, {hi*100:.1f}]' if lo is not None else '—'

md = ['# Master matrix v16 — through Phase D planner-model swap', '',
      'B0 from v11. B2_v5 Phase A. B4_v5 Phase C (planner=Coder-7B, single-model setup).',
      'Phase D = B4_v5 with Qwen3-8B or Gemma-3-12b-it as the planner LLM (synth=Coder-7B unchanged).',
      '',
      '| Baseline | Bench | N | EX | 95% CI | Exec | Plan valid | Avg LM calls | Lat p50 |',
      '|---|---|---:|---:|---:|---:|---:|---:|---:|']
for r in mm_rows:
    md.append(f'| {r["baseline"]} | {r["benchmark"]} | {r["N"]} | {pct(r.get("EX"))} | {ci(r.get("EX_lo"),r.get("EX_hi"))} | '
              f'{pct(r.get("exec_pct"))} | {pct(r.get("plan_valid_pct"))} | '
              f'{r.get("lm_calls_avg",0):.2f} | {(r.get("lat_p50") or 0):.0f} |')
(TBL/'final_experiment_master_matrix_fullbench_v5.md').write_text('\n'.join(md)+'\n', encoding='utf-8')

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
    ('Spider','B4_v5','B4_v5_planner_qwen3_8b','spider_dev'),
    ('Spider','B4_v5','B4_v5_planner_gemma_12b','spider_dev'),
    ('Spider','B4_v5_planner_qwen3_8b','B4_v5_planner_gemma_12b','spider_dev'),
    ('BIRD','B4_v5','B4_v5_planner_qwen3_8b','bird_full'),
    ('BIRD','B4_v5','B4_v5_planner_gemma_12b','bird_full'),
    ('BIRD','B4_v5_planner_qwen3_8b','B4_v5_planner_gemma_12b','bird_full'),
    ('Spider','B0','B4_v5_planner_qwen3_8b','spider_dev'),
    ('Spider','B0','B4_v5_planner_gemma_12b','spider_dev'),
    ('BIRD','B2_v5','B4_v5_planner_qwen3_8b','bird_full'),
    ('BIRD','B2_v5','B4_v5_planner_gemma_12b','bird_full'),
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
with (TBL/'paired_significance_phase_d_v1.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(ps_rows[0].keys()))
    w.writeheader(); [w.writerow(r) for r in ps_rows]

# ---------- source breakdown comparison (planner-related stats) ----------
sb_rows = []
for label, key in [('phase_c_default','B4_v5'),
                    ('phase_d_qwen3_8b','B4_v5_planner_qwen3_8b'),
                    ('phase_d_gemma_12b','B4_v5_planner_gemma_12b')]:
    for bench in ('spider_dev','bird_full'):
        rows = data.get((key, bench), {}).get('rows', [])
        if not rows: continue
        cnt = Counter(r.get('selected_candidate_source','?') for r in rows)
        em_by = {}
        for r in rows:
            s = r.get('selected_candidate_source','?')
            em_by[s] = em_by.get(s, 0) + (1 if r.get('execution_match') else 0)
        plan_valid = sum(1 for r in rows if r.get('plan_valid'))
        plan_used = sum(1 for r in rows if r.get('planner_used'))
        for src, n in cnt.most_common():
            sb_rows.append({'lane':label,'benchmark':bench,'source':src,'count':n,
                             'pct':round(n/len(rows),4),'em':em_by.get(src, 0),
                             'em_rate':round(em_by.get(src,0)/max(1,n),4),
                             'plan_valid_pct':round(plan_valid/len(rows),4),
                             'planner_used_pct':round(plan_used/len(rows),4)})
with (TBL/'planner_swap_source_breakdown_v1.csv').open('w', newline='', encoding='utf-8') as f:
    if sb_rows:
        w = csv.DictWriter(f, fieldnames=list(sb_rows[0].keys()))
        w.writeheader(); [w.writerow(r) for r in sb_rows]

# ---------- analysis markdown ----------
def m_for(b, bench):
    return next((r for r in mm_rows if r['baseline']==b and r['benchmark']==bench), {})

an = ['# Phase D planner-model swap analysis (full benchmarks)', '',
      f'_Generated: {time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}._',
      '',
      '## Headline EX', '',
      '| Bench | B0 | B2_v5 | B4_v5 (Coder-7B planner) | B4_v5 (Qwen3-8B planner) | B4_v5 (Gemma-12b planner) |',
      '|---|---:|---:|---:|---:|---:|']
for bench, label in [('spider_dev','Spider dev'),('bird_full','BIRD Mini-Dev')]:
    an.append(f'| {label} | {pct(m_for("B0",bench).get("EX"))} | {pct(m_for("B2_v5",bench).get("EX"))} | '
               f'{pct(m_for("B4_v5",bench).get("EX"))} | '
               f'{pct(m_for("B4_v5_planner_qwen3_8b",bench).get("EX"))} | '
               f'{pct(m_for("B4_v5_planner_gemma_12b",bench).get("EX"))} |')

an += ['', '## Paired comparisons', '',
       '| Bench | A | B | n | EX(A) | EX(B) | Δ pp | 95% CI pp | McNemar p | helpful | harmful |',
       '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in ps_rows:
    if r['n']==0: continue
    an.append(f'| {r["bench"]} | {r["A"]} | {r["B"]} | {r["n"]} | {r["A_em"]*100:.2f}% | {r["B_em"]*100:.2f}% | '
               f'{r["diff_pp"]:+.2f} | [{r["boot_lo_pp"]:+.2f}, {r["boot_hi_pp"]:+.2f}] | '
               f'{r["mcnemar_p"]:.4f} | {r["helpful"]} | {r["harmful"]} |')

an += ['', '## Plan validity + source breakdown by planner lane', '',
       '| lane | bench | source | count | pct | EX rate | plan_valid_pct | planner_used_pct |',
       '|---|---|---|---:|---:|---:|---:|---:|']
for r in sb_rows:
    an.append(f'| {r["lane"]} | {r["benchmark"]} | {r["source"]} | {r["count"]} | {r["pct"]*100:.1f}% | '
               f'{r["em_rate"]*100:.2f}% | {r["plan_valid_pct"]*100:.1f}% | {r["planner_used_pct"]*100:.1f}% |')

an += ['', '## Verdicts', '']
def verdict(r):
    if r['mcnemar_p'] is None: return 'inconclusive'
    if r['mcnemar_p'] >= 0.05: return f'no significant difference (p={r["mcnemar_p"]:.4f})'
    if r['diff_pp'] > 0: return f'**{r["B"]} significantly beats {r["A"]}** (Δ {r["diff_pp"]:+.2f} pp, p={r["mcnemar_p"]:.4f})'
    return f'**{r["B"]} significantly worse than {r["A"]}** (Δ {r["diff_pp"]:+.2f} pp, p={r["mcnemar_p"]:.4f})'
for r in ps_rows:
    if r['n']==0: continue
    an.append(f'- {r["bench"]} {r["A"]} → {r["B"]}: {verdict(r)} (helpful {r["helpful"]} / harmful {r["harmful"]})')

(LOG/'planner_swap_analysis_fullbench_v1.md').write_text('\n'.join(an)+'\n', encoding='utf-8')

# ---------- plot ----------
fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
order = ['B0','B2_v5','B4_v5','B4_v5_planner_qwen3_8b','B4_v5_planner_gemma_12b']
short_label = {'B4_v5_planner_qwen3_8b':'B4_v5\n+Qwen3-8B planner',
                'B4_v5_planner_gemma_12b':'B4_v5\n+Gemma-12b planner',
                'B4_v5':'B4_v5\n(Coder planner)'}
cmap = {'B0':'#3a82f6','B2_v5':'#a855f7','B4_v5':'#22c55e',
        'B4_v5_planner_qwen3_8b':'#f97316','B4_v5_planner_gemma_12b':'#06b6d4'}
for ax, bench, ttl in zip(axes, ['spider_dev','bird_full'],
                            ['Spider dev (1034)','BIRD Mini-Dev (500)']):
    cells = [r for r in mm_rows if r['benchmark']==bench and r.get('EX') is not None
              and r['baseline'] in order]
    cells.sort(key=lambda r: order.index(r['baseline']))
    xs = [short_label.get(r['baseline'], r['baseline']) for r in cells]
    ys = [r['EX']*100 for r in cells]
    err_lo = [r['EX']*100 - r['EX_lo']*100 for r in cells]
    err_hi = [r['EX_hi']*100 - r['EX']*100 for r in cells]
    bars = ax.bar(xs, ys, yerr=[err_lo, err_hi], capsize=5,
                   color=[cmap.get(r['baseline'],'#888') for r in cells], edgecolor='black', linewidth=0.6)
    for bar, y in zip(bars, ys):
        ax.text(bar.get_x()+bar.get_width()/2, y+0.5, f'{y:.1f}%', ha='center', fontsize=10, fontweight='bold')
    ax.set_title(ttl); ax.set_ylabel('Execution Match (%)'); ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(0, max(ys)*1.25 if ys else 100)
    ax.tick_params(axis='x', labelsize=9)
fig.suptitle('Phase D — Planner-model swap (synth = Qwen2.5-Coder-7B)', fontsize=13, fontweight='bold')
fig.tight_layout()
fig.savefig(PLT/'phase_d_planner_swap.png', dpi=140, bbox_inches='tight')
plt.close(fig)

print('Phase D consolidation done.')
print()
for r in mm_rows:
    print(f'  {r["baseline"]:30s} {r["benchmark"]:12s} N={r["N"]:5d} EX={pct(r.get("EX")):>8s}')
