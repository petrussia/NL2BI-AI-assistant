# Phase A: gap audit from physical files only.
# Build the canonical 5-bench × 5-baseline × 5-model matrix and compare against
# what actually exists on Drive.

import csv
import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
NOW = dt.datetime.now(dt.timezone.utc).isoformat()

# ============================================================
# Canonical sets
# ============================================================
BENCHMARKS = [
    # (key, internal_subset_name_or_None, benchmark_group, metric_type)
    ('smoke_10',          'smoke_10',     'internal_core',         'EX'),
    ('smoke_25',          'smoke_25',     'internal_core',         'EX'),
    ('multidb_30',        'multidb_30',   'internal_core',         'EX'),
    ('bird_minidev_30',   None,           'external_validation',   'EX'),
    ('spider2lite_30',    None,           'external_validation',   'structural_only'),
]
BASELINES = ['B0', 'B1', 'B2_v2', 'B3_v2', 'B4_v2']
MODELS = [
    # (slug_used_in_run_id, display_name)
    ('qwen2p5_coder_7b',         'Qwen2.5-Coder-7B-Instruct'),
    ('qwen2p5_coder_14b',        'Qwen2.5-Coder-14B-Instruct'),
    ('llama_3p1_8b',             'Llama-3.1-8B-Instruct'),
    ('qwen_qwen2.5_7b_instruct', 'Qwen2.5-7B-Instruct'),
    ('deepseek_coder_v2_lite',   'DeepSeek-Coder-V2-Lite-Instruct'),
]

# Some historic prefixes use a different model_slug — map them.
# For each (baseline, benchmark, model_slug), produce the set of run_id prefixes
# that COULD represent this cell.
def candidate_prefixes(baseline, bench, model_slug):
    bl = baseline.lower()  # 'b0','b1','b2_v2','b3_v2','b4_v2'
    bl_compact = bl.replace('_', '')  # 'b0','b1','b2v2','b3v2','b4v2'
    out = set()
    if bench == 'smoke_10':
        # Internal Spider primary model has historic prefix `spider_smoke10`
        if model_slug == 'qwen2p5_coder_7b':
            out.add(f'{bl_compact}_spider_smoke10')
        # Cross-model historic
        if model_slug == 'qwen_qwen2.5_7b_instruct':
            out.add(f'{bl_compact}_qwen_qwen2.5_7b_instruct_smoke10')
        # Llama instruct prefix
        if model_slug == 'llama_3p1_8b':
            out.add(f'{bl_compact}_llama_3p1_8b_instruct_smoke10')
            out.add(f'{bl_compact}_llama_3p1_8b_smoke10')
        if model_slug == 'qwen2p5_coder_14b':
            out.add(f'{bl_compact}_qwen2p5_coder_14b_instruct_smoke10')
        if model_slug == 'deepseek_coder_v2_lite':
            out.add(f'{bl_compact}_deepseek_coder_v2_lite_instruct_smoke10')
            out.add(f'{bl_compact}_deepseek_b0_smoke10' if bl_compact == 'b0' else f'{bl_compact}_deepseek_b1_smoke10')
    elif bench == 'smoke_25':
        if model_slug == 'qwen2p5_coder_7b':
            out.add(f'{bl_compact}_spider_smoke25')
        if model_slug == 'llama_3p1_8b':
            out.add(f'{bl_compact}_llama_3p1_8b_instruct_smoke25')
            out.add(f'{bl_compact}_llama_3p1_8b_smoke25')
        if model_slug == 'qwen2p5_coder_14b':
            out.add(f'{bl_compact}_qwen2p5_coder_14b_instruct_smoke25')
        if model_slug == 'qwen_qwen2.5_7b_instruct':
            out.add(f'{bl_compact}_qwen_qwen2.5_7b_instruct_smoke25')
        if model_slug == 'deepseek_coder_v2_lite':
            out.add(f'{bl_compact}_deepseek_coder_v2_lite_instruct_smoke25')
    elif bench == 'multidb_30':
        if model_slug == 'qwen2p5_coder_7b':
            # historic prefixes: `b0_multidb30_v2`, `b2v1_multidb30`, `b2v2_multidb30`, etc.
            if bl_compact in ('b0','b1'):
                out.add(f'{bl_compact}_multidb30_v2')
            out.add(f'{bl_compact}_multidb30')
        if model_slug == 'llama_3p1_8b':
            out.add(f'{bl_compact}_llama_3p1_8b_instruct_multidb30')
            out.add(f'{bl_compact}_llama_3p1_8b_multidb30')
        if model_slug == 'qwen2p5_coder_14b':
            out.add(f'{bl_compact}_qwen2p5_coder_14b_instruct_multidb30')
        if model_slug == 'qwen_qwen2.5_7b_instruct':
            out.add(f'{bl_compact}_qwen_qwen2.5_7b_instruct_multidb30')
        if model_slug == 'deepseek_coder_v2_lite':
            out.add(f'{bl_compact}_deepseek_coder_v2_lite_instruct_multidb30')
    elif bench == 'bird_minidev_30':
        out.add(f'{bl_compact}_{model_slug}_bird_minidev_30')
        if model_slug == 'qwen2p5_coder_14b':
            out.add(f'{bl_compact}_qwen2p5_coder_14b_instruct_bird_minidev_30')
        if model_slug == 'llama_3p1_8b':
            out.add(f'{bl_compact}_llama_3p1_8b_instruct_bird_minidev_30')
        if model_slug == 'qwen_qwen2.5_7b_instruct':
            out.add(f'{bl_compact}_qwen_qwen2.5_7b_instruct_bird_minidev_30')
    elif bench == 'spider2lite_30':
        out.add(f'{bl_compact}_{model_slug}_spider2lite_30')
        if model_slug == 'qwen2p5_coder_14b':
            out.add(f'{bl_compact}_qwen2p5_coder_14b_instruct_spider2lite_30')
        if model_slug == 'llama_3p1_8b':
            out.add(f'{bl_compact}_llama_3p1_8b_instruct_spider2lite_30')
        if model_slug == 'qwen_qwen2.5_7b_instruct':
            out.add(f'{bl_compact}_qwen_qwen2.5_7b_instruct_spider2lite_30')
    return out


