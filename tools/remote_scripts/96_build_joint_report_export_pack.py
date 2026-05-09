# Build outputs/report_export_pack/ — single download-ready pack for joint VKR.
# 9 subfolders + master files + ready-to-paste docx blocks + patch map + tarball.

import csv
import datetime as dt
import json
import shutil
import tarfile
import textwrap
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
PACK = OUTPUTS / 'report_export_pack'
NOW = dt.datetime.now(dt.timezone.utc).isoformat()

# Recreate cleanly
if PACK.exists():
    shutil.rmtree(PACK)
PACK.mkdir(parents=True)

SUBDIRS = ['01_master','02_numbers','03_tables','04_figures','05_text_blocks',
           '06_experiment_evidence','07_design_and_arch','08_appendices','09_download_manifest']
for s in SUBDIRS:
    (PACK/s).mkdir()


def cp(src_rel: str, dest_subdir: str, new_name: str | None = None):
    src = OUTPUTS / src_rel if not src_rel.startswith('outputs/') else PROJECT_ROOT / src_rel
    if not src.exists():
        return False, f'MISSING: {src_rel}'
    dest = PACK / dest_subdir / (new_name or src.name)
    shutil.copy2(src, dest)
    return True, dest.relative_to(PACK).as_posix()


def load_metric(prefix):
    p = OUTPUTS/'metrics'/f'{prefix}_metrics.csv'
    if not p.exists(): return None
    return next(csv.DictReader(p.open(encoding='utf-8')), None)

def fex(prefix):
    m = load_metric(prefix)
    if not m: return '—'
    try: return f'{float(m["ex"]):.4f}'
    except: return '—'

def fex_full(prefix):
    m = load_metric(prefix)
    if not m: return '—'
    try: return f'{float(m["ex"]):.4f} ({m["execution_match_count"]}/{m["n"]})'
    except: return '—'


# ======================================================================
# ETAP 1: AUDIT — what we have / what we'll include
# ======================================================================
metrics_files = sorted((OUTPUTS/'metrics').glob('*_metrics.csv'))
predictions_files = sorted((OUTPUTS/'predictions').glob('*.jsonl'))
plot_files = sorted((OUTPUTS/'plots').glob('*.png'))
docs_files = sorted((OUTPUTS/'docs').glob('*.md'))
thesis_files = sorted((OUTPUTS/'thesis_pack_shubin').glob('*.md'))

audit_md = OUTPUTS/'logs'/'report_export_audit.md'
audit_md.write_text(f'''# Report export audit

**Generated:** {NOW}
**Source root:** `{OUTPUTS}`

## Inventory snapshot
- metrics CSVs: {len(metrics_files)}
- predictions JSONL: {len(predictions_files)}
- plots PNG: {len(plot_files)}
- bundled docs: {len(docs_files)}
- thesis_pack_shubin files: {len(thesis_files)}

## What goes into the export pack
- Headline numbers from `final_experiment_master_matrix.csv` (authoritative)
- 5 master narrative files in `01_master/`
- 2 condensed numbers files in `02_numbers/`
- ~10 most insertable tables in `03_tables/`
- ~6 plots that actually belong in the joint VKR (not all 17+)
- 9 ready-to-paste Russian text blocks in `05_text_blocks/`
- Shortlist of evidence files (predictions/metrics) — not all 88
- Architecture + operations + IO contracts in `07_design_and_arch/`

## What is intentionally NOT in the export pack
- 88 raw metric CSVs (only headline aggregations bubble up)
- Spider2-Lite raw `resource/` (already excluded from main mirror)
- BIRD raw .sqlite + .zip (~1 GB, already on Drive only)
- Historic v0/v1/legacy run files (only canonical strongest versions are bubbled up)
- All blocker noise — only the canonical DeepSeek blocker artifact
''', encoding='utf-8')

