# 16 — DOCX apply order (1-2 hour insertion plan)

_Generated: 2026-04-30T14:50:05.209628+00:00_

## Goal
Apply the patch-map from `12_docx_patch_map_detailed.md` to the existing draft docx files in 1-2 hours without errors.

## Order of operations

### Step 1 (5 min): Prep
1. Open `outputs/thesis_pack_shubin/01_final_numbers.md` in one window.
2. Open `outputs/thesis_pack_shubin/11_final_insertion_blocks.md` in another.
3. Open `outputs/thesis_pack_shubin/12_docx_patch_map_detailed.md` as the master plan.

### Step 2 (15 min): Insert into `Исследование_подсистемы_Text_to_SQL_ВКР.docx`
1. Replace EX numbers in the experiments section using BLOCK A from `11_final_insertion_blocks.md`.
2. Insert the architecture diagram (`outputs/plots/system_architecture_overview.png`) and the multi-DB plot (`outputs/plots/multidb30_strongest_configs.png`).
3. Replace the ablation table with `outputs/tables/final_experiment_master_matrix.md` (paste only the relevant rows).
4. Append BLOCK D (limitations) as a new subsection.

### Step 3 (15 min): Insert into `Оценка_Технологии_Natural_Language_to_Analytics.docx`
1. Replace the model-block status section with BLOCK E from `11_final_insertion_blocks.md`.
2. Insert `outputs/plots/model_comparison_smoke10.png` and `outputs/plots/model_comparison_multidb30.png`.
3. Insert the head-to-head table from `outputs/tables/qwen14b_vs_qwen7b_comparison.md`.
4. Append BLOCK F (заключение работы) as the closing section.

### Step 4 (30-60 min): Insert into `VKR_Petukhov_Shubin_full_draft (7).docx` (Shubin sections only)
1. Open the doc; jump to the section index for Shubin's sections (do NOT touch Petukhov sections).
2. Section "Постановка задачи (Shubin part)": replace with BLOCK F head.
3. Section "Архитектура (Shubin part)": replace with `architecture_document_v2.md` sections 1-4. Insert architecture overview plot.
4. Section "Эксперименты (Shubin part)": replace EX tables with `01_final_numbers.md`. Insert master overview plot + multi-DB strongest plot.
5. Section "Заключение (Shubin part)": insert BLOCK A from `11_final_insertion_blocks.md`.
6. Section "Граница Шубин/Петухов": insert BLOCK C.
7. Appendix: insert BLOCK E (model block) + reference `outputs/logs/deepseek_blocker_final_h100.md` and `outputs/logs/llama_blocker_final.md`.

### Step 5 (10 min): Final QA pass
1. Spell-check (RU + EN where applicable).
2. Verify all numeric citations match `outputs/tables/final_experiment_master_matrix.md`.
3. Verify all figure references point to existing files in `outputs/plots/`.
4. Verify Shubin/Petukhov ownership grid (section "Section ownership grid" in `08_doc_alignment_map.md`) is respected.

### Step 6 (5 min): Submit
1. Save all docx files.
2. Hand over to the supervisor.

## Don't forget
- DO NOT touch Petukhov's sections.
- DO NOT touch the practice-package narrative.
- DO NOT replace the overall structure — only fill in the Shubin slots.
- DO use `01_final_numbers.md` as the SINGLE source of EX numbers.
