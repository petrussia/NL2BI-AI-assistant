# Step 5: B0 vs B1 smoke25 comparison + aggregate progression smoke10/smoke25
# + error taxonomy & failure buckets. All saved on Drive.

import csv
import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
for sub in ['logs', 'metrics', 'plots', 'tables']:
    (OUTPUTS / sub).mkdir(parents=True, exist_ok=True)


def load_jsonl(p):
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]


def load_csv_one(p):
    if not p.exists():
        return None
    return list(csv.DictReader(p.open(encoding='utf-8')))[0]


def short(s, n=240):
    s = (s or '').replace('|', '\\|').replace('\n', ' ')
    return s if len(s) <= n else s[:n - 3] + '...'


# ============= 1. B0 vs B1 smoke25 comparison =============
b0_25 = load_jsonl(OUTPUTS / 'predictions' / 'b0_spider_smoke25_predictions.jsonl')
b1_25 = load_jsonl(OUTPUTS / 'predictions' / 'b1_spider_smoke25_predictions.jsonl')
assert len(b0_25) == len(b1_25) and len(b0_25) > 0, f'smoke25 predictions missing or misaligned: b0={len(b0_25)} b1={len(b1_25)}'

n25 = len(b0_25)
ex_b0_25 = sum(1 for r in b0_25 if r['execution_match']) / n25
ex_b1_25 = sum(1 for r in b1_25 if r['execution_match']) / n25
exe_b0_25 = sum(1 for r in b0_25 if r['executable'])
exe_b1_25 = sum(1 for r in b1_25 if r['executable'])

improvements_25, regressions_25, unchanged_25, diffs_25 = [], [], [], []
for r0, r1 in zip(b0_25, b1_25):
    diff = {
        'idx': r0['idx'], 'db_id': r0['db_id'], 'question': r0['question'],
        'b0_executable': r0['executable'], 'b0_match': r0['execution_match'],
        'b0_sql': r0['generated_sql'], 'b0_error': r0.get('error_type', ''),
        'b1_executable': r1['executable'], 'b1_match': r1['execution_match'],
        'b1_sql': r1['generated_sql'], 'b1_error': r1.get('error_type', ''),
        'b1_selected_tables': r1.get('selected_tables', []),
        'b1_reduction': r1.get('schema_reduction_ratio', None),
    }
    diffs_25.append(diff)
    if r0['execution_match'] == r1['execution_match']:
        unchanged_25.append(diff)
    elif r1['execution_match']:
        improvements_25.append(diff)
    else:
        regressions_25.append(diff)

cmp25_csv = OUTPUTS / 'tables' / 'b0_vs_b1_smoke25_comparison.csv'
with cmp25_csv.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['metric', 'b0', 'b1'])
    w.writerow(['EX', f'{ex_b0_25:.4f}', f'{ex_b1_25:.4f}'])
    w.writerow(['executable_count', exe_b0_25, exe_b1_25])
    w.writerow(['n', n25, n25])
    w.writerow(['improvements_b0_to_b1', '', len(improvements_25)])
    w.writerow(['regressions_b0_to_b1', '', len(regressions_25)])
    w.writerow(['unchanged', '', len(unchanged_25)])

winner25 = 'B1' if ex_b1_25 > ex_b0_25 else 'B0' if ex_b0_25 > ex_b1_25 else 'tie'
cmp25_md = OUTPUTS / 'tables' / 'b0_vs_b1_smoke25_comparison.md'
cmp25_md.write_text(f'''# B0 vs B1 Comparison (Spider smoke25)

Checked at: {dt.datetime.now(dt.timezone.utc).isoformat()}
Subset: spider/smoke_25 (n={n25})
Model: Qwen/Qwen2.5-Coder-7B-Instruct (4-bit nf4 bitsandbytes), greedy decode
B1 schema strategy: lexical schema linking (token overlap, stopwords removed, min_score=0.5)

| Metric | B0 (full schema) | B1 (reduced schema) |
|---|---|---|
| EX | {ex_b0_25:.4f} | {ex_b1_25:.4f} |
| executable count | {exe_b0_25} / {n25} | {exe_b1_25} / {n25} |

| Transitions B0 -> B1 | count |
|---|---|
| Improvements (B0 wrong, B1 right) | {len(improvements_25)} |
| Regressions (B0 right, B1 wrong) | {len(regressions_25)} |
| Unchanged (same EX outcome) | {len(unchanged_25)} |

Winner on smoke25: **{winner25}**
''', encoding='utf-8')

