# Stage D1: B2 targeted error triage. Read existing B2_v0 / B2_v1 predictions
# on smoke_10, identify the exact failure modes per item.

import csv
import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
NOW = dt.datetime.now(dt.timezone.utc).isoformat()


def load_jsonl(p):
    if not Path(p).exists(): return []
    return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]


b2v0 = load_jsonl(OUTPUTS/'predictions'/'b2_spider_smoke10_predictions.jsonl')
b2v1 = load_jsonl(OUTPUTS/'predictions'/'b2v1_spider_smoke10_predictions.jsonl')


def categorize(rec):
    """Return (category, reason)."""
    if rec.get('execution_match'): return ('correct', '')
    et = rec.get('error_type', '')
    plan = rec.get('plan') or {}
    plan_err = rec.get('plan_error', '') or ''
    if et == 'timeout': return ('timeout', et)
    if et and not rec.get('executable'):
        if 'OperationalError' in et: return ('sql_invalid_operational', et)
        return ('sql_invalid', et)
    if et == 'result_mismatch':
        # Heuristic: distinguish intent misframing vs filter wrong
        intent = plan.get('intent', '') if isinstance(plan, dict) else ''
        gold = rec.get('gold_sql', '').lower()
        gen = rec.get('generated_sql', '').lower()
        if 'distinct' in gold and 'distinct' not in gen:
            return ('missing_distinct', 'gold has DISTINCT, gen does not')
        if any(k in gold for k in ('group by','count(','min(','max(','avg(','sum(')) \
                and not any(k in gen for k in ('group by','count(','min(','max(','avg(','sum(')):
            return ('aggregation_misframed', f'gold has aggregation, gen does not (intent={intent})')
        if 'where' in gold and 'where' not in gen:
            return ('missing_filter', 'gold has WHERE, gen does not')
        if 'order by' in gold and 'order by' not in gen:
            return ('missing_order_by', 'gold has ORDER BY, gen does not')
        if 'limit' in gold and 'limit' not in gen:
            return ('missing_limit', 'gold has LIMIT, gen does not')
        return ('result_mismatch_other', f'intent={intent}')
    return ('other', et or 'unknown')


# Build matrix
out_rows = []
for src_label, recs in [('B2_v0', b2v0), ('B2_v1', b2v1)]:
    for rec in recs:
        cat, why = categorize(rec)
        out_rows.append({
            'source': src_label,
            'idx': rec.get('idx'),
            'db_id': rec.get('db_id'),
            'question': rec.get('question'),
            'gold_sql': rec.get('gold_sql', ''),
            'generated_sql': rec.get('generated_sql', ''),
            'execution_match': rec.get('execution_match'),
            'category': cat,
            'why': why,
        })

p_csv = OUTPUTS/'tables'/'b2_error_case_matrix.csv'
with p_csv.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
    w.writeheader()
    for r in out_rows: w.writerow(r)

# Triage doc
from collections import Counter
counts = Counter((r['source'], r['category']) for r in out_rows)
b2v0_failed = [r for r in out_rows if r['source']=='B2_v0' and not r['execution_match']]
b2v1_failed = [r for r in out_rows if r['source']=='B2_v1' and not r['execution_match']]

triage = OUTPUTS/'logs'/'b2_targeted_error_triage.md'
lines = [
    '# B2 targeted error triage', f'_Generated: {NOW}_', '',
    '## Failure category counts',
    '| source | category | count |', '|---|---|---|',
]
for (src, cat), n in sorted(counts.items()):
    lines.append(f'| {src} | {cat} | {n} |')

lines += ['', '## Per-item failed cases (B2_v0)', '']
for r in b2v0_failed:
    lines.append(f'### idx={r["idx"]} db={r["db_id"]} category={r["category"]}')
    lines.append(f'**Q:** {r["question"]}')
    lines.append(f'**Gold:** `{r["gold_sql"]}`')
    lines.append(f'**Gen:** `{r["generated_sql"]}`')
    lines.append(f'**Why:** {r["why"]}')
    lines.append('')

lines += ['', '## Per-item failed cases (B2_v1)', '']
for r in b2v1_failed:
    lines.append(f'### idx={r["idx"]} db={r["db_id"]} category={r["category"]}')
    lines.append(f'**Q:** {r["question"]}')
    lines.append(f'**Gold:** `{r["gold_sql"]}`')
    lines.append(f'**Gen:** `{r["generated_sql"]}`')
    lines.append(f'**Why:** {r["why"]}')
    lines.append('')

# Hypotheses for B2_v2
lines += [
    '## Hypotheses for B2_v2 (minimal targeted patches)', '',
    '1. **Strengthen DISTINCT prompt cue.** When the question contains words like',
    '   "distinct", "different", "unique", "all the X" (set semantics), the planner',
    '   must mark `distinct: true`. Currently this is implied; make it explicit',
    '   and add 1–2 in-context positive examples.',
    '2. **Strengthen subquery filter cue.** Questions like "the youngest", "the',
    '   tallest", "the X with the highest Y" need a subquery in WHERE',
    '   (`(SELECT MIN(...) FROM T)`). Make the planner emit this pattern',
    '   explicitly when it sees a superlative.',
    '3. **B1 fallback on plan failure.** Same trick as B3_v2 / B4_v2: if the plan',
    '   is invalid, fall back to B1 single-shot. This guarantees',
    '   `EX(B2_v2) >= EX(B1) - sql_noise`.',
    '4. **Ban over-engineering.** When the question is a simple SELECT-FROM-WHERE',
    '   without aggregation, ordering, limit, or subqueries — the planner often',
    '   adds spurious GROUP BY or ORDER BY because the prompt mentions them as',
    '   options. Add a short instruction: "Use the simplest plan that satisfies',
    '   the question; do not add operations not requested."',
    '',
    '## Decision',
    'Apply hypotheses 1–4 in `baselines_b2_v2.py`, then run B2_v2 smoke_10 + multidb_30.',
    'Stop if delta < +0.03 EX vs B2_v1 — the planner direction is exhausted on',
    'this benchmark and the right answer is "use B0/B1, keep B2_v2 as a safety',
    'net only when an external system requires the plan as an audit trail".',
]
triage.write_text('\n'.join(lines)+'\n', encoding='utf-8')
print(f'WROTE {p_csv}')
print(f'WROTE {triage}')
print(f'b2v0_failed={len(b2v0_failed)} b2v1_failed={len(b2v1_failed)}')
