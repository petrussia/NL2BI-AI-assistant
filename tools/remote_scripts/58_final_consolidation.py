# Stage 9 + 10: TZ coverage final + master ablation + system status + REPORT.

import csv
import datetime as dt
import json
import re
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
ts = dt.datetime.now(dt.timezone.utc).isoformat()


def has(rel): return (PROJECT_ROOT / rel).exists()
def load_metrics(prefix):
    p = OUTPUTS / 'metrics' / f'{prefix}_metrics.csv'
    if not p.exists(): return None
    return list(csv.DictReader(p.open(encoding='utf-8')))[0]
def f(d,k):
    if not d or d.get(k) in (None,''): return None
    try: return float(d[k])
    except Exception: return d.get(k)


# ===== FINAL ABLATION MASTER =====
runs = [
    # (label, prefix, model, subset)
    ('B0',       'b0_spider_smoke10',     'Qwen-Coder-7B-Instruct', 'smoke10'),
    ('B1',       'b1_spider_smoke10',     'Qwen-Coder-7B-Instruct', 'smoke10'),
    ('B2_v0',    'b2_spider_smoke10',     'Qwen-Coder-7B-Instruct', 'smoke10'),
    ('B2_v1',    'b2v1_spider_smoke10',   'Qwen-Coder-7B-Instruct', 'smoke10'),
    ('B3',       'b3_spider_smoke10',     'Qwen-Coder-7B-Instruct', 'smoke10'),
    ('B3_v1',    'b3v1_spider_smoke10',   'Qwen-Coder-7B-Instruct', 'smoke10'),
    ('B4-lite',  'b4_spider_smoke10',     'Qwen-Coder-7B-Instruct', 'smoke10'),
    ('B4_final', 'b4_final_spider_smoke10','Qwen-Coder-7B-Instruct','smoke10'),
    ('B0',       'b0_spider_smoke25',     'Qwen-Coder-7B-Instruct', 'smoke25'),
    ('B1',       'b1_spider_smoke25',     'Qwen-Coder-7B-Instruct', 'smoke25'),
    ('B0',       'b0_qwen_qwen2.5_7b_instruct_smoke10', 'Qwen-7B-Instruct', 'smoke10'),
    ('B1',       'b1_qwen_qwen2.5_7b_instruct_smoke10', 'Qwen-7B-Instruct', 'smoke10'),
    ('B0',       'b0_multidb30_v2',       'Qwen-Coder-7B-Instruct', 'multidb_30'),
    ('B1',       'b1_multidb30_v2',       'Qwen-Coder-7B-Instruct', 'multidb_30'),
    ('B2_v1',    'b2v1_multidb30',        'Qwen-Coder-7B-Instruct', 'multidb_30'),
    ('B3_v1',    'b3v1_multidb30',        'Qwen-Coder-7B-Instruct', 'multidb_30'),
    ('B4_final', 'b4_final_multidb30',    'Qwen-Coder-7B-Instruct', 'multidb_30'),
]

master_csv = OUTPUTS / 'tables' / 'final_ablation_master.csv'
with master_csv.open('w', newline='', encoding='utf-8') as fh:
    w = csv.writer(fh)
    w.writerow(['baseline','model','subset','EX','executable_count','plan_valid_count','avg_reduction_ratio','n','present'])
    for label, prefix, model, subset in runs:
        d = load_metrics(prefix)
        if d is None:
            w.writerow([label, model, subset, '—','—','—','—','—', False])
            continue
        w.writerow([label, model, subset,
                    f(d,'ex'),
                    d.get('executable_count','—'),
                    d.get('plan_valid_count','—'),
                    d.get('avg_reduction_ratio','—'),
                    d.get('n','—'),
                    True])

# MD
md = ['# Final Ablation Master', '',
      f'Generated at: {ts}',
      '', '## All baseline × model × subset rows', '',
      '| Baseline | Model | Subset | EX | Executable | Plan valid | Avg reduction | n | Present |',
      '|---|---|---|---|---|---|---|---|---|']
for label, prefix, model, subset in runs:
    d = load_metrics(prefix)
    if d is None:
        md.append(f'| {label} | {model} | {subset} | — | — | — | — | — | False |'); continue
    ex_v = f(d,'ex')
    md.append(f"| {label} | {model} | {subset} | {ex_v:.4f} | {d.get('executable_count','—')}/{d.get('n','—')} | "
              f"{d.get('plan_valid_count','—')} | {d.get('avg_reduction_ratio','—')} | {d.get('n','—')} | True |")
(OUTPUTS / 'tables' / 'final_ablation_master.md').write_text('\n'.join(md) + '\n', encoding='utf-8')