# Plot
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(6, 4))
bars = ax.bar(['B0\nfull schema', 'B1\nreduced schema'], [ex_b0_25, ex_b1_25], color=['#4C72B0', '#55A868'])
for bar, val in zip(bars, [ex_b0_25, ex_b1_25]):
    ax.text(bar.get_x() + bar.get_width() / 2, val + 0.02, f'{val:.2f}', ha='center', va='bottom', fontsize=11)
ax.set_ylim(0, 1.1)
ax.set_ylabel('EX (Execution Match)')
ax.set_title(f'B0 vs B1 on Spider smoke25 (n={n25})')
plt.tight_layout()
plt.savefig(OUTPUTS / 'plots' / 'b0_vs_b1_smoke25_bar.png', dpi=140)
plt.close(fig)

# Case diff (>=5)
case_lines = ['# B0 vs B1 Case Diff (smoke25)\n']
selected = []
selected.extend(improvements_25[:3])
selected.extend(regressions_25[:3])
seen = {c['idx'] for c in selected}
for c in unchanged_25 + diffs_25:
    if len(selected) >= 5: break
    if c['idx'] not in seen:
        selected.append(c); seen.add(c['idx'])
for c in selected:
    if c['b0_match'] == c['b1_match']:
        verdict = 'unchanged'
        comment = 'reduction did not change the outcome.'
    elif c['b1_match']:
        verdict = 'B1 better'
        comment = 'reduced schema steered the model to the right tables.'
    else:
        verdict = 'B1 worse'
        comment = 'lexical linking dropped a table needed for the answer.'
    case_lines.append(f"## Case {c['idx']} (db: {c['db_id']}) -- {verdict}\n")
    case_lines.append(f"- **Question:** {short(c['question'])}\n")
    case_lines.append(f"- **B0:** executable={c['b0_executable']}, match={c['b0_match']}, error={c['b0_error']!r}\n")
    case_lines.append(f"  - SQL: `{short(c['b0_sql'])}`\n")
    case_lines.append(f"- **B1:** executable={c['b1_executable']}, match={c['b1_match']}, error={c['b1_error']!r}\n")
    case_lines.append(f"  - SQL: `{short(c['b1_sql'])}`\n")
    sel = ', '.join(c['b1_selected_tables']) if c['b1_selected_tables'] else '--'
    case_lines.append(f"  - selected tables: {sel} (reduction={c['b1_reduction']})\n")
    case_lines.append(f"- **Comment:** {comment}\n")
(OUTPUTS / 'tables' / 'b0_vs_b1_smoke25_case_diff.md').write_text('\n'.join(case_lines), encoding='utf-8')

print(f'smoke25 cmp: EX_B0={ex_b0_25:.4f} EX_B1={ex_b1_25:.4f} winner={winner25} '
      f'imp={len(improvements_25)} reg={len(regressions_25)} unchanged={len(unchanged_25)}')

# ============= 2. Aggregate progression smoke10 + smoke25 =============
b0_10_metrics = load_csv_one(OUTPUTS / 'metrics' / 'b0_spider_smoke10_metrics.csv')
b1_10_metrics = load_csv_one(OUTPUTS / 'metrics' / 'b1_spider_smoke10_metrics.csv')
b0_25_metrics = load_csv_one(OUTPUTS / 'metrics' / 'b0_spider_smoke25_metrics.csv')
b1_25_metrics = load_csv_one(OUTPUTS / 'metrics' / 'b1_spider_smoke25_metrics.csv')


def fnum(d, k):
    if not d or d.get(k) in (None, ''):
        return None
    try:
        return float(d[k])
    except Exception:
        return d[k]


agg_csv = OUTPUTS / 'tables' / 'baseline_progression_smoke10_smoke25.csv'
with agg_csv.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['baseline', 'subset', 'n', 'EX', 'executable_count', 'avg_reduction_ratio'])
    for label, m in [('B0', b0_10_metrics), ('B1', b1_10_metrics), ('B0', b0_25_metrics), ('B1', b1_25_metrics)]:
        if m:
            w.writerow([label, m.get('subset', '?'), m.get('n', '?'), m.get('ex', '?'),
                        m.get('executable_count', '?'), m.get('avg_reduction_ratio', '')])

