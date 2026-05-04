# Phase 6 consolidation:
# - Joins B6_v7 cells with the full ladder (B0..B5_v6).
# - Computes:
#     * master matrix v17
#     * paired stats: B6_v7 vs B0/B2_v5/B4_v5/B5_v6 on Spider+BIRD
#     * judge invocation/override audit
#     * selector confusion C0 vs C2 (the named gap)
#     * judge confidence calibration buckets
#     * helpful/harmful by judge override
# - Writes:
#     outputs/tables/final_experiment_master_matrix_fullbench_v6.{csv,md}
#     outputs/tables/paired_significance_b6_v7.csv
#     outputs/tables/selector_confusion_c0_c2_v7.csv
#     outputs/tables/controller_source_breakdown_b6_v7.csv
#     outputs/tables/helpful_harmful_selector_v7.csv
#     outputs/tables/judge_calibration_buckets_v7.csv
#     outputs/logs/selector_design_v7.md
#     outputs/logs/bird_discrimination_gap_closure_v7.md
#     outputs/plots/b6v7_overview.png
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
    ('B3_v5', 'spider_dev', 'b3v5_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_b'),
    ('B4_v5', 'spider_dev', 'b4v5_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_c'),
    ('B5_v6', 'spider_dev', 'b5v6_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_r2'),
    ('B6_v7', 'spider_dev', 'b6v7_qwen2p5_coder_7b_spider_dev_full', 1034, 'phase_six'),
    ('B0',    'bird_full',  'b0_qwen2p5_coder_7b_bird_full',          500, 'v11_anchor'),
    ('B1_v5', 'bird_full',  'b1v5_qwen2p5_coder_7b_bird_full',        500, 'phase_a'),
    ('B2_v5', 'bird_full',  'b2v5_qwen2p5_coder_7b_bird_full',        500, 'phase_a'),
    ('B3_v5', 'bird_full',  'b3v5_qwen2p5_coder_7b_bird_full',        500, 'phase_b'),
    ('B4_v5', 'bird_full',  'b4v5_qwen2p5_coder_7b_bird_full',        500, 'phase_c'),
    ('B5_v6', 'bird_full',  'b5v6_qwen2p5_coder_7b_bird_full',        500, 'phase_r2'),
    ('B6_v7', 'bird_full',  'b6v7_qwen2p5_coder_7b_bird_full',        500, 'phase_six'),
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
    lats = [float(r.get('latency_ms',0) or 0) for r in rows]
    cts = [int(r.get('completion_tokens',0) or 0) for r in rows]
    lm_avg = (sum(int(r.get('lm_calls',1) or 1) for r in rows) / n)
    ex_rate = em/n; lo, hi = wilson(ex_rate, n)
    return {'N':n,'EX':ex_rate,'EX_lo':lo,'EX_hi':hi,
            'exec_pct':exec_ok/n,'safe_pct':safe/n,
            'judge_invoked_pct':j_inv/n,'judge_overrode_pct':j_ovr/n,
            'lat_p50':percentile(lats,0.5),'lat_p95':percentile(lats,0.95),
            'completion_tokens_p50':percentile(cts,0.5),'lm_calls_avg':lm_avg}

mm_rows = []
for (b, bench), d in data.items():
    m = cell_metrics(d)
    mm_rows.append({'cell':d['prefix'],'baseline':b,'benchmark':bench,
                    'N':m.get('N',0),'expected':d['expected'],'complete':d['complete'],
                    'source':d['source'], **m})

