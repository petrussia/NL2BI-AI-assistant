# Phase 10 (Spider2 BQ agent_v8) consolidation — produces master matrix v10,
# structural CSV, error taxonomy, source breakdown, helpful/harmful vs v7,
# and the v8-vs-v7 paired stats tables.
#
# Inputs (Drive):
#   outputs/predictions/spider2_bq_agent_v8_predictions_with_em.jsonl  (205)
#   outputs/predictions/spider2lite_agent_v7_full_predictions.jsonl    (547, A_bq=205)
#   outputs/tables/final_experiment_master_matrix_fullbench_v9.csv     (prior)
#
# Outputs:
#   outputs/tables/spider2_bq_agent_v8_metrics.csv
#   outputs/tables/spider2_bq_agent_v8_error_taxonomy.csv
#   outputs/tables/spider2_bq_agent_v8_source_breakdown.csv
#   outputs/tables/spider2_bq_agent_v8_helpful_harmful_vs_v7.csv
#   outputs/tables/final_experiment_master_matrix_spider2_v8.csv
#   outputs/tables/paired_significance_phase_ten_v1.csv
#   outputs/logs/spider2_bq_agent_v8_readout.md
#   outputs/plots/spider2_bq_v8_overview.png
from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
PRED_V8 = ROOT / 'outputs' / 'predictions' / 'spider2_bq_agent_v8_predictions_with_em.jsonl'
PRED_V8_NO_EM = ROOT / 'outputs' / 'predictions' / 'spider2_bq_agent_v8_predictions.jsonl'
PRED_V7 = ROOT / 'outputs' / 'predictions' / 'spider2lite_agent_v7_full_predictions.jsonl'
TBL = ROOT / 'outputs' / 'tables'
LOG = ROOT / 'outputs' / 'logs'
PLT = ROOT / 'outputs' / 'plots'
for p in (TBL, LOG, PLT): p.mkdir(parents=True, exist_ok=True)


def utcnow(): return datetime.now(timezone.utc).isoformat()


def _safe_div(a, b): return a / b if b else 0.0


def _wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0: return 0.0, 0.0
    denom = 1 + z*z/n
    centre = (p + z*z/(2*n)) / denom
    half = z * math.sqrt((p*(1-p) + z*z/(4*n))/n) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def _bucket(rec: dict) -> str:
    """Coarse error bucket — same vocabulary as Step 0 audit."""
    em = (rec.get('error_message') or '').lower()
    et = (rec.get('error_type') or '').strip()
    if rec.get('execution_match') is True: return 'EX_MATCH'
    if rec.get('executable') is True and rec.get('execution_match') is False:
        return 'exec_ok_but_rows_mismatch'
    if rec.get('executable') is True and rec.get('execution_match') is None:
        return 'exec_ok_no_gold_to_compare'
    if et == 'BadRequest' or 'badrequest' in et.lower():
        if 'syntax error' in em: return 'syntax_error'
        if 'function not found' in em or 'no matching signature' in em: return 'function_signature'
        if 'unrecognized name' in em or 'no such column' in em: return 'unrecognized_column'
        if 'not found: table' in em or 'not found: dataset' in em: return 'table_or_dataset_not_found'
        if 'permission denied' in em or 'access denied' in em: return 'permission_denied'
        if 'bytesbilledexceeded' in em or 'maximum bytes' in em: return 'bytes_billed_exceeded'
        if 'aggregat' in em: return 'aggregation_error'
        return 'other_bad_request'
    if 'permission' in et.lower() or 'forbidden' in et.lower(): return 'permission_denied'
    if 'notfound' in et.lower(): return 'table_or_dataset_not_found'
    if 'timeout' in et.lower(): return 'timeout'
    if not rec.get('parses') and rec.get('lane') == 'A_bq': return 'parse_failure'
    if rec.get('error_type'): return f'other:{et[:40]}'
    return 'unknown'


# ---------- load ----------