# ===== TZ COVERAGE FINAL STRICT =====
items = [
    ('2.2.1', 'Анализ NL-запросов', 'functional',
     ['repo/src/evaluation/query_analysis.py',
      'outputs/logs/query_analysis_design.md',
      'outputs/tables/query_analysis_examples.md',
      'outputs/tables/query_analysis_ablation.csv'],
     'Rule-based intent + signals analyzer + design + examples + ablation table.'),
    ('2.2.2', 'Определение релевантных источников/таблиц/атрибутов', 'functional',
     ['repo/src/evaluation/baselines.py',
      'repo/src/evaluation/retrieval.py',
      'outputs/tables/b1_schema_linking_examples.md',
      'outputs/tables/b1_schema_linking_smoke25_examples.md',
      'outputs/logs/b3_retrieval_audit.md',
      'outputs/tables/b3v1_retrieval_examples.md'],
     'Lexical schema linker + cross-DB retrieval helper + adaptive dual retrieval (B3_v1).'),
    ('2.2.3', 'Генерация формализованных запросов с safety/performance', 'functional',
     ['outputs/predictions/b0_spider_smoke10_predictions.jsonl',
      'outputs/predictions/b4_final_spider_smoke10_predictions.jsonl',
      'repo/src/evaluation/baselines_b4_final.py',
      'outputs/logs/b4_final_validation_policy.md'],
     'B0..B4_final implemented; SELECT-only AST guard + 8s SQLite timeout enforced.'),
    ('2.2.4', 'Валидация и repair', 'functional',
     ['repo/docs/plan_schema.json',
      'repo/docs/plan_schema_v1.json',
      'outputs/tables/b4_final_candidate_examples.md',
      'outputs/logs/b4_final_validation_policy.md'],
     'jsonschema validation of plans; bounded repair (depth=1); multi-candidate with consistency selection.'),
    ('2.2.5', 'Предварительная обработка и агрегация результатов', 'functional',
     ['repo/src/evaluation/postprocess.py',
      'outputs/logs/postprocess_and_handoff_design.md',
      'outputs/tables/analytics_handoff_examples.md',
      'outputs/analytics_handoff'],
     'normalize_rows + compute_summary; demo payloads on Drive.'),
    ('2.2.6', 'Передача результатов в подсистему аналитического представления', 'functional',
     ['repo/src/evaluation/postprocess.py',
      'outputs/analytics_handoff',
      'outputs/logs/postprocess_and_handoff_design.md',
      'outputs/docs/io_contracts.md'],
     'AnalyticsPayload v1 contract + JSON+CSV export + handoff section in io_contracts.'),
    ('2.3', 'Документация (архитектура, форматы, тестирование, эксплуатация)', 'functional',
     ['outputs/docs/architecture_document.md',
      'outputs/docs/functional_specification.md',
      'outputs/docs/io_contracts.md',
      'outputs/docs/use_cases_and_scenarios.md',
      'outputs/docs/testing_methodology.md',
      'outputs/docs/operations_manual.md',
      'outputs/docs/installation_and_runtime.md'],
     '7 bundled docs.'),

    ('3.1', 'Постановка задачи / ТЗ', 'work_content',
     ['outputs/practice_package/01_fact_sheet_for_practice.md',
      'outputs/logs/baseline_registry.md',
      'outputs/docs/functional_specification.md'],
     'Fact sheet + registry + functional spec; cleanly stated.'),
    ('3.2', 'Анализ предметной области', 'work_content',
     ['data/spider/SOURCE_AND_AUDIT.md',
      'outputs/logs/smoke25_subset_audit.md',
      'outputs/logs/multidb_30_audit.md'],
     'Spider provenance + subset audits.'),
    ('3.3', 'Исследование методов NLP', 'work_content',
     ['outputs/logs/b1_schema_linking_audit.md',
      'outputs/logs/b3v1_design_decision.md',
      'outputs/logs/b4_final_design_decision.md',
      'outputs/logs/b4_final_validation_policy.md',
      'outputs/logs/query_analysis_design.md'],
     'Lexical/dual retrieval, planner schema, validation+repair design notes; query analysis.'),
    ('3.4', 'Формализация требований', 'work_content',
     ['repo/docs/plan_schema.json',
      'repo/docs/plan_schema_v1.json',
      'outputs/logs/postprocess_and_handoff_design.md',
      'outputs/logs/baseline_registry.md',
      'outputs/docs/io_contracts.md'],
     'Two plan schemas + handoff contract + baseline registry + IO contracts doc.'),
    ('3.5', 'Архитектура системы', 'work_content',
     ['outputs/docs/architecture_document.md',
      'outputs/plots/system_architecture_overview.png',
      'outputs/plots/ablation_pipeline_ladder.png',
      'outputs/tables/component_registry.csv'],
     'Bundled architecture document + 2 diagrams + component registry CSV.'),
    ('3.6', 'Прототип системы', 'work_content',
     ['repo/src/evaluation/baselines.py',
      'repo/src/evaluation/baselines_b2.py',
      'repo/src/evaluation/baselines_b2_v1.py',
      'repo/src/evaluation/baselines_b3.py',
      'repo/src/evaluation/baselines_b3_v1.py',
      'repo/src/evaluation/baselines_b4.py',
      'repo/src/evaluation/baselines_b4_final.py',
      'repo/src/evaluation/postprocess.py',
      'repo/src/evaluation/query_analysis.py',
      'repo/src/evaluation/retrieval.py'],
     '10 modules: B1, B2, B2_v1, B3, B3_v1, B4-lite, B4_final, postprocess, query_analysis, retrieval.'),
    ('3.7', 'Экспериментальное исследование', 'work_content',
     ['outputs/tables/baseline_progression_smoke10_smoke25.csv',
      'outputs/tables/b0_b1_b2_smoke10_comparison.csv',
      'outputs/tables/error_taxonomy_smoke25.md',
      'outputs/predictions/b2v1_spider_smoke10_predictions.jsonl',
      'outputs/predictions/b3v1_spider_smoke10_predictions.jsonl',
      'outputs/predictions/b4_final_spider_smoke10_predictions.jsonl',
      'outputs/tables/multidb30_ablation.csv',
      'outputs/tables/final_ablation_master.csv'],
     'B0..B4_final smoke10 + B0/B1 smoke25 + multidb_30 5-baseline ablation + master.'),
    ('3.8', 'Техническая документация', 'work_content',
     ['outputs/docs/operations_manual.md',
      'outputs/docs/installation_and_runtime.md',
      'outputs/docs/testing_methodology.md',
      'tools/notebook_tooling_audit.md',
      'tools/tool_manifest.md',
      'tools/tooling_readme.md',
      'outputs/logs/model_block_closure.md'],
     'Bundled docs + tooling docs + model block closure note.'),
]


