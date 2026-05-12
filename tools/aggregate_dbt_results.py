"""Aggregate DBT task_success metrics across the 3 DBT runs.

Sources:
  1. outputs/spider2_dbt/dbt_full_v26_runlog.txt — runlog of first run (crashed
     at task 41/68 with SSH timeout); parse per-task eval lines.
  2. outputs/spider2_dbt/dbt_full_v26_resume28_runlog.txt — minimal (only
     launching line; output was buffered, lost).
  3. outputs/dbt_ablation/dbt_full_v26_final17/per_task.jsonl — clean 17-task
     run with structured eval results.

Output: outputs/spider2_dbt/dbt_full_v26_aggregate.csv + summary printout.
"""
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNLOG = REPO / 'outputs/spider2_dbt/dbt_full_v26_runlog.txt'
FINAL17_PT = REPO / 'outputs/dbt_ablation/dbt_full_v26_final17/per_task.jsonl'
ALL_68 = REPO / '_all_68.txt'
OUT_CSV = REPO / 'outputs/spider2_dbt/dbt_full_v26_aggregate.csv'

all_tasks = ALL_68.read_text(encoding='utf-8').strip().split()

# Parse runlog (first run, crashed at task 41)
# Format per task:
#   ========== TASK <iid> ==========
#     --- <iid> | v4 ---
#     prompt: True
#     inference: True
#     apply: kind=diff pushed=['patch.diff']
#     eval: dbt_run=1 pass=44/err=1 score={'rate': 0.0, 'matched': 0, 'total': 1}
runlog_results = {}
text = RUNLOG.read_text(encoding='utf-8', errors='replace')
TASK_HDR = re.compile(r'^========== TASK (\S+) ==========', re.M)
hdrs = list(TASK_HDR.finditer(text))
for i, m in enumerate(hdrs):
    iid = m.group(1)
    body = text[m.end():hdrs[i+1].start()] if i + 1 < len(hdrs) else text[m.end():]
    rec = {'instance_id': iid, 'source': 'runlog_first'}
    pm = re.search(r"prompt:\s*(\S+)", body)
    if pm: rec['prompt'] = (pm.group(1) == 'True')
    im = re.search(r"inference:\s*(\S+)", body)
    if im: rec['inference'] = (im.group(1) == 'True')
    am = re.search(r"apply: kind=(\S+) pushed=(\[[^\]]*\])", body)
    if am: rec['apply_kind'] = am.group(1)
    em = re.search(r"eval: dbt_run=(\d+) pass=(\d+)/err=(\d+) score=(\{[^}]*\})", body)
    if em:
        rec['dbt_run_rc'] = int(em.group(1))
        rec['pass_n'] = int(em.group(2))
        rec['err_n'] = int(em.group(3))
        try:
            # Parse the score dict — Python repr like {'rate': 0.0, 'matched': 0, 'total': 1}
            rec['score'] = eval(em.group(4))
        except Exception:
            rec['score'] = None
    runlog_results[iid] = rec

print(f'Runlog (first crashed run): {len(runlog_results)} tasks with eval data')
crashed_task = None
# Check last task in runlog — that's where it crashed (no eval, only apply)
for iid, rec in runlog_results.items():
    if 'eval' not in rec and 'pass_n' not in rec:
        pass  # skipped — see below
# Re-check the last header — it may have apply but no eval (the crashed one)
last_iid = hdrs[-1].group(1) if hdrs else None
print(f'  last header in runlog: {last_iid}')
if last_iid and 'pass_n' not in runlog_results.get(last_iid, {}):
    crashed_task = last_iid
    print(f'  CRASHED on task: {crashed_task}')

# Parse FINAL17 per_task.jsonl
final17_results = {}
with FINAL17_PT.open(encoding='utf-8') as f:
    for ln in f:
        if not ln.strip(): continue
        rec = json.loads(ln)
        rec['source'] = 'final17'
        final17_results[rec['instance_id']] = rec
print(f'FINAL17 (clean): {len(final17_results)} tasks')

# Aggregate: prefer FINAL17 for any overlap, else runlog_first
combined = {}
for iid in all_tasks:
    if iid in final17_results:
        combined[iid] = final17_results[iid]
    elif iid in runlog_results and runlog_results[iid].get('pass_n') is not None:
        combined[iid] = runlog_results[iid]
    elif iid in runlog_results:
        # Has model_response but eval missing
        combined[iid] = {**runlog_results[iid], 'status': 'eval_missing'}
    else:
        combined[iid] = {'instance_id': iid, 'status': 'no_data'}

print(f'\n=== AGGREGATE SUMMARY (n=68) ===')
print(f'Has eval data: {sum(1 for r in combined.values() if r.get("pass_n") is not None)}/68')

# Compute task_success metric: official_score.matched > 0 OR score['matched']>0
matched_n = 0
dbt_run_ok = 0
dbt_test_ok = 0
score_recorded = 0
no_data = 0
eval_missing = 0
for iid in all_tasks:
    r = combined[iid]
    score = r.get('official_score') or r.get('score') or {}
    if isinstance(score, dict):
        matched = score.get('matched', 0) or 0
        if matched > 0: matched_n += 1
        if score.get('rate') is not None or score.get('matched') is not None:
            score_recorded += 1
    if r.get('dbt_run_rc') == 0: dbt_run_ok += 1
    if r.get('dbt_test_rc') == 0: dbt_test_ok += 1
    if r.get('status') == 'no_data': no_data += 1
    elif r.get('status') == 'eval_missing': eval_missing += 1

print(f'task_success (matched>0): {matched_n}/68 = {matched_n*100/68:.1f}%')
print(f'dbt_run_ok (rc=0):       {dbt_run_ok}/68 = {dbt_run_ok*100/68:.1f}%')
print(f'dbt_test_ok (rc=0):      {dbt_test_ok}/68 = {dbt_test_ok*100/68:.1f}%')
print(f'score_recorded:          {score_recorded}/68')
print(f'no_data:                 {no_data}')
print(f'eval_missing:            {eval_missing}')

# Write CSV
with OUT_CSV.open('w', encoding='utf-8') as f:
    f.write('instance_id,source,status,prompt,inference,apply_kind,dbt_deps_rc,dbt_run_rc,dbt_test_rc,pass_n,err_n,score_rate,score_matched,score_total,task_success\n')
    for iid in all_tasks:
        r = combined[iid]
        score = r.get('official_score') or r.get('score') or {}
        if not isinstance(score, dict): score = {}
        ts = 1 if (score.get('matched', 0) or 0) > 0 else 0
        f.write(','.join([
            iid,
            r.get('source','no_data'),
            r.get('status', 'done' if r.get('pass_n') is not None else ''),
            str(r.get('prompt', '')),
            str(r.get('inference', '')),
            r.get('apply_kind', ''),
            str(r.get('dbt_deps_rc', '')),
            str(r.get('dbt_run_rc', '')),
            str(r.get('dbt_test_rc', '')),
            str(r.get('pass_n', '')),
            str(r.get('err_n', '')),
            str(score.get('rate', '')),
            str(score.get('matched', '')),
            str(score.get('total', '')),
            str(ts),
        ]) + '\n')

print(f'\nWROTE: {OUT_CSV}')

# Sources histogram
src = Counter(combined[iid].get('source','no_data') for iid in all_tasks)
print(f'\nsource breakdown: {dict(src)}')