existing_metrics = {p.stem.replace('_metrics',''): p for p in (OUTPUTS/'metrics').glob('*_metrics.csv')}

cells = []
for benchmark, _, bench_group, metric_type in BENCHMARKS:
    for baseline in BASELINES:
        for model_slug, model_name in MODELS:
            cands = candidate_prefixes(baseline, benchmark, model_slug)
            found = sorted(c for c in cands if c in existing_metrics)
            if found:
                # Read EX from the first existing run
                row = next(csv.DictReader(existing_metrics[found[0]].open(encoding='utf-8')))
                ex_str = row.get('ex', '')
                try: ex_val = float(ex_str)
                except: ex_val = None
                # Distinguish EX vs structural_only
                eval_mode = row.get('evaluation_mode', '') or ('structural_only' if 'spider2lite' in benchmark else '')
                if metric_type == 'structural_only':
                    primary_metric_name = 'structural_safe_select_pct'
                    primary_metric_value = row.get('struct_pct_safe_select','')
                else:
                    primary_metric_name = 'EX'
                    primary_metric_value = ex_str
                cells.append({
                    'benchmark': benchmark,
                    'benchmark_group': bench_group,
                    'baseline': baseline,
                    'model': model_name,
                    'model_slug': model_slug,
                    'status': 'done',
                    'metric_type': metric_type,
                    'primary_metric_name': primary_metric_name,
                    'primary_metric_value': primary_metric_value,
                    'numerator': row.get('execution_match_count',''),
                    'denominator': row.get('n',''),
                    'existing_artifact_prefix': found[0],
                    'blocker_reason': '',
                })
            else:
                # Decide status: blocked vs missing
                blocker = ''
                status = 'missing'
                if model_slug == 'deepseek_coder_v2_lite':
                    status = 'blocked'
                    blocker = 'environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3'
                cells.append({
                    'benchmark': benchmark,
                    'benchmark_group': bench_group,
                    'baseline': baseline,
                    'model': model_name,
                    'model_slug': model_slug,
                    'status': status,
                    'metric_type': metric_type,
                    'primary_metric_name': '',
                    'primary_metric_value': '',
                    'numerator': '',
                    'denominator': '',
                    'existing_artifact_prefix': '',
                    'blocker_reason': blocker,
                })


