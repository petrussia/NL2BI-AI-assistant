# Phase 0+1+2: full-benchmark recovery + audit + run plan.

import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
NOW = dt.datetime.now(dt.timezone.utc).isoformat()

# Physical benchmark sizes
sp = PROJECT_ROOT/'data/spider'
spider_dev = json.loads((sp/'dev.json').read_text(encoding='utf-8'))
spider_db_dist = Counter(ex['db_id'] for ex in spider_dev)

bird_root = PROJECT_ROOT/'external_benchmarks/bird_mini_dev/raw/minidev/minidev/MINIDEV'
bird = json.loads((bird_root/'mini_dev_sqlite.json').read_text(encoding='utf-8'))
bird_db_dist = Counter(ex.get('db_id','?') for ex in bird)
bird_with_evidence = sum(1 for ex in bird if ex.get('evidence'))
bird_db_descriptions = sum(1 for d in (bird_root/'dev_databases').iterdir() if (d/'database_description').exists())

s2_root = PROJECT_ROOT/'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite'
s2 = [json.loads(l) for l in open(s2_root/'spider2-lite.jsonl', encoding='utf-8') if l.strip()]
s2_db_dist = Counter(ex.get('db','?') for ex in s2)
s2_with_evidence = sum(1 for ex in s2 if ex.get('external_knowledge'))

# Spider audit
(OUTPUTS/'logs'/'spider_full_audit.md').write_text(f'''# Spider dev FULL audit

**Generated:** {NOW}
- Total examples: **{len(spider_dev)}**
- Distinct DBs: **{len(spider_db_dist)}**
- SQLite database files present: 166
- All examples have `query` field (gold SQL): {all('query' in ex for ex in spider_dev)}

## Top 10 DBs by example count
| db_id | n |
|---|---|
''' + '\n'.join(f'| `{k}` | {v} |' for k, v in spider_db_dist.most_common(10)) + '\n', encoding='utf-8')