def load_jsonl(p: Path) -> list[dict]:
    if not p.exists(): return []
    return [json.loads(l) for l in p.open(encoding='utf-8')]


pred_v8 = load_jsonl(PRED_V8) or load_jsonl(PRED_V8_NO_EM)
pred_v7_all = load_jsonl(PRED_V7)
v7_a_bq = [r for r in pred_v7_all if r.get('lane') == 'A_bq']
v7_by_iid = {r['instance_id']: r for r in v7_a_bq if r.get('instance_id')}

print(f'V8 rows={len(pred_v8)}  V7 A_bq rows={len(v7_a_bq)}')

# ---------- v8 metrics CSV ----------

m_path = TBL / 'spider2_bq_agent_v8_metrics.csv'
fields = ['instance_id', 'db_id', 'final_source', 'parses', 'all_known',
            'executable', 'execution_match', 'exec_match_reason',
            'rows_count', 'unknown_tables_n', 'has_join', 'has_groupby',
            'has_subquery', 'has_window', 'has_unnest', 'has_with',
            'bytes_billed', 'bytes_processed', 'lm_calls', 'latency_ms',
            'completion_tokens', 'wall_time_s', 'candidate_count',
            'repair_used', 'repair_success', 'repair_rounds',
            'judge_invoked', 'judge_overrode', 'judge_chose',
            'judge_confidence', 'error_type', 'error_message_short',
            'bucket']
with m_path.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in pred_v8:
        row = {k: r.get(k, '') for k in fields if k != 'bucket' and k != 'error_message_short'}
        row['bucket'] = _bucket(r)
        row['error_message_short'] = (r.get('error_message') or '')[:160]
        w.writerow(row)
print(f'WROTE {m_path}')

# ---------- error taxonomy ----------

bk_v8 = Counter(_bucket(r) for r in pred_v8)
bk_v7 = Counter(_bucket(r) for r in v7_a_bq)
tax_path = TBL / 'spider2_bq_agent_v8_error_taxonomy.csv'
with tax_path.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['bucket', 'v7_n', 'v7_pct', 'v8_n', 'v8_pct', 'delta_pp'])
    all_keys = sorted(set(list(bk_v7.keys()) + list(bk_v8.keys())))
    for k in all_keys:
        v7n, v8n = bk_v7.get(k, 0), bk_v8.get(k, 0)
        w.writerow([k, v7n, round(100*v7n/max(1,len(v7_a_bq)),2),
                     v8n, round(100*v8n/max(1,len(pred_v8)),2),
                     round(100*(v8n - v7n)/max(1,len(pred_v8)),2)])
print(f'WROTE {tax_path}')

# ---------- source breakdown ----------

src_path = TBL / 'spider2_bq_agent_v8_source_breakdown.csv'
with src_path.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['final_source', 'n', 'parses', 'exec_ok', 'em', 'em_rate'])
    by_src = defaultdict(lambda: {'n': 0, 'parses': 0, 'exec': 0, 'em': 0})
    for r in pred_v8:
        s = r.get('final_source', '?')
        by_src[s]['n'] += 1
        if r.get('parses'): by_src[s]['parses'] += 1
        if r.get('executable') is True: by_src[s]['exec'] += 1
        if r.get('execution_match') is True: by_src[s]['em'] += 1
    for s, d in sorted(by_src.items(), key=lambda x: -x[1]['n']):
        w.writerow([s, d['n'], d['parses'], d['exec'], d['em'],
                     round(100*d['em']/max(1, d['n']), 2)])
print(f'WROTE {src_path}')

# ---------- helpful / harmful vs v7 ----------

