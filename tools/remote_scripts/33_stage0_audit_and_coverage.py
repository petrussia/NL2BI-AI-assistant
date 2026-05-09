# Stage 0 + 1: hard audit + tz_coverage_initial + model_matrix_plan.

import csv
import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
ts = dt.datetime.now(dt.timezone.utc).isoformat()


def list_dir(rel):
    p = PROJECT_ROOT / rel
    if not p.exists():
        return []
    return sorted([x.name for x in p.iterdir() if x.is_file()])


# ============= Audit =============
audit_lines = [
    '# Current Experiment Audit',
    '',
    f'Audited at: {ts}',
    'Source: hard read of `/content/drive/MyDrive/diploma_plan_sql/` after Drive restore from local mirror + Spider re-download.',
    '',
    '## Predictions present',
    '',
    '| File | Size B | Notes |',
    '|---|---|---|',
]
preds = sorted((OUTPUTS / 'predictions').iterdir()) if (OUTPUTS / 'predictions').exists() else []
for p in preds:
    n_rows = sum(1 for _ in open(p, encoding='utf-8'))
    audit_lines.append(f'| `outputs/predictions/{p.name}` | {p.stat().st_size} | n={n_rows} |')

audit_lines += ['', '## Metrics present', '',
                '| File | Size B | Run id | EX | n |',
                '|---|---|---|---|---|']
metrics = sorted((OUTPUTS / 'metrics').iterdir()) if (OUTPUTS / 'metrics').exists() else []
for p in metrics:
    try:
        row = next(csv.DictReader(p.open(encoding='utf-8')))
        audit_lines.append(f'| `outputs/metrics/{p.name}` | {p.stat().st_size} | `{row.get("run_id","")}` | {row.get("ex","")} | {row.get("n","")} |')
    except Exception as exc:
        audit_lines.append(f'| `outputs/metrics/{p.name}` | {p.stat().st_size} | parse_error: {exc!r} | | |')

audit_lines += ['', '## Plots present', '']
for n in list_dir('outputs/plots'): audit_lines.append(f'- `outputs/plots/{n}`')

audit_lines += ['', '## Repo modules', '']
for n in sorted((PROJECT_ROOT / 'repo' / 'src' / 'evaluation').iterdir()) if (PROJECT_ROOT / 'repo' / 'src' / 'evaluation').exists() else []:
    audit_lines.append(f'- `repo/src/evaluation/{n.name}` ({n.stat().st_size} B)')
for n in sorted((PROJECT_ROOT / 'repo' / 'docs').iterdir()) if (PROJECT_ROOT / 'repo' / 'docs').exists() else []:
    audit_lines.append(f'- `repo/docs/{n.name}` ({n.stat().st_size} B)')

audit_lines += ['', '## Tooling files (on Drive — not local)', '',
                f'- bridge URL marker: `{(PROJECT_ROOT / ".bridge_url").exists()}`',
                f'- Drive root files in this folder: {sorted(p.name for p in PROJECT_ROOT.iterdir() if p.is_file())}']

audit_lines += ['', '## Spider data', '',
                f'- `data/spider/dev.json`: {(PROJECT_ROOT / "data/spider/dev.json").exists()}, '
                f'size={(PROJECT_ROOT / "data/spider/dev.json").stat().st_size if (PROJECT_ROOT / "data/spider/dev.json").exists() else 0} B',
                f'- `data/spider/tables.json`: {(PROJECT_ROOT / "data/spider/tables.json").exists()}',
                f'- `data/spider/database/`: {sum(1 for _ in (PROJECT_ROOT / "data/spider/database").rglob("*.sqlite"))} sqlite files',
                f'- `data/spider/subsets/`: {sorted(p.name for p in (PROJECT_ROOT / "data/spider/subsets").iterdir())}',
                ]

