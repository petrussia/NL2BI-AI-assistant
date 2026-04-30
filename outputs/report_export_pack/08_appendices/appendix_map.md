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
