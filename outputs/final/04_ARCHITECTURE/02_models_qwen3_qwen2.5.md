# 3.2.2 Модели: Qwen3-Coder-30B-A3B (planner) + Qwen2.5-Coder-7B (emitter)

## Главный тезис

В работе используется **пара open-weight моделей**: **Qwen3-Coder-30B-A3B-Instruct** (Mixture-of-Experts, 30 миллиардов общих параметров, ~3B активных параметров на токен) выполняет роль **планировщика** (planner), а **Qwen2.5-Coder-7B-Instruct** — роль **эмиттера** SQL (emitter). Обе модели запускаются в BF16 precision (без quantization), без supervised fine-tuning, через библиотеку `transformers` от Hugging Face. Общий VRAM footprint обеих моделей в памяти: ~76 GB на A100 80 GB (с запасом ~3 GB для activations).

Выбор именно этой пары — компромисс между четырьмя ограничениями:

1. **Open-weight constraint** (исключает GPT-4, Claude, Gemini, o3, o1).
2. **Параметрический бюджет ≤30B** total параметров planner-а (исключает DeepSeek-V3 685B, GPT-OSS-120B, Llama 405B).
3. **Bandwidth A100 80 GB** (исключает любой single-GPU 70B+ stack в BF16).
4. **Coder-specific tuning** (исключает general Llama-class, Qwen-base без Coder, и т.п.).

## Qwen3-Coder-30B-A3B как planner

| Характеристика | Значение |
|---|---|
| Architecture | Mixture-of-Experts transformer |
| Total parameters | ~30B |
| Active parameters per token | ~3B (A3B) |
| Precision | BF16 |
| Memory footprint | ~60 GB VRAM |
| Context length | до 128K tokens (используем ~32K в practice) |
| Тренировочный домен | Code (general code generation + SQL fine-tune) |
| Год выпуска | 2025 (Q3-Q4) |
| Hugging Face alias (в наших scripts) | `qwen3_coder_30b_bf16` |

Загрузка через `model_registry_v17.load_model_and_tokenizer('qwen3_coder_30b_bf16')` — см. [08_CUSTOM_TOOLS/08_runner_orchestration.md](../08_CUSTOM_TOOLS/08_runner_orchestration.md). Inference занимает ~80-90s на одну plan-JSON генерацию длиной ~1000-1500 tokens на 32K-token prompt.

**Почему MoE A3B для planner-а**: planner делает один шаг reasoning над схемой (выбор tables/columns/operations), не требует длинных decoding sequences (output типично ~1-2K tokens). MoE даёт характеристики 30B модели по reasoning quality при cost ~3B active params per token — выгодно на длинных prompt-ах (наш Snow pack может быть 35-40K characters = ~10-15K tokens). Альтернативный dense 30B model дал бы примерно ту же quality но в ~10× slower inference.

**Trade-off**: MoE inference на единственном GPU имеет особенности — routing overhead и memory layout не идеальны при batch=1. Для production deployment с тысячами concurrent users dense model 14B мог бы дать лучше throughput. Для нашего исследовательского scope (sequential single-task processing) MoE — рациональный выбор.

## Qwen2.5-Coder-7B как emitter

| Характеристика | Значение |
|---|---|
| Architecture | Dense decoder-only transformer |
| Total parameters | ~7.6B |
| Active parameters per token | ~7.6B |
| Precision | BF16 |
| Memory footprint | ~14-15 GB VRAM |
| Context length | до 32K tokens (используем ~16K typically) |
| Тренировочный домен | Code (Coder line, primary) |
| Год выпуска | 2024 |
| Hugging Face alias | `qwen2_5_coder_7b` |

Загрузка через `model_registry_v17.load_model_and_tokenizer('qwen2_5_coder_7b')`. Inference: ~10-30s на SQL длиной 300-1500 tokens.

**Почему Qwen2.5-Coder-7B для emitter-а**: эмиссия SQL по уже сформированному plan-JSON — mechanically простая задача (формирование SQL текста по слотам); это близко к code completion / fill-in-the-middle, где Qwen2.5-Coder-7B имеет сильные результаты на public bench-ах (e.g., HumanEval +83.5%, MBPP +75.8% per Qwen technical report). Использовать здесь 30B-class модель — overkill.

**Critical observation про aider Polyglot**: согласно research dossier [§4 aider, см. `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md`], **Qwen2.5-Coder-7B теряет ~30% accuracy на Polyglot benchmark при переключении edit-format от whole-file к diff-patch** на файлах <200 LOC. Это **direct evidence**, что на Spider2-DBT lane (где наш agent должен производить diff-patches к DBT-models) Qwen2.5-Coder-7B имеет structural disadvantage. Это объясняет почему DBT lane стоит на 13.2% (Phase 11 baseline) и не двигается с upgrade-ом моделей — проблема в edit format, не в model capability. Phase 31 territory (out of scope для current dossier).

## Сравнение с альтернативами

Phase 17 (`outputs/REPORT_SPIDER2_V17.md` + memory `spider2_phase17_findings.md`) — **model swap pilot10 grid**, систематически тестировал четыре model-family по две lanes (BQ + Snow). Сводка результатов:

