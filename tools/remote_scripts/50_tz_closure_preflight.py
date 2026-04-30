# Stage 0: tz_closure_preflight — re-verify by hand-walking artefacts.

import csv
import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
ts = dt.datetime.now(dt.timezone.utc).isoformat()


def has(rel):
    return (PROJECT_ROOT / rel).exists()


def has_any(*rels):
    return any(has(r) for r in rels)


# Re-derive status from PHYSICAL files only — no carry-forward of prior claims
items = [
    # (id, title, category, status_hint, evidence_paths, gap_to_close)
    ('2.2.1', 'Анализ NL-запросов', 'functional', 'partial',
     ['outputs/tables/b1_schema_linking_examples.md',
      'outputs/tables/b2_v1_plan_examples_smoke10.md',
      'outputs/tables/b3_retrieval_examples.md',
      'repo/src/evaluation/query_analysis.py',
      'outputs/logs/query_analysis_design.md',
      'outputs/tables/query_analysis_examples.md'],
     'Need explicit query analysis layer (intent + signals) — STAGE 1 in this iteration.'),
    ('2.2.2', 'Определение релевантных источников/таблиц/атрибутов', 'functional', 'done',
     ['repo/src/evaluation/baselines.py',
      'outputs/tables/b1_schema_linking_examples.md',
      'outputs/tables/b1_schema_linking_smoke25_examples.md',
      'outputs/logs/b3_retrieval_audit.md'],
     'Already done.'),
    ('2.2.3', 'Генерация формализованных запросов с safety/performance', 'functional', 'done',
     ['outputs/predictions/b0_spider_smoke10_predictions.jsonl',
      'outputs/predictions/b1_spider_smoke10_predictions.jsonl',
      'outputs/predictions/b3_spider_smoke10_predictions.jsonl',
      'outputs/predictions/b4_spider_smoke10_predictions.jsonl',
      'repo/src/evaluation/baselines_b4.py',
      'outputs/logs/b4_validation_policy.md'],
     'Already done.'),
    ('2.2.4', 'Валидация и repair', 'functional', 'done',
     ['repo/docs/plan_schema.json',
      'repo/docs/plan_schema_v1.json',
      'outputs/tables/b4_candidate_selection_examples.md',
      'outputs/logs/b4_validation_policy.md'],
     'Already done.'),
    ('2.2.5', 'Предварительная обработка и агрегация результатов', 'functional', 'done',
     ['repo/src/evaluation/postprocess.py',
      'outputs/logs/postprocess_and_handoff_design.md',
      'outputs/tables/analytics_handoff_examples.md',
      'outputs/analytics_handoff'],
     'Already done.'),
    ('2.2.6', 'Передача результатов в подсистему аналитического представления', 'functional', 'done',
     ['repo/src/evaluation/postprocess.py',
      'outputs/analytics_handoff',
      'outputs/logs/postprocess_and_handoff_design.md'],
     'Already done.'),
    ('2.3', 'Документация (архитектура, форматы, тестирование, эксплуатация)', 'functional', 'partial',
     ['outputs/docs/architecture_document.md',
      'outputs/docs/functional_specification.md',
      'outputs/docs/io_contracts.md',
      'outputs/docs/use_cases_and_scenarios.md',
      'outputs/docs/testing_methodology.md',
      'outputs/docs/operations_manual.md',
      'outputs/docs/installation_and_runtime.md'],
     'Need bundled docs/ package — STAGE 2 in this iteration.'),

    ('3.1', 'Постановка задачи / ТЗ', 'work_content', 'done',
     ['outputs/practice_package/01_fact_sheet_for_practice.md',
      'outputs/practice_package/02_individual_task_content.md',
      'outputs/logs/baseline_registry.md'],
     'Already done.'),
    ('3.2', 'Анализ предметной области', 'work_content', 'done',
     ['data/spider/SOURCE_AND_AUDIT.md',
      'outputs/logs/smoke25_subset_audit.md',
      'outputs/logs/multidb_30_audit.md'],
     'Already done.'),
    ('3.3', 'Исследование методов NLP', 'work_content', 'done',
     ['outputs/logs/b1_schema_linking_audit.md',
      'outputs/logs/b3_design_decision.md',
      'outputs/logs/b4_design_decision.md',
      'outputs/logs/b4_validation_policy.md',
      'outputs/logs/query_analysis_design.md'],
     'Already done; query_analysis_design.md will reinforce it.'),
    ('3.4', 'Формализация требований', 'work_content', 'done',
     ['repo/docs/plan_schema.json',
      'repo/docs/plan_schema_v1.json',
      'outputs/logs/postprocess_and_handoff_design.md',
      'outputs/logs/baseline_registry.md',
      'outputs/docs/io_contracts.md'],
     'Already done.'),
    ('3.5', 'Архитектура системы', 'work_content', 'partial',
     ['outputs/docs/architecture_document.md',
      'outputs/plots/system_architecture_overview.png',
      'outputs/plots/ablation_pipeline_ladder.png',
      'outputs/tables/component_registry.csv'],
     'Need bundled architecture artefacts — STAGE 3.'),
    ('3.6', 'Прототип системы', 'work_content', 'done',
     ['repo/src/evaluation/baselines.py',
      'repo/src/evaluation/baselines_b2.py',
      'repo/src/evaluation/baselines_b2_v1.py',
      'repo/src/evaluation/baselines_b3.py',
      'repo/src/evaluation/baselines_b4.py',
      'repo/src/evaluation/postprocess.py',
      'repo/src/evaluation/query_analysis.py'],
     'Already done; query_analysis adds extra component.'),
    ('3.7', 'Экспериментальное исследование', 'work_content', 'partial',
     ['outputs/tables/baseline_progression_smoke10_smoke25.csv',
      'outputs/tables/b0_b1_b2_smoke10_comparison.csv',
      'outputs/tables/final_ablation_summary.csv',
      'outputs/tables/error_taxonomy_smoke25.md',
      'outputs/predictions/b2_v1_spider_smoke10_predictions.jsonl',
      'outputs/predictions/b3v1_spider_smoke10_predictions.jsonl',
      'outputs/predictions/b4_final_spider_smoke10_predictions.jsonl',
      'outputs/tables/multidb30_ablation.csv'],
     'Need B2_v1 rerun + B3_v1 + B4_final + multidb_30 ablation — STAGES 4/5/6/8.'),
    ('3.8', 'Техническая документация', 'work_content', 'partial',
     ['outputs/docs/operations_manual.md',
      'outputs/docs/installation_and_runtime.md',
      'outputs/docs/testing_methodology.md',
      'tools/notebook_tooling_audit.md',
      'tools/tool_manifest.md'],
     'Need bundled docs — STAGE 2.'),
]