helpful = harmful = neutral = 0
hh_rows = []
for r8 in pred_v8:
    iid = r8.get('instance_id', '')
    r7 = v7_by_iid.get(iid)
    if r7 is None: continue
    em7 = r7.get('execution_match')
    em8 = r8.get('execution_match')
    if em7 is True and em8 is True: tag = 'both_match'
    elif em7 is False and em8 is True: tag = 'helpful'; helpful += 1
    elif em7 is True and em8 is False: tag = 'harmful'; harmful += 1
    elif em7 is False and em8 is False: tag = 'both_miss'; neutral += 1
    else: tag = 'one_no_gold'
    hh_rows.append({
        'instance_id': iid, 'tag': tag,
        'v7_executable': r7.get('executable'), 'v8_executable': r8.get('executable'),
        'v7_em': em7, 'v8_em': em8,
        'v7_source': r7.get('final_source'), 'v8_source': r8.get('final_source'),
        'v7_bucket': _bucket(r7), 'v8_bucket': _bucket(r8),
    })
hh_path = TBL / 'spider2_bq_agent_v8_helpful_harmful_vs_v7.csv'
with hh_path.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(hh_rows[0].keys()) if hh_rows else
                          ['instance_id','tag'])
    w.writeheader()
    for r in hh_rows: w.writerow(r)
print(f'WROTE {hh_path}  helpful={helpful} harmful={harmful} neutral={neutral}')

# ---------- master matrix v8 (Spider2 row) ----------

n8 = len(pred_v8)
parses_n8 = sum(1 for r in pred_v8 if r.get('parses') is True)
exec_n8 = sum(1 for r in pred_v8 if r.get('executable') is True)
em_n8 = sum(1 for r in pred_v8 if r.get('execution_match') is True)
em_compared8 = sum(1 for r in pred_v8 if r.get('execution_match') is not None)
all_known_n8 = sum(1 for r in pred_v8 if r.get('all_known') is True)
bytes_total = sum(int(r.get('bytes_billed') or 0) for r in pred_v8)
src_cnt = Counter(r.get('final_source','?') for r in pred_v8)

n7 = len(v7_a_bq)
parses_n7 = sum(1 for r in v7_a_bq if r.get('parses') is True)
exec_n7 = sum(1 for r in v7_a_bq if r.get('executable') is True)
em_n7 = sum(1 for r in v7_a_bq if r.get('execution_match') is True)
em_compared7 = sum(1 for r in v7_a_bq if r.get('execution_match') is not None)

mat_path = TBL / 'final_experiment_master_matrix_spider2_v8.csv'
with mat_path.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['method', 'n_a_bq', 'parses_pct', 'exec_pct', 'em_n', 'em_compared',
                  'em_pct_of_compared', 'em_pct_of_total',
                  'all_known_n', 'bytes_billed_gb', 'final_sources'])
    w.writerow(['agent_v7_spider2_a_bq', n7,
                  round(100*parses_n7/max(1,n7),2),
                  round(100*exec_n7/max(1,n7),2),
                  em_n7, em_compared7,
                  round(100*em_n7/max(1,em_compared7),2),
                  round(100*em_n7/max(1,n7),2),
                  '',  # not tracked in v7
                  round((sum(int(r.get('bytes_billed') or 0) for r in v7_a_bq)) / (1<<30), 2),
                  ''])
    w.writerow(['agent_v8_bq_a_bq', n8,
                  round(100*parses_n8/max(1,n8),2),
                  round(100*exec_n8/max(1,n8),2),
                  em_n8, em_compared8,
                  round(100*em_n8/max(1,em_compared8),2),
                  round(100*em_n8/max(1,n8),2),
                  all_known_n8,
                  round(bytes_total / (1<<30), 2),
                  '|'.join(f'{k}:{v}' for k,v in src_cnt.most_common())])
print(f'WROTE {mat_path}')

# ---------- paired stats (McNemar on EX) ----------

# Build paired vector on items where BOTH have execution_match defined
paired = []
for r8 in pred_v8:
    iid = r8['instance_id']
    r7 = v7_by_iid.get(iid)
    if r7 is None: continue
    em7 = r7.get('execution_match'); em8 = r8.get('execution_match')
    if em7 is None or em8 is None: continue
    paired.append((bool(em7), bool(em8)))