audit_lines += ['', '## What model runs ACTUALLY happened (per artefacts)', '',
                'Strict: a baseline×subset is "real" iff its predictions JSONL has the expected number of rows AND its metrics CSV has a non-empty EX field.',
                '']
expected = [
    ('B0','smoke10',10), ('B1','smoke10',10), ('B2','smoke10',10),
    ('B0','smoke25',25), ('B1','smoke25',25),
    ('B2_v1','smoke10',10),
]
for label, subset, n in expected:
    if label == 'B2_v1':
        pred_p = OUTPUTS / 'predictions' / f'b2_v1_spider_{subset}_predictions.jsonl'
        m_p = OUTPUTS / 'metrics' / f'b2_v1_spider_{subset}_metrics.csv'
    elif label == 'B2':
        pred_p = OUTPUTS / 'predictions' / f'b2_spider_{subset}_predictions.jsonl'
        m_p = OUTPUTS / 'metrics' / f'b2_spider_{subset}_metrics.csv'
    else:
        pred_p = OUTPUTS / 'predictions' / f'{label.lower()}_spider_{subset}_predictions.jsonl'
        m_p = OUTPUTS / 'metrics' / f'{label.lower()}_spider_{subset}_metrics.csv'
    pred_n = sum(1 for _ in open(pred_p, encoding='utf-8')) if pred_p.exists() else 0
    ex_val = ''
    if m_p.exists():
        try:
            ex_val = next(csv.DictReader(m_p.open(encoding='utf-8'))).get('ex','')
        except Exception: pass
    real = pred_n == n and ex_val != ''
    audit_lines.append(f"- {label} on {subset}: pred_rows={pred_n}/{n}, EX={ex_val}, REAL={real}")

audit_lines += ['', '## Note on B2_v1 smoke25', '',
                'The B2_v1 smoke25 BG inference was at 24/25 when the cloudflared tunnel died (Cloudflare quick-tunnels have no SLA). The Colab kernel may have continued and finished item 25, OR the kernel itself was restarted (current bridge pid=3928 differs from the previous pid=2218).',
                'After Drive restore from local mirror, we have B2_v1 smoke10 artefacts but NOT smoke25. If B2_v1 smoke25 is needed for the final report, it must be re-run.',
                ]

(OUTPUTS / 'logs' / 'current_experiment_audit.md').write_text('\n'.join(audit_lines) + '\n', encoding='utf-8')

# ============= Inventory CSV =============
inv_path = OUTPUTS / 'tables' / 'current_experiment_inventory.csv'
with inv_path.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['category','file','exists','size_bytes'])
    for sub in ['predictions','metrics','tables','logs','plots']:
        d = OUTPUTS / sub
        if d.exists():
            for p in sorted(d.iterdir()):
                if p.is_file():
                    w.writerow([sub, f'outputs/{sub}/{p.name}', True, p.stat().st_size])
    for ev_dir in [PROJECT_ROOT / 'repo' / 'src' / 'evaluation', PROJECT_ROOT / 'repo' / 'docs', PROJECT_ROOT / 'practice']:
        if ev_dir.exists():
            for p in sorted(ev_dir.iterdir()):
                if p.is_file():
                    rel = str(p.relative_to(PROJECT_ROOT)).replace('\\\\','/')
                    w.writerow([ev_dir.name, rel, True, p.stat().st_size])