# Status: re-derive from physical files
def derive_status(evs):
    n = sum(1 for e in evs if has(e))
    if n == 0: return 'not_started'
    if n == len(evs): return 'done'
    return 'partial'


results = []
for tid, title, cat, hint, evs, gap in items:
    cur = derive_status(evs)
    n_present = sum(1 for e in evs if has(e))
    results.append({
        'id': tid, 'title': title, 'category': cat,
        'current_status': cur, 'evidence_present': n_present, 'evidence_required': len(evs),
        'evidence_paths': evs, 'gap_to_close': gap,
    })

# CSV
csv_path = OUTPUTS / 'tables' / 'tz_closure_inventory.csv'
with csv_path.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['id','title','category','current_status','evidence_present','evidence_required','gap_to_close'])
    for r in results:
        w.writerow([r['id'],r['title'],r['category'],r['current_status'],
                    r['evidence_present'],r['evidence_required'],r['gap_to_close']])

# MD
md = ['# TZ Closure Preflight', '',
      f'Audited at: {ts}',
      'Status is **derived from physical files only**, no carry-forward of prior claims.',
      '',
      '## Functional (2.2.*, 2.3)', '',
      '| ID | Title | current_status | evidence_present/required | gap_to_close |',
      '|---|---|---|---|---|']
for r in [x for x in results if x['category']=='functional']:
    md.append(f"| {r['id']} | {r['title']} | **{r['current_status']}** | {r['evidence_present']}/{r['evidence_required']} | {r['gap_to_close']} |")
md += ['', '## Work content (3.1–3.8)', '',
       '| ID | Title | current_status | evidence_present/required | gap_to_close |',
       '|---|---|---|---|---|']
for r in [x for x in results if x['category']=='work_content']:
    md.append(f"| {r['id']} | {r['title']} | **{r['current_status']}** | {r['evidence_present']}/{r['evidence_required']} | {r['gap_to_close']} |")

still_partial = [r for r in results if r['current_status'] != 'done']
md += ['', '## Still partial (gaps to close in this iteration)', '']
for r in still_partial:
    md.append(f"- **{r['id']}** {r['title']} → {r['gap_to_close']}")

(OUTPUTS / 'logs' / 'tz_closure_preflight.md').write_text('\n'.join(md) + '\n', encoding='utf-8')

print(f'WROTE {csv_path}')
print(f'WROTE {OUTPUTS / "logs" / "tz_closure_preflight.md"}')
print(f'still partial: {[r["id"] for r in still_partial]}')
print('STATUS=DONE')
