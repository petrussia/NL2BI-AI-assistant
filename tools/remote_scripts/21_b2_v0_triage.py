# Stage 1: B2_v0 smoke10 triage. Inspect idx 6, 7, 8 in detail and emit
# both an MD diagnostic + a CSV of failure cases.

import csv
import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
preds = OUTPUTS / 'predictions' / 'b2_spider_smoke10_predictions.jsonl'
records = [json.loads(l) for l in preds.read_text(encoding='utf-8').splitlines() if l.strip()]
fails = [r for r in records if not r['execution_match']]
assert len(fails) == 3, f'expected 3 fails, got {len(fails)}'

# Per-case interpretation
def diagnose(r):
    if r['error_type'] == 'plan_invalid':
        return {
            'probable_root_cause': 'Plan failed schema validation: schema does not express DISTINCT cleanly. The intent enum lacks "select_distinct"; aggregations cover COUNT/SUM/etc. but not DISTINCT projection. Planner emitted JSON the model thought was valid but jsonschema rejected.',
            'minimal_fix_idea': 'Extend plan_schema: add "distinct": bool flag (top-level), or accept "DISTINCT" as a function in aggregations. Update planner prompt to mention how to express DISTINCT.',
        }
    # result_mismatch — look at the SQL
    sql = (r.get('generated_sql') or '').lower()
    gold = (r.get('gold_sql') or '').lower()
    if 'limit 1' in sql and 'limit' not in gold:
        return {
            'probable_root_cause': 'Planner collapsed "youngest singer" + "songs" into "single row of singer". Plan-to-SQL prompt then materialised "ORDER BY Age ASC LIMIT 1" instead of subquery / WHERE Age = (SELECT MIN(Age) FROM singer). Question semantics ("songs of the youngest") got lost between plan and SQL stages.',
            'minimal_fix_idea': 'Planner prompt should explicitly distinguish "find the entity with min/max property" (subquery filter) from "first/single row by sort order" (LIMIT 1). Add a one-line in-context example showing the subquery pattern for "songs of the youngest singer".',
        }
    return {
        'probable_root_cause': 'Other SQL mismatch; inspect manually.',
        'minimal_fix_idea': 'Manual review.',
    }

triage_rows = []
md_lines = [
    '# B2 v0 Triage on smoke10',
    '',
    f'Generated at: {dt.datetime.now(dt.timezone.utc).isoformat()}',
    'Detailed walk-through of the 3 failure cases (idx 6, 7, 8) of B2_v0 on smoke10.',
    '',
]
for r in fails:
    diag = diagnose(r)
    plan_parsed_str = json.dumps(r.get('plan_parsed'), ensure_ascii=False, indent=2) if r.get('plan_parsed') else '(none)'
    md_lines += [
        f"## idx {r['idx']} (db: {r['db_id']}) — {r['error_type']}",
        '',
        f"- **Question:** {r['question']}",
        f"- **Gold SQL:** `{r['gold_sql']}`",
        '- **Plan raw (model output):**',
        '',
        '```',
        (r.get('plan_raw') or '').strip(),
        '```',
        '- **Plan parsed:**',
        '',
        '```json',
        plan_parsed_str,
        '```',
        f"- **Generated SQL:** `{r.get('generated_sql') or '(none)'}`",
        f"- **plan_valid:** `{r.get('plan_valid')}`  **plan_error:** `{r.get('plan_error')!r}`",
        f"- **Probable root cause:** {diag['probable_root_cause']}",
        f"- **Minimal fix idea:** {diag['minimal_fix_idea']}",
        '',
    ]
    triage_rows.append({
        'idx': r['idx'],
        'db_id': r['db_id'],
        'question': r['question'],
        'gold_sql': r['gold_sql'],
        'plan_valid': r.get('plan_valid'),
        'plan_error': r.get('plan_error'),
        'generated_sql': r.get('generated_sql') or '',
        'error_type': r['error_type'],
        'probable_root_cause': diag['probable_root_cause'],
        'minimal_fix_idea': diag['minimal_fix_idea'],
    })

# Aggregate diagnostic answers
answers = '''## Answers to triage questions

### Why did idx 6 and 7 collapse to LIMIT 1?
Both questions are *"songs of the youngest singer"* / *"name and release year of the song by the youngest singer"*. The planner reduced "youngest" to a sort-and-LIMIT-1 pattern instead of recognising it as a subquery filter (`WHERE Age = (SELECT MIN(Age) FROM singer)`). The plan-to-SQL prompt then literally implemented the planner's framing. Both questions get the same wrong SQL `SELECT Name, Song_release_year FROM singer ORDER BY Age ASC LIMIT 1;` because the planner emitted nearly identical plans.

### Why did idx 8 become plan_invalid?
The question *"all distinct countries where singers above age 20 are from"* requires DISTINCT projection plus a WHERE filter. The current `plan_schema.json` has no first-class way to express DISTINCT — the `intent` enum has `select_filter`, `select_aggregate`, `select_other`, but no dedicated `select_distinct`, and `aggregations` only covers COUNT/SUM/AVG/MIN/MAX. The model probably emitted a field that did not exist (e.g. `"distinct": true`) which triggered `additionalProperties: false` rejection.

### Is this a problem of prompt, schema, intent space, or plan->SQL translation?

| Symptom | Real cause |
|---|---|
| LIMIT 1 collapse (idx 6, 7) | **Prompt**: planner does not distinguish "subquery filter" from "ORDER BY + LIMIT 1". Schema is fine; intent space is fine; plan->SQL translation is faithful but to a wrong plan. |
| Plan invalid (idx 8) | **Schema**: missing DISTINCT capability AND likely **prompt**: planner did not know how to map DISTINCT to existing fields (e.g., it could have used `select_other` + `notes`). |

### Minimal patch path for B2_v1

1. Prompt fix: add a one-sentence instruction "for 'find the entity whose property is min/max, then list its other rows', use a subquery filter, not LIMIT 1". Optionally include 1 in-context example.
2. Schema fix: add a top-level `"distinct": {"type": "boolean"}` field. Update `additionalProperties: false` accordingly.
3. Prompt fix: instruct planner to use `"distinct": true` for "all distinct X" questions.
4. Plan->SQL prompt: minor instruction "honour the `distinct` flag when generating SQL".

These four micro-fixes are minimum scope for B2_v1 and do not introduce repair, retrieval, or sampling.
'''

md_lines.append(answers)

(OUTPUTS / 'logs' / 'b2_v0_smoke10_triage.md').write_text('\n'.join(md_lines), encoding='utf-8')

csv_path = OUTPUTS / 'tables' / 'b2_v0_smoke10_failure_cases.csv'
with csv_path.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(triage_rows[0].keys()))
    w.writeheader()
    for r in triage_rows: w.writerow(r)

print(f'WROTE {OUTPUTS / "logs" / "b2_v0_smoke10_triage.md"}')
print(f'WROTE {csv_path}')
print(f'fails={len(fails)}')
for r in triage_rows:
    print(f"  idx={r['idx']} db={r['db_id']} error_type={r['error_type']}")