b = sum(1 for x, y in paired if x and not y)  # v7 right, v8 wrong
c = sum(1 for x, y in paired if y and not x)  # v8 right, v7 wrong
n_both_right = sum(1 for x, y in paired if x and y)
n_both_wrong = sum(1 for x, y in paired if not x and not y)

# McNemar exact-ish (no scipy)
def _mcnemar_p(b: int, c: int) -> float:
    # Using normal approx with continuity correction; good enough
    if b + c == 0: return 1.0
    chi2 = (abs(b - c) - 1) ** 2 / (b + c)
    # one-sided -> two-sided; convert chi2(df=1) -> p via erfc
    z = math.sqrt(chi2)
    # P(|Z| > z) for standard normal
    return 2.0 * 0.5 * math.erfc(z / math.sqrt(2))

p_mc = _mcnemar_p(b, c)
delta_pp = 100 * (em_n8 - em_n7) / max(1, len(paired))
v7_pct = 100 * em_n7 / max(1, em_compared7)
v8_pct = 100 * em_n8 / max(1, em_compared8)
v7_lo, v7_hi = _wilson(em_n7/max(1,em_compared7), em_compared7)
v8_lo, v8_hi = _wilson(em_n8/max(1,em_compared8), em_compared8)

ps_path = TBL / 'paired_significance_phase_ten_v1.csv'
with ps_path.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['comparison', 'n_paired', 'v7_em', 'v8_em',
                  'v7_pct', 'v8_pct',
                  'v7_wilson_lo', 'v7_wilson_hi',
                  'v8_wilson_lo', 'v8_wilson_hi',
                  'helpful_b', 'harmful_c', 'mcnemar_p',
                  'delta_pp', 'verdict'])
    verdict = ('improved_sig' if p_mc < 0.05 and c > b else
               ('regressed_sig' if p_mc < 0.05 and b > c else 'tied'))
    w.writerow(['agent_v7 -> agent_v8 (A_bq)', len(paired), em_n7, em_n8,
                  round(v7_pct,2), round(v8_pct,2),
                  round(100*v7_lo,2), round(100*v7_hi,2),
                  round(100*v8_lo,2), round(100*v8_hi,2),
                  c, b,  # helpful_b is items where v8 is right + v7 wrong
                  round(p_mc, 6), round(delta_pp, 2), verdict])
print(f'WROTE {ps_path}')

# ---------- readout MD ----------

md_path = LOG / 'spider2_bq_agent_v8_readout.md'
md = ['# Spider2-Lite BQ agent_v8 — readout',
       '',
       f'_Generated: {utcnow()}_',
       '',
       '## Headline numbers (A_bq lane only, n=205)',
       '',
       '| Metric | v7 baseline | v8 agent | Delta |',
       '|---|---:|---:|---:|',
       f'| parses | {parses_n7} ({100*parses_n7/n7:.1f}%) | {parses_n8} ({100*parses_n8/n8:.1f}%) | {parses_n8-parses_n7:+d} (note: v7 used sqlglot OR exec; v8 uses BQ dry_run authoritative) |',
       f'| executable | {exec_n7} ({100*exec_n7/n7:.1f}%) | {exec_n8} ({100*exec_n8/n8:.1f}%) | **{100*exec_n8/n8 - 100*exec_n7/n7:+.1f}pp** |',
       f'| EX vs gold (compared {em_compared8}) | {em_n7}/{em_compared7} ({v7_pct:.2f}%) | {em_n8}/{em_compared8} ({v8_pct:.2f}%) | **{v8_pct-v7_pct:+.2f}pp** |',
       f'| EX of total 205 | {em_n7} ({100*em_n7/n7:.2f}%) | {em_n8} ({100*em_n8/n8:.2f}%) | {100*em_n8/n8 - 100*em_n7/n7:+.2f}pp |',
       f'| Wilson 95% CI (v7) | [{100*v7_lo:.2f}, {100*v7_hi:.2f}] | | |',
       f'| Wilson 95% CI (v8) | | [{100*v8_lo:.2f}, {100*v8_hi:.2f}] | |',
       '',
       '## Paired stats (McNemar on EX)',
       '',
       f'- n_paired with EM defined on both: **{len(paired)}**',
       f'- helpful (v8 right, v7 wrong): **{c}**',
       f'- harmful (v8 wrong, v7 right): **{b}**',
       f'- both right: {n_both_right}, both wrong: {n_both_wrong}',
       f'- McNemar p (continuity-corrected): **{p_mc:.4f}**',
       f'- verdict: **{verdict}**',
       '',
       '## Source breakdown (v8)',
       '',
       '| source | n | parses | exec_ok | em | em_rate |',
       '|---|---:|---:|---:|---:|---:|']
