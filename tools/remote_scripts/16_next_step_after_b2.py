# Step 16: produce next_step_after_b2.md based on what just happened.

import csv
import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
LOGS = OUTPUTS / 'logs'
ts = dt.datetime.now(dt.timezone.utc).isoformat()

def load_csv_one(p):
    if not p.exists(): return None
    return list(csv.DictReader(p.open(encoding='utf-8')))[0]

b0 = load_csv_one(OUTPUTS / 'metrics' / 'b0_spider_smoke10_metrics.csv')
b1 = load_csv_one(OUTPUTS / 'metrics' / 'b1_spider_smoke10_metrics.csv')
b2 = load_csv_one(OUTPUTS / 'metrics' / 'b2_spider_smoke10_metrics.csv')

def fnum(d, k):
    if not d or d.get(k) in (None, ''): return None
    try: return float(d[k])
    except Exception: return d[k]

ex0 = fnum(b0, 'ex'); ex1 = fnum(b1, 'ex'); ex2 = fnum(b2, 'ex')
plan_valid = b2.get('plan_valid_count') if b2 else None
plan_parse_fail = b2.get('plan_parse_failures') if b2 else None
n = b2.get('n') if b2 else 10

# Decision rules
if ex2 is None:
    rec_first = '**1) re-run B2 on smoke10** — B2 metrics missing; cannot judge.'
    rationale = 'cannot recommend further work without smoke10 numbers'
elif ex2 >= 0.8:
    if int(plan_parse_fail or 0) <= 1:
        rec_first = '**1) B2 on smoke25** — B2 is healthy on smoke10; check it scales (more questions per DB).'
        rationale = 'B2 EX strong AND planner is mostly emitting valid JSON. Smoke25 is the cheap soak test before architectural work.'
    else:
        rec_first = '**1) tighten the planner prompt** — fix plan parse failures before scaling subset.'
        rationale = 'EX is OK but planner is unreliable; scaling will multiply parse failures.'
elif ex2 >= 0.5:
    rec_first = '**1) B2 error triage on smoke10** — investigate plan_invalid and result_mismatch cases, then B2 smoke25.'
    rationale = 'B2 is below the comfort zone; smoke10 is small enough to triage by hand.'
else:
    rec_first = '**1) B2 design rework** — current planner format may be too restrictive; revisit plan_schema and prompt before larger runs.'
    rationale = 'B2 is weak; scaling cannot save it.'

# Multi-DB recommendation depends on whether B0/B1/B2 are still tied
if ex0 is not None and ex1 is not None and ex2 is not None and ex0 == ex1 == ex2:
    multi_db_note = 'Strong recommendation: a multi-DB sample is the only way to distinguish baselines that tie on single-DB smoke sets. After (1), build a multi-DB subset (one or two questions each from `concert_singer`, `wrestler`, `assets_maintenance`, etc.) and run all three baselines.'
elif ex2 is not None and ex2 > max(ex0 or 0, ex1 or 0):
    multi_db_note = "Multi-DB will validate that B2's gain is real and not subset-specific."
else:
    multi_db_note = 'Multi-DB sample remains valuable but not the most urgent next step.'

content = f'''# Next Step After B2

Updated: {ts}

## Current state on smoke10
- B0 EX = {ex0}
- B1 EX = {ex1}
- B2 EX = {ex2}
- B2 plan_valid_count = {plan_valid} / {n}
- B2 plan_parse_failures = {plan_parse_fail} / {n}

## Recommended ordering
{rec_first}

2. **B2 on smoke25** — same code path, larger n; soak test before any architectural change.
3. **Multi-DB sample** — pick one or two questions from each of several Spider DBs (`concert_singer`, `wrestler`, `assets_maintenance`, `world_1`, `pets_1`). This is the first evaluation slice where lexical schema linking can show real gain (table elimination across DBs, not within one). Run B0/B1/B2 against it.
4. **B2.5 retrieval-enhanced** — replace the within-DB lexical linker with a cross-DB retrieval index (still lexical / TF-IDF, no embeddings yet). Stage this only after multi-DB sample shows separation.

## Rationale
{rationale}

## Multi-DB note
{multi_db_note}

## Out of scope until the above is done
- B3, B4 (more complex pipelines).
- Fine-tuning of any kind.
- Final practice / thesis chapters.
- Replacing 4-bit quantisation.
- Domain-doc retrieval (Spider has no glossary that justifies it).

## Risks to watch
- Cloudflare quick-tunnel timeout (~100 s) — keep using the bridge-side BG-thread pattern (`13_b2_smoke10_bg.py`).
- Plan parse failures inflate B2 error rate without informing about the underlying SQL skill — track them separately.
- Single-DB subsets continue to mask schema-linking benefit. Treat smoke25 ties cautiously.
'''
(LOGS / 'next_step_after_b2.md').write_text(content, encoding='utf-8')
print(f'WROTE {LOGS / "next_step_after_b2.md"}')
print(f'EX_B0={ex0} EX_B1={ex1} EX_B2={ex2} plan_valid={plan_valid}/{n}')
print('STATUS=DONE')