# ============= TZ coverage initial =============
# Reading the proposal/TZ items into a structured assessment.
tz_items = [
    # (id, title, category, status, evidence_paths, comment)
    ('2.2.1', 'Анализ NL-запросов', 'functional', 'partial',
     ['outputs/tables/b2_plan_examples_smoke10.md','outputs/tables/b1_schema_linking_examples.md'],
     'Лексический анализ + token tokenisation сделан в B1 schema linker. Полноценный intent classifier отсутствует, но B2 planner де-факто эмитит intent enum.'),
    ('2.2.2', 'Определение релевантных источников/таблиц/атрибутов', 'functional', 'done',
     ['repo/src/evaluation/baselines.py','outputs/tables/b1_schema_linking_examples.md','outputs/tables/b1_schema_linking_smoke25_examples.md'],
     'Lexical schema linking реализован, прогнан на smoke10/25, артефакты сохранены.'),
    ('2.2.3', 'Генерация формализованных запросов с учётом safety/performance', 'functional', 'partial',
     ['outputs/predictions/b0_spider_smoke10_predictions.jsonl','outputs/predictions/b1_spider_smoke10_predictions.jsonl','outputs/predictions/b2_spider_smoke10_predictions.jsonl'],
     'Генерация работает (B0/B1/B2). Safety guard (SELECT-only / DDL block) и performance constraints — этап 4 (B4-lite) в работе.'),
    ('2.2.4', 'Валидация и repair', 'functional', 'partial',
     ['outputs/logs/b2_design_decision.md'],
     'Валидация JSON Plan против schema есть (jsonschema). SQL execution gate есть (через func_timeout SQLite). Repair loop ещё нет (запланирован в B4).'),
    ('2.2.5', 'Предварительная обработка и агрегация результатов', 'functional', 'not_started',
     [],
     'Postprocess module и handoff contract — этап 6.'),
    ('2.2.6', 'Передача результатов в подсистему аналитического представления', 'functional', 'not_started',
     [],
     'Handoff формат / analytics package — этап 6.'),
    ('2.3', 'Документация (архитектура, сценарии, форматы, методика тестирования, эксплуатация)', 'functional', 'partial',
     ['outputs/practice_package/04_practice_report_outline.md','outputs/logs/b2_design_decision.md','outputs/logs/b2_implementation_plan.md'],
     'Practice package + design decisions есть. Архитектурный документ как отдельный artefact ещё нет.'),

    ('3.1', 'Постановка задачи / ТЗ', 'work_content', 'done',
     ['outputs/practice_package/01_fact_sheet_for_practice.md','outputs/practice_package/02_individual_task_content.md'],
     'Сформулировано в practice_package и совпадает с proposal.'),
    ('3.2', 'Анализ предметной области', 'work_content', 'partial',
     ['data/spider/SOURCE_AND_AUDIT.md'],
     'Spider как domain (provenance + audit). Полноценный analysis chapter ещё не написан, но фактически сделан (выбран dataset, описан масштаб).'),
    ('3.3', 'Исследование методов NLP', 'work_content', 'partial',
     ['outputs/logs/b1_schema_linking_audit.md','outputs/logs/b2_design_decision.md'],
     'Lexical schema linking рассмотрен, retrieval будет добавлен (B3). Embedding методы пока не использованы (явно вне scope этой итерации).'),
    ('3.4', 'Формализация требований', 'work_content', 'done',
     ['repo/docs/plan_schema.json','outputs/logs/b2_design_decision.md','outputs/logs/baseline_registry.md'],
     'plan_schema.json — формальный контракт промежуточного представления. baseline_registry — формальный реестр выполненных рунов.'),
    ('3.5', 'Архитектура системы', 'work_content', 'partial',
     ['outputs/logs/b2_design_decision.md','outputs/logs/b2_implementation_plan.md','tools/notebook_tooling_audit.md'],
     'Архитектура B0/B1/B2 описана. B3/B4 архитектурные доки на этой итерации.'),
    ('3.6', 'Прототип системы', 'work_content', 'partial',
     ['repo/src/evaluation/baselines.py','repo/src/evaluation/baselines_b2.py','repo/src/evaluation/baselines_b2_v1.py'],
     'Прототип B0/B1/B2/B2_v1 работает и прогнан. B3/B4 в этой итерации.'),
    ('3.7', 'Экспериментальное исследование', 'work_content', 'partial',
     ['outputs/tables/baseline_progression_smoke10_smoke25.csv','outputs/tables/b0_b1_b2_smoke10_comparison.csv','outputs/tables/b2_v0_vs_b2_v1_smoke10_comparison.csv','outputs/tables/error_taxonomy_smoke25.md'],
     'Сравнение B0/B1/B2 на smoke10/25 + B2_v1 vs B2 + error taxonomy. Multi-DB и model-matrix эксперименты — частично/в работе.'),
    ('3.8', 'Техническая документация', 'work_content', 'partial',
     ['tools/notebook_tooling_audit.md','tools/tool_manifest.md','tools/tooling_readme.md','tools/run_cell_changelog.md','tools/bridge_status.md'],
     'Tooling docs полные. System-level operation manual ещё нет.'),
]