def derive(evs):
    n = sum(1 for e in evs if has(e))
    if n == 0: return 'not_started'
    if n == len(evs): return 'done'
    return 'partial'


def percent(rs):
    if not rs: return 0.0
    w = {'done':1.0,'partial':0.5,'not_started':0.0,'blocked':0.5}
    return sum(w[r['status']] for r in rs) / len(rs) * 100


results = []
for tid, title, cat, evs, just in items:
    status = derive(evs)
    n_present = sum(1 for e in evs if has(e))
    results.append({'id':tid,'title':title,'category':cat,'status':status,
                    'evidence_paths':evs,'evidence_present':n_present,
                    'evidence_required':len(evs),'justification':just})

funcs = [r for r in results if r['category']=='functional']
works = [r for r in results if r['category']=='work_content']
fpct = percent(funcs); wpct = percent(works); tpct = (fpct+wpct)/2

# tz_coverage_almost_final.md
md = ['# TZ Coverage — Almost Final', '', f'Snapshot at: {ts}', '',
      '## Functional (2.2.*, 2.3)', '',
      '| ID | Title | Status | Evidence found / required | Justification |',
      '|---|---|---|---|---|']
for r in funcs:
    md.append(f"| {r['id']} | {r['title']} | **{r['status']}** | {r['evidence_present']}/{r['evidence_required']} | {r['justification']} |")
md += ['', '## Work content (3.1–3.8)', '',
       '| ID | Title | Status | Evidence found / required | Justification |',
       '|---|---|---|---|---|']
for r in works:
    md.append(f"| {r['id']} | {r['title']} | **{r['status']}** | {r['evidence_present']}/{r['evidence_required']} | {r['justification']} |")
md += ['', '## Coverage', '',
       f'- Functional: **{fpct:.1f}%**',
       f'- Work content: **{wpct:.1f}%**',
       f'- **Total: {tpct:.1f}%**']
(OUTPUTS / 'logs' / 'tz_coverage_almost_final.md').write_text('\n'.join(md) + '\n', encoding='utf-8')

# tz_coverage_final_strict.md (one-line per item)
strict = ['# TZ Coverage — Final (Strict)', '', f'Snapshot at: {ts}', '',
          'STRICT means a pass requires every listed evidence file to physically exist on Drive.',
          '',
          '## Functional', '',
          '| ID | Title | Status | Evidence | Justification (one line) |',
          '|---|---|---|---|---|']
for r in funcs:
    ev = ', '.join(f'`{e}`' for e in r['evidence_paths'])
    strict.append(f"| {r['id']} | {r['title']} | **{r['status']}** | {ev} | {r['justification']} |")
strict += ['', '## Work content', '',
           '| ID | Title | Status | Evidence | Justification (one line) |',
           '|---|---|---|---|---|']
for r in works:
    ev = ', '.join(f'`{e}`' for e in r['evidence_paths'])
    strict.append(f"| {r['id']} | {r['title']} | **{r['status']}** | {ev} | {r['justification']} |")