with (TBL/'final_experiment_master_matrix_fullbench_v6.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(mm_rows[0].keys()))
    w.writeheader(); [w.writerow(r) for r in mm_rows]

def pct(x): return f'{x*100:.2f}%' if x is not None else '—'
def ci(lo,hi): return f'[{lo*100:.1f}, {hi*100:.1f}]' if lo is not None else '—'

md = ['# Master matrix v17 — Phase 6 (B6_v7 LLM-as-judge controller)', '',
      'B0 from v11. B1_v5/B2_v5 Phase A. B3_v5 Phase B. B4_v5 Phase C. B5_v6 Phase R2.',
      'B6_v7 = B4_v5 controller + calibrated LLM-as-judge selector layer (Coder-7B as judge).',
      '',
      '| Baseline | Bench | N | EX | 95% CI | Exec | Safe | Judge inv | Judge ovr | Avg LM calls | Lat p50 | Lat p95 |',
      '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in mm_rows:
    md.append(f'| {r["baseline"]} | {r["benchmark"]} | {r["N"]} | {pct(r.get("EX"))} | {ci(r.get("EX_lo"),r.get("EX_hi"))} | '
              f'{pct(r.get("exec_pct"))} | {pct(r.get("safe_pct"))} | '
              f'{pct(r.get("judge_invoked_pct",0))} | {pct(r.get("judge_overrode_pct",0))} | '
              f'{r.get("lm_calls_avg",0):.2f} | '
              f'{(r.get("lat_p50") or 0):.0f} | {(r.get("lat_p95") or 0):.0f} |')
(TBL/'final_experiment_master_matrix_fullbench_v6.md').write_text('\n'.join(md)+'\n', encoding='utf-8')

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
    ('Spider','B0','B6_v7','spider_dev'),
    ('Spider','B2_v5','B6_v7','spider_dev'),
    ('Spider','B4_v5','B6_v7','spider_dev'),
    ('Spider','B5_v6','B6_v7','spider_dev'),
    ('BIRD','B0','B6_v7','bird_full'),
    ('BIRD','B2_v5','B6_v7','bird_full'),
    ('BIRD','B4_v5','B6_v7','bird_full'),
    ('BIRD','B5_v6','B6_v7','bird_full'),
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
with (TBL/'paired_significance_b6_v7.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(ps_rows[0].keys()))
    w.writeheader(); [w.writerow(r) for r in ps_rows]

# ---------- selector confusion C0 vs C2 (the named BIRD gap) ----------
sc_rows = []
for bench in ('spider_dev','bird_full'):
    rows = data.get(('B6_v7', bench), {}).get('rows', [])
    if not rows: continue
    # confusion: heuristic_top vs final_top, focus on C0/C2
    cm = defaultdict(int)
    for r in rows:
        h = r.get('heuristic_top_source','?')
        f = r.get('selected_candidate_source','?')
        cm[(h, f)] += 1
        # judge override impact on EX
    for (h, f), n in sorted(cm.items()):
        rs = [r for r in rows if r.get('heuristic_top_source')==h and r.get('selected_candidate_source')==f]
        em_n = sum(1 for r in rs if r.get('execution_match'))
        sc_rows.append({'benchmark':bench,'heuristic_top':h,'final_top':f,
                         'count':n,'em':em_n,
                         'em_rate':round(em_n/max(1,n),4),
                         'override': h != f})
with (TBL/'selector_confusion_c0_c2_v7.csv').open('w', newline='', encoding='utf-8') as f:
    if sc_rows:
        w = csv.DictWriter(f, fieldnames=list(sc_rows[0].keys()))
        w.writeheader(); [w.writerow(r) for r in sc_rows]

# ---------- source breakdown ----------
sb_rows = []
for bench in ('spider_dev','bird_full'):
    rows = data.get(('B6_v7', bench), {}).get('rows', [])
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
with (TBL/'controller_source_breakdown_b6_v7.csv').open('w', newline='', encoding='utf-8') as f:
    if sb_rows:
        w = csv.DictWriter(f, fieldnames=list(sb_rows[0].keys()))
        w.writeheader(); [w.writerow(r) for r in sb_rows]

# ---------- helpful/harmful by judge override ----------
hh_rows = []
for bench, anchor_baseline in [('spider_dev','B4_v5'),('bird_full','B4_v5')]:
    b6 = data.get(('B6_v7', bench), {}).get('rows', [])
    anchor = data.get((anchor_baseline, bench), {}).get('rows', [])
    if not b6 or not anchor: continue
    am = {r['idx']: r for r in anchor}
    helpful = harmful = neutral = 0
    h_overrode = ha_overrode = neu_overrode = 0
    for r in b6:
        a = am.get(r['idx'])
        if a is None: continue
        b6_em = bool(r.get('execution_match')); a_em = bool(a.get('execution_match'))
        ovr = bool(r.get('judge_overrode'))
        if b6_em and not a_em: helpful += 1; h_overrode += int(ovr)
        elif a_em and not b6_em: harmful += 1; ha_overrode += int(ovr)
        else: neutral += 1; neu_overrode += int(ovr)
    hh_rows.append({'benchmark':bench,'anchor_baseline':anchor_baseline,
                     'helpful':helpful,'harmful':harmful,'neutral':neutral,
                     'helpful_via_override':h_overrode,
                     'harmful_via_override':ha_overrode,
                     'neutral_via_override':neu_overrode,
                     'net':helpful-harmful})
with (TBL/'helpful_harmful_selector_v7.csv').open('w', newline='', encoding='utf-8') as f:
    if hh_rows:
        w = csv.DictWriter(f, fieldnames=list(hh_rows[0].keys()))
        w.writeheader(); [w.writerow(r) for r in hh_rows]

# ---------- judge confidence calibration ----------
jc_rows = []
buckets = [(0.0,0.5,'low'),(0.5,0.65,'mid'),(0.65,0.8,'high'),(0.8,1.01,'very_high')]
for bench in ('spider_dev','bird_full'):
    rows = data.get(('B6_v7', bench), {}).get('rows', [])
    if not rows: continue
    inv = [r for r in rows if r.get('judge_invoked')]
    for lo, hi, lbl in buckets:
        in_b = [r for r in inv if lo <= float(r.get('judge_confidence', 0) or 0) < hi]
        n_b = len(in_b); em_b = sum(1 for r in in_b if r.get('execution_match'))
        ovr_b = sum(1 for r in in_b if r.get('judge_overrode'))
        jc_rows.append({'benchmark':bench,'bucket':lbl,
                         'lo':lo,'hi':hi,'n':n_b,
                         'em':em_b,'em_rate':round(em_b/max(1,n_b),4),
                         'overrode':ovr_b,
                         'override_rate':round(ovr_b/max(1,n_b),4)})
with (TBL/'judge_calibration_buckets_v7.csv').open('w', newline='', encoding='utf-8') as f:
    if jc_rows:
        w = csv.DictWriter(f, fieldnames=list(jc_rows[0].keys()))
        w.writeheader(); [w.writerow(r) for r in jc_rows]

# ---------- design memo + bird closure memo ----------
def m_for(b, bench):
    return next((r for r in mm_rows if r['baseline']==b and r['benchmark']==bench), {})

design = ['# Selector design v7 (LLM-as-judge over heuristic verifier)', '',
    f'_Generated: {time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}._',
    '',
    'Architecture: B4_v5 controller (Phase C) augmented with a calibrated',
    'LLM-as-judge selector (Coder-7B as judge, single-model setup).',
    '',
    '## Calibration triggers',
    '',
    '- benchmark profile: bird (loose: margin<0.10, conf>=0.65, anchor override OK)',
    '- benchmark profile: spider (safe: margin<0.04, conf>=0.75, anchor override OK)',
    '- requires C2_retrieval_evidence executable in candidate set',
    '- requires non-empty evidence text or db-level evidence store',
    '- requires consensus_top_count < n_candidates (not all agree)',
    '',
    '## Headline EX', '',
    '| Bench | B0 | B2_v5 | B4_v5 | B5_v6 | **B6_v7** |',
    '|---|---:|---:|---:|---:|---:|']
for bench, label in [('spider_dev','Spider dev (1034)'),('bird_full','BIRD Mini-Dev (500)')]:
    design.append(f'| {label} | {pct(m_for("B0",bench).get("EX"))} | {pct(m_for("B2_v5",bench).get("EX"))} | '
                   f'{pct(m_for("B4_v5",bench).get("EX"))} | {pct(m_for("B5_v6",bench).get("EX"))} | '
                   f'**{pct(m_for("B6_v7",bench).get("EX"))}** |')

design += ['', '## Paired stats vs prior best', '',
           '| Bench | A | B | n | EX(A) | EX(B) | Δ pp | 95% CI pp | McNemar p | helpful | harmful |',
           '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in ps_rows:
    if r['n']==0: continue
    design.append(f'| {r["bench"]} | {r["A"]} | {r["B"]} | {r["n"]} | {r["A_em"]*100:.2f}% | {r["B_em"]*100:.2f}% | '
                   f'{r["diff_pp"]:+.2f} | [{r["boot_lo_pp"]:+.2f}, {r["boot_hi_pp"]:+.2f}] | '
                   f'{r["mcnemar_p"]:.4f} | {r["helpful"]} | {r["harmful"]} |')

design += ['', '## Verdicts', '']
def verdict(r):
    if r['mcnemar_p'] is None: return 'inconclusive'
    if r['mcnemar_p'] >= 0.05: return f'no significant difference (p={r["mcnemar_p"]:.4f})'
    if r['diff_pp'] > 0: return f'**{r["B"]} significantly beats {r["A"]}** (Δ {r["diff_pp"]:+.2f} pp, p={r["mcnemar_p"]:.4f})'
    return f'**{r["B"]} significantly worse than {r["A"]}** (Δ {r["diff_pp"]:+.2f} pp, p={r["mcnemar_p"]:.4f})'
for r in ps_rows:
    if r['n']==0: continue
    design.append(f'- {r["bench"]} {r["A"]} → {r["B"]}: {verdict(r)} (helpful {r["helpful"]} / harmful {r["harmful"]})')

(LOG/'selector_design_v7.md').write_text('\n'.join(design)+'\n', encoding='utf-8')

# BIRD closure memo
bird_closure = ['# BIRD discrimination gap closure memo v7', '',
    f'_Generated: {time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}._',
    '',
    '## The named gap',
    '',
    'Phase R2 conclusion (frozen): on BIRD, B2_v5 standalone (37.60%) outperformed',
    'B4_v5 controller (34.00%) and B5_v6 + reranker (31.20%). The verifier could',
    'not distinguish C0_anchor from C2_retrieval_evidence on close-call items;',
    'non-harm tie-break biased toward C0_anchor and discarded productive C2 picks.',
    '',
    '## Phase 6 result', '',
    '| Bench | B2_v5 (was best) | B6_v7 | Δ |',
    '|---|---:|---:|---:|']
b2 = m_for('B2_v5', 'bird_full'); b6 = m_for('B6_v7', 'bird_full')
b6_b2 = next((r for r in ps_rows if r['bench']=='BIRD' and r['A']=='B2_v5' and r['B']=='B6_v7'), None)
if b6 and b2:
    bird_closure.append(f'| BIRD Mini-Dev (500) | {pct(b2.get("EX"))} | {pct(b6.get("EX"))} | '
                          f'{(b6_b2["diff_pp"] if b6_b2 else 0):+.2f} pp |')

bird_closure += ['', '## Selector confusion C0 vs C2 (BIRD only)', '']
sc_bird = [r for r in sc_rows if r['benchmark']=='bird_full']
bird_closure.append('| heuristic top → final top | count | EX | EX rate | override |')
bird_closure.append('|---|---:|---:|---:|---:|')
for r in sc_bird:
    bird_closure.append(f'| {r["heuristic_top"]} → {r["final_top"]} | {r["count"]} | {r["em"]} | '
                          f'{r["em_rate"]*100:.2f}% | {r["override"]} |')

bird_closure += ['', '## Source breakdown (B6_v7 BIRD final picks)', '',
                 '| source | count | pct | EX | EX rate |',
                 '|---|---:|---:|---:|---:|']
for r in [x for x in sb_rows if x['benchmark']=='bird_full']:
    bird_closure.append(f'| {r["source"]} | {r["count"]} | {r["pct"]*100:.1f}% | {r["em"]} | {r["em_rate"]*100:.2f}% |')

bird_closure += ['', '## Helpful / harmful via judge override (vs B4_v5 anchor)', '']
hh_bird = next((r for r in hh_rows if r['benchmark']=='bird_full'), None)
if hh_bird:
    bird_closure.append(f'- helpful (B6 right, B4 wrong): {hh_bird["helpful"]}')
    bird_closure.append(f'- harmful (B6 wrong, B4 right): {hh_bird["harmful"]}')
    bird_closure.append(f'- neutral: {hh_bird["neutral"]}')
    bird_closure.append(f'- net: {hh_bird["net"]:+d}')
    bird_closure.append(f'- of which produced via judge override: helpful {hh_bird["helpful_via_override"]}, '
                          f'harmful {hh_bird["harmful_via_override"]}, neutral {hh_bird["neutral_via_override"]}')

bird_closure += ['', '## Judge confidence calibration (BIRD only)', '',
                 '| bucket | range | n | EX | EX rate | overrode | override rate |',
                 '|---|---|---:|---:|---:|---:|---:|']
for r in [x for x in jc_rows if x['benchmark']=='bird_full']:
    bird_closure.append(f'| {r["bucket"]} | [{r["lo"]:.2f}, {r["hi"]:.2f}) | {r["n"]} | {r["em"]} | '
                          f'{r["em_rate"]*100:.2f}% | {r["overrode"]} | {r["override_rate"]*100:.1f}% |')

(LOG/'bird_discrimination_gap_closure_v7.md').write_text('\n'.join(bird_closure)+'\n', encoding='utf-8')

# ---------- plot ----------
fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))
order = ['B0','B1_v5','B2_v5','B3_v5','B4_v5','B5_v6','B6_v7']
cmap = {'B0':'#3a82f6','B1_v5':'#f59e0b','B2_v5':'#a855f7','B3_v5':'#ef4444',
        'B4_v5':'#22c55e','B5_v6':'#0ea5e9','B6_v7':'#e879f9'}
for ax, bench, ttl in zip(axes, ['spider_dev','bird_full'],
                            ['Spider dev (1034)','BIRD Mini-Dev (500)']):
    cells = [r for r in mm_rows if r['benchmark']==bench and r.get('EX') is not None
              and r['baseline'] in order]
    cells.sort(key=lambda r: order.index(r['baseline']))
    xs = [r['baseline'] for r in cells]
    ys = [r['EX']*100 for r in cells]
    err_lo = [r['EX']*100 - r['EX_lo']*100 for r in cells]
    err_hi = [r['EX_hi']*100 - r['EX']*100 for r in cells]
    bars = ax.bar(xs, ys, yerr=[err_lo, err_hi], capsize=5,
                   color=[cmap.get(b,'#888') for b in xs], edgecolor='black', linewidth=0.6)
    for bar, y in zip(bars, ys):
        ax.text(bar.get_x()+bar.get_width()/2, y+0.5, f'{y:.1f}%', ha='center', fontsize=10, fontweight='bold')
    ax.set_title(ttl); ax.set_ylabel('Execution Match (%)'); ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(0, max(ys)*1.25 if ys else 100)
fig.suptitle('Phase 6 ladder — B6_v7 LLM-as-judge selector', fontsize=13, fontweight='bold')
fig.tight_layout()
fig.savefig(PLT/'b6v7_overview.png', dpi=140, bbox_inches='tight')
plt.close(fig)

print('B6_v7 consolidation done.')
print()
for r in mm_rows:
    print(f'  {r["baseline"]:6s} {r["benchmark"]:12s} N={r["N"]:5d} EX={pct(r.get("EX")):>8s} CI={ci(r.get("EX_lo"),r.get("EX_hi")):>14s}')
