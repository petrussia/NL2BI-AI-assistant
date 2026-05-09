# Plot captions (ready to paste into ВКР figure environments)

_Generated: 2026-04-30T12:31:29.037908+00:00_

## final_experiment_master_overview.png
Сводная картина: EX по всем 11 baseline-конфигурациям × 3 подмножества Spider (smoke_10, smoke_25, multidb_30) на основной модели Qwen2.5-Coder-7B-Instruct (4-bit nf4). Видно: B0 доминирует на всех subset; v2-варианты восстановили большую часть EX, потерянной в v1.

## multidb30_strongest_configs.png
multidb_30 как master scientific slice: 9 сильнейших конфигураций (B0/B1/B2_v1/B2_v2/B3_v1/B3_v2/B4_final/B4_v2 на Qwen-Coder-7B + B0/B1 на Qwen-Coder-14B где доступно). Главный результат: B2_v2 = 0.80 — единственная structured конфигурация, обогнавшая B1 = 0.7667.

## ablation_pipeline_ladder.png
Ablation lader: эволюция baseline B0 → B1 → B2 → B3 → B4 с указанием, какой компонент добавляется на каждой ступени. Сопровождает архитектурный документ.

## system_architecture_overview.png
Архитектурная диаграмма подсистемы извлечения: NL question → query analysis → schema linking → planner → plan validator → SQL synthesizer → validation gate → multi-cand/repair → executor → postprocess → analytics handoff payload. Граница с подсистемой Петухова — payload v1.

## baseline_progression_smoke10_smoke25.png
EX по smoke_10 и smoke_25 для B0/B1 на Qwen-Coder-7B. Иллюстрация информационной эквивалентности B0 = B1 на small uniform DBs.

## b0_b1_b2_smoke10_bar.png
Прямое сравнение B0 vs B1 vs B2_v0 на smoke_10. Используется в разделе "первые впечатления от planner stack".

## final_project_overview.png
Тройная картина: TZ coverage timeline + EX heatmap + model block status. Подходит для слайда обзора.

## final_ablation_overview.png
Aggregated EX bars по B0..B4_final на Qwen-Coder-7B по всем subset, без детализации по версиям. Для слайдов.