# Save CSV
gap_csv = OUTPUTS/'tables'/'full_closure_gap_matrix.csv'
with gap_csv.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(cells[0].keys()))
    w.writeheader()
    for c in cells: w.writerow(c)

# Save MD (compact view)
gap_md = OUTPUTS/'tables'/'full_closure_gap_matrix.md'
def status_emoji(s):
    return {'done':'✅','missing':'❌','blocked':'🚫','not_applicable':'⚪'}.get(s,'?')

# Pivot view: row = (model, benchmark), col = baseline, cell = status emoji + value
md_lines = [
    '# Full closure gap matrix',
    f'_Generated: {NOW}_',
    f'_Total cells: {len(cells)}_  ',
    f'_done: {sum(1 for c in cells if c["status"]=="done")}  '
    f'missing: {sum(1 for c in cells if c["status"]=="missing")}  '
    f'blocked: {sum(1 for c in cells if c["status"]=="blocked")}  '
    f'not_applicable: {sum(1 for c in cells if c["status"]=="not_applicable")}_',
    '',
    'Legend: ✅ done · ❌ missing · 🚫 blocked · ⚪ N/A',
    '',
]
# By model
for slug, model in MODELS:
    md_lines.append(f'## {model}')
    md_lines.append('| Benchmark | B0 | B1 | B2_v2 | B3_v2 | B4_v2 |')
    md_lines.append('|---|---|---|---|---|---|')
    for bench, _, _, mt in BENCHMARKS:
        row_cells = [bench]
        for bl in BASELINES:
            cell = next(c for c in cells
                        if c['benchmark']==bench and c['baseline']==bl and c['model_slug']==slug)
            if cell['status'] == 'done':
                if mt == 'structural_only':
                    val = f'{float(cell["primary_metric_value"]):.0f}%' if cell["primary_metric_value"] else '?'
                else:
                    try: val = f'{float(cell["primary_metric_value"]):.2f}'
                    except: val = '?'
                row_cells.append(f'✅ {val}')
            else:
                tag = status_emoji(cell['status'])
                row_cells.append(f'{tag}')
        md_lines.append('| ' + ' | '.join(row_cells) + ' |')
    md_lines.append('')

# Missing/blocked details list
md_lines.append('## Missing cells (in prioritized order)')
md_lines.append('')
priority_order = [
    ('qwen2p5_coder_7b', 'P0'),
    ('llama_3p1_8b', 'P0'),
    ('qwen2p5_coder_14b', 'P0'),
    ('qwen_qwen2.5_7b_instruct', 'P1'),
    ('deepseek_coder_v2_lite', 'P2'),
]
for slug, prio in priority_order:
    miss = [c for c in cells if c['model_slug']==slug and c['status']=='missing']
    blk = [c for c in cells if c['model_slug']==slug and c['status']=='blocked']
    if miss or blk:
        md_lines.append(f'### {prio}: {next(m for s,m in MODELS if s==slug)}')
        for c in miss:
            md_lines.append(f'- **MISSING** {c["baseline"]} on {c["benchmark"]}')
        for c in blk:
            md_lines.append(f'- **BLOCKED** {c["baseline"]} on {c["benchmark"]} — {c["blocker_reason"]}')
        md_lines.append('')

gap_md.write_text('\n'.join(md_lines), encoding='utf-8')

# Plan
plan_md = OUTPUTS/'logs'/'full_closure_plan.md'
done = sum(1 for c in cells if c["status"]=="done")
missing = sum(1 for c in cells if c["status"]=="missing")
blocked = sum(1 for c in cells if c["status"]=="blocked")
not_app = sum(1 for c in cells if c["status"]=="not_applicable")