strict += ['', '## Strict completion percent',
           f'- Functional: **{fpct:.1f}%**',
           f'- Work content: **{wpct:.1f}%**',
           f'- **Total: {tpct:.1f}%**',
           '',
           '## What remains to claim 100%', '']

remaining = [r for r in results if r['status'] != 'done']
if not remaining:
    strict.append('Nothing — all 16 items have full evidence on Drive.')
else:
    for r in remaining:
        missing = [e for e in r['evidence_paths'] if not has(e)]
        strict.append(f"- **{r['id']}** {r['title']} (status={r['status']}): missing {missing}")

(OUTPUTS / 'logs' / 'tz_coverage_final_strict.md').write_text('\n'.join(strict) + '\n', encoding='utf-8')

# ===== final_system_status.md =====
runs_present = []
for label, prefix, model, subset in runs:
    p = OUTPUTS / 'metrics' / f'{prefix}_metrics.csv'
    if p.exists():
        try:
            d = next(csv.DictReader(p.open(encoding='utf-8')))
            runs_present.append((label, model, subset, f(d,'ex'), d.get('executable_count','—'), d.get('n','—')))
        except Exception: pass

status_md = ['# Final System Status', '', f'Generated at: {ts}', '',
             '## Runs that PHYSICALLY exist on Drive', '',
             '| Baseline | Model | Subset | EX | Executable | n |',
             '|---|---|---|---|---|---|']
for label, model, subset, ex, exec_count, n in runs_present:
    ex_s = f'{ex:.4f}' if isinstance(ex, float) else str(ex)
    status_md.append(f'| {label} | {model} | {subset} | {ex_s} | {exec_count}/{n} | {n} |')
status_md += ['', '## Coverage',
              f'- Functional: **{fpct:.1f}%**',
              f'- Work content: **{wpct:.1f}%**',
              f'- **Total: {tpct:.1f}%**',
              '',
              '## 60% threshold',
              f'- Total **{tpct:.1f}%** vs target 60%: {"**PASSED**" if tpct >= 60 else "**NOT PASSED**"}.',
              '']
(OUTPUTS / 'logs' / 'final_system_status.md').write_text('\n'.join(status_md) + '\n', encoding='utf-8')

# ===== final_project_overview.png =====
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# All Qwen-Coder runs grouped by subset
data_smoke10 = []
data_smoke25 = []
data_multidb = []
for label, prefix, model, subset in runs:
    if 'Qwen-Coder' not in model: continue
    d = load_metrics(prefix)
    if d is None: continue
    ex_v = f(d,'ex')
    if ex_v is None: continue
    if subset == 'smoke10': data_smoke10.append((label, ex_v))
    elif subset == 'smoke25': data_smoke25.append((label, ex_v))
    elif subset == 'multidb_30': data_multidb.append((label, ex_v))

fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
for ax, data, title in zip(axes, [data_smoke10, data_smoke25, data_multidb],
                            ['Spider smoke10', 'Spider smoke25', 'Multi-DB 30']):
    if not data:
        ax.text(0.5, 0.5, '(no runs)', ha='center', va='center')
        ax.set_title(title); ax.axis('off'); continue
    L = [a for a,_ in data]; V = [b for _,b in data]
    cmap = ['#4C72B0','#55A868','#C44E52','#8172B2','#CCB974','#64B5CD','#937860','#DA8BC3']
    bars = ax.bar(L, V, color=cmap[:len(L)])
    for bar, v in zip(bars, V):
        ax.text(bar.get_x()+bar.get_width()/2, v+0.02, f'{v:.2f}', ha='center', va='bottom', fontsize=10)
    ax.set_ylim(0, 1.15); ax.set_ylabel('EX'); ax.set_title(title)
    ax.tick_params(axis='x', labelrotation=30)

plt.suptitle('NL2BI System — Baseline EX across subsets (Qwen2.5-Coder-7B-Instruct)', y=1.02, fontsize=14)
plt.tight_layout()
plt.savefig(OUTPUTS / 'plots' / 'final_project_overview.png', dpi=140, bbox_inches='tight')
plt.close(fig)

print(f'Functional %: {fpct:.1f}')
print(f'Work content %: {wpct:.1f}')
print(f'Total %: {tpct:.1f}')
print(f'Runs present: {len(runs_present)}')
print(f'Items still not done: {[r["id"] for r in remaining]}')
print(f'WROTE {master_csv}')
print(f'WROTE {OUTPUTS / "logs" / "tz_coverage_almost_final.md"}')
print(f'WROTE {OUTPUTS / "logs" / "tz_coverage_final_strict.md"}')
print(f'WROTE {OUTPUTS / "logs" / "final_system_status.md"}')
print(f'WROTE {OUTPUTS / "plots" / "final_project_overview.png"}')
print('STATUS=DONE')
