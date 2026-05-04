# Phase 7 consolidation:
# - Joins B7 cells with the full ladder (B0..B6_v7).
# - Computes:
#     * master matrix v18
#     * paired stats: B7d_rich vs B6_v7 (key); B7d vs B7c (gold contribution);
#       B7d vs B7e (full ablation); B7c vs B7e (profiles vs none)
#     * source breakdown for B7 cells
#     * evidence ablation table
# - Writes:
#     outputs/tables/final_experiment_master_matrix_fullbench_v7.{csv,md}
#     outputs/tables/paired_significance_b7_v7.csv
#     outputs/tables/evidence_ablation_fullbench_v7.csv
#     outputs/tables/evidence_quality_breakdown_v7.csv
#     outputs/tables/controller_source_breakdown_b7_v7.csv
#     outputs/logs/evidence_semantics_design_v7.md
#     outputs/logs/evidence_negative_result_v7.md
#     outputs/plots/b7v7_overview.png
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
    ('B0',    'bird_full', 'b0_qwen2p5_coder_7b_bird_full',          500, 'v11_anchor'),
    ('B2_v5', 'bird_full', 'b2v5_qwen2p5_coder_7b_bird_full',        500, 'phase_a'),
    ('B4_v5', 'bird_full', 'b4v5_qwen2p5_coder_7b_bird_full',        500, 'phase_c'),
    ('B6_v7', 'bird_full', 'b6v7_qwen2p5_coder_7b_bird_full',        500, 'phase_six'),
    ('B7d_rich',          'bird_full', 'b7d_rich_qwen2p5_coder_7b_bird_full',          500, 'phase_seven'),
    ('B7c_profiles_only', 'bird_full', 'b7c_profiles_only_qwen2p5_coder_7b_bird_full', 500, 'phase_seven'),
    ('B7e_none',          'bird_full', 'b7e_none_qwen2p5_coder_7b_bird_full',          500, 'phase_seven'),
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
    ev_chars = [int(r.get('evidence_chars_rendered',0) or 0) for r in rows]
    lats = [float(r.get('latency_ms',0) or 0) for r in rows]
    cts = [int(r.get('completion_tokens',0) or 0) for r in rows]
    lm_avg = (sum(int(r.get('lm_calls',1) or 1) for r in rows) / n)
    ex_rate = em/n; lo, hi = wilson(ex_rate, n)
    return {'N':n,'EX':ex_rate,'EX_lo':lo,'EX_hi':hi,
            'exec_pct':exec_ok/n,'safe_pct':safe/n,
            'judge_invoked_pct':j_inv/n,'judge_overrode_pct':j_ovr/n,
            'evidence_chars_avg': (sum(ev_chars)/len(ev_chars)) if ev_chars else 0,
            'lat_p50':percentile(lats,0.5),'lat_p95':percentile(lats,0.95),
            'completion_tokens_p50':percentile(cts,0.5),'lm_calls_avg':lm_avg}

mm_rows = []
for (b, bench), d in data.items():
    m = cell_metrics(d)
    mm_rows.append({'cell':d['prefix'],'baseline':b,'benchmark':bench,
                    'N':m.get('N',0),'expected':d['expected'],'complete':d['complete'],
                    'source':d['source'], **m})

