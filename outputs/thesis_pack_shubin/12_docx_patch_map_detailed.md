# 12 — DOCX patch-map detailed (Shubin sections only)

_Generated: 2026-04-30T14:15:29.989758+00:00_

This map tells you exactly where to edit which file and which artefact to use as the source of truth.

## Source-of-truth rules
- All EX numbers → from `outputs/tables/final_experiment_master_matrix.md`.
- All architecture claims → from `outputs/docs/architecture_document.md`.
- All limitations / threats → from `outputs/thesis_pack_shubin/05_limitations_and_threats.md`.
- All defense narrative → from `outputs/thesis_pack_shubin/09_defense_narrative_shubin.md`.
- All ready-to-paste blocks → from `outputs/thesis_pack_shubin/11_final_insertion_blocks.md`.
- All commission Q&A → from `outputs/thesis_pack_shubin/10_answers_to_expected_questions.md`.

## File: `Исследование_подсистемы_Text_to_SQL_ВКР.docx`

| ВКР section (heading text or page approx.) | What to do | Source artefact / block |
|---|---|---|
| Постановка задачи / введение | Replace generic NL→SQL motivation with the Shubin-only scope statement | `11_final_insertion_blocks.md` BLOCK C (boundary) + first paragraph of BLOCK F (заключение работы) |
| Анализ предметной области (если есть) | Add Spider provenance + multi-DB audit | `data/spider/SOURCE_AND_AUDIT.md` (если есть) + `outputs/logs/multidb_30_audit.md` |
| Архитектура подсистемы | Replace any old diagram and component table | `outputs/docs/architecture_document.md` целиком + `outputs/plots/system_architecture_overview.png` + `outputs/plots/ablation_pipeline_ladder.png` |
| Эксперименты | Заменить старые EX-числа на финальные | `01_final_numbers.md` целиком + `outputs/plots/multidb30_strongest_configs.png` |
| Заключение | Вставить BLOCK A | `11_final_insertion_blocks.md` BLOCK A |
| Production-рекомендация | Вставить BLOCK B | `11_final_insertion_blocks.md` BLOCK B |
| Ограничения | Вставить BLOCK D | `11_final_insertion_blocks.md` BLOCK D |

## File: `Оценка_Технологии_Natural_Language_to_Analytics.docx`

| ВКР section | What to do | Source |
|---|---|---|
| Описание модельного блока | Заменить устаревшие model-availability claims | BLOCK E from `11_final_insertion_blocks.md` + `outputs/logs/model_block_closure.md` |
| Сравнение архитектур | Заменить таблицу EX | `outputs/tables/final_experiment_master_matrix.md` |
| Графики | Вставить master overview + multidb30 strongest | `outputs/plots/final_experiment_master_overview.png`, `outputs/plots/multidb30_strongest_configs.png` |
| Заключение | Вставить BLOCK F | `11_final_insertion_blocks.md` BLOCK F |

## File: `VKR_Petukhov_Shubin_full_draft (7).docx`

| ВКР section | What to do | Source |
|---|---|---|
| Раздел Шубина — постановка | Заменить плейсхолдеры на BLOCK F | `11_final_insertion_blocks.md` BLOCK F |
| Раздел Шубина — архитектура | Заменить устаревшую диаграмму на final | `outputs/plots/system_architecture_overview.png` + `outputs/docs/architecture_document.md` секции 1–4 |
| Раздел Шубина — эксперименты | Заменить таблицу EX | `01_final_numbers.md` целиком |
| Раздел Шубина — заключение | Вставить BLOCK A | `11_final_insertion_blocks.md` BLOCK A |
| Раздел границы Шубин/Петухов | Вставить BLOCK C | `11_final_insertion_blocks.md` BLOCK C |
| Приложение — blockers | Вставить BLOCK E + ссылку на `outputs/logs/deepseek_blocker_h100_final.md` | `11_final_insertion_blocks.md` BLOCK E |
| Раздел Петухова | НЕ ТРОГАТЬ | — |
| Practice-package narrative | НЕ ТРОГАТЬ | — |

## What to delete from the drafts (stale content)
- Любые заявления о том, что Llama-3.1-8B-Instruct «не оценена» — теперь оценена (B0 = 0.8000 (8/10), B1 = 0.9000 (9/10)).
- Любые заявления о том, что слойные baseline «дают худший результат» без квалификации — теперь у нас есть B2_v2, обгоняющий B1 на multi-DB.
- Любые placeholder-цифры с пометкой «TBD».
- Любая ссылка на старую версию plan-схемы без `additionalProperties: false`.

## Order of operations recommended for the human writer
1. Открыть `01_final_numbers.md` и `11_final_insertion_blocks.md` рядом.
2. Пройтись по drafts по порядку этой таблицы, делать замены.
3. Прогнать spell-check.
4. Проверить, что все ссылки на artefacts работают (paths начинаются с `outputs/` или `repo/`).
5. Вставить final master plot и multidb30 strongest plot в графический раздел.
6. Submit.
