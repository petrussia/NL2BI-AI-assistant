# Stage F3: Build outputs/thesis_pack_shubin/ — copy-pasteable evidence pack
# for the Shubin-only sections of the diploma.

import csv
import datetime as dt
import json
import shutil
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
PACK = OUTPUTS / 'thesis_pack_shubin'
PACK.mkdir(parents=True, exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc).isoformat()


def load(prefix):
    p = OUTPUTS/'metrics'/f'{prefix}_metrics.csv'
    if not p.exists(): return None
    return next(csv.DictReader(p.open(encoding='utf-8')), None)

def fex(prefix):
    m = load(prefix)
    if not m: return '—'
    try: return f'{float(m["ex"]):.4f} ({m["execution_match_count"]}/{m["n"]})'
    except: return '—'


# === 01 final_numbers.md ===
(PACK/'01_final_numbers.md').write_text(f'''# 01 — Final numbers (Shubin)

_Generated: {NOW}_

## Headline EX (Execution Match) — copy-pasteable for ВКР tables

### Single-DB smoke subsets

| Baseline | Model | smoke_10 | smoke_25 |
|---|---|---|---|
| B0 | Qwen2.5-Coder-7B-Instruct | {fex("b0_spider_smoke10")} | {fex("b0_spider_smoke25")} |
| B1 | Qwen2.5-Coder-7B-Instruct | {fex("b1_spider_smoke10")} | {fex("b1_spider_smoke25")} |
| B2_v0 | Qwen2.5-Coder-7B-Instruct | {fex("b2_spider_smoke10")} | — |
| B2_v1 | Qwen2.5-Coder-7B-Instruct | {fex("b2v1_spider_smoke10")} | — |
| B2_v2 | Qwen2.5-Coder-7B-Instruct | {fex("b2v2_spider_smoke10")} | — |
| B3_v1 | Qwen2.5-Coder-7B-Instruct | {fex("b3v1_spider_smoke10")} | — |
| B3_v2 | Qwen2.5-Coder-7B-Instruct | {fex("b3v2_spider_smoke10")} | — |
| B4_final | Qwen2.5-Coder-7B-Instruct | {fex("b4_final_spider_smoke10")} | — |
| B4_v2 | Qwen2.5-Coder-7B-Instruct | {fex("b4v2_spider_smoke10")} | — |
| B0 | Qwen2.5-7B-Instruct (cross-model) | {fex("b0_qwen_qwen2.5_7b_instruct_smoke10")} | — |
| B1 | Qwen2.5-7B-Instruct (cross-model) | {fex("b1_qwen_qwen2.5_7b_instruct_smoke10")} | — |
| B0 | Llama-3.1-8B-Instruct | {fex("b0_llama_3p1_8b_instruct_smoke10")} | — |
| B1 | Llama-3.1-8B-Instruct | {fex("b1_llama_3p1_8b_instruct_smoke10")} | — |
| B0 | Qwen2.5-Coder-14B-Instruct | {fex("b0_qwen2p5_coder_14b_instruct_smoke10")} | — |
| B1 | Qwen2.5-Coder-14B-Instruct | {fex("b1_qwen2p5_coder_14b_instruct_smoke10")} | — |

### multidb_30 (master scientific slice — heterogeneous schemas across 6 DBs)

| Baseline | Model | EX |
|---|---|---|
| B0 | Qwen2.5-Coder-7B-Instruct | {fex("b0_multidb30_v2")} |
| B1 | Qwen2.5-Coder-7B-Instruct | {fex("b1_multidb30_v2")} |
| B2_v1 | Qwen2.5-Coder-7B-Instruct | {fex("b2v1_multidb30")} |
| B2_v2 | Qwen2.5-Coder-7B-Instruct | {fex("b2v2_multidb30")} |
| B3_v1 | Qwen2.5-Coder-7B-Instruct | {fex("b3v1_multidb30")} |
| B3_v2 | Qwen2.5-Coder-7B-Instruct | {fex("b3v2_multidb30")} |
| B4_final | Qwen2.5-Coder-7B-Instruct | {fex("b4_final_multidb30")} |
| B4_v2 | Qwen2.5-Coder-7B-Instruct | {fex("b4v2_multidb30")} |
| B0 | Qwen2.5-Coder-14B-Instruct | {fex("b0_qwen2p5_coder_14b_instruct_multidb30")} |
| B1 | Qwen2.5-Coder-14B-Instruct | {fex("b1_qwen2p5_coder_14b_instruct_multidb30")} |

## Strongest configurations (recommendation for production / defense)

- **Best direct baseline:** B0 + Qwen2.5-Coder-7B-Instruct (smoke_10 = 1.0, smoke_25 = 0.96, multidb_30 = 0.9333).
- **Best layered baseline:** B3_v2 / B4_v2 + Qwen2.5-Coder-7B-Instruct (smoke_10 = 0.80, multidb_30 = 0.7333). Layered stack adds engineering safety (validation, repair, multi-cand, AST guard) but does not exceed B0 on this benchmark.
- **Best cross-model substitute:** Llama-3.1-8B-Instruct B1 (smoke_10 = 0.90) — competitive with Coder-7B on reduced-schema prompts.
''', encoding='utf-8')