with (TBL/'final_experiment_master_matrix_fullbench_v7.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(mm_rows[0].keys()))
    w.writeheader(); [w.writerow(r) for r in mm_rows]

def pct(x): return f'{x*100:.2f}%' if x is not None else '—'
def ci(lo,hi): return f'[{lo*100:.1f}, {hi*100:.1f}]' if lo is not None else '—'

md = ['# Master matrix v18 — Phase 7 (B7 evidence ablations on FULL BIRD)', '',
      'B0/B2_v5/B4_v5 from prior phases. B6_v7 from Phase 6 (LLM-as-judge selector).',
      'B7 = B6_v7 controller + evidence_semantics_v7 layer with mode flags.',
      '',
      '| Baseline | Bench | N | EX | 95% CI | Exec | Judge inv | Judge ovr | Evidence chars avg | Avg LM calls |',
      '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in mm_rows:
    md.append(f'| {r["baseline"]} | {r["benchmark"]} | {r["N"]} | {pct(r.get("EX"))} | {ci(r.get("EX_lo"),r.get("EX_hi"))} | '
              f'{pct(r.get("exec_pct"))} | {pct(r.get("judge_invoked_pct",0))} | {pct(r.get("judge_overrode_pct",0))} | '
              f'{r.get("evidence_chars_avg",0):.0f} | {r.get("lm_calls_avg",0):.2f} |')
(TBL/'final_experiment_master_matrix_fullbench_v7.md').write_text('\n'.join(md)+'\n', encoding='utf-8')

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
    ('BIRD','B6_v7','B7d_rich','bird_full'),                  # rich vs judge-only
    ('BIRD','B7d_rich','B7c_profiles_only','bird_full'),       # gold contribution
    ('BIRD','B7d_rich','B7e_none','bird_full'),                # full ablation
    ('BIRD','B7c_profiles_only','B7e_none','bird_full'),       # profiles vs nothing
    ('BIRD','B6_v7','B7c_profiles_only','bird_full'),          # profiles vs B6 (no gold path)
    ('BIRD','B6_v7','B7e_none','bird_full'),                   # none vs B6
    ('BIRD','B2_v5','B7d_rich','bird_full'),                   # vs prior best evidence baseline
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
with (TBL/'paired_significance_b7_v7.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(ps_rows[0].keys()))
    w.writeheader(); [w.writerow(r) for r in ps_rows]

# ---------- evidence ablation summary table ----------
ea_rows = []
for bl in ('B7d_rich','B7c_profiles_only','B7e_none'):
    rows = data.get((bl, 'bird_full'), {}).get('rows', [])
    if not rows: continue
    n = len(rows); em = sum(1 for r in rows if r.get('execution_match'))
    j_inv = sum(1 for r in rows if r.get('judge_invoked'))
    j_ovr = sum(1 for r in rows if r.get('judge_overrode'))
    ev = [int(r.get('evidence_chars_rendered', 0) or 0) for r in rows]
    src = Counter(r.get('selected_candidate_source','?') for r in rows)
    ea_rows.append({'cell':bl, 'n':n, 'em':em, 'em_rate':round(em/n,4),
                     'evidence_chars_avg': (sum(ev)/n) if ev else 0,
                     'judge_invoked_pct': round(j_inv/n,4),
                     'judge_overrode_pct': round(j_ovr/n,4),
                     'C0_anchor': src.get('C0_anchor',0),
                     'C1_retrieval': src.get('C1_retrieval_direct',0),
                     'C2_evidence': src.get('C2_retrieval_evidence',0),
                     'C3_planner': src.get('C3_planner_compiled',0)})
with (TBL/'evidence_ablation_fullbench_v7.csv').open('w', newline='', encoding='utf-8') as f:
    if ea_rows:
        w = csv.DictWriter(f, fieldnames=list(ea_rows[0].keys()))
        w.writeheader(); [w.writerow(r) for r in ea_rows]

# ---------- evidence quality breakdown (from B7d_rich) ----------
# We don't have per-evidence-item scores in JSONL, but we can break by ev_chars buckets
eq_rows = []
buckets = [(0, 200, 'short'), (200, 400, 'mid'), (400, 600, 'long'), (600, 1000, 'very_long')]
for bl in ('B7d_rich','B7c_profiles_only','B7e_none'):
    rows = data.get((bl, 'bird_full'), {}).get('rows', [])
    if not rows: continue
    for lo, hi, lbl in buckets:
        in_b = [r for r in rows if lo <= int(r.get('evidence_chars_rendered',0) or 0) < hi]
        n_b = len(in_b); em_b = sum(1 for r in in_b if r.get('execution_match'))
        eq_rows.append({'cell':bl,'bucket':lbl,'lo':lo,'hi':hi,
                         'n':n_b,'em':em_b,
                         'em_rate': round(em_b/max(1,n_b), 4)})
with (TBL/'evidence_quality_breakdown_v7.csv').open('w', newline='', encoding='utf-8') as f:
    if eq_rows:
        w = csv.DictWriter(f, fieldnames=list(eq_rows[0].keys()))
        w.writeheader(); [w.writerow(r) for r in eq_rows]

# ---------- source breakdown ----------
sb_rows = []
for bl in ('B7d_rich','B7c_profiles_only','B7e_none'):
    rows = data.get((bl, 'bird_full'), {}).get('rows', [])
    if not rows: continue
    cnt = Counter(r.get('selected_candidate_source','?') for r in rows)
    em_by = {}
    for r in rows:
        s = r.get('selected_candidate_source','?')
        em_by[s] = em_by.get(s, 0) + (1 if r.get('execution_match') else 0)
    for src, n in cnt.most_common():
        sb_rows.append({'cell':bl,'source':src,'count':n,
                         'pct':round(n/len(rows),4),
                         'em':em_by.get(src,0),
                         'em_rate':round(em_by.get(src,0)/max(1,n),4)})
with (TBL/'controller_source_breakdown_b7_v7.csv').open('w', newline='', encoding='utf-8') as f:
    if sb_rows:
        w = csv.DictWriter(f, fieldnames=list(sb_rows[0].keys()))
        w.writeheader(); [w.writerow(r) for r in sb_rows]

# ---------- design memo ----------
def m_for(b, bench='bird_full'):
    return next((r for r in mm_rows if r['baseline']==b and r['benchmark']==bench), {})

design = ['# Evidence semantics design v7', '',
    f'_Generated: {time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}._',
    '',
    'Architecture: B6_v7 controller (Phase 6 LLM-as-judge selector) + extended',
    'evidence layer per `evidence_semantics_v7`.',
    '',
    '## Evidence layers',
    '- gold: BIRD per-item snippet (was the only source in B6_v7).',
    '- schema: table/column comments + FK summary (from IR).',
    '- value-hints: bounded SQLite probes (DISTINCT LIMIT 10 / MIN-MAX).',
    '- generated_aliases: rule-based camelCase/snake_case → English mapping.',
    '',
    '## Per-db precompute',
    'Value hints and schema evidence are computed once per db_id (~5s for 11 BIRD dbs)',
    'and reused across all 500 questions. Per-item cost is just rendering + ranking.',
    '',
    '## Headline ablation (FULL BIRD 500)', '',
    '| Cell | EX | 95% CI | evidence chars avg |',
    '|---|---:|---:|---:|']
for bl in ['B6_v7','B7d_rich','B7c_profiles_only','B7e_none']:
    r = m_for(bl)
    if not r: continue
    design.append(f'| {bl} | {pct(r.get("EX"))} | {ci(r.get("EX_lo"),r.get("EX_hi"))} | {r.get("evidence_chars_avg",0):.0f} |')

design += ['', '## Paired stats', '',
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
(LOG/'evidence_semantics_design_v7.md').write_text('\n'.join(design)+'\n', encoding='utf-8')

# ---------- negative-result memo ----------
b7d = m_for('B7d_rich'); b7c = m_for('B7c_profiles_only'); b7e = m_for('B7e_none')
b6 = m_for('B6_v7')
neg = ['# Evidence semantics — negative result memo (FULL BIRD)', '',
    f'_Generated: {time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}._',
    '',
    '## TL;DR',
    '',
    'The richer evidence layer (`evidence_semantics_v7`: schema comments, '
    'bounded value-hints, rule-based aliases) does **not** produce a',
    'measurable improvement on BIRD when the gold per-item evidence is',
    'already present. Without gold, the rich evidence layer **hurts**',
    'relative to no evidence at all.',
    '',
    '## Numbers (FULL BIRD 500)', '',
    f'- B6_v7 (judge over Phase A/C candidates, gold via per_item_evidence)  ─ EX = {pct(b6.get("EX"))}',
    f'- B7d_rich (gold + schema + profiles + aliases)                         ─ EX = {pct(b7d.get("EX"))}',
    f'- B7c_profiles_only (schema + profiles only, NO gold)                    ─ EX = {pct(b7c.get("EX"))}',
    f'- B7e_none (no evidence at all)                                          ─ EX = {pct(b7e.get("EX"))}',
    '',
    'Paired tests (see `outputs/tables/paired_significance_b7_v7.csv`):',
]
for r in ps_rows:
    if r['n']==0: continue
    neg.append(f'  - {r["bench"]} {r["A"]} → {r["B"]}: Δ {r["diff_pp"]:+.2f} pp, p={r["mcnemar_p"]:.4f}')

neg += ['',
    '## Why',
    '',
    '1. **Gold per-item evidence already encodes the disambiguating',
    '   formula or domain term**. Adding bounded value-probes and schema',
    '   comments does not contribute new information once the gold hint',
    '   is in the prompt.',
    '2. **Without gold, value profiles are noisy**. SELECT DISTINCT col',
    '   LIMIT 10 returns whatever is at the start of the table — these',
    '   examples may be unrepresentative or even misleading. The judge',
    '   reads them as factual constraints and over-fits filters to the',
    '   leaked sample values.',
    '3. **Schema comments in BIRD are sparse**. Many BIRD dbs ship with',
    '   no column-level descriptions, so the schema layer collapses to',
    '   FK summary (already used by retrieval).',
    '4. **Generated aliases via cheap regex are too coarse**. The',
    '   rule-based camelCase / snake_case splitter recovers common',
    '   English words but misses domain-specific abbreviations (`PRJ`,',
    '   `SKU`, `LTV`) that BIRD evidence explicitly explains.',
    '',
    '## What would help next sprint',
    '',
    '1. **LM-generated semantic aliases** (single small LM call per',
    '   db, cached). Rule-based regex is too shallow.',
    '2. **Targeted column profiles**: instead of bulk DISTINCT LIMIT 10',
    '   per column, profile only the columns the judge marks as',
    '   ambiguous — read failure → expand-evidence retry.',
    '3. **Stop trying to replace gold with synthesized evidence on',
    '   BIRD**. Gold evidence is the load-bearing component; future work',
    '   should focus on (a) improving how the judge USES gold evidence',
    '   and (b) generating synthetic evidence only on benchmarks that',
    '   lack gold (e.g. Spider2 enterprise lane).',
    '',
    '## Recommendation',
    '',
    '- Do NOT enable `evidence_semantics_v7` in the production B6_v7',
    '  controller — it is a no-op when gold evidence is already',
    '  present and a regression when it is not.',
    '- Keep the module for future Spider2 work, where gold evidence',
    '  is absent and value profiles + LM-generated aliases may matter.',
    '',
    '## Honest limitation',
    '',
    'B7c and B7e were re-run after a closure-bug in v1 of the runner',
    '(`global ev_mode` did not override main-scope local), which had',
    'silently shipped all three "modes" as the rich variant. The fixed',
    'runner re-ran B7c and B7e from scratch with the correct mode flag',
    'while keeping B7d_rich (already valid). The 500-row JSONLs',
    '`b7c_profiles_only_*` and `b7e_none_*` reflect the corrected runs.',
]
(LOG/'evidence_negative_result_v7.md').write_text('\n'.join(neg)+'\n', encoding='utf-8')

# ---------- plot ----------
fig, ax = plt.subplots(figsize=(11, 5.5))
order = ['B0','B2_v5','B4_v5','B6_v7','B7d_rich','B7c_profiles_only','B7e_none']
cmap = {'B0':'#3a82f6','B2_v5':'#a855f7','B4_v5':'#22c55e','B6_v7':'#e879f9',
        'B7d_rich':'#f59e0b','B7c_profiles_only':'#ef4444','B7e_none':'#6b7280'}
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
ax.set_title('Phase 7 evidence ablation — FULL BIRD (500)', fontsize=13, fontweight='bold')
ax.set_ylabel('Execution Match (%)'); ax.grid(axis='y', alpha=0.3)
ax.set_ylim(0, max(ys)*1.25 if ys else 100)
fig.tight_layout()
fig.savefig(PLT/'b7v7_overview.png', dpi=140, bbox_inches='tight')
plt.close(fig)

print('Phase 7 consolidation done.')
print()
for r in mm_rows:
    print(f'  {r["baseline"]:20s} N={r["N"]:5d} EX={pct(r.get("EX")):>8s}')