# Counts
funcs = [t for t in tz_items if t[2] == 'functional']
works = [t for t in tz_items if t[2] == 'work_content']
def percent(items):
    if not items: return 0.0
    weights = {'done':1.0, 'partial':0.5, 'not_started':0.0}
    return sum(weights[t[3]] for t in items) / len(items) * 100

func_pct = percent(funcs)
work_pct = percent(works)
total_pct = (func_pct + work_pct) / 2

cov_lines = [
    '# TZ Coverage — Initial Snapshot',
    '',
    f'Snapshot at: {ts}',
    '',
    '## Functional requirements (ТЗ 2.2.*, 2.3)',
    '',
    '| ID | Title | Status | Evidence | Comment |',
    '|---|---|---|---|---|',
]
for t in funcs:
    ev = '<br>'.join(f'`{e}`' for e in t[4]) or '—'
    cov_lines.append(f'| {t[0]} | {t[1]} | **{t[3]}** | {ev} | {t[5]} |')

cov_lines += ['', '## Work content (ВКР 3.1–3.8)', '',
              '| ID | Title | Status | Evidence | Comment |',
              '|---|---|---|---|---|']
for t in works:
    ev = '<br>'.join(f'`{e}`' for e in t[4]) or '—'
    cov_lines.append(f'| {t[0]} | {t[1]} | **{t[3]}** | {ev} | {t[5]} |')

cov_lines += ['', '## Honest coverage percent', '',
              f'- Functional requirements: **{func_pct:.1f}%** ({sum(1 for t in funcs if t[3]=="done")} done, {sum(1 for t in funcs if t[3]=="partial")} partial, {sum(1 for t in funcs if t[3]=="not_started")} not_started)',
              f'- Work content (3.1–3.8): **{work_pct:.1f}%** ({sum(1 for t in works if t[3]=="done")} done, {sum(1 for t in works if t[3]=="partial")} partial, {sum(1 for t in works if t[3]=="not_started")} not_started)',
              f'- **Total practical completion: {total_pct:.1f}%**',
              '',
              '## Notes on counting',
              '- "done" = full артефакт уже есть и прогнан.',
              '- "partial" = ключевые компоненты реализованы, отдельные части ещё в плане. Считается как 0.5.',
              '- "not_started" = ничего по этому пункту не сделано.',
              '- Считается строго по фактическим артефактам, без декларативного засчитывания.',
              ]
(OUTPUTS / 'logs' / 'tz_coverage_initial.md').write_text('\n'.join(cov_lines) + '\n', encoding='utf-8')