# Conclusion logic
ex_b0_10 = fnum(b0_10_metrics, 'ex')
ex_b1_10 = fnum(b1_10_metrics, 'ex')
diff_10 = (ex_b1_10 - ex_b0_10) if (ex_b0_10 is not None and ex_b1_10 is not None) else None
diff_25 = ex_b1_25 - ex_b0_25
if diff_10 is not None and diff_10 > 0 and diff_25 > 0:
    conclusion = 'consistent benefit: B1 > B0 on both subsets'
elif diff_10 is not None and diff_10 < 0 and diff_25 < 0:
    conclusion = 'consistent regression: B1 < B0 on both subsets'
elif diff_10 == 0 and diff_25 == 0:
    conclusion = 'tie on both subsets — no benefit, no harm from schema reduction (information-equivalent on this data)'
elif diff_10 is not None and diff_25 != diff_10:
    conclusion = 'inconsistent: behaviour changes from smoke10 to smoke25 — schema linking effect is subset-dependent'
else:
    conclusion = 'inconclusive on this evidence'

agg_md = OUTPUTS / 'tables' / 'baseline_progression_smoke10_smoke25.md'
agg_md.write_text(f'''# Baseline Progression smoke10 → smoke25

Checked at: {dt.datetime.now(dt.timezone.utc).isoformat()}

| Baseline | Subset | n | EX | Executable | Avg reduction |
|---|---|---|---|---|---|
| B0 | smoke10 | {b0_10_metrics.get('n') if b0_10_metrics else '-'} | {ex_b0_10 if ex_b0_10 is not None else '-'} | {b0_10_metrics.get('executable_count') if b0_10_metrics else '-'} | — |
| B1 | smoke10 | {b1_10_metrics.get('n') if b1_10_metrics else '-'} | {ex_b1_10 if ex_b1_10 is not None else '-'} | {b1_10_metrics.get('executable_count') if b1_10_metrics else '-'} | {b1_10_metrics.get('avg_reduction_ratio') if b1_10_metrics else '-'} |
| B0 | smoke25 | {n25} | {ex_b0_25:.4f} | {exe_b0_25} | — |
| B1 | smoke25 | {n25} | {ex_b1_25:.4f} | {exe_b1_25} | {b1_25_metrics.get('avg_reduction_ratio') if b1_25_metrics else '-'} |

## Deltas
- Δ EX (B1 - B0) on smoke10: {f'{diff_10:+.4f}' if diff_10 is not None else 'n/a'}
- Δ EX (B1 - B0) on smoke25: {diff_25:+.4f}

## Conclusion
**{conclusion}**

Caveat: smoke10 and smoke25 both come from `dev[:10]` and `dev[:25]` respectively, all `concert_singer`. Same DB, only question diversity grows. To stress schema linking, future runs should use a multi-DB subset.
''', encoding='utf-8')

# Aggregate plot (4 bars)
fig, ax = plt.subplots(figsize=(8, 4))
labels = ['B0\nsmoke10', 'B1\nsmoke10', 'B0\nsmoke25', 'B1\nsmoke25']
vals = [ex_b0_10 or 0, ex_b1_10 or 0, ex_b0_25, ex_b1_25]
colors = ['#4C72B0', '#55A868', '#4C72B0', '#55A868']
bars = ax.bar(labels, vals, color=colors)
for bar, v in zip(bars, vals):
    ax.text(bar.get_x() + bar.get_width() / 2, v + 0.02, f'{v:.2f}', ha='center', va='bottom', fontsize=10)
ax.set_ylim(0, 1.15)
ax.set_ylabel('EX (Execution Match)')
ax.set_title('Baseline progression: smoke10 → smoke25')
plt.tight_layout()
plt.savefig(OUTPUTS / 'plots' / 'baseline_progression_smoke10_smoke25.png', dpi=140)
plt.close(fig)

print(f'aggregate: diff10={diff_10} diff25={diff_25:+.4f} conclusion={conclusion!r}')

