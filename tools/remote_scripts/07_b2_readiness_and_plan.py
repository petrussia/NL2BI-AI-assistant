# Step 7: B2 readiness + scaffolding plan. No execution, just two markdown
# documents on Drive that capture what's missing and the cheapest first step.

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


b0_25 = load_csv_one(OUTPUTS / 'metrics' / 'b0_spider_smoke25_metrics.csv')
b1_25 = load_csv_one(OUTPUTS / 'metrics' / 'b1_spider_smoke25_metrics.csv')


def fnum(d, k):
    if not d or d.get(k) in (None, ''): return None
    try: return float(d[k])
    except Exception: return d[k]


ex_b0_25 = fnum(b0_25, 'ex')
ex_b1_25 = fnum(b1_25, 'ex')

if ex_b0_25 is None or ex_b1_25 is None:
    state = 'unknown'
    rec_step = '1) baseline triage — re-run smoke25 if metrics missing'
else:
    if ex_b0_25 >= 0.8 and ex_b1_25 >= 0.8:
        state = 'baselines strong'
        rec_step = '1) B2 on smoke10 (cheap dry-run of Plan->SQL pipeline)'
    elif ex_b0_25 >= 0.5 or ex_b1_25 >= 0.5:
        state = 'baselines middling'
        rec_step = '1) error triage on smoke25 first; only then B2 on smoke10'
    else:
        state = 'baselines weak'
        rec_step = '1) baseline analysis — fix B0 prompt or model setup before B2'

# ============= b2_readiness_after_smoke25.md =============
ready = f'''# B2 Readiness After smoke25

Updated: {ts}

## Current baseline state on smoke25
- B0 EX = {ex_b0_25}
- B1 EX = {ex_b1_25}
- Both subsets so far probe only `concert_singer` (4 tables, smoke10 ⊂ smoke25). Schema-linking benefit is bounded on this slice.

State summary: **{state}**

## What B2 needs vs what we already have

| Component | Required for B2 | Already in repo? | Notes |
|---|---|---|---|
| Spider data + schema linking helper | yes | yes (`repo/src/evaluation/baselines.py`) | Reused from B1. |
| Reduced-schema prompt builder | yes | yes (`build_reduced_schema_context`, `make_b1_prompt`) | Reused from B1. |
| Execution + EX evaluation | yes | yes (`execute_sql`, evaluator pattern) | Reused from B0/B1. |
| **Planner** that emits a JSON Plan | yes | no | Need a `make_plan_prompt`, JSON parser, validation against `plan_schema.json`. |
| **Schema retrieval** index (db -> top-K tables/columns) | yes | partial (lexical linker is the seed) | Could start with the same lexical scorer as B1, ranking *across DBs* not within one. |
| **Domain doc retrieval** (e.g. column descriptions, glossary) | nice-to-have | no | Not strictly needed for Spider; document if later switching benchmarks. |
| **Plan -> SQL prompt routing** | yes | no | New prompt template that takes the Plan + reduced schema and emits SQL. |
| **Validation + repair loop** | yes | no | Run generated SQL, inspect error, ask model to repair. Bounded retries. |
| **Execution-guided selection** (multi-candidate generate, pick by execution result) | yes | no | Sample N candidates, prefer the executable one whose result matches another candidate's. |

## Cheapest next experiment ordering
1. **{rec_step.lstrip("1) ").strip()}**
2. If (1) clears, B2 on smoke25 (more questions per DB but still single DB — primarily a soak test of the pipeline).
3. Build a multi-DB sample (e.g. one question per `concert_singer`, `wrestler`, `assets_maintenance`, …) — this is where schema linking and retrieval start mattering.
4. After multi-DB shows separation between B0/B1/B2, scale to dev-full.

## Risks
- 4-bit model may regress on planner-style prompts that produce JSON; sanity-check JSON validity before counting EX.
- Cloudflare quick-tunnel timeouts (~100 s) keep biting; the bridge-side background-thread pattern from `04b_smoke25_b0_and_b1_bg.py` should be reused for any B2 run that touches >10 questions.
- One-DB smoke sets give noisy signal; do not treat smoke25 ties as evidence that schema linking is useless in general.
'''
(LOGS / 'b2_readiness_after_smoke25.md').write_text(ready, encoding='utf-8')