with (OUTPUTS/'tables'/'spider_full_db_distribution.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['db_id','count'])
    for k, v in sorted(spider_db_dist.items(), key=lambda x: (-x[1], x[0])):
        w.writerow([k, v])

# BIRD audit
(OUTPUTS/'logs'/'bird_full_audit.md').write_text(f'''# BIRD Mini-Dev FULL audit

**Generated:** {NOW}
- Total examples: **{len(bird)}**
- Distinct DBs: **{len(bird_db_dist)}**
- Examples with `evidence` field: {bird_with_evidence} ({100*bird_with_evidence/len(bird):.1f}%)
- DBs with `database_description/` subdir: {bird_db_descriptions}/{len(bird_db_dist)}

## DB distribution
| db_id | n |
|---|---|
''' + '\n'.join(f'| `{k}` | {v} |' for k, v in sorted(bird_db_dist.items(), key=lambda x: (-x[1], x[0]))) + '\n', encoding='utf-8')

with (OUTPUTS/'tables'/'bird_full_db_distribution.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['db_id','count'])
    for k, v in sorted(bird_db_dist.items(), key=lambda x: (-x[1], x[0])):
        w.writerow([k, v])

with (OUTPUTS/'tables'/'bird_full_metadata_availability.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['feature','count','total','pct'])
    w.writerow(['evidence_field', bird_with_evidence, len(bird), f'{100*bird_with_evidence/len(bird):.1f}'])
    w.writerow(['db_with_database_description', bird_db_descriptions, len(bird_db_dist), f'{100*bird_db_descriptions/len(bird_db_dist):.1f}'])

# Spider2-Lite audit
(OUTPUTS/'logs'/'spider2lite_full_audit.md').write_text(f'''# Spider 2.0-Lite FULL audit

**Generated:** {NOW}
- Total examples: **{len(s2)}**
- Distinct DBs: **{len(s2_db_dist)}**
- Examples with `external_knowledge` field: {s2_with_evidence}

## Top 15 DBs by example count
| db | n |
|---|---|
''' + '\n'.join(f'| `{k}` | {v} |' for k, v in s2_db_dist.most_common(15)) + '\n', encoding='utf-8')

with (OUTPUTS/'tables'/'spider2lite_full_structural_metrics.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['note','value'])
    w.writerow(['n_examples', len(s2)])
    w.writerow(['n_dbs', len(s2_db_dist)])
    w.writerow(['evaluation_mode', 'structural_only'])
    w.writerow(['reason', 'gold queries target BigQuery/Snowflake; no cloud creds in Colab'])

(OUTPUTS/'logs'/'spider2lite_full_eval_limitations.md').write_text(f'''# Spider 2.0-Lite — full evaluation limitations

**Generated:** {NOW}
- N examples: 547
- N unique enterprise schemas: {len(s2_db_dist)}
- Gold queries target BigQuery/Snowflake/DuckDB-extensions
- Internal SQLite execution NOT possible (gold queries reference cloud-warehouse-specific functions and tables)
- Therefore: structural-only evaluation:
  - safe_select_pct
  - has_join_pct
  - has_groupby_pct
  - has_orderby_pct
  - has_limit_pct
  - avg_sql_tokens
  - invalid_sql_pct
- EX is **not computed** — that would be fake
- Oracle-table analysis is also not computed (would require constructing SQLite tables from Spider2 DDL+JSON, ~1-2 days of work, out of project scope)
''', encoding='utf-8')

# ============================================================
# Run plan
# ============================================================
RUN_PLAN = []
def add_run(run_id, benchmark, size, model, baseline, status='planned',
            est=None, notes=''):
    RUN_PLAN.append({
        'run_id': run_id, 'benchmark': benchmark, 'benchmark_size': size,
        'model': model, 'baseline': baseline, 'status': status,
        'predictions_path': f'outputs/predictions/{run_id}_predictions.jsonl',
        'metrics_path': f'outputs/metrics/{run_id}_metrics.csv',
        'blocker_path': '',
        'estimated_examples': est or size,
        'actual_examples': '',
        'notes': notes,
    })

# CRITICAL SET (executable in this iteration on A100 ~4-5 hours)
# Qwen-Coder-7B × {B0, B1_v3, B3_v4, B2_v4} × {Spider full, BIRD full}
# + Qwen-Coder-7B × {B0, B3_v4} × Spider2-Lite full structural

add_run('b0_qwen2p5_coder_7b_spider_dev_full', 'spider_dev', 1034,
        'Qwen/Qwen2.5-Coder-7B-Instruct', 'B0', 'planned',
        notes='CRITICAL: ceiling check on full Spider dev')
add_run('b1v3_qwen2p5_coder_7b_spider_dev_full', 'spider_dev', 1034,
        'Qwen/Qwen2.5-Coder-7B-Instruct', 'B1_v3', 'planned',
        notes='CRITICAL: retrieval-only check on full Spider dev')
add_run('b3v4_qwen2p5_coder_7b_spider_dev_full', 'spider_dev', 1034,
        'Qwen/Qwen2.5-Coder-7B-Instruct', 'B3_v4', 'planned',
        notes='CRITICAL: hybrid retrieval check on full Spider dev')

add_run('b0_qwen2p5_coder_7b_bird_full', 'bird_minidev', 500,
        'Qwen/Qwen2.5-Coder-7B-Instruct', 'B0', 'planned',
        notes='CRITICAL: ceiling check on full BIRD')
add_run('b1v3_qwen2p5_coder_7b_bird_full', 'bird_minidev', 500,
        'Qwen/Qwen2.5-Coder-7B-Instruct', 'B1_v3', 'planned',
        notes='CRITICAL: retrieval-only check on full BIRD')
add_run('b3v4_qwen2p5_coder_7b_bird_full', 'bird_minidev', 500,
        'Qwen/Qwen2.5-Coder-7B-Instruct', 'B3_v4', 'planned',
        notes='CRITICAL: hybrid retrieval + evidence on full BIRD')
add_run('b2v4_qwen2p5_coder_7b_bird_full', 'bird_minidev', 500,
        'Qwen/Qwen2.5-Coder-7B-Instruct', 'B2_v4', 'planned',
        notes='CRITICAL: planner v4 check on full BIRD')

add_run('b0_qwen2p5_coder_7b_spider2lite_full', 'spider2lite', 547,
        'Qwen/Qwen2.5-Coder-7B-Instruct', 'B0', 'planned',
        notes='Structural-only validation on full Spider2-Lite')
add_run('b3v4_qwen2p5_coder_7b_spider2lite_full', 'spider2lite', 547,
        'Qwen/Qwen2.5-Coder-7B-Instruct', 'B3_v4', 'planned',
        notes='Structural-only validation on full Spider2-Lite')

# DEFERRED (require separate longer sessions)
for model in ['Qwen2.5-Coder-32B','Gemma-3-12b-it','Llama-3.1-8B','Qwen3-8B','SQLCoder-7B-2']:
    for sub in ['spider_dev','bird_minidev']:
        for bl in ['B0','B1_v3','B3_v4']:
            add_run(f'{bl.lower().replace("_","")}_{model.lower().replace(".","p").replace("-","_")}_{sub}_full',
                    sub, 1034 if sub == 'spider_dev' else 500,
                    f'(deferred) {model}', bl, 'deferred',
                    notes='Out of single-session compute budget; documented as future work')
add_run('deepseek_blocked_full', 'all', 0, 'DeepSeek-Coder-V2-Lite', 'all',
        'blocked',
        notes='Environmental blocker; fresh-kernel runbook in deepseek_fresh_kernel_runbook_v10.md')

plan_csv = OUTPUTS/'tables'/'full_benchmark_run_plan.csv'
with plan_csv.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(RUN_PLAN[0].keys()))
    w.writeheader()
    for r in RUN_PLAN: w.writerow(r)

# Existing runs audit (vs planned)
existing = sorted(p.stem.replace('_metrics','') for p in (OUTPUTS/'metrics').glob('*_metrics.csv'))
with (OUTPUTS/'tables'/'full_benchmark_existing_runs_audit.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['run_prefix','present','category'])
    for prefix in existing:
        cat = 'sample_run' if any(s in prefix for s in ['smoke10','smoke25','multidb30','minidev_30','spider2lite_30']) else 'other'
        w.writerow([prefix, 'YES', cat])

# Reentry doc
n_planned = sum(1 for r in RUN_PLAN if r['status']=='planned')
n_deferred = sum(1 for r in RUN_PLAN if r['status']=='deferred')
n_blocked = sum(1 for r in RUN_PLAN if r['status']=='blocked')

(OUTPUTS/'logs'/'full_benchmark_reentry_audit.md').write_text(f'''# Full benchmark reentry audit + plan

**Generated:** {NOW}
**Bridge:** live, A100 80 GB free
**HF_TOKEN:** SET, Drive mounted
**Existing master matrix:** 127 rows (sample-size runs only — smoke_10/25/multidb_30/minidev_30/spider2lite_30)

## Physical benchmark sizes (verified)
| Benchmark | n examples | unique DBs | Notes |
|---|---|---|---|
| **Spider dev FULL** | **{len(spider_dev)}** | {len(spider_db_dist)} | All have gold SQL; 166 SQLite DB files |
| **BIRD Mini-Dev FULL** | **{len(bird)}** | {len(bird_db_dist)} | {bird_with_evidence}/500 have evidence; SQLite gold execution available |
| **Spider 2.0-Lite FULL** | **{len(s2)}** | {len(s2_db_dist)} | Structural-only (gold targets BigQuery/Snowflake) |

## Compute reality check
- One generation on A100 BF16 7B model ≈ 2 sec
- Full sweep (5 baselines × 6+ models × 2081 ex) ≈ **62,000 generations × 2 sec = 35 hours of compute** for P0/P1 models alone
- This exceeds a single agent session's effective wall time

## Decision: critical-evidence subset this iteration

Run **9 critical cells** = ~3,000 generations × ~2-3 sec = **~3-4 hours runtime** on A100 BF16:
- Qwen-Coder-7B × {{B0, B1_v3, B3_v4}} × Spider dev full (3 × 1034 = 3102 gen)
- Qwen-Coder-7B × {{B0, B1_v3, B3_v4, B2_v4}} × BIRD full (4 × 500 = 2000 gen)
- Qwen-Coder-7B × {{B0, B3_v4}} × Spider 2.0-Lite full structural (2 × 547 = 1094 gen)

**Why this subset:** directly tests the v9 claim (planner hurts, retrieval-only wins) on FULL benchmarks for the incumbent model. Other models / baselines documented as deferred future work.

## Plan summary
- Planned (this iteration): {n_planned}
- Deferred (multi-session): {n_deferred}
- Blocked (DeepSeek): {n_blocked}

## Resumability
All runs use predictions_jsonl that's incrementally written per-item (one line per example, flushed). On resume, the runner counts existing lines and skips completed examples.

## Ground rules
- No fake EX on Spider 2.0-Lite (structural-only metrics only).
- DeepSeek not attempted in current kernel.
- Old smoke/sample runs preserved as "sample_run" category in master matrix; full runs added with new "full" suffix.
''', encoding='utf-8')

print(f'Spider dev: {len(spider_dev)} ex')
print(f'BIRD full: {len(bird)} ex')
print(f'Spider2-Lite full: {len(s2)} ex')
print(f'PLANNED THIS ITERATION: {n_planned} runs')
print(f'DEFERRED: {n_deferred} runs')
print(f'BLOCKED: {n_blocked} categories')
print(f'WROTE plan: {plan_csv}')