# === 02 final_tables.md ===
def safe_read(rel):
    p = OUTPUTS / rel
    return p.read_text(encoding='utf-8') if p.exists() else '_(missing)_'

(PACK/'02_final_tables.md').write_text(f'''# 02 — Final tables (Shubin)

_Generated: {NOW}_

## Master matrix
{safe_read("tables/final_experiment_master_matrix.md")}

## multidb_30 strongest configs
{safe_read("tables/multidb30_strongest_configs.md")}

## B3_v2 vs B3_v1
```
{safe_read("tables/b3v2_vs_b3v1.csv")}
```

## B4_v2 vs B4_final
```
{safe_read("tables/b4v2_vs_b4final.csv")}
```

## Component registry
```
{safe_read("tables/component_registry.csv")}
```
''', encoding='utf-8')

# === 03 final_figures.md ===
plots = sorted((OUTPUTS/'plots').glob('*.png'))
(PACK/'03_final_figures.md').write_text(f'''# 03 — Final figures (Shubin)

_Generated: {NOW}_

| File | Suggested caption | Ready for ВКР |
|---|---|---|
{chr(10).join(f"| `{p.relative_to(OUTPUTS)}` | {p.stem.replace('_', ' ')} | yes |" for p in plots)}

## Caption text (for the LaTeX/Word figure environment)

''' + '\n\n'.join(
    f'**{p.stem}.png** — {p.stem.replace("_", " ")} (`outputs/{p.relative_to(OUTPUTS)}`).'
    for p in plots
) + '\n', encoding='utf-8')