| Model | Family | Params | BQ pilot10 (Phase 16 stack) | Snow pilot10 (Phase 16 stack) |
|---|---|---|---|---|
| **Qwen2.5-Coder-7B-Instruct** | Coder | 7B | 5/10 schema_valid | 0/10 (Snow grounding не fixed yet) |
| **Mistral-7B-Instruct (v0.3)** | General | 7B | 1/10 schema_valid | 0/10 |
| **Mistral-7B-Instruct BF16** | General | 7B | 1/10 | 0/10 |
| **Qwen3-14B (general)** | General | 14B | 3/10 | 0/10 |
| **Qwen3-Coder-30B-BF16** (joint emit) | Coder | 30B (dense) | 4/10 | 0/10 |

**Главный вывод Phase 17**: **family > scale**. Coder-line моделей (Qwen2.5-Coder-7B) превосходят general-line моделей с равным или большим size (Mistral-7B, Qwen3-14B). Это согласуется с literature: CodeS-15B [Li et al., SIGMOD 2024] и Qwen2.5-Coder family имеют specialized SQL-tuning, влияющий выше любого general LLM с тем же или большим size.

После Phase 17 выбор закрепился: emitter = Qwen2.5-Coder-7B. Planner — был переключён с Qwen3-Coder-30B (dense, joint emit) на Qwen3-Coder-30B-A3B (MoE) в Phase 25 после релиза MoE-варианта.

## Соответствующие альтернативы в литературе

| System / Model | Params | Primary technique | Best Spider2-Snow EX | Status в нашей работе |
|---|---|---|---|---|
| **CodeS-15B (SFT)** | 15B | SFT on Spider1 train | 0.0% | rejected (SFT prohibited; transferability failure) |
| **Arctic-Text2SQL-R1** | unknown (Snowflake) | Hybrid SFT R1-reasoner + agent | 75.14% (via Arctic-FLEX) | closed-weights — не reproducible |
| **DSR-SQL + DeepSeek-R1** | 685B base | zero-shot decoupled reasoning | 63.80% | out of param budget (DeepSeek-R1 685B) |
| **AutoLink + DeepSeek-R1** | 685B | iterative schema linking | 54.84% | out of param budget |
| **ReFoRCE + o3** | closed | three-component self-refine | 62.89% | closed-weight |
| **Spider-Agent + Qwen3-Coder-30B-A3B** | 30B | ReAct agent | 31.08% | **same base model class as ours** — used as direct upper bound for open-weight ≤30B |
| **Spider-Agent + QwQ-32B** | 32B (Q-reasoning) | ReAct | 8.96% | open but reasoning family — significantly worse |
| **Наш v28-revert-A** | 30B + 7B | Plan→Emit scaffolding | **23.76 % Snowflake EXPLAIN-pass (\*)** (130/547, plan-level acceptance — see [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md); cross-metric vs leaderboard row-match) | reference |

Источники: research dossier `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md` §1 (Snow leaderboard) и §4 (per-system summaries).

**Чем мы отличаемся от Spider-Agent + Qwen3-Coder (31.08% Snow)** при той же base model: мы НЕ используем ReAct agent loop. Мы используем single-pass plan→emit pipeline с post-processing. Это:

| Аспект | Spider-Agent (ReAct) | Наш v28-revert-A (Plan→Emit) |
|---|---|---|
| **Iterations per task** | Multi-step (bash + filesystem tools) | Single-pass (одна plan + одна emit) |
| **Schema linking** | Implicit (через bash exploration) | Explicit (BM25 + per-task partition) |
| **Validator** | Imlicit (model decides when to terminate) | Explicit layered (JSON + AST + engine) |
| **Wall time per task** | minutes to hours | seconds |
| **Cost in token budget** | Высокий (many tool-use calls) | Низкий (~2 LLM calls) |
| **Snow** | 31.08 % row-match (paper) | **23.76 % EXPLAIN-pass (\*)** (cross-metric — Spider-Agent paper is row-match, we report plan-acceptance) |

При equal model class, наш pipeline трудно превзойти Spider-Agent ReAct без F3 self-refine (Phase 29). Spider-Agent имеет преимущество в multi-step exploration; мы — в structured pipeline и быстром inference. С F3 self-refine + F2 JOIN-graph (Phase 30) ожидаем достичь зоны 35-45% EX, что соответствует Spider-Agent + lower-budget closed models (e.g., Claude-3.5-Sonnet 19.34%).

## Параметры inference

### Planner

```python
_gen_planner(prompt, max_new=1100)
# Sampling: temperature ~0.4-0.6 (deterministic-leaning)
# Output format: JSON план (см. 05_planner_emitter_decomposition.md)
# Stop tokens: }, max_new_tokens reached
```

### Emitter