# ============= Model matrix plan =============
mm_lines = [
    '# Model Matrix Plan',
    '',
    f'Authored at: {ts}',
    '',
    '## Mandatory models (per proposal/презентация)',
    '',
    '| Model | Params | Quantization | Disk size | VRAM (4-bit) | Status | Target baselines |',
    '|---|---|---|---|---|---|---|',
    '| Qwen/Qwen2.5-Coder-7B-Instruct | 7B | nf4 bitsandbytes 4-bit | ~14 GB hf cache | ~5.3 GB | **loaded, prior runs done** | B0/B1/B2/B2_v1/B3/B4 on smoke10; B0/B1 done on smoke25 |',
    '| meta-llama/Llama-3.1-8B-Instruct | 8B | nf4 bitsandbytes 4-bit | ~16 GB | ~6 GB | not loaded yet, gated repo (HF token required) | minimum B0+B1 on smoke10 |',
    '| deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct | 16B (MoE 2.4B active) | nf4 bitsandbytes 4-bit | ~32 GB | ~12-14 GB | not loaded yet | minimum B0 on smoke10 |',
    '',
    '## Optional models',
    '',
    '| Model | Params | Notes |',
    '|---|---|---|',
    '| Qwen/Qwen3-8B | 8B | updated comparator; B0/B1 smoke10 if time |',
    '| deepseek-ai/DeepSeek-R1-Distill-Qwen-7B | 7B | planner-only comparator inside B2/B3 on smoke10 if time |',
    '',
    '## Capability assessment on current runtime (NVIDIA L4, 23 GB VRAM)',
    '',
    '- L4 has 23 GB VRAM, 16 GB system RAM (Colab default).',
    '- Single Qwen 7B 4-bit takes ~5.3 GB. Llama 8B 4-bit would take ~6 GB. Sequential load (free Qwen → load Llama) is required (cannot host both simultaneously without OOM risk on 16 GB system RAM).',
    '- DeepSeek-Coder-V2-Lite is 16B MoE; 4-bit quant ~12-14 GB. Fits but tight; would need to free other models first.',
    '- Llama 3.1 8B is gated on HF — needs `HF_TOKEN` env or `huggingface_hub.login()`. If token not available in Colab kernel, loading will fail — fallback: try `meta-llama/Meta-Llama-3-8B-Instruct` (3.0 family, less gated path) or `mistralai/Mistral-7B-Instruct-v0.3` as comparator.',
    '',
    '## Realistic execution plan for THIS iteration',
    '',
    '1. **Qwen2.5-Coder-7B** (already loaded): run B3 + B4 on smoke10 (mandatory). Skip B3/B4 smoke25 — too long (~3 hours combined).',
    '2. **Llama-3.1-8B** (or fallback): try to load; if HF token works, run B0 on smoke10 for cross-model sanity. If load fails, document and skip.',
    '3. **DeepSeek-Coder-V2-Lite**: defer. ~12 GB VRAM + needs separate load cycle. Mark as "next iteration" with honest note.',
    '4. **Optional Qwen3-8B / DeepSeek-R1-Distill**: defer to next iteration.',
    '',
    '## Justification for deferring some models',
    '',
    '- Total wall-clock budget for this iteration is bounded; Cloudflare quick-tunnels also recycle.',
    '- DeepSeek-Coder-V2-Lite would consume ~30 min just for download and load on first use.',
    '- Honest decision: prioritize *system completeness* (B3, B4, postprocess) over *model breadth* on this iteration.',
    '- Cross-model evidence on smoke10 with at least one second model (Llama or Mistral) is sufficient for a "comparator exists" claim in the thesis.',
    '',
    '## Priority order',
    '',
    '1. Qwen2.5-Coder-7B B3 smoke10',
    '2. Qwen2.5-Coder-7B B4 smoke10',
    '3. Llama-3.1-8B (or fallback) B0 smoke10',
    '4. (defer) DeepSeek-Coder-V2-Lite',
    '5. (defer) Optional models',
]
(OUTPUTS / 'logs' / 'model_matrix_plan.md').write_text('\n'.join(mm_lines) + '\n', encoding='utf-8')

print(f'Functional coverage: {func_pct:.1f}%')
print(f'Work content coverage: {work_pct:.1f}%')
print(f'Total: {total_pct:.1f}%')
print(f'WROTE {OUTPUTS / "logs" / "current_experiment_audit.md"}')
print(f'WROTE {inv_path}')
print(f'WROTE {OUTPUTS / "logs" / "tz_coverage_initial.md"}')
print(f'WROTE {OUTPUTS / "logs" / "model_matrix_plan.md"}')
print('STATUS=DONE')