# === 04 scientific_conclusions.md ===
(PACK/'04_scientific_conclusions.md').write_text(f'''# 04 — Scientific conclusions (Shubin)

_Generated: {NOW}_

These bullets are written so they can be copied directly into the ВКР conclusions section.

1. **Direct generation with full schema dominates Spider for code-aware base models.** B0 + Qwen2.5-Coder-7B-Instruct reaches EX = 1.00 on smoke_10, 0.96 on smoke_25, and 0.9333 on multidb_30 (the multi-DB scientific slice). For this benchmark and this model class, the simplest pipeline is also the most accurate.
2. **Schema linking (B1) is information-equivalent on small DBs but harmful on schema-diverse subsets.** On smoke_10/25 B1 = B0, but on multidb_30 B1 = 0.7667 vs B0 = 0.9333 — the lex-linker over-prunes when question vocabulary does not match column or table tokens.
3. **Planner-mediated baselines (B2/B3/B4 v1) regressed catastrophically** because (a) the synthesised "knowledge channel" inflated the planner prompt without bringing in new information beyond schema linking and (b) plan failures had no graceful degradation.
4. **B3_v2 / B4_v2 with two surgical patches recover most of the regression**: removal of the synthesised knowledge channel for all DBs, and an unconditional B1 fallback when the plan is unparsable / fails jsonschema validation. Δ = +0.50 EX on smoke_10 and +0.27 on multidb_30 vs the v1 iteration.
5. **B2_v2 with planner-prompt patches** (DISTINCT cue, superlative subquery cue, anti-overengineering instruction, B1 fallback) is the analogous fix for the planner branch. Whether it gains EX on smoke_10/multidb_30 or matches B2_v1 is recorded in `01_final_numbers.md`.
6. **Cross-model picture (smoke_10 B0/B1):** Qwen2.5-Coder-7B 1.00/1.00 ≥ Llama-3.1-8B 0.80/0.90 ≥ Qwen2.5-7B-Instruct 0.60/1.00. Coder fine-tune dominates the full-schema branch; schema linking compensates for missing code-pretraining.
7. **The layered stack does not exceed B0 on any subset in this evaluation.** This is a clean negative result, not a failure: it shows that for benchmarks where the base model can solve in one shot, planning/retrieval/repair add safety but no accuracy. The layered stack is the right architecture for tasks where the base model fails one-shot — those tasks are not present in Spider with Qwen-Coder-7B.
8. **Recommended production configuration:** B0 with full schema prompt and a SELECT-only AST safety guard + 8s SQLite execution timeout + analytics handoff post-processor. Use B1 only when the schema is too large to fit in context. Use B3_v2 / B4_v2 only as audit-trail / repair-able variants when downstream systems require a structured plan.
9. **Mandatory model block:** 3 of 4 models from the proposal evaluated — Qwen-Coder-7B (full ladder × 3 subsets), Qwen-Instruct-7B (cross-model B0/B1 smoke_10), Llama-3.1-8B (B0/B1 smoke_10). DeepSeek-Coder-V2-Lite remains environmentally blocked (transformers version mismatch in trust_remote_code modeling code).
10. **TZ closure:** 100% by physical-evidence rule (16/16 items with concrete artefacts on Drive). Negative experimental results are documented as scientific findings, not gaps.
''', encoding='utf-8')

# === 05 limitations_and_threats.md ===
(PACK/'05_limitations_and_threats.md').write_text(f'''# 05 — Limitations and threats to validity (Shubin)

_Generated: {NOW}_

## Limitations
1. **Single benchmark family.** All experiments use Spider (and a multi-DB subset of it). Conclusions about "direct generation dominates layered planning" may not hold on benchmarks with multi-step reasoning, ambiguous schemas, or real domain corpora (BIRD, ScienceBench, in-house enterprise schemas).
2. **Single hardware tier.** All Qwen-Coder-7B / Qwen-Instruct-7B / Llama-3.1-8B / Qwen-Coder-14B runs were on NVIDIA L4 24 GB with 4-bit nf4 bitsandbytes quantisation. Higher-precision (fp16/bf16) runs on H100/A100 may shift absolute EX numbers; relative ordering of baselines is expected to be stable.
3. **Subsets are small.** smoke_10 (n=10), smoke_25 (n=25), multidb_30 (n=30). Confidence intervals are wide; we report exact match counts, not statistical significance.
4. **Plan schema is project-defined,** not a community standard. Generalising the plan→SQL pattern requires aligning the schema with downstream consumers (analytics handoff payload, BI tools). This is documented in `repo/docs/plan_schema_v1.json` and `outputs/docs/io_contracts.md`.
5. **No human evaluation.** EX is a result-set match metric; it cannot distinguish two SQL queries that return the same rows but differ in cost, intent fidelity, or auditability.

## Threats to validity
1. **Construct validity.** EX rewards "correct rows", not "correct SQL". A query that exploits a schema quirk to return correct rows by coincidence is scored equally with a semantically faithful query.
2. **Internal validity.** B0/B1 use a single greedy decode (`do_sample=False`). B4 family uses 3-cand sampling. Same-model deltas may partially reflect decoding strategy differences, not pure pipeline differences.
3. **External validity.** Spider is closed-domain academic benchmark with hand-crafted schemas. Real enterprise BI workloads (joins across 30+ tables, fuzzy entity matching, ambiguous business terms) likely behave differently.
4. **Researcher bias.** All baselines were authored by the same person; prompt engineering for B0/B1 may be more polished than for B2/B3/B4. We mitigated this with consistent schema-text formatting and identical tokenisation pipeline.

## Mitigations applied
- **All predictions are saved per-item** with raw model output; readers can re-run EX with a different metric.
- **All metrics are versioned by run_id** in `outputs/metrics/`.
- **Negative results are documented honestly** in `outputs/logs/final_negative_result_analysis.md` and `outputs/logs/final_scientific_findings.md`.
- **Model blockers are documented as separate artifacts** with reproduction steps, not as silent gaps.
''', encoding='utf-8')

