# 08 — Alignment map between Shubin pack and existing ВКР drafts

_Generated: 2026-04-30T12:28:47.260219+00:00_

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