for s, d in sorted(by_src.items(), key=lambda x: -x[1]['n']):
    md.append(f'| {s} | {d["n"]} | {d["parses"]} | {d["exec"]} | {d["em"]} | '
              f'{100*d["em"]/max(1,d["n"]):.2f}% |')
md += ['',
        '## Error bucket comparison (v7 vs v8)',
        '',
        '| bucket | v7_n | v7% | v8_n | v8% | delta_pp |',
        '|---|---:|---:|---:|---:|---:|']
for k in sorted(set(list(bk_v7.keys()) + list(bk_v8.keys())),
                  key=lambda x: -bk_v8.get(x, 0)):
    v7n, v8n = bk_v7.get(k, 0), bk_v8.get(k, 0)
    md.append(f'| {k} | {v7n} | {100*v7n/n7:.1f}% | {v8n} | {100*v8n/n8:.1f}% | '
              f'{100*v8n/n8 - 100*v7n/n7:+.1f} |')
md += ['',
        '## Repair impact',
        f'- repair_used: {sum(1 for r in pred_v8 if r.get("repair_used"))}/{n8}',
        f'- repair_success: {sum(1 for r in pred_v8 if r.get("repair_success"))}',
        '',
        '## Cost',
        f'- BQ bytes billed total (run+exec_match): {bytes_total/(1<<30):.2f} GB',
        f'- approximate cost @ $5/TB: ${bytes_total*5/(1<<40):.4f}',
        '',
       ]
md_path.write_text('\n'.join(md), encoding='utf-8')
print(f'WROTE {md_path}')

# ---------- plot ----------

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    metrics = ['parses', 'exec_ok', 'EX (of compared)']
    v7_vals = [100*parses_n7/n7, 100*exec_n7/n7, v7_pct]
    v8_vals = [100*parses_n8/n8, 100*exec_n8/n8, v8_pct]
    x = range(len(metrics))
    ax[0].bar([i-0.2 for i in x], v7_vals, width=0.4, label='v7', color='gray')
    ax[0].bar([i+0.2 for i in x], v8_vals, width=0.4, label='v8', color='steelblue')
    ax[0].set_xticks(list(x)); ax[0].set_xticklabels(metrics)
    ax[0].set_ylabel('%'); ax[0].set_title('Spider2-Lite A_bq: v7 vs v8')
    ax[0].legend()
    src_labels = list(by_src.keys())
    src_n = [by_src[s]['n'] for s in src_labels]
    src_em = [by_src[s]['em'] for s in src_labels]
    ax[1].bar(src_labels, src_n, label='picked', color='lightgray')
    ax[1].bar(src_labels, src_em, label='EX matched', color='seagreen')
    ax[1].set_xticklabels(src_labels, rotation=15, ha='right')
    ax[1].set_title('v8 candidate source breakdown'); ax[1].legend()
    fig.tight_layout()
    pp = PLT / 'spider2_bq_v8_overview.png'
    fig.savefig(pp, dpi=130); plt.close(fig)
    print(f'WROTE {pp}')
except Exception as e:
    print(f'plot_skip {type(e).__name__}: {e}')

print('CONSOLIDATION_DONE')