# ============= b2_implementation_plan.md =============
plan = f'''# B2 Implementation Plan (scaffolding)

Updated: {ts}.
**Scope: minimal.** No retrieval indexes built yet, no repair loop yet, no fine-tuning.
This document defines the minimum viable B2 (Plan -> SQL) so it can be run on smoke10
the moment the user gives the go-ahead. Nothing here gets executed by this script.

## Files to add
| Path on Drive | Purpose |
|---|---|
| `repo/src/evaluation/planner.py` | `make_plan_prompt(question, reduced_schema)`; `parse_plan(raw)` (JSON-fenced extraction + schema validation against `plan_schema.json`); `make_plan_sql_prompt(plan, reduced_schema)`; `extract_sql_from_plan_run(raw)`. |
| `repo/src/evaluation/baselines_b2.py` | `run_b2_on_subset(items, model, tokenizer, tables_map, db_paths)`; reuses `lexical_schema_linking`, `build_reduced_schema_context`, `extract_sql`, `execute_sql` from `baselines.py`. |
| `tools/remote_scripts/10_b2_smoke10_bg.py` | Background-thread inference dispatcher analogous to `04b_smoke25_b0_and_b1_bg.py`, but for B2. |

## Notebook cells to add
1. `B2_SETUP` — imports planner, defines `make_plan_prompt`, `parse_plan`, `make_plan_sql_prompt`. Side-effect-free (no inference). One Shift+Enter at the start of a B2 session.
2. `B2_INFERENCE_SMOKE10` — kicks off `run_b2_on_subset(smoke10, …)` in a background thread (mirrors `04b`). Saves predictions incrementally.
3. `B2_VS_B0_VS_B1_SMOKE10` — three-way comparison after the BG thread finishes. Outputs `outputs/tables/baseline_progression_b0_b1_b2_smoke10.{{csv,md}}`, `outputs/plots/baseline_progression_b0_b1_b2_smoke10.png`.

## Artifacts B2 must produce (smoke10 first run)
- `outputs/predictions/b2_spider_smoke10_predictions.jsonl` (with extra fields: `plan_raw`, `plan_parsed`, `plan_valid`, `selected_tables`, `schema_reduction_ratio`, `executable`, `execution_match`, `error_type`)
- `outputs/metrics/b2_spider_smoke10_metrics.csv` (with extra columns: `plan_valid_count`, `plan_parse_failures`)
- `outputs/tables/b2_spider_smoke10_summary.csv`
- `outputs/logs/b2_spider_smoke10_runlog.txt`
- `outputs/tables/b2_spider_smoke10_error_cases.md`
- `outputs/tables/b2_spider_smoke10_examples.md`
- Optional: `outputs/tables/b2_plan_examples_smoke10.md` showing 5 question -> plan -> SQL traces.

## Plan schema (already in repo)
The existing `plan_schema.json` defines the JSON Plan contract — reuse it to validate `parse_plan` output before invoking `make_plan_sql_prompt`. If a plan fails validation, record `plan_valid=False` and skip SQL generation (count as `error_type='plan_invalid'`).

## Decoding choices for B2
- Same model: `Qwen/Qwen2.5-Coder-7B-Instruct`, 4-bit `nf4`, greedy.
- `max_new_tokens` for plan: 256.
- `max_new_tokens` for SQL: 192 (same as B0/B1).
- Two sequential generations per question; ~3-4 s total → smoke10 = ~40 s. Comfortably within Cloudflare timeout, but use the bridge-bg pattern anyway for parity with B1 smoke25.

## Acceptance for "B2 first run done"
- Predictions JSONL has 10 rows with all expected fields populated.
- Metrics CSV has `ex` and `plan_valid_count`.
- Three-way progression CSV/PNG produced.
- `outputs/logs/b2_first_run_notes.md` written with observations.

## Out of scope for first B2 run
- Schema retrieval across DBs (future).
- Repair / retry loop (future).
- Multi-candidate execution-guided selection (future).
- Fine-tuning (out of scope altogether).
'''
(LOGS / 'b2_implementation_plan.md').write_text(plan, encoding='utf-8')

print('B2 readiness + plan written')
print(f'state={state} rec_step={rec_step!r}')
print('STATUS=DONE')