# ============= 3. Error taxonomy + failure buckets =============
def classify(rec):
    """Classify a prediction record into a failure bucket."""
    if rec['execution_match']:
        return 'unchanged_correct' if rec['executable'] else 'unexpected'
    et = (rec.get('error_type') or '').lower()
    if not rec['executable']:
        # SQL didn't execute — syntax / runtime
        if 'timeout' in et:
            return 'sqlite_timeout'
        return 'syntax_or_runtime_error'
    # executable but wrong result
    sql_lower = (rec['generated_sql'] or '').lower()
    gold_lower = (rec.get('gold_sql') or '').lower()
    pred_tables = set(t for t in re.findall(r'from\\s+([a-z_][a-z0-9_]*)', sql_lower) +
                       re.findall(r'join\\s+([a-z_][a-z0-9_]*)', sql_lower))
    gold_tables = set(t for t in re.findall(r'from\\s+([a-z_][a-z0-9_]*)', gold_lower) +
                       re.findall(r'join\\s+([a-z_][a-z0-9_]*)', gold_lower))
    if pred_tables != gold_tables:
        return 'wrong_join_or_table'
    if ('count(' in sql_lower) != ('count(' in gold_lower) or \
       ('avg(' in sql_lower) != ('avg(' in gold_lower) or \
       ('sum(' in sql_lower) != ('sum(' in gold_lower) or \
       ('max(' in sql_lower) != ('max(' in gold_lower) or \
       ('min(' in sql_lower) != ('min(' in gold_lower) or \
       ('group by' in sql_lower) != ('group by' in gold_lower):
        return 'wrong_aggregation'
    if ('where' in sql_lower) != ('where' in gold_lower) or \
       ('having' in sql_lower) != ('having' in gold_lower):
        return 'wrong_filter_or_predicate'
    return 'result_mismatch_subtle'


import re
buckets_csv = OUTPUTS / 'tables' / 'b0_b1_failure_buckets.csv'
all_buckets_set = set()
b0_classified = [(r['idx'], classify(r), r) for r in b0_25]
b1_classified = [(r['idx'], classify(r), r) for r in b1_25]
for _, b, _ in b0_classified + b1_classified:
    all_buckets_set.add(b)
all_buckets = sorted(all_buckets_set)
b0_counts = {b: 0 for b in all_buckets}
b1_counts = {b: 0 for b in all_buckets}
for _, b, _ in b0_classified:
    b0_counts[b] += 1
for _, b, _ in b1_classified:
    b1_counts[b] += 1
with buckets_csv.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['bucket', 'b0_count', 'b1_count'])
    for b in all_buckets:
        w.writerow([b, b0_counts[b], b1_counts[b]])

tax_md = OUTPUTS / 'tables' / 'error_taxonomy_smoke25.md'
tax_lines = [
    '# Error Taxonomy (smoke25)',
    '',
    f'Generated at: {dt.datetime.now(dt.timezone.utc).isoformat()}',
    '',
    'Bucket counts by baseline:',
    '',
    '| Bucket | B0 | B1 |',
    '|---|---|---|',
]
for b in all_buckets:
    tax_lines.append(f'| `{b}` | {b0_counts[b]} | {b1_counts[b]} |')
tax_lines += ['', '## Bucket definitions', '',
              '- **unchanged_correct** — execution_match=True, both rows agree (the happy path).',
              '- **syntax_or_runtime_error** — SQL did not execute (SQLite OperationalError, ProgrammingError, etc.).',
              '- **sqlite_timeout** — SQL executed but timed out (>8s).',
              '- **wrong_join_or_table** — SQL executed, but FROM/JOIN tables differ from gold.',
              '- **wrong_aggregation** — same tables, but COUNT/AVG/SUM/MIN/MAX/GROUP BY presence differs from gold.',
              '- **wrong_filter_or_predicate** — same tables and aggregation, but WHERE/HAVING presence differs.',
              '- **result_mismatch_subtle** — executable, same tables/agg/filters, but rows differ (column choice, alias, ordering when ambiguous, etc.).',
              '- **unexpected** — execution_match=True but executable=False (should not happen).',
              '',
              '## Per-cell errors (smoke25 union of B0 and B1)',
              '',
              '| idx | db_id | B0 bucket | B1 bucket |',
              '|---|---|---|---|']
for (idx, b0_b, _), (_, b1_b, _) in zip(b0_classified, b1_classified):
    if b0_b == 'unchanged_correct' and b1_b == 'unchanged_correct':
        continue
    db = b0_25[idx]['db_id']
    tax_lines.append(f'| {idx} | {db} | `{b0_b}` | `{b1_b}` |')
tax_md.write_text('\n'.join(tax_lines) + '\n', encoding='utf-8')

print(f'error_taxonomy: B0_buckets={b0_counts} B1_buckets={b1_counts}')
print('STATUS=DONE')