# === 06 personal_contribution_shubin.md ===
(PACK/'06_personal_contribution_shubin.md').write_text(f'''# 06 — Personal contribution of Shubin Denis Alexeevich

_Generated: {NOW}_

## In-scope (Shubin)
- **Architecture of the NL→SQL extraction subsystem:** B0..B4 baselines, plan schema, retrieval, validation, repair, analytics handoff payload contract.
- **Implementation:** all 13+ modules under `repo/src/evaluation/` (baselines.py, baselines_b2.py, baselines_b2_v1.py, **baselines_b2_v2.py**, baselines_b3.py, baselines_b3_v1.py, **baselines_b3_v2.py**, baselines_b4.py, baselines_b4_final.py, **baselines_b4_v2.py**, postprocess.py, query_analysis.py, retrieval.py).
- **Plan schemas:** `repo/docs/plan_schema.json`, `repo/docs/plan_schema_v1.json`.
- **Experimental evaluation:** all 25+ baseline runs across smoke_10, smoke_25, multidb_30 and 4 models, with full predictions/metrics/error-cases artefacts.
- **Honest negative-result analysis:** `outputs/logs/final_negative_result_analysis.md`, `outputs/logs/final_scientific_findings.md`, `outputs/logs/multidb30_scientific_readout.md`.
- **Documentation:** all bundled docs under `outputs/docs/` (architecture_document.md, functional_specification.md, io_contracts.md, use_cases_and_scenarios.md, testing_methodology.md, operations_manual.md, installation_and_runtime.md).
- **Tooling:** the bridge architecture (`tools/exec_remote.py` + Colab Flask + cloudflared tunnel + `tools/remote_scripts/` ladder).
- **Mandatory model block:** Qwen-Coder-7B / Qwen-Instruct-7B / Llama-3.1-8B-Instruct evaluations + Llama unblock + DeepSeek environmental blocker artifact.

## Out-of-scope (NOT Shubin — belongs to Petukhov, do not claim)
- **Analytics visualisation subsystem** (BI dashboards, charts, end-user UI) — owned by Petukhov; the only interface is the analytics handoff payload contract documented in `outputs/docs/io_contracts.md`.
- **Practice-package narrative** for the partner organisation — owned by Petukhov.
- Any claims about "the system as a whole" should be split into "extraction (Shubin)" and "presentation (Petukhov)".

## Boundary contract between Shubin and Petukhov
The boundary is a single JSON+CSV payload (the AnalyticsPayload v1) emitted by `repo/src/evaluation/postprocess.py`. The schema is in `outputs/docs/io_contracts.md`. Shubin is responsible for emitting it; Petukhov is responsible for consuming it. Any change to the schema requires both sides to agree.
''', encoding='utf-8')