# Aggregated by priority
priority_summary = []
for slug, prio in priority_order:
    miss_count = sum(1 for c in cells if c['model_slug']==slug and c['status']=='missing')
    done_count = sum(1 for c in cells if c['model_slug']==slug and c['status']=='done')
    blk_count = sum(1 for c in cells if c['model_slug']==slug and c['status']=='blocked')
    name = next(m for s,m in MODELS if s==slug)
    priority_summary.append((prio, name, done_count, miss_count, blk_count))

plan_md.write_text(f'''# Full closure plan

**Generated:** {NOW}

## Canonical matrix scope
- **Benchmarks:** {", ".join(b[0] for b in BENCHMARKS)} (5)
- **Baselines:** {", ".join(BASELINES)} (5)
- **Models:** {", ".join(m[1] for m in MODELS)} (5)
- **Total logical cells:** {len(cells)} (5 × 5 × 5)

## Status counts
- ✅ done: **{done}**
- ❌ missing: **{missing}**
- 🚫 blocked: **{blocked}**
- ⚪ not_applicable: {not_app}

## Per-model summary

| Priority | Model | Done | Missing | Blocked |
|---|---|---|---|---|
''' + '\n'.join(f'| {p} | {n} | {d}/25 | {m} | {b} |' for p,n,d,m,b in priority_summary) + f'''

## Priority order for closure (this iteration)

### P0 (defense-critical) — {sum(m for p,n,d,m,b in priority_summary if p=="P0")} runs to add
1. **Qwen-Coder-7B fill** — close `B1, B3_v2, B4_v2` on bird/spider2lite (6 runs)
2. **Llama-3.1-8B fill** — close `B2_v2, B3_v2, B4_v2` on smoke/multidb (9 runs) + `B1, B3_v2, B4_v2` on external (6 runs) = 15 runs
3. **Qwen-Coder-14B fill** — close `B2_v2, B3_v2, B4_v2` on smoke/multidb (9 runs) + `B0, B1, B2_v2, B3_v2, B4_v2` on external (10 runs) = 19 runs

### P1 — {sum(m for p,n,d,m,b in priority_summary if p=="P1")} runs to add
4. **Qwen2.5-7B-Instruct comparator extension** — minimum `B0, B1, B2_v2` on each of 5 benchmarks = 13 missing (2 already done on smoke_10)

### P2 — {sum(b for p,n,d,m,b in priority_summary if p=="P2")} blocked
5. **DeepSeek-Coder-V2-Lite-Instruct** — environmental blocker (transformers 5.0 ABI vs trust_remote_code modeling). Documented as blocker; clean-notebook unblock recipe in `outputs/tables/deepseek_blocker_reproduction_checklist.csv`.

## Realistic closure scope this iteration

Given A100 budget (~5 min per run on 30-item benchmarks, ~2 min on smoke):

**Aim to add ~30-50 runs in batches:**
- Batch 01: Qwen-Coder-7B external fill (6 runs, ~30 min)
- Batch 02: Llama-3.1-8B internal layered fill (9 runs, ~30 min)
- Batch 03: Llama-3.1-8B external fill (6 runs, ~30 min)
- Batch 04: Qwen-Coder-14B internal layered fill (9 runs, ~30 min)
- Batch 05: Qwen-Coder-14B external fill (10 runs, ~50 min)
- Batch 06: Qwen2.5-7B-Instruct B0/B1/B2_v2 across 5 benchmarks (13 runs, ~50 min)
- Batch 07: DeepSeek final blocker artifact (no runs)

**Total estimated wall time:** ~3-4 hours on A100. Run as detached subprocess BG with incremental Drive sync.

## Stop rule
Phase done when every cell in `outputs/tables/full_closure_gap_matrix.csv` is one of:
- `done` with a real artifact, OR
- `blocked` with a real reproduction-checklist artifact, OR
- `not_applicable` with a one-line explanation.
''', encoding='utf-8')

print(f'WROTE {gap_csv}')
print(f'WROTE {gap_md}')
print(f'WROTE {plan_md}')
print(f'TOTAL cells: {len(cells)}, done={done}, missing={missing}, blocked={blocked}')