```python
_gen(prompt, max_new=900)
# Sampling: temperature ~0.3 (very deterministic)
# Output format: ```sql ... ``` block (parsed by _extract_sql)
# Stop tokens: ```, max_new_tokens reached
```

Полные definitions в `tools/remote_scripts/_phase27_snow_runner.py` lines 30-77. См. [08_CUSTOM_TOOLS/08_runner_orchestration.md](../08_CUSTOM_TOOLS/08_runner_orchestration.md).

## Затраты VRAM в практике

| Состояние | VRAM allocated |
|---|---|
| Idle (kernel just started) | 0 GB |
| Qwen2.5-Coder-7B loaded | ~15 GB |
| + Qwen3-Coder-30B-A3B loaded | ~76 GB (cumulative) |
| Peak во время planner inference (~32K context) | ~78-79 GB (within 80 GB limit) |
| Peak во время emitter inference (~16K context) | ~78 GB |

A100 80 GB достаточен с запасом ~1-2 GB. На A100 40 GB BF16 enable приведёт к OOM — phase 23 это показал на concurrent inference attempt (см. memory `spider2_phase23_findings.md`).

## Trade-off: planner cost на простых бенчмарках

Phase 17-18 показали, что **на Spider 1.0 / BIRD** (где задачи в среднем проще, schemas меньше) decomposed pipeline (planner → emitter) даёт **−0.033 EX** относительно joint emit (один Qwen2.5-Coder-7B напрямую генерирующий SQL). Это согласуется с DIN-SQL findings [Pourreza & Rafiei, NeurIPS 2023, arXiv 2304.11015]: *"decomposed CoT hurts easy queries"*. Простой query не требует сложного reasoning over schema — direct emit достаточен.

**Mitigation на момент защиты**: на Spider1/BIRD мы можем bypass planner и использовать только emitter (Family B direct emit). Phase 1-17 это и делалось. На Spider 2.0 family decomposition необходим — без plan-JSON validator не может проверить identifier residency.

Идеальное решение — **complexity router** (детектор «простая или сложная задача?» → переключение в joint emit vs plan-then-emit). Не реализован в текущей версии — direct emit для Spider1/BIRD, plan→emit для Spider2 — обоснованное упрощение.

## Особые наблюдения

### MoE и schema linker «mismatch»

В практике observed: Qwen3-Coder-30B-A3B (MoE) иногда **выбирает таблицу не из топ-3 pack hits**, а из 5-7-го места. Это поведение consistent с MoE routing — некоторые experts могут систематически предпочитать «менее обычные» tokens в input context. Не блокирующее, но создаёт occasional «model выбрал необычную таблицу, validator её принял (она в pack), engine её отверг (не та в реальности)» — это часть **column-name hallucination** failure class, обсуждаемой в [09_RESULTS_ANALYSIS/06_failure_analysis_remaining.md](../09_RESULTS_ANALYSIS/06_failure_analysis_remaining.md).

### Emitter на длинных context-ах

Qwen2.5-Coder-7B при context >24K показывает occasional degradation (повторение блоков, отказ закрывать SQL fence). Mitigation в нашем pipeline: prompt budget held ≤16K, pack capped at max_tables=10 × max_cols_per_table=22 ≈ 220 columns. Этот budget основан на empirical sweet-spot — не размер pack, а его density.

## Cross-references

- Детали planner-emitter контракта (plan-JSON format) → [05_planner_emitter_decomposition.md](./05_planner_emitter_decomposition.md)
- Pack budget rationale → [04_pack_builder_v18.md](./04_pack_builder_v18.md)
- DBT-specific edit format challenges → [05_PIPELINES/05_spider2_dbt_pipeline.md](../05_PIPELINES/05_spider2_dbt_pipeline.md)
- Spider1/BIRD direct-emit option → [05_PIPELINES/01_spider1_pipeline.md](../05_PIPELINES/01_spider1_pipeline.md), [05_PIPELINES/02_bird_pipeline.md](../05_PIPELINES/02_bird_pipeline.md)
- Model load implementation → [08_CUSTOM_TOOLS/08_runner_orchestration.md](../08_CUSTOM_TOOLS/08_runner_orchestration.md) (`_phase25_load_models.py`)
- Open-source Text-to-SQL models survey → [02_RELATED_WORK/03_open_source_text2sql_models.md](../02_RELATED_WORK/03_open_source_text2sql_models.md)
- Phase 17 model swap pilot10 details → [06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md)

## Источники для этого раздела

| Утверждение | Источник |
|---|---|
| Phase 17 «family > scale» grid | `outputs/REPORT_SPIDER2_V17.md`; memory `spider2_phase17_findings.md` |
| Qwen2.5-Coder-7B drops ~30% on diff-patch <200 LOC | research dossier `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md` §4 aider |
| DIN-SQL «decomposed CoT hurts easy queries» | Pourreza & Rafiei, NeurIPS 2023, arXiv 2304.11015 |
| ReFoRCE 62.89% Snow EX | research dossier §1 |
| Spider-Agent + Qwen3-Coder 31.08% Snow | research dossier §1 |
| CodeS-15B 0.73% Spider2-Lite | research dossier §4 |
| Phase 23 OOM на concurrent inference | memory `spider2_phase23_findings.md` |
| VRAM footprint 76 GB | own measurement `_phase25_load_models.py` final log |