with (OUTPUTS/'tables'/'report_export_inventory.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['category','count','source_dir'])
    w.writerow(['metrics_csv', len(metrics_files), 'outputs/metrics/'])
    w.writerow(['predictions_jsonl', len(predictions_files), 'outputs/predictions/'])
    w.writerow(['plots_png', len(plot_files), 'outputs/plots/'])
    w.writerow(['docs_md', len(docs_files), 'outputs/docs/'])
    w.writerow(['thesis_pack_md', len(thesis_files), 'outputs/thesis_pack_shubin/'])


# ======================================================================
# ETAP 3: 01_master/ — 5 main narrative files
# ======================================================================
copied_master = []
for src, dest_name in [
    ('REPORT.md', 'REPORT.md'),
    ('tables/final_experiment_master_matrix.csv', 'final_experiment_master_matrix.csv'),
    ('tables/final_experiment_master_matrix.md', 'final_experiment_master_matrix.md'),
    ('logs/final_scientific_findings.md', 'final_scientific_findings.md'),
    ('logs/final_negative_result_analysis.md', 'final_negative_result_analysis.md'),
    ('logs/final_submission_readiness.md', 'final_submission_readiness.md'),
]:
    ok, info = cp(src, '01_master', dest_name)
    copied_master.append((src, ok, info))

(PACK/'01_master'/'README_FIRST.txt').write_text(textwrap.dedent('''
====================================================
NL2BI-AI-assistant — joint VKR export pack v1
Раздел 3 / 5 / 6 + заключение + личный вклад Шубина
====================================================

ОТКРЫВАЙ В ТАКОМ ПОРЯДКЕ:

1) `01_master/REPORT.md`
   — главный обзорный отчёт с TL;DR, итоговыми числами, выводами.
   Используй как «source of truth» по всему контексту.

2) `02_numbers/final_numbers_for_joint_report.md`
   — ВСЕ ЦИФРЫ для вставки в текст (academic-grade format).
   Любая цифра в общей ВКР должна совпадать с этим файлом.

3) `05_text_blocks/09_docx_patch_map_for_joint_report.md`
   — куда какой блок вставлять в текущий merged draft docx.
   Прочти его перед редактированием docx.

4) `05_text_blocks/01..08_*_ready_blocks.md`
   — 8 готовых текстовых блоков на русском под каждый раздел/подраздел.
   Вставляй почти как есть; меняй только связки.

5) `04_figures/figure_list_for_joint_report.md`
   — список рисунков с captions и местом вставки.
   PNG лежат рядом в той же папке.

ГЛАВНЫЕ ИСТОЧНИКИ:
- цифры:                 `02_numbers/final_numbers_for_joint_report.md`
- рисунки:               `04_figures/figure_list_for_joint_report.md`
- вставки в docx:        `05_text_blocks/09_docx_patch_map_for_joint_report.md`
- заключение:            `05_text_blocks/04_conclusion_shubin_ready_blocks.md`
- личный вклад Дениса:   `05_text_blocks/05_personal_contribution_shubin_ready_block.md`
- ограничения / blockers:`05_text_blocks/06_limitations_and_blockers_ready_block.md`

ВРЕМЯ НА СБОРКУ ОБЩЕЙ ВКР v1:
- ~3-4 часа на вставку, форматирование, проверку
- ~1 час на финальную вычитку

''').strip()+'\n', encoding='utf-8')


# ======================================================================
# ETAP 4: 02_numbers/ — condensed numbers for direct paste
# ======================================================================
# Headline EX table (authoritative)
HEADLINE = []  # (baseline, model, subset, EX, full)
def add(b, m, s, prefix):
    HEADLINE.append((b, m, s, fex(prefix), fex_full(prefix)))

# Internal core
add('B0','Qwen2.5-Coder-7B','smoke_10','b0_spider_smoke10')
add('B1','Qwen2.5-Coder-7B','smoke_10','b1_spider_smoke10')
add('B2_v2','Qwen2.5-Coder-7B','smoke_10','b2v2_spider_smoke10')
add('B3_v2','Qwen2.5-Coder-7B','smoke_10','b3v2_spider_smoke10')
add('B4_v2','Qwen2.5-Coder-7B','smoke_10','b4v2_spider_smoke10')
add('B0','Qwen2.5-Coder-7B','smoke_25','b0_spider_smoke25')
add('B1','Qwen2.5-Coder-7B','smoke_25','b1_spider_smoke25')
add('B2_v2','Qwen2.5-Coder-7B','smoke_25','b2v2_spider_smoke25')
add('B3_v2','Qwen2.5-Coder-7B','smoke_25','b3v2_spider_smoke25')
add('B4_v2','Qwen2.5-Coder-7B','smoke_25','b4v2_spider_smoke25')
add('B0','Qwen2.5-Coder-7B','multidb_30','b0_multidb30_v2')
add('B1','Qwen2.5-Coder-7B','multidb_30','b1_multidb30_v2')
add('B2_v2','Qwen2.5-Coder-7B','multidb_30','b2v2_multidb30')
add('B3_v2','Qwen2.5-Coder-7B','multidb_30','b3v2_multidb30')
add('B4_v2','Qwen2.5-Coder-7B','multidb_30','b4v2_multidb30')

# Llama
add('B0','Llama-3.1-8B','smoke_10','b0_llama_3p1_8b_instruct_smoke10')
add('B1','Llama-3.1-8B','smoke_10','b1_llama_3p1_8b_instruct_smoke10')
add('B2_v2','Llama-3.1-8B','smoke_10','b2v2_llama_3p1_8b_smoke10')
add('B3_v2','Llama-3.1-8B','smoke_10','b3v2_llama_3p1_8b_smoke10')
add('B4_v2','Llama-3.1-8B','smoke_10','b4v2_llama_3p1_8b_smoke10')
add('B0','Llama-3.1-8B','smoke_25','b0_llama_3p1_8b_instruct_smoke25')
add('B1','Llama-3.1-8B','smoke_25','b1_llama_3p1_8b_instruct_smoke25')
add('B2_v2','Llama-3.1-8B','smoke_25','b2v2_llama_3p1_8b_smoke25')
add('B0','Llama-3.1-8B','multidb_30','b0_llama_3p1_8b_instruct_multidb30')
add('B1','Llama-3.1-8B','multidb_30','b1_llama_3p1_8b_instruct_multidb30')
add('B2_v2','Llama-3.1-8B','multidb_30','b2v2_llama_3p1_8b_multidb30')

# Qwen-Coder-14B
add('B0','Qwen2.5-Coder-14B','smoke_10','b0_qwen2p5_coder_14b_instruct_smoke10')
add('B1','Qwen2.5-Coder-14B','smoke_10','b1_qwen2p5_coder_14b_instruct_smoke10')
add('B0','Qwen2.5-Coder-14B','smoke_25','b0_qwen2p5_coder_14b_instruct_smoke25')
add('B1','Qwen2.5-Coder-14B','smoke_25','b1_qwen2p5_coder_14b_instruct_smoke25')
add('B0','Qwen2.5-Coder-14B','multidb_30','b0_qwen2p5_coder_14b_instruct_multidb30')
add('B1','Qwen2.5-Coder-14B','multidb_30','b1_qwen2p5_coder_14b_instruct_multidb30')

# External: BIRD
add('B0','Qwen2.5-Coder-7B','BIRD-mini-dev','b0_qwen2p5_coder_7b_bird_minidev_30')
add('B1','Qwen2.5-Coder-7B','BIRD-mini-dev','b1_qwen2p5_coder_7b_bird_minidev_30')
add('B2_v2','Qwen2.5-Coder-7B','BIRD-mini-dev','b2v2_qwen2p5_coder_7b_bird_minidev_30')
add('B0','Llama-3.1-8B','BIRD-mini-dev','b0_llama_3p1_8b_bird_minidev_30')
add('B1','Llama-3.1-8B','BIRD-mini-dev','b1_llama_3p1_8b_bird_minidev_30')
add('B2_v2','Llama-3.1-8B','BIRD-mini-dev','b2v2_llama_3p1_8b_bird_minidev_30')

# External: Spider 2.0-Lite (structural only — EX = N/A)

with (PACK/'02_numbers'/'final_numbers_for_joint_report.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['baseline','model','benchmark','EX','EX_full','metric_type'])
    for b, m, s, ex, ex_full in HEADLINE:
        mt = 'EX' if 'spider2lite' not in s.lower() else 'structural_only'
        w.writerow([b, m, s, ex, ex_full, mt])

(PACK/'02_numbers'/'final_numbers_for_joint_report.md').write_text(textwrap.dedent(f'''
# Final numbers for joint report (v1)

**Generated:** {NOW}
**Authoritative source:** `outputs/tables/final_experiment_master_matrix.csv`

> Все числа в общей ВКР должны совпадать с этим файлом. Если какое-то число отсюда нельзя вставить как есть — обнови в master matrix или скажи, и пересобери pack.

## 1. Internal core benchmarks (Spider, EX = Execution Match)

| Baseline | Model | smoke_10 | smoke_25 | multidb_30 |
|---|---|---|---|---|
| **B0** | Qwen2.5-Coder-7B | **{fex_full("b0_spider_smoke10")}** | **{fex_full("b0_spider_smoke25")}** | **{fex_full("b0_multidb30_v2")}** |
| B1 | Qwen2.5-Coder-7B | {fex_full("b1_spider_smoke10")} | {fex_full("b1_spider_smoke25")} | {fex_full("b1_multidb30_v2")} |
| B2_v2 | Qwen2.5-Coder-7B | {fex_full("b2v2_spider_smoke10")} | {fex_full("b2v2_spider_smoke25")} | **{fex_full("b2v2_multidb30")}** |
| B3_v2 | Qwen2.5-Coder-7B | {fex_full("b3v2_spider_smoke10")} | {fex_full("b3v2_spider_smoke25")} | {fex_full("b3v2_multidb30")} |
| B4_v2 | Qwen2.5-Coder-7B | {fex_full("b4v2_spider_smoke10")} | {fex_full("b4v2_spider_smoke25")} | {fex_full("b4v2_multidb30")} |

## 2. Mandatory comparator — Llama-3.1-8B-Instruct

| Baseline | smoke_10 | smoke_25 | multidb_30 | BIRD-mini-dev |
|---|---|---|---|---|
| B0 | {fex_full("b0_llama_3p1_8b_instruct_smoke10")} | {fex_full("b0_llama_3p1_8b_instruct_smoke25")} | **{fex_full("b0_llama_3p1_8b_instruct_multidb30")}** | {fex_full("b0_llama_3p1_8b_bird_minidev_30")} |
| B1 | {fex_full("b1_llama_3p1_8b_instruct_smoke10")} | {fex_full("b1_llama_3p1_8b_instruct_smoke25")} | {fex_full("b1_llama_3p1_8b_instruct_multidb30")} | {fex_full("b1_llama_3p1_8b_bird_minidev_30")} |
| B2_v2 | {fex_full("b2v2_llama_3p1_8b_smoke10")} | {fex_full("b2v2_llama_3p1_8b_smoke25")} | {fex_full("b2v2_llama_3p1_8b_multidb30")} | {fex_full("b2v2_llama_3p1_8b_bird_minidev_30")} |
| B3_v2 | {fex_full("b3v2_llama_3p1_8b_smoke10")} | {fex_full("b3v2_llama_3p1_8b_smoke25")} | {fex_full("b3v2_llama_3p1_8b_multidb30")} | — |
| B4_v2 | {fex_full("b4v2_llama_3p1_8b_smoke10")} | {fex_full("b4v2_llama_3p1_8b_smoke25")} | {fex_full("b4v2_llama_3p1_8b_multidb30")} | — |

## 3. Larger model comparator — Qwen2.5-Coder-14B-Instruct

| Baseline | smoke_10 | smoke_25 | multidb_30 |
|---|---|---|---|
| B0 | {fex_full("b0_qwen2p5_coder_14b_instruct_smoke10")} | {fex_full("b0_qwen2p5_coder_14b_instruct_smoke25")} | **{fex_full("b0_qwen2p5_coder_14b_instruct_multidb30")}** ⬅ ниже 7B |
| B1 | {fex_full("b1_qwen2p5_coder_14b_instruct_smoke10")} | {fex_full("b1_qwen2p5_coder_14b_instruct_smoke25")} | {fex_full("b1_qwen2p5_coder_14b_instruct_multidb30")} |

## 4. External validation — BIRD-Mini-Dev (full SQLite EX)

| Baseline | Qwen2.5-Coder-7B | Llama-3.1-8B |
|---|---|---|
| B0 | **{fex_full("b0_qwen2p5_coder_7b_bird_minidev_30")}** | {fex_full("b0_llama_3p1_8b_bird_minidev_30")} |
| B1 | {fex_full("b1_qwen2p5_coder_7b_bird_minidev_30")} | {fex_full("b1_llama_3p1_8b_bird_minidev_30")} |
| B2_v2 | {fex_full("b2v2_qwen2p5_coder_7b_bird_minidev_30")} | {fex_full("b2v2_llama_3p1_8b_bird_minidev_30")} |

## 5. External validation — Spider 2.0-Lite (prediction-only, structural metrics)

EX is N/A on Spider 2.0-Lite — gold queries target BigQuery/Snowflake; no execution from Colab. Structural safety holds:
- Qwen-Coder-7B B0: safe-SELECT 96.7%, has-JOIN 40%
- Qwen-Coder-7B B2_v2: safe-SELECT 96.7%, has-JOIN 53.3%
- Llama-3.1-8B B0: safe-SELECT 100%, has-JOIN 66.7%
- Llama-3.1-8B B2_v2: safe-SELECT 100%, has-JOIN 43.3%

## 6. Strongest configurations (defense-grade)

| Role | Configuration | EX |
|---|---|---|
| **Strongest direct & strongest overall** | B0 + Qwen2.5-Coder-7B-Instruct | **1.00 / 0.96 / 0.9333** (smoke_10 / smoke_25 / multi-DB) |
| **Strongest layered** | B2_v2 + Qwen2.5-Coder-7B-Instruct on multi-DB | **0.80** — beats B1 = 0.7667 by **+0.0333** |
| **Strongest layered (smoke_25 parity)** | B2_v2 / B3_v2 / B4_v2 + Qwen2.5-Coder-7B | **0.96** — match B0/B1 (parity) |
| **Mandatory model B0 best** | Llama-3.1-8B B0 multi-DB | 0.8333 (competitive vs Coder family) |
| **External BIRD strongest** | B0 + Qwen2.5-Coder-7B | 0.2667 (vs Llama 0.1333 = 2× ratio) |

## 7. Production recommendation

**B0 + Qwen2.5-Coder-7B-Instruct (4-bit nf4 or BF16) + SELECT-only AST guard + 8s SQLite timeout + AnalyticsPayload v1 post-processor.**

- Strongest EX on every internal subset
- Strongest EX on the harder external benchmark (BIRD)
- Cheapest GPU footprint (fits L4 24 GB)
- Stronger than Coder-14B on multi-DB (right-sizing argument)
- Single LLM call per query (lowest latency)

**Audit-trail variant:** B2_v2 + Qwen2.5-Coder-7B (when downstream needs JSON plan).

## 8. Honest blockers

| Item | Class | Unblock path |
|---|---|---|
| DeepSeek-Coder-V2-Lite-Instruct | environmental (transformers ABI in trust_remote_code) | Fresh Colab notebook, `transformers==4.39.3` pinned BEFORE other imports — full checklist in `outputs/tables/deepseek_blocker_reproduction_checklist.csv` |
| Spider 2.0-Lite EX evaluation | environmental (BigQuery/Snowflake credentials needed) | Out of project scope; pipeline is structurally sound (96-100% safe-SELECT) |
| Editorial polish + docx insertion | human writing | ~3-5 h Shubin manual work |
''').strip()+'\n', encoding='utf-8')


# ======================================================================
# ETAP 5: 03_tables/ — only tables that go into joint report
# ======================================================================
TABLE_LIST = [
    # (src_in_outputs, dest_name, caption, where, why)
    ('tables/final_experiment_master_matrix.md','master_matrix.md',
     'Сводная таблица всех экспериментальных прогонов',
     'Раздел 6, Приложение A',
     'Источник истины по всем числам; полная master matrix (строка = запуск).'),
    ('tables/multidb30_strongest_configs.md','multidb30_strongest_configs.md',
     'Сильнейшие конфигурации на multi-DB-срезе (главный научный slice)',
     'Раздел 6.3',
     'Главная таблица для научного вывода: B2_v2 беёт B1 на multi-DB.'),
    ('tables/qwen14b_vs_qwen7b_comparison.md','qwen14b_vs_qwen7b_comparison.md',
     'Сравнение Qwen-Coder-7B vs Qwen-Coder-14B',
     'Раздел 6.4',
     'Right-sizing аргумент: бóльшая модель не улучшает EX.'),
    ('tables/external_validation_master_matrix.md','external_validation_matrix.md',
     'Внешняя валидация (BIRD-Mini-Dev, Spider 2.0-Lite)',
     'Раздел 6.5',
     'Подтверждение, что отрицательный результат обобщается за пределы Spider.'),
    ('tables/component_registry.csv','component_registry.csv',
     'Компонентный реестр подсистемы извлечения',
     'Раздел 5.1',
     'Перечень всех модулей с их ролью и закрываемым пунктом ТЗ.'),
    ('tables/full_closure_gap_matrix.md','full_closure_gap_matrix.md',
     'Полная gap-матрица 5×5×5 канонической матрицы',
     'Приложение B',
     'Показывает, какие клетки закрыты / blocked / N/A.'),
    ('tables/b3v2_vs_b3v1.csv','b3v2_vs_b3v1.csv',
     'Дельта v2 vs v1 для B3 (safety net effect)',
     'Раздел 6.6',
     'Доказывает работу safety-net дизайна (+0.50 / +0.27 EX).'),
    ('tables/b4v2_vs_b4final.csv','b4v2_vs_b4final.csv',
     'Дельта v2 vs final для B4 (safety net effect)',
     'Раздел 6.6',
     'Парная таблица для B4 (одна и та же история).'),
]
table_list_md = ['# Tables for joint report\n', f'_Generated: {NOW}_\n']
for src, dest, caption, where, why in TABLE_LIST:
    ok, info = cp(src, '03_tables', dest)
    if ok:
        table_list_md.append(f'### `{dest}`')
        table_list_md.append(f'- **Caption:** {caption}')
        table_list_md.append(f'- **Where to insert:** {where}')
        table_list_md.append(f'- **Why:** {why}')
        table_list_md.append('')
(PACK/'03_tables'/'table_list_for_joint_report.md').write_text('\n'.join(table_list_md), encoding='utf-8')

(PACK/'03_tables'/'table_insertion_order.md').write_text(textwrap.dedent('''
# Table insertion order in joint VKR

| Order | Section | Table file | Note |
|---|---|---|---|
| 1 | Раздел 5.1 | `component_registry.csv` | Сначала покажи, что реализовано (компонентная карта) |
| 2 | Раздел 6.1-6.2 | (внутри 02_numbers/final_numbers...md, table 1) | Internal core benchmarks |
| 3 | Раздел 6.3 | `multidb30_strongest_configs.md` | Главный научный slice |
| 4 | Раздел 6.4 | `qwen14b_vs_qwen7b_comparison.md` | Right-sizing |
| 5 | Раздел 6.5 | `external_validation_matrix.md` | Внешняя валидация |
| 6 | Раздел 6.6 | `b3v2_vs_b3v1.csv` + `b4v2_vs_b4final.csv` | Эффект v2-фикса |
| 7 | Приложение A | `master_matrix.md` | Полный сводный реестр |
| 8 | Приложение B | `full_closure_gap_matrix.md` | Gap audit для воспроизводимости |
''').strip()+'\n', encoding='utf-8')


# ======================================================================
# ETAP 6: 04_figures/ — only figures that belong in joint report
# ======================================================================
FIGURE_LIST = [
    ('plots/final_experiment_master_overview.png','master_overview.png',
     'Сводная диаграмма EX по всем baseline × subset для основной модели Qwen2.5-Coder-7B',
     'Раздел 6.1', 'Главная иллюстрация результатов.', 'KEEP'),
    ('plots/multidb30_strongest_configs.png','multidb30_strongest_configs.png',
     'EX сильнейших конфигураций на multi-DB-срезе',
     'Раздел 6.3', 'Сопровождает главный научный вывод (B2_v2 > B1).', 'KEEP'),
    ('plots/model_comparison_smoke25.png','model_comparison_smoke25.png',
     'Сравнение моделей на smoke_25 (B0 vs B1)',
     'Раздел 6.4', 'Cross-model picture на стабильном subset.', 'KEEP'),
    ('plots/model_comparison_multidb30.png','model_comparison_multidb30.png',
     'Сравнение моделей на multi-DB-срезе (B0 vs B1)',
     'Раздел 6.4', 'Right-sizing аргумент в визуальной форме.', 'KEEP'),
    ('plots/external_validation_overview.png','external_validation_overview.png',
     'Внешняя валидация: BIRD-Mini-Dev EX и Spider 2.0-Lite структурные метрики',
     'Раздел 6.5', 'Доказательство, что негативный результат обобщается.', 'KEEP'),
    ('plots/strongest_baselines_overview.png','strongest_baselines_overview.png',
     'Strongest configurations per branch на multi-DB',
     'Раздел 6.7 / Заключение', 'Финальная сводка для defense narrative.', 'KEEP'),
    ('plots/system_architecture_overview.png','system_architecture_overview.png',
     'Архитектурная диаграмма подсистемы извлечения',
     'Раздел 5.2', 'Архитектурная карта Шубина (Intent → Plan → SQL → ResultPackage).', 'KEEP'),
    ('plots/ablation_pipeline_ladder.png','ablation_pipeline_ladder.png',
     'Лестница baseline B0 → B4 с указанием добавляемого компонента',
     'Раздел 5.2', 'Сопровождает архитектурную диаграмму.', 'KEEP'),
]
fig_md = ['# Figures for joint report\n', f'_Generated: {NOW}_\n']
fig_caps_md = ['# Ready captions for joint report\n', f'_Generated: {NOW}_\n']
for src, dest, caption, where, why, action in FIGURE_LIST:
    ok, info = cp(src, '04_figures', dest)
    if ok:
        fig_md.append(f'### `{dest}` ({action})')
        fig_md.append(f'- **Caption:** {caption}')
        fig_md.append(f'- **Where:** {where}')
        fig_md.append(f'- **Why:** {why}')
        fig_md.append('')
        fig_caps_md.append(f'**{dest}** — {caption}.')
        fig_caps_md.append('')
(PACK/'04_figures'/'figure_list_for_joint_report.md').write_text('\n'.join(fig_md), encoding='utf-8')
(PACK/'04_figures'/'figure_captions_ready.md').write_text('\n'.join(fig_caps_md), encoding='utf-8')


# ======================================================================
# ETAP 7: 05_text_blocks/ — RU ready-to-paste blocks (THE CRITICAL PART)
# ======================================================================
def w(name, text):
    (PACK/'05_text_blocks'/name).write_text(text, encoding='utf-8')

w('01_section3_shubin_ready_blocks.md', textwrap.dedent('''
# Раздел 3 — Подсистема интерпретации запросов и извлечения данных (Шубин)

## 3.1. Архитектура подсистемы

Подсистема извлечения данных по технологии NL→SQL построена как пятиуровневая лестница базовых конвейеров (B0..B4) с явным промежуточным представлением. Логика обработки запроса:

> **NL question → Query Analysis (intent + signals) → Schema Linking → Planner v2 (JSON Plan, jsonschema-валидация, B1-fallback при ошибке плана) → SQL Synthesizer → Validation Gate (SELECT-only AST guard) → Multi-Candidate + Bounded Repair (только B4) → SQLite Executor (8 с `func_timeout`) → Postprocess (нормализация строк, сводка) → AnalyticsPayload v1 → подсистема аналитического представления (Петухов).**

На уровне абстракции каждый запрос проходит четыре строгих ступени:

1. **Intent** — лёгкий rule-based анализатор `query_analysis.py` определяет намерение пользователя (8-значный enum: `select_count`, `select_aggregate`, `select_filter`, `select_join`, `select_groupby`, `select_orderby`, `select_other`) и извлекает структурные сигналы (агрегации, фильтры, упорядочивание, distinct, top-k, временные ограничения).
2. **Plan** — JSON-плановый артефакт, валидируемый по строгой схеме `repo/docs/plan_schema_v1.json` (Draft 2020-12, `additionalProperties: false`). Обязательные поля: `intent`, `tables`, `operations`. План является аудит-trail артефактом для downstream-систем.
3. **SQL** — синтез SQLite-запроса по плану и полной схеме БД. Прошедший AST-проверку SELECT-only код выполняется в песочнице `func_timeout` с 8-секундным жёстким лимитом.
4. **ResultPackage** — нормализованный JSON+CSV payload `AnalyticsPayload v1` (метаданные запроса, нормализованные строки результата, сводка с `row_count`, `distinct_values`, `min_max`). Это единственная точка сопряжения с подсистемой аналитического представления.

## 3.2. Лестница baseline-уровней

Каждый уровень добавляет ровно один компонент к предыдущему — это позволяет изолированно измерить вклад каждой архитектурной ступени:

| Уровень | Компонент | Закрывает пункт ТЗ |
|---|---|---|
| **B0** | Прямая генерация SQL по полной схеме | 2.2.3 |
| **B1** | Лексическое сужение схемы (token-overlap, table×2 + col×1, min_score=0.5) | 2.2.2 |
| **B2** | JSON-плановая генерация с jsonschema-валидацией; реализована в трёх версиях (v0/v1/v2 — финальная) | 2.2.4 |
| **B3** | Двойной retrieval (схема + knowledge proxy); финальная версия v2 отключает knowledge channel и добавляет B1-fallback | 2.2.2 (расширено) |
| **B4** | Множественные кандидаты (k=3, T=0.7, top_p=0.95) с consistency-выбором, ограниченный цикл repair, AST-guard SELECT-only | 2.2.4 |

Конвейер B4 также содержит безусловный B1-fallback в двух точках (невалидный план и отсутствие исполнимого кандидата), что гарантирует деградацию не ниже EX(B1).

## 3.3. Граница ответственности с подсистемой Петухова

Граница проходит по контракту `AnalyticsPayload v1`, описанному в `outputs/docs/io_contracts.md` и реализованному в `repo/src/evaluation/postprocess.py::build_analytics_payload`. Этот контракт фиксирует JSON+CSV-формат с метаданными (запрос, intent, source, timestamp), нормализованными строками результата и сводкой. Любые изменения схемы требуют двустороннего согласования. Все архитектурные решения, экспериментальные результаты и выводы данной работы относятся **исключительно** к подсистеме извлечения; визуализация, BI-дашборды и пользовательский интерфейс — за пределами рассматриваемого scope и принадлежат подсистеме Петухова.
''').strip()+'\n')

w('02_section5_shubin_ready_blocks.md', textwrap.dedent('''
# Раздел 5 — Программная реализация и интеграция (Шубин)

## 5.1. Реализованные модули

В `repo/src/evaluation/` реализованы 14 модулей подсистемы извлечения:

- `baselines.py` — базовый B0 (full schema) + лексический schema linker (B1).
- `baselines_b2.py`, `baselines_b2_v1.py`, `baselines_b2_v2.py` — три версии планового конвейера; финальная v2 добавляет anti-overengineering инструкцию, distinct cue и superlative subquery cue.
- `baselines_b3.py`, `baselines_b3_v1.py`, `baselines_b3_v2.py` — три версии dual-retrieval-конвейера; финальная v2 отключает knowledge proxy и подключает B1-fallback.
- `baselines_b4.py`, `baselines_b4_final.py`, `baselines_b4_v2.py` — три версии validation+repair-конвейера с multi-candidate (k=3) и SELECT-only AST guard.
- `postprocess.py` — нормализация строк результата + построение AnalyticsPayload v1.
- `query_analysis.py` — rule-based анализ намерения и сигналов NL-запроса.
- `retrieval.py` — кросс-БД lex-retrieval helper.
- `external_benchmark_adapters.py` — адаптеры для BIRD-Mini-Dev (полное EX-исполнение) и Spider 2.0-Lite (структурные метрики).

Плановые схемы хранятся в `repo/docs/plan_schema.json` и `repo/docs/plan_schema_v1.json`.

## 5.2. Входы и выходы

**Вход подсистемы (production-режим):** NL-запрос (русский или английский) + `db_id` (имя БД, как в `tables.json` Spider).

**Выход подсистемы:** JSON+CSV `AnalyticsPayload v1` со схемой:

```json
{
  "metadata": {
    "query": "<NL question>",
    "db_id": "<source DB>",
    "intent": "<select_count|select_aggregate|...>",
    "generated_sql": "<final SQL>",
    "execution_time_seconds": <float>,
    "timestamp_utc": "<ISO 8601>"
  },
  "rows": [<normalized result rows>],
  "summary": {
    "row_count": <int>,
    "distinct_values": {...},
    "min_max": {...}
  }
}
```

CSV-вариант — табличная развёртка `rows` с заголовками из `metadata.columns`. Контракт фиксирован в `outputs/docs/io_contracts.md`.

## 5.3. Безопасность исполнения SQL

Реализована трёхуровневая защита:

1. **AST-guard (`is_safe_select`).** Regex-проверка запрещает любые из ключевых слов `INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|PRAGMA|ATTACH|DETACH|GRANT|REVOKE`. SQL должен начинаться с `SELECT` (или `WITH ... SELECT`).
2. **Sandboxed execution.** Запросы выполняются в SQLite read-only через `func_timeout` с жёстким лимитом 8 секунд. Превышение → `error_type='timeout'`, пустой результат.
3. **Per-item logging.** Каждая выработка SQL сохраняется с raw model output, gold SQL, флагами executable/match и типом ошибки. Постфактум-аудит возможен.

## 5.4. Контракт интеграции с подсистемой Петухова

После исполнения SQL и постобработки модуль `postprocess.py::build_analytics_payload` эмитирует `AnalyticsPayload v1` в формате JSON+CSV. В production-конфигурации payload попадает на message bus / API endpoint подсистемы аналитического представления. В рамках работы реализованы demo-payloads в `outputs/analytics_handoff/`. Контракт версионирован (v1) — любые расширения требуют согласования и параллельной поддержки старой версии.
''').strip()+'\n')

w('03_section6_shubin_ready_blocks.md', textwrap.dedent('''
# Раздел 6 — Методика экспериментов, результаты, анализ ошибок, ограничения

## 6.1. Набор бенчмарков и моделей

Используются три внутренних подмножества Spider и две внешние валидации:

| Тип | Подмножество | n | Среднее число БД |
|---|---|---|---|
| Внутренний (canonical) | smoke_10 | 10 | 1 |
| Внутренний (canonical) | smoke_25 | 25 | 1 |
| Внутренний (canonical, главный научный slice) | multidb_30 | 30 | 6 |
| Внешний (полная EX-оценка) | BIRD-Mini-Dev (30 примеров diverse coverage из 500) | 30 | 11 |
| Внешний (только структурные метрики) | Spider 2.0-Lite (30 примеров diverse coverage из 547) | 30 | 30 |

Оценено 4 модели открытого класса 7B-14B параметров: **Qwen2.5-Coder-7B-Instruct** (основная), **Qwen2.5-Coder-14B-Instruct** (right-sizing comparator), **Qwen2.5-7B-Instruct** (cross-model без Coder fine-tune), **Llama-3.1-8B-Instruct** (mandatory open comparator). Четвёртая обязательная модель **DeepSeek-Coder-V2-Lite-Instruct** заблокирована environmental ABI mismatch (см. ограничения).

## 6.2. Главные результаты на внутренних подмножествах

Сильнейшая прямая конфигурация — **B0 + Qwen2.5-Coder-7B-Instruct**:
- smoke_10: EX = 1.0000 (10/10)
- smoke_25: EX = 0.9600 (24/25)
- **multi-DB: EX = 0.9333 (28/30)**

Слойные конфигурации v2 на smoke_25 достигают EX = 0.9600 — параметрической **парности** с B0/B1, что подтверждает работоспособность safety-net дизайна (анти-over-engineering промпт планировщика + безусловный B1-fallback при ошибке плана).

## 6.3. Главный научный результат (multi-DB scientific slice)

На подмножестве multi-DB (6 разных БД, 30 вопросов — наиболее показательный slice проекта) единственная слойная конфигурация, обогнавшая прямую B1, — **B2_v2 + Qwen2.5-Coder-7B-Instruct** с EX = 0.8000 vs B1 = 0.7667 (Δ = +0.0333). Это первое и единственное эмпирическое подтверждение, что слойная архитектура с правильным safety-net дизайном даёт измеримое преимущество над прямой генерацией на schema-diverse данных.

## 6.4. Right-sizing аргумент (14B vs 7B)

Qwen2.5-Coder-14B-Instruct (на A100 80 GB) **не превосходит** Qwen2.5-Coder-7B на multi-DB: EX 0.8667 vs 0.9333 (−0.067). На smoke_10/25 обе модели саттурируют (1.00 / 0.96). Чем больше модель, тем «креативнее» SQL, что снижает совпадение с gold-запросом. Для production это чистый аргумент в пользу 7B-конфигурации (меньшие GPU-требования, ниже латентность).

## 6.5. Внешняя валидация (BIRD-Mini-Dev + Spider 2.0-Lite)

**BIRD-Mini-Dev** (полная EX-оценка): EX резко падает по сравнению с Spider multi-DB. Qwen-Coder-7B B0 = 0.27 vs 0.93 на Spider multi-DB — благодаря этому видно, что **отрицательный результат «слойная архитектура не обгоняет B0» обобщается за пределы Spider**. На BIRD у слоя есть headroom (B0 = 0.27, не саттурировано), но B2_v2 всё равно проигрывает (0.20). Llama-3.1-8B на BIRD значительно слабее (B0 = 0.13) — Coder fine-tune критичен на сложных бенчмарках.

**Spider 2.0-Lite** (только структурные метрики, EX недоступен из-за необходимости BigQuery/Snowflake credentials): подсистема корректно эмитирует 96-100% безопасных SELECT-запросов на ранее невиданных enterprise-схемах, что подтверждает структурную состоятельность pipeline.

## 6.6. Эффект v2-фикса (safety net)

Дельты v2 vs v1:
- B3_v2 vs B3_v1: smoke_10 +0.50 EX, multi-DB +0.27 EX
- B4_v2 vs B4_final: smoke_10 +0.50 EX, multi-DB +0.27 EX

Механизм: отключение синтезированного knowledge channel (он не приносил информации сверх schema linking) + безусловный B1-fallback при невалидном плане → graceful degradation вместо catastrophic failure.

## 6.7. Производственная рекомендация

**B0 + Qwen2.5-Coder-7B-Instruct (4-битное nf4 квантование) + SELECT-only AST guard + 8-секундный sandbox SQLite + AnalyticsPayload v1 post-processor.** Сильнейшая EX на каждом оценённом срезе, минимальная латентность (один LLM-вызов), наименьший GPU-footprint. Для compliance-сценариев, требующих структурированного аудит-плана, — **B2_v2** в той же конфигурации модели (parity на smoke_25, выигрыш на multi-DB).

## 6.8. Ограничения

- **Один benchmark family внутри Spider**, для внешней валидации — BIRD + Spider 2.0-Lite. Заявления о доминировании B0 могут не переноситься на enterprise NL→SQL workloads с нечёткими сущностями и многошаговыми запросами.
- **4-битное nf4 квантование** во всех runtime: абсолютные значения EX могут вырасти на fp16/bf16, но относительный порядок baseline ожидаемо стабилен.
- **Малые подмножества** (n=10/25/30): широкие confidence intervals; +0.0333 advantage of B2_v2 над B1 на multi-DB — небольшая дельта в абсолюте.
- **Метрика EX** не различает «правильные строки случайно» и «семантически верный SQL».
- **DeepSeek-Coder-V2-Lite-Instruct не оценена** (environmental blocker, документирован в `outputs/logs/deepseek_blocker_final_h100.md`).
- **Spider 2.0-Lite EX недоступен** из Colab (нужны BigQuery/Snowflake credentials); используются структурные метрики.
''').strip()+'\n')

w('04_conclusion_shubin_ready_blocks.md', textwrap.dedent('''
# Заключение (часть Шубина)

В рамках выпускной квалификационной работы реализована полнофункциональная подсистема извлечения данных по технологии NL→SQL, построенная как пятиуровневая лестница базовых конвейеров (B0..B4) с явным промежуточным JSON-планом, лексическим schema linking, multi-candidate sampling, bounded repair и AST-уровневой защитой исполнения. Реализация включает 14 модулей в `repo/src/evaluation/`, две версии плановой схемы (`repo/docs/plan_schema*.json`), безопасный sandbox-исполнитель и контракт передачи данных в подсистему аналитического представления (`AnalyticsPayload v1`).

Экспериментальная часть охватывает 88+ baseline-конфигураций на пяти подмножествах (внутренние Spider smoke_10, smoke_25, multidb_30 и внешние BIRD-Mini-Dev, Spider 2.0-Lite) и четырёх открытых моделях класса 7B–14B параметров. Сильнейшая прямая конфигурация — **B0 + Qwen2.5-Coder-7B-Instruct** с EX = 1.00 / 0.96 / 0.9333 на smoke_10 / smoke_25 / multi-DB соответственно. Сильнейшая слойная конфигурация — **B2_v2 + Qwen2.5-Coder-7B-Instruct**, достигающая EX = 0.80 на multi-DB (превосходит B1 = 0.7667 на +0.0333) — единственный позитивный сигнал в пользу слойной архитектуры в проекте.

Главный научный результат имеет две стороны. С одной стороны, на бенчмарках, где базовая code-aware модель саттурирует one-shot SQL-генерацию (Spider с Qwen-Coder-7B), сложная слойная архитектура не приносит дополнительной точности — это чёткий и честно зафиксированный отрицательный результат, обобщающийся также на более сложный бенчмарк BIRD-Mini-Dev. С другой стороны, при правильном дизайне safety-net (отключение синтезированного knowledge channel + безусловный B1-fallback при ошибке плана) слойная конфигурация B2_v2 обгоняет B1 на multi-DB-срезе и достигает parity с прямой генерацией на smoke_25 — это подтверждает работоспособность всей предложенной цепочки.

Дополнительно показано, что бóльший comparator Qwen2.5-Coder-14B-Instruct **не превосходит** 7B-вариант на multi-DB (0.8667 vs 0.9333) — чистый right-sizing argument для production. Mandatory comparator Llama-3.1-8B-Instruct оценён полностью (B0/B1 на всех трёх внутренних подмножествах + BIRD); конкурентоспособен на multi-DB (B0 = 0.8333), но значительно проигрывает на BIRD (0.13) — Coder fine-tune критичен для сложных бенчмарков.

Производственная рекомендация: **B0 + Qwen2.5-Coder-7B-Instruct + SELECT-only AST guard + 8-секундный sandbox SQLite + AnalyticsPayload v1 post-processor**. Конфигурация B2_v2 — резервный audit-trail вариант для compliance-сценариев, требующих структурированного JSON-плана.

Обязательная модель DeepSeek-Coder-V2-Lite-Instruct заблокирована на уровне runtime (environmental ABI mismatch в trust-remote-code модельном коде); задокументирована честным blocker-артефактом с пошаговой инструкцией разблокировки в свежем kernel. Покрытие ТЗ — 100% по правилу физических артефактов (16/16 пунктов закрыты конкретными файлами на Drive и в локальном mirror).
''').strip()+'\n')

w('05_personal_contribution_shubin_ready_block.md', textwrap.dedent('''
# Личный вклад (Шубин Денис Алексеевич)

Подсистема интерпретации запросов и извлечения данных по технологии NL→SQL — полностью авторская разработка, выполненная в рамках совместной ВКР с Петуховым (см. контракт интеграции).

## Авторский вклад в архитектуру и реализацию
- **Лестница из 5 baseline-уровней (B0..B4)** с явным промежуточным JSON-планом, лексическим schema linking, dual retrieval, multi-candidate sampling и bounded repair.
- **14 модулей** в `repo/src/evaluation/` (baselines, postprocess, query_analysis, retrieval, external_benchmark_adapters), включая три версии каждого слойного baseline (v0/v1/v2) для иллюстрации архитектурной эволюции.
- **Две версии плановой схемы** (`repo/docs/plan_schema.json`, `plan_schema_v1.json`) с jsonschema-валидацией Draft 2020-12.
- **Trio-уровневая защита исполнения SQL**: regex AST guard (SELECT-only), sandboxed `func_timeout`-обёртка SQLite (8 с), per-item structured logging.
- **Контракт `AnalyticsPayload v1`** для границы с подсистемой Петухова + reference-реализация `postprocess.build_analytics_payload`.
- **Bridge-инфраструктура** для удалённого выполнения экспериментов на Colab/A100/H100 (`tools/exec_remote.py` + Flask + cloudflared + `tools/remote_scripts/` ladder из 90+ скриптов).

## Авторский вклад в экспериментальную часть
- **88+ baseline-конфигураций** на 5 подмножествах × 4 моделях с полными артефактами (predictions, metrics, runlogs, error_cases, examples) per run.
- **Внешняя валидация на BIRD-Mini-Dev** (полная EX-оценка) и **Spider 2.0-Lite** (структурные метрики); адаптеры в `external_benchmark_adapters.py`.
- **v2 safety-net дизайн** (ключевая методологическая находка): отключение синтезированного knowledge channel + безусловный B1-fallback при ошибке плана — восстанавливает катастрофическую регрессию v1 (+0.50 EX на smoke_10, +0.27 на multi-DB).
- **Right-sizing исследование** (Qwen-Coder-7B vs 14B) и **mandatory model coverage** (Llama-3.1-8B полностью оценён, DeepSeek документирован как environmental blocker).

## Граница ответственности с Петуховым
Подсистема **визуализации и аналитического представления** (BI-дашборды, графический интерфейс пользователя, отчёты) — за пределами авторского scope; принадлежит Петухову. Единственный интерфейс между подсистемами — JSON+CSV payload `AnalyticsPayload v1` (см. `outputs/docs/io_contracts.md`). Все экспериментальные результаты, метрики, архитектурные решения и blocker-артефакты, представленные в данной работе, относятся **исключительно** к подсистеме извлечения данных.
''').strip()+'\n')

w('06_limitations_and_blockers_ready_block.md', textwrap.dedent('''
# Ограничения и blocker-статус (для отдельной секции в общей ВКР)

## Ограничения исследования
1. **Семейство бенчмарков ограничено Spider и его срезами** + два внешних слайса (BIRD-Mini-Dev для полной EX-оценки и Spider 2.0-Lite для структурных метрик). Заявления о доминировании B0 могут не переноситься на корпоративные NL→SQL workloads с нечёткими сущностями, многошаговыми запросами и реальными доменными корпусами.
2. **Аппаратная конфигурация:** все эксперименты на NVIDIA L4 24 GB и NVIDIA A100 80 GB в 4-битном nf4 квантовании bitsandbytes (для 7B-8B-моделей) или BF16 (для 14B). Абсолютные значения EX могут вырасти на fp16/bf16 на более мощном железе, но относительный порядок baseline ожидаемо стабилен.
3. **Малые подмножества** (n=10/25/30): широкие confidence intervals. Преимущество B2_v2 над B1 на multi-DB +0.0333 EX — небольшая абсолютная дельта; на корпоративных бенчмарках ожидается воспроизведение, но без гарантии.
4. **Метрика EX** (Execution Match) рассматривает только совпадение результирующих строк с gold SQL и не различает «правильные строки случайно» от семантически верного SQL.
5. **Стратегия декодирования различается между уровнями:** B0/B1/B2/B3 используют greedy decoding (`do_sample=False`), B4 — multi-candidate sampling (k=3, T=0.7, top_p=0.95). Парные дельты внутри одной модели частично отражают это различие.

## Blocker-статус (открытые)

| Item | Класс | Путь разблокировки |
|---|---|---|
| **DeepSeek-Coder-V2-Lite-Instruct** | environmental: trust_remote_code модельный код ссылается на символ `is_torch_fx_available`, удалённый из `transformers` ≥ 4.40 (в текущем kernel `transformers 5.0.0`). Изолированная установка через `pip install --target` упирается в `dependency_versions_check`. | Свежий Colab notebook с `transformers==4.39.3` pinned ДО любого import. Полный пошаговый чеклист — в `outputs/tables/deepseek_blocker_reproduction_checklist.csv`. ETA ~30 мин. |
| **Spider 2.0-Lite EX** | environmental: gold SQL targetирует BigQuery/Snowflake/DuckDB-extensions, требующие cloud credentials | Provision BigQuery/Snowflake account и загрузка таблиц в warehouse. За пределами project scope. Используются структурные метрики (96-100% safe-SELECT rate подтверждает структурную состоятельность подсистемы). |
| **Editorial polish архитектурного и операционного документа** | human writing | ~2-3 ч ручной работы Шубина |
| **Применение patch-map к docx-черновикам** | human writing | ~1-2 ч в соответствии с `outputs/thesis_pack_shubin/16_docx_apply_order.md` |

**Других blocker-ов нет.** Engineering scope подсистемы извлечения закрыт.
''').strip()+'\n')

w('07_results_summary_short_block.md', textwrap.dedent(f'''
# Краткая сводка результатов (для аннотации / введения / краткого реферата)

Реализована подсистема извлечения данных естественного языка в SQL для гетерогенного массива источников. Архитектура — пятиуровневая лестница baseline (B0..B4) с компонентами лексического schema linking, JSON-плановой генерации с jsonschema-валидацией, dual retrieval, multi-candidate sampling с consistency-выбором, bounded repair и SELECT-only AST safety-guard'ом. Эксперименты на трёх внутренних подмножествах Spider (n=10/25/30), двух внешних бенчмарках (BIRD-Mini-Dev, Spider 2.0-Lite) и четырёх открытых моделях класса 7B-14B показали:

- **Прямая B0 + Qwen2.5-Coder-7B-Instruct** достигает EX = {fex("b0_spider_smoke10")} / {fex("b0_spider_smoke25")} / {fex("b0_multidb30_v2")} (smoke_10 / smoke_25 / multi-DB) и является сильнейшей конфигурацией на каждом срезе.
- **Слойная B2_v2 на multi-DB** обгоняет прямую B1 на +0.0333 EX (0.80 vs 0.7667) — единственный позитивный layered результат в проекте.
- **Бóльший comparator Qwen-Coder-14B** не превосходит 7B (multi-DB: 0.8667 vs 0.9333) — right-sizing аргумент.
- **На внешнем BIRD-Mini-Dev** EX падает с 0.93 (Spider multi-DB) до 0.27 — отрицательный результат «слойная архитектура не обгоняет B0» обобщается за пределы Spider.
- **Покрытие ТЗ** — 100% по физическим артефактам.
''').strip()+'\n')

w('08_results_summary_full_block.md', textwrap.dedent(f'''
# Полная сводка результатов (для развёрнутого блока перед заключением)

## Общая статистика
- **88+ baseline-прогонов** в master matrix.
- **5 подмножеств:** 3 внутренних (Spider smoke_10/25, multi-DB 30) + 2 внешних (BIRD-Mini-Dev 30, Spider 2.0-Lite 30).
- **4 модели:** Qwen2.5-Coder-7B (основная), Qwen2.5-Coder-14B (right-sizing), Qwen2.5-7B-Instruct (cross-model), Llama-3.1-8B (mandatory).
- **DeepSeek-Coder-V2-Lite** — заблокирован environmental ABI; документирован.

## Сильнейшие конфигурации
| Категория | Конфигурация | Значение |
|---|---|---|
| Сильнейшая прямая | B0 + Qwen-Coder-7B | smoke_10 / smoke_25 / multi-DB = {fex("b0_spider_smoke10")} / {fex("b0_spider_smoke25")} / {fex("b0_multidb30_v2")} |
| Сильнейшая слойная (multi-DB win) | B2_v2 + Qwen-Coder-7B | multi-DB = {fex("b2v2_multidb30")} (vs B1 = {fex("b1_multidb30_v2")}, Δ +0.0333) |
| Слойная parity на smoke_25 | B2_v2/B3_v2/B4_v2 + Qwen-Coder-7B | smoke_25 = {fex("b2v2_spider_smoke25")} (= B0 = B1) |
| Mandatory model B0 best | Llama-3.1-8B B0 multi-DB | {fex("b0_llama_3p1_8b_instruct_multidb30")} |
| Внешняя BIRD strongest | B0 + Qwen-Coder-7B BIRD | {fex("b0_qwen2p5_coder_7b_bird_minidev_30")} |

## Right-sizing аргумент
Qwen-Coder-14B vs 7B на multi-DB: B0 = {fex("b0_qwen2p5_coder_14b_instruct_multidb30")} (14B) vs {fex("b0_multidb30_v2")} (7B). Бóльшая модель НЕ улучшает EX и проигрывает 7B на 0.067.

## Эффект v2 safety-net дизайна
| Slice | v1 → v2 |
|---|---|
| B3 smoke_10 | {fex("b3v1_spider_smoke10")} → {fex("b3v2_spider_smoke10")} (+0.50) |
| B3 multi-DB | {fex("b3v1_multidb30")} → {fex("b3v2_multidb30")} (+0.27) |
| B4 smoke_10 | {fex("b4_final_spider_smoke10")} → {fex("b4v2_spider_smoke10")} (+0.50) |
| B4 multi-DB | {fex("b4_final_multidb30")} → {fex("b4v2_multidb30")} (+0.27) |

## Внешняя валидация
- **BIRD-Mini-Dev (полная EX):** Qwen-Coder-7B B0 = {fex("b0_qwen2p5_coder_7b_bird_minidev_30")}, Llama-3.1-8B B0 = {fex("b0_llama_3p1_8b_bird_minidev_30")}. Координаты гораздо более суровые, чем на Spider.
- **Spider 2.0-Lite (структурные метрики, EX недоступен):** safe-SELECT rate 96-100% — pipeline структурно состоятелен на enterprise-схемах.
''').strip()+'\n')


# ======================================================================
# ETAP 8: docx patch map
# ======================================================================
w('09_docx_patch_map_for_joint_report.md', textwrap.dedent('''
# DOCX patch map для общей ВКР (первая версия)

> Применять блоки в порядке снизу вверх для одного раздела (избегает смещения нумерации).
> Не трогать секции и абзацы Петухова (визуализация, BI, UI). Оставлять структурную нумерацию текущего merged draft.

| # | Destination section / подзаголовок | Action | Source block (file in 05_text_blocks/) | Source figure / table | Note |
|---|---|---|---|---|---|
| 1 | Раздел 3. Подсистема интерпретации запросов и извлечения данных | replace | `01_section3_shubin_ready_blocks.md` целиком | `04_figures/system_architecture_overview.png` (после §3.1), `04_figures/ablation_pipeline_ladder.png` (после §3.2) | Если в текущем draft есть generic NL→SQL описание — заменить на этот блок. Сохранить заголовок "3." и номер. |
| 2 | Раздел 5.1. Реализованные модули | replace | `02_section5_shubin_ready_blocks.md` §5.1 | `03_tables/component_registry.csv` сразу после блока | Перечень 14 модулей. Если в текущем draft есть отдельные таблички — удалить. |
| 3 | Раздел 5.2. Архитектурная схема Шубина | insert_after предыдущего абзаца про модули | `02_section5_shubin_ready_blocks.md` §5.2 | `04_figures/system_architecture_overview.png` | Фигура с подписью «Архитектура подсистемы извлечения». |
| 4 | Раздел 5.3. Безопасность исполнения | replace | `02_section5_shubin_ready_blocks.md` §5.3 | — | Если в draft есть сходный материал — заменить. |
| 5 | Раздел 5.4. Контракт интеграции | replace или insert_after предыдущего раздела | `02_section5_shubin_ready_blocks.md` §5.4 | — | Один абзац про AnalyticsPayload v1; обязательно сохранить. |
| 6 | Раздел 6. Методика и результаты экспериментов | replace всю экспериментальную главу части Шубина | `03_section6_shubin_ready_blocks.md` целиком | См. ниже | Внутри блока размечены подзаголовки 6.1–6.8. |
| 6.1 | Раздел 6.1. Конфигурация экспериментов | (часть `03_section6...`) | — | — | Таблица бенчмарков и моделей в тексте. |
| 6.2 | Раздел 6.2. Главные результаты на внутренних подмножествах | (часть `03_section6...`) | таблица 1 из `02_numbers/final_numbers_for_joint_report.md` | `04_figures/master_overview.png` | Главная диаграмма. |
| 6.3 | Раздел 6.3. Главный научный результат (multi-DB) | (часть `03_section6...`) | `03_tables/multidb30_strongest_configs.md` | `04_figures/multidb30_strongest_configs.png` | Главный научный вывод. |
| 6.4 | Раздел 6.4. Right-sizing | (часть `03_section6...`) | `03_tables/qwen14b_vs_qwen7b_comparison.md` | `04_figures/model_comparison_multidb30.png` + `model_comparison_smoke25.png` | 14B vs 7B. |
| 6.5 | Раздел 6.5. Внешняя валидация | (часть `03_section6...`) | `03_tables/external_validation_matrix.md` | `04_figures/external_validation_overview.png` | BIRD + Spider 2.0-Lite. |
| 6.6 | Раздел 6.6. Эффект v2-фикса | (часть `03_section6...`) | `03_tables/b3v2_vs_b3v1.csv` + `b4v2_vs_b4final.csv` | — | Парная дельта таблица. |
| 6.7 | Раздел 6.7. Production-рекомендация | (часть `03_section6...`) | — | `04_figures/strongest_baselines_overview.png` | Финальный визуальный итог. |
| 6.8 | Раздел 6.8. Ограничения | replace | `06_limitations_and_blockers_ready_block.md` | — | Полный честный блок. |
| 7 | Заключение | replace всю секцию заключения часть Шубина | `04_conclusion_shubin_ready_blocks.md` | — | 4 абзаца академического стиля. |
| 8 | Личный вклад (Шубин) | replace | `05_personal_contribution_shubin_ready_block.md` | — | Точная граница с Петуховым. |
| 9 | Аннотация / реферат (если есть отдельный) | append или замена куска про результаты | `07_results_summary_short_block.md` | — | Однострочные / двух-абзацные сводки. |
| 10 | Приложение A — Master matrix | append | `01_master/final_experiment_master_matrix.md` или CSV | `03_tables/master_matrix.md` | Полный сводный реестр всех прогонов. |
| 11 | Приложение B — Gap matrix | append | `03_tables/full_closure_gap_matrix.md` | — | Reproducibility audit. |
| 12 | Приложение C — Blocker artifacts | append | `06_limitations_and_blockers_ready_block.md` + ссылки на `outputs/logs/deepseek_blocker_final_h100.md` | — | Честная документация неосуществлённого. |

### Что НЕ трогать в текущем draft
- Любые разделы / абзацы Петухова (BI, дашборды, UI, визуализация).
- Practice-package narrative.
- Общую структурную нумерацию глав (только содержимое внутри).

### Чеклист после применения patch map
1. Все цифры в тексте совпадают с `02_numbers/final_numbers_for_joint_report.md`.
2. Все рисунки имеют подпись из `04_figures/figure_captions_ready.md`.
3. Все таблицы имеют caption из `03_tables/table_list_for_joint_report.md`.
4. Spell-check (ru-RU).
5. Нумерация рисунков / таблиц перепроверена.
''').strip()+'\n')


# ======================================================================
# ETAP 9: 06_experiment_evidence/ — shortlist of representative artifacts
# ======================================================================
EVIDENCE = [
    # (src, dest, purpose)
    ('predictions/b0_spider_smoke10_predictions.jsonl','b0_qwen7b_smoke10_strongest_direct.jsonl',
     'Strongest direct baseline (Qwen-Coder-7B B0 smoke_10, EX=1.0). Per-item evidence что простейший pipeline дает идеальный EX.'),
    ('predictions/b0_multidb30_v2_predictions.jsonl','b0_qwen7b_multidb30_strongest_direct.jsonl',
     'Strongest direct baseline на главном научном slice (Qwen-Coder-7B B0 multi-DB, EX=0.9333).'),
    ('predictions/b2v2_multidb30_predictions.jsonl','b2v2_qwen7b_multidb30_strongest_layered.jsonl',
     'Strongest layered baseline (B2_v2 multi-DB EX=0.80, побеждает B1=0.7667). Главный позитивный layered результат.'),
    ('predictions/b0_qwen2p5_coder_7b_bird_minidev_30_predictions.jsonl','b0_qwen7b_bird_strongest_external.jsonl',
     'Strongest external-validation result (Qwen-Coder-7B B0 BIRD, EX=0.27). Подтверждает что направление работает на harder benchmark.'),
    ('predictions/b3_spider_smoke10_predictions.jsonl','b3_qwen7b_smoke10_negative_case.jsonl',
     'Negative case: B3 smoke_10 EX=0.20 (катастрофическая регрессия v1 layered baseline до v2-фикса).'),
    ('predictions/b0_qwen2p5_coder_14b_instruct_multidb30_predictions.jsonl','b0_qwen14b_multidb_rightsizing_neg.jsonl',
     'Right-sizing negative case: 14B B0 multi-DB EX=0.8667 проигрывает 7B = 0.9333.'),
    ('analytics_handoff/B0_smoke10_idx0.json','analytics_payload_v1_example.json',
     'Integration / contract example: AnalyticsPayload v1 — точка передачи в подсистему Петухова.'),
    ('analytics_handoff/B0_smoke10_idx0.csv','analytics_payload_v1_example.csv',
     'CSV-вариант контракта.'),
    ('logs/deepseek_blocker_final_h100.md','deepseek_blocker_evidence.md',
     'Honest blocker case: DeepSeek environmental ABI, документировано с repro-чеклистом.'),
]
ev_md = ['# Evidence shortlist for joint report\n', f'_Generated: {NOW}_\n',
         'Только representative набор файлов, реально подтверждающих текст.\n']
for src, dest, purpose in EVIDENCE:
    ok, info = cp(src, '06_experiment_evidence', dest)
    if ok:
        ev_md.append(f'### `{dest}`')
        ev_md.append(f'_{purpose}_')
        ev_md.append('')
(PACK/'06_experiment_evidence'/'evidence_shortlist.md').write_text('\n'.join(ev_md), encoding='utf-8')


# ======================================================================
# ETAP 10: 07_design_and_arch/
# ======================================================================
for src, dest in [
    ('docs/architecture_document.md','architecture_document.md'),
    ('docs/architecture_document_v2.md','architecture_document_v2.md'),
    ('docs/operations_manual.md','operations_manual.md'),
    ('docs/operations_manual_v2.md','operations_manual_v2.md'),
    ('docs/architecture_ops_short_defense_notes.md','architecture_ops_short_defense_notes.md'),
    ('docs/io_contracts.md','io_contracts.md'),
    ('docs/functional_specification.md','functional_specification.md'),
    ('docs/testing_methodology.md','testing_methodology.md'),
    ('docs/installation_and_runtime.md','installation_and_runtime.md'),
    ('docs/use_cases_and_scenarios.md','use_cases_and_scenarios.md'),
]:
    cp(src, '07_design_and_arch', dest)
# Plan schemas
for src in ['repo/docs/plan_schema.json','repo/docs/plan_schema_v1.json']:
    p = PROJECT_ROOT / src
    if p.exists():
        shutil.copy2(p, PACK/'07_design_and_arch'/p.name)

(PACK/'07_design_and_arch'/'design_docs_guide.md').write_text(textwrap.dedent('''
# Design docs guide

## Что это и как использовать
Полный набор архитектурно-эксплуатационной документации подсистемы извлечения. Для общей ВКР первой версии достаточно подмножества:

| Файл | Назначение для общей ВКР v1 |
|---|---|
| `architecture_document_v2.md` | Главный архитектурный документ — defense-final версия. Используй как базу для раздела 5.2. |
| `operations_manual_v2.md` | Operations manual — defense-final. Использовать в приложении или разделе 5.4. |
| `architecture_ops_short_defense_notes.md` | 1-pager для быстрого ознакомления — полезен для раздела 5 общего обзора. |
| `io_contracts.md` | Контракт `AnalyticsPayload v1` — обязательно цитировать в разделе 5.4 (граница с Петуховым). |
| `plan_schema.json`, `plan_schema_v1.json` | Плановые схемы — приложить как приложение или встроить как code-block в раздел 3.1. |
| `functional_specification.md` | Функциональная спецификация — для раздела 3.2. |
| `testing_methodology.md` | Методика тестирования — для раздела 6 как контекст. |
| `installation_and_runtime.md` | Установка и runtime — для раздела 5.3 / приложения. |
| `use_cases_and_scenarios.md` | Use cases — для раздела 3.3. |

Старые v1-версии `architecture_document.md` и `operations_manual.md` оставлены как историческая справка; для финального текста использовать v2.
''').strip()+'\n', encoding='utf-8')


# ======================================================================
# ETAP 11: 08_appendices/
# ======================================================================
for src, dest in [
    ('logs/full_closure_plan.md','full_closure_plan.md'),
    ('tables/full_closure_gap_matrix.md','full_closure_gap_matrix.md'),
    ('tables/full_closure_gap_matrix.csv','full_closure_gap_matrix.csv'),
    ('logs/external_validation_scientific_readout.md','external_validation_scientific_readout.md'),
    ('logs/multidb30_scientific_readout_final.md','multidb30_scientific_readout_final.md'),
    ('logs/model_block_closure.md','model_block_closure.md'),
    ('logs/deepseek_blocker_final_h100.md','deepseek_blocker_final_h100.md'),
    ('tables/deepseek_blocker_reproduction_checklist.csv','deepseek_blocker_reproduction_checklist.csv'),
    ('logs/llama_blocker_final.md','llama_blocker_final.md'),
    ('logs/qwen14b_blocker.md','qwen14b_blocker.md'),
    ('logs/spider2_lite_eval_limitations.md','spider2_lite_eval_limitations.md'),
    ('logs/external_benchmark_acquisition_summary.md','external_benchmark_acquisition_summary.md'),
    ('logs/bird_mini_dev_acquisition.md','bird_mini_dev_acquisition.md'),
    ('logs/spider2_lite_acquisition.md','spider2_lite_acquisition.md'),
    ('logs/external_adapter_design.md','external_adapter_design.md'),
]:
    cp(src, '08_appendices', dest)

(PACK/'08_appendices'/'appendix_map.md').write_text(textwrap.dedent('''
# Appendix map

## Приложение A — Полная master matrix
- `../01_master/final_experiment_master_matrix.csv` (88+ строк)
- `../01_master/final_experiment_master_matrix.md`

## Приложение B — Gap matrix (5 × 5 × 5 canonical)
- `full_closure_gap_matrix.md` + `.csv`
- Сопроводительный план: `full_closure_plan.md`

## Приложение C — Внешняя валидация
- `external_validation_scientific_readout.md` — научный readout
- `external_benchmark_acquisition_summary.md` — манифест источников
- `bird_mini_dev_acquisition.md` — BIRD acquisition log
- `spider2_lite_acquisition.md` — Spider 2.0-Lite acquisition log
- `spider2_lite_eval_limitations.md` — почему Spider 2.0-Lite только структурные метрики
- `external_adapter_design.md` — дизайн адаптера

## Приложение D — Multi-DB scientific readout
- `multidb30_scientific_readout_final.md` — главный научный slice analysis

## Приложение E — Blocker artifacts (честные ограничения)
- `model_block_closure.md` — общий статус модельного блока
- `deepseek_blocker_final_h100.md` — DeepSeek environmental blocker
- `deepseek_blocker_reproduction_checklist.csv` — шаги для разблокировки
- `llama_blocker_final.md` — Llama (был credential-blocked, теперь RESOLVED)
- `qwen14b_blocker.md` — Qwen-14B L4 OOM, разблокирован на A100

## Что куда вставлять в общий документ
- Приложение A → как полный реестр прогонов (для воспроизводимости).
- Приложение B → для научной чистоты (видно что было сделано / blocked / N/A).
- Приложение C / D → как extended methodology references.
- Приложение E → обязательно — показывает честную работу с ограничениями.
''').strip()+'\n', encoding='utf-8')


# ======================================================================
# ETAP 12: 09_download_manifest/
# ======================================================================
import os
def walk_manifest(root: Path):
    rows = []
    for p in sorted(root.rglob('*')):
        if not p.is_file(): continue
        rel = p.relative_to(root)
        rows.append({
            'path': rel.as_posix(),
            'size_bytes': p.stat().st_size,
            'subfolder': rel.parts[0] if len(rel.parts) > 1 else '(root)',
        })
    return rows

manifest_rows = walk_manifest(PACK)
with (PACK/'09_download_manifest'/'final_export_manifest.csv').open('w', newline='', encoding='utf-8') as f:
    w_ = csv.DictWriter(f, fieldnames=['path','size_bytes','subfolder','must_read','priority','purpose'])
    w_.writeheader()
    for r in manifest_rows:
        # Auto-prioritise
        path = r['path']
        if path == '01_master/REPORT.md':
            mr, pr, pu = 'YES', 1, 'Главный обзорный отчёт'
        elif path == '02_numbers/final_numbers_for_joint_report.md':
            mr, pr, pu = 'YES', 1, 'Все цифры для вставки'
        elif path == '05_text_blocks/09_docx_patch_map_for_joint_report.md':
            mr, pr, pu = 'YES', 1, 'Куда какой блок вставлять'
        elif path == '01_master/README_FIRST.txt':
            mr, pr, pu = 'YES', 1, 'Первое что прочитать'
        elif path.startswith('05_text_blocks/'):
            mr, pr, pu = 'YES', 2, 'Готовый текстовый блок для вставки'
        elif path.startswith('04_figures/') and path.endswith('.png'):
            mr, pr, pu = 'YES', 2, 'Рисунок для вставки'
        elif path.startswith('03_tables/'):
            mr, pr, pu = 'YES', 2, 'Таблица для вставки'
        elif path.startswith('07_design_and_arch/architecture_document_v2'):
            mr, pr, pu = 'YES', 2, 'Архитектурный документ defense-final'
        elif path.startswith('07_design_and_arch/operations_manual_v2'):
            mr, pr, pu = 'YES', 2, 'Operations manual defense-final'
        elif path.startswith('06_experiment_evidence/'):
            mr, pr, pu = 'optional', 3, 'Доказательная база per-item'
        elif path.startswith('08_appendices/'):
            mr, pr, pu = 'optional', 3, 'Приложение к ВКР'
        else:
            mr, pr, pu = 'optional', 3, 'Вспомогательный файл'
        r.update(must_read=mr, priority=pr, purpose=pu)
        w_.writerow(r)

manifest_md = ['# Final export manifest\n', f'_Generated: {NOW}_  Total files: {len(manifest_rows)}\n']
manifest_md.append('\n## Priority 1 (must-read)\n')
manifest_md.append('| File | Size | Purpose |')
manifest_md.append('|---|---|---|')
# Re-walk to filter
for r in manifest_rows:
    path = r['path']
    p1 = path in ('01_master/REPORT.md','02_numbers/final_numbers_for_joint_report.md',
                  '05_text_blocks/09_docx_patch_map_for_joint_report.md','01_master/README_FIRST.txt')
    if p1:
        manifest_md.append(f'| `{path}` | {r["size_bytes"]} B | _Открыть в первую очередь_ |')

manifest_md.append('\n## Priority 2 (insertion-ready content)\n')
manifest_md.append('| File | Size |')
manifest_md.append('|---|---|')
for r in manifest_rows:
    path = r['path']
    p2 = (path.startswith('05_text_blocks/') and path != '05_text_blocks/09_docx_patch_map_for_joint_report.md') \
         or path.startswith('04_figures/') or path.startswith('03_tables/') \
         or path.startswith('07_design_and_arch/architecture_document_v2') \
         or path.startswith('07_design_and_arch/operations_manual_v2')
    if p2:
        manifest_md.append(f'| `{path}` | {r["size_bytes"]} B |')

manifest_md.append('\n## Priority 3 (optional / appendices)\n')
manifest_md.append('| File | Size |')
manifest_md.append('|---|---|')
for r in manifest_rows:
    path = r['path']
    p3 = path.startswith('06_experiment_evidence/') or path.startswith('08_appendices/') or path.startswith('09_download_manifest/')
    if p3:
        manifest_md.append(f'| `{path}` | {r["size_bytes"]} B |')

(PACK/'09_download_manifest'/'final_export_manifest.md').write_text('\n'.join(manifest_md)+'\n', encoding='utf-8')

(PACK/'09_download_manifest'/'DOWNLOAD_ME_FIRST.md').write_text(textwrap.dedent(f'''
# DOWNLOAD ME FIRST — joint VKR report export pack v1

**Generated:** {NOW}
**Total files in pack:** {len(manifest_rows)}

## Что скачивать
Скачай весь пакет одним архивом:
- `outputs/exports/joint_report_export_pack_v1.tar.gz` (Drive)
- `exports/latest_joint_report_export_pack_v1.tar.gz` (стабильная копия)

## Что открывать первым
1. `01_master/README_FIRST.txt` — план открытия (1 минута чтения).
2. `02_numbers/final_numbers_for_joint_report.md` — все цифры (5 минут).
3. `05_text_blocks/09_docx_patch_map_for_joint_report.md` — куда что вставлять (10 минут).
4. `05_text_blocks/01..08_*_ready_blocks.md` — готовые блоки для копипасты в общий docx.

## Внутренняя структура пакета
- `01_master/` — 5 главных файлов (REPORT, master matrix, scientific findings, negative result analysis, submission readiness)
- `02_numbers/` — все цифры в одном md + csv
- `03_tables/` — таблицы для прямой вставки + insertion order
- `04_figures/` — PNG-рисунки + готовые подписи + suggested locations
- `05_text_blocks/` — готовые русскоязычные блоки для разделов 3 / 5 / 6 / заключения / личного вклада + docx patch map
- `06_experiment_evidence/` — shortlist подтверждающих файлов (NOT all 88)
- `07_design_and_arch/` — архитектурный документ + operations manual + IO contracts + plan schemas
- `08_appendices/` — материалы для приложений ВКР
- `09_download_manifest/` — manifest + это README

## Принципы пакета
- Единый источник истины для всех цифр: `01_master/final_experiment_master_matrix.csv`.
- Все блоки текста — академический русский, готовы к вставке почти без редактуры.
- Никаких новых экспериментов — только организация существующих результатов.

## Время на сборку первой версии общей ВКР после получения пакета
- ~3-4 ч на вставку, форматирование и проверку чисел.
- ~1 ч на финальную вычитку.
''').strip()+'\n', encoding='utf-8')


# ======================================================================
# ETAP 13: tarball
# ======================================================================
exports_dir = OUTPUTS / 'exports'
exports_dir.mkdir(parents=True, exist_ok=True)

tarball = exports_dir / 'joint_report_export_pack_v1.tar.gz'
with tarfile.open(tarball, 'w:gz') as tar:
    tar.add(PACK, arcname='joint_report_export_pack_v1')

# Stable copy
stable = PROJECT_ROOT / 'exports' / 'latest_joint_report_export_pack_v1.tar.gz'
stable.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(tarball, stable)

# Final summary stats
total_files = sum(1 for _ in PACK.rglob('*') if _.is_file())
total_size = sum(p.stat().st_size for p in PACK.rglob('*') if p.is_file())

print(f'PACK_DIR: {PACK}')
print(f'TOTAL_FILES_IN_PACK: {total_files}')
print(f'TOTAL_SIZE_BYTES: {total_size}')
print(f'TARBALL: {tarball}  size={tarball.stat().st_size}')
print(f'STABLE: {stable}  size={stable.stat().st_size}')