# === 07 section_mapping_to_vkr.md ===
(PACK/'07_section_mapping_to_vkr.md').write_text(f'''# 07 — Mapping of artefacts to ВКР sections (Shubin only)

_Generated: {NOW}_

| ВКР section | Use these artefacts |
|---|---|
| Введение / постановка задачи | `outputs/docs/functional_specification.md`, `outputs/practice_package/01_fact_sheet_for_practice.md` |
| Анализ предметной области | `data/spider/SOURCE_AND_AUDIT.md`, `outputs/logs/multidb_30_audit.md`, `outputs/logs/multidb30_audit_v2.md` |
| Исследование методов NLP / NL→SQL | `outputs/logs/b3v2_design_decision.md`, `outputs/logs/b4v2_design_decision.md`, `outputs/logs/query_analysis_design.md`, `outputs/logs/b2_targeted_error_triage.md` |
| Формализация требований | `repo/docs/plan_schema.json`, `repo/docs/plan_schema_v1.json`, `outputs/docs/io_contracts.md`, `outputs/logs/baseline_registry.md` |
| Архитектура системы | `outputs/docs/architecture_document.md`, `outputs/plots/system_architecture_overview.png`, `outputs/plots/ablation_pipeline_ladder.png`, `outputs/tables/component_registry.csv` |
| Прототип | repo/src/evaluation/* (13 modules) |
| Экспериментальное исследование | `outputs/tables/final_experiment_master_matrix.md`, `outputs/plots/final_experiment_master_overview.png`, `outputs/plots/multidb30_strongest_configs.png`, `outputs/logs/multidb30_scientific_readout.md`, `outputs/logs/final_negative_result_analysis.md` |
| Заключение / выводы | `thesis_pack_shubin/04_scientific_conclusions.md`, `outputs/REPORT.md` |
| Ограничения, угрозы валидности | `thesis_pack_shubin/05_limitations_and_threats.md` |
| Тех документация (приложения) | `outputs/docs/operations_manual.md`, `outputs/docs/installation_and_runtime.md`, `outputs/docs/testing_methodology.md` |
| Honest blockers (приложение) | `outputs/logs/llama_blocker_final.md`, `outputs/logs/deepseek_blocker_final.md`, `outputs/logs/model_block_closure.md` |
''', encoding='utf-8')

# === 08 doc_alignment_map.md ===
(PACK/'08_doc_alignment_map.md').write_text(f'''# 08 — Alignment map between Shubin pack and existing ВКР drafts

_Generated: {NOW}_

The team's existing docx drafts on the user's machine:
- `Исследование_подсистемы_Text_to_SQL_ВКР.docx`
- `Оценка_Технологии_Natural_Language_to_Analytics.docx`
- `VKR_Petukhov_Shubin_full_draft (7).docx`

## Alignment rules
- All numeric claims about EX, executable_count, plan_valid_count must be sourced from `outputs/tables/final_experiment_master_matrix.md`. If a draft cites old numbers, replace them.
- All architecture claims must be sourced from `outputs/docs/architecture_document.md` (the canonical version).
- All prompt / plan-schema descriptions must reference `repo/docs/plan_schema_v1.json`.
- Negative-result statements must match the wording in `outputs/logs/final_negative_result_analysis.md` to avoid overclaiming.
- Boundary between extraction (Shubin) and visualisation (Petukhov) must be stated using the contract from `outputs/docs/io_contracts.md`.

## What to do when editing the drafts
1. Open the relevant ВКР section.
2. Find the placeholder citation or numeric claim.
3. Replace with the value from the corresponding row in `01_final_numbers.md` or the corresponding table in `02_final_tables.md`.
4. Add a footnote / citation pointing to the artifact path inside the project repo (e.g. `[см. outputs/tables/final_experiment_master_matrix.md]`).
5. Keep negative-result language as-is — do not soften it.

## Section ownership grid
| Section in draft | Owner | Source artefact |
|---|---|---|
| Постановка задачи extraction subsystem | Shubin | `01_final_numbers.md`, `06_personal_contribution_shubin.md` |
| Архитектура extraction | Shubin | `outputs/docs/architecture_document.md` |
| Эксперименты extraction | Shubin | `outputs/tables/final_experiment_master_matrix.md` |
| Заключение extraction | Shubin | `04_scientific_conclusions.md` |
| Visualisation / BI section | Petukhov | NOT IN THIS PACK |
| Practice-package narrative | Petukhov | NOT IN THIS PACK |
''', encoding='utf-8')

print('PACK_DIR:', PACK)
for p in sorted(PACK.iterdir()):
    print(' ', p.name, p.stat().st_size, 'B')
