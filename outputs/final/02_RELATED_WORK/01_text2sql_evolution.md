# 2.1 Эволюция text-to-SQL области

## Назначение раздела

Этот файл — narrative обзор text-to-SQL field, сгруппированный по пяти эпохам (eras). Цель — поместить нашу работу в исторический контекст и обосновать, **почему именно наша архитектурная конфигурация** (BM25 schema linker + closed-set planner + Coder-7B emitter + lane-specific dialect handlers) — рациональный выбор для NL2BI задачи на open-weight ≤30B стэке в 2025-2026 годах.

## Эра 1: Pre-neural (до 2017)

Классический подход к text-to-SQL — **semantic parsing** через grammar-based parsers и lambda calculus representations. Систем как **NaLIR** (Li & Jagadish, VLDB 2014) преобразовывали natural language через dependency parsing к SQL skeleton + slot filling. **Bonifati et al.** (2018 survey) суммируют period.

Limitations:
- Domain-specific grammars не generalized.
- Schema linking — manual rules per database.
- Бенчмарки small (ATIS, GeoQuery, RestaurantsNL — все ≤ thousand queries one domain).

Для нашей работы — historical context only. Современные benchmarks (Spider, BIRD, Spider 2.0) и LLM-based methods полностью overshadow.

## Эра 2: Seq2seq encoder-decoder (2017-2020)

**Spider 1.0** [Yu et al., EMNLP 2018, arXiv 1809.08887] — pivotal benchmark introducing cross-domain evaluation. Catalyst для **seq2seq era**.

Key systems:

- **SqlNet** [Xu et al., 2017] — slot-filling network avoiding sequence-to-sequence direct generation. Achieved ~60% Spider 1.0 EX. Insight: structural slots align better with SQL grammar than open generation.
- **TypeSQL** [Yu et al., NAACL 2018] — adds type-awareness в schema encoding. ~75% Spider on simple/medium subset.
- **IRNet** [Guo et al., ACL 2019] — intermediate representation (SemQL) decouples reasoning from SQL syntax. Best Spider 1.0 result of era ~50% EX overall.
- **RAT-SQL** [Wang et al., ACL 2020] — relation-aware self-attention для schema linking. Achieved ~70% Spider 1.0 EX, established **schema linking как separate first-class problem**.

### Key insight emerging from this era

> Schema linking matters even with neural models. Free generation produces identifier hallucination at rates incompatible with execution accuracy. **Constrained or graph-aware decoding necessary.**

Эта insight — **direct ancestor нашей closed-set planning design** (Phase 18). Без explicit schema linking, neural models произвольно invent column names — failure mode мы видели в Phase 16 audit (95.7% historical failures = true_hallucination).

## Эра 3: Pre-LLM constrained generation (2020-2022)

Bridge между classical seq2seq и LLM era. **Pre-trained encoder-decoder models** (T5, BART) fine-tuned для text-to-SQL with **constrained decoding**.

Key systems:

- **PICARD** [Scholak et al., EMNLP 2021] — incremental SQL parsing during T5 decoding. Token-level grammar constraints prevent syntactic invalid output. ~75-80% Spider 1.0 EX. Innovation: **constraint integration into generation step**, не post-hoc filter.
- **SmBoP** [Rubin & Berant, NAACL 2021] — bottom-up SQL parser. State-of-the-art bottom-up approach.
- **RESDSQL** [Li et al., AAAI 2023] — ranking-enhanced encoder + skeleton-aware decoder. Achieves ~84% Spider 1.0 EX.

### Connections to our work

Constrained decoding influenced our **AST validator + feedback retry** design. We don't constrain SQL token-by-token during emit (LLM decoding constrained tokenization expensive), но мы validate the plan-JSON (output of planner) against closed-set pack и retry. Similar effect — **structural constraints enforced before/after emit step**.

PICARD direct inspiration — its constraint integration validated principle что schema-awareness can be added to neural pipeline без full re-training.

## Эра 4: LLM in-context learning (2022-2024)

GPT-4 release (March 2023) shifted text-to-SQL paradigm к **zero/few-shot prompting закрытыми LLMs**. Most published work это era based on GPT-3.5 / GPT-4 / Claude / Gemini.

### Key systems

#### DIN-SQL [Pourreza & Rafiei, NeurIPS 2023, arXiv 2304.11015]
*Decomposed In-context learning with Self-correction*. Multi-step: classification → schema linking → SQL generation → self-correction. Each step separate LLM call. Achieves ~85% Spider 1.0 dev EX с GPT-4.

**Critical ablation finding**: *"decomposed CoT hurts easy queries"* — **direct evidence** для observation we replicated в Phase 17: planner-emitter decomposition на Spider 1.0 / BIRD дает −0.033 EX vs direct emit. См. подробное обсуждение в [05_PIPELINES/01_spider1_pipeline.md](../05_PIPELINES/01_spider1_pipeline.md).

#### C3-SQL [Dong et al., arXiv 2307.07306]
*Calibration, Conventional prompting, Consistency-enhanced*. Multi-LLM-call ensembling. Marginal gains over DIN-SQL.

#### DAIL-SQL [Gao et al., VLDB 2024, arXiv 2308.15363, github.com/BeachWang/DAIL-SQL]
**Most influential of this era на industrial practice**. Three contributions:
1. **Masked-question retrieval** для few-shot examples — mask domain tokens (table/column names) before similarity match by SQL skeleton.
2. **Self-consistency voting** — multiple sampling + majority pick. +0.4% Spider 1.0, +1% BIRD.
3. **Open-source prompting templates** widely reused.

#### MAC-SQL [Wang et al., COLING 2025, arXiv 2312.11242]
**Multi-agent collaborative framework**. Three agents: decomposer (break question into sub-questions), selector (pick relevant tables), refiner (iterative SQL improvement). Achieves 86.8% Spider 1.0 EX с GPT-4.

**Direct ancestor нашей planner-emitter decomposition + validator-feedback retry**. MAC-SQL's refiner role inspired our retry pattern. Difference: we use single retry on validator fail, MAC-SQL uses multi-turn agent interaction.

#### CHESS [Talaei et al., arXiv 2405.16755, scalingintelligence.stanford.edu/pubs/CHESSpaper/]
Stanford system. Pipeline: schema description generation → keyword extraction → candidate retrieval → query generation → consistency-based selection. Achieved ~88% Spider 1.0 with GPT-4.

**Key contribution**: forces injection of PK/FK columns into retrieved schema set. After BM25 selects по semantic similarity, force-append declared PK/FK + heuristic `*_id` columns. **Direct inspiration для нашей Phase 27 correction 3** (PK/FK heuristic injection в pack builder).

#### Other notable systems

- **DTS-SQL** [Pourreza & Rafiei, EMNLP-F 2024, arXiv 2402.01117] — *Decomposed Text-to-SQL for small LLMs*. Two-stage: schema linking → SQL generation. Achieves 79.9% Spider 1.0 с CodeLlama-13B fine-tuned. **Confirms decomposition помогает small models** — supporting evidence для нашей 7B emitter + decomposition design.
- **MCS-SQL** [Lee et al., COLING 2025, arXiv 2405.07467] — multiple prompts + multiple-choice selection. +2.1% over plain self-consistency on BIRD.
- **RSL-SQL** [arXiv 2411.00073, github.com/Laqcce-cao/RSL-SQL] — robust schema linking with multi-turn correction. +2-5 EX from one-round repair feedback.

### Closing era 4

By 2024 end, **Spider 1.0 considered solved** for closed-API tier (top systems 88-91% EX). BIRD partially solved (top ~73-76% EX). Research focus shifted к **harder benchmarks + open-source competitiveness**.

## Эра 5: Agentic / enterprise (2024-2026)

**Spider 2.0** [Lei et al., ICLR 2025 Oral, arXiv 2411.07763] release in early 2025 marked era shift. Benchmark introduced:
- Multi-database settings (152 DBs in Snow lane).
- Multi-dialect (BigQuery + Snowflake + DuckDB).
- Multi-file transformations (DBT lane).
- Real-world domain knowledge requirements.
- Classical methods (DAIL/CHESS/DIN + GPT-4o) collapse to **0-2.2% EX** на Spider2-Snow.

### Key new systems

#### ReFoRCE [Deng et al., arXiv 2502.00675, github.com/Snowflake-Labs/ReFoRCE]
**Best fully-reproducible system on Spider2 family**. Three components:
1. **Self-Refinement** — execution feedback retry loop.
2. **Format Restriction** — output template controlling SQL structure.
3. **Column Exploration** — iterative INFORMATION_SCHEMA probing для finding relevant columns.

Achieves **62.89% Spider2-Snow** + **55.21% Spider2-Lite** with o3 backbone.

Note from research dossier: *"our prompts are primarily designed for the Snowflake dialect, leading to occasional errors when handling certain cases в the BigQuery dialect"* — implies BQ-specific tooling может outperform ReFoRCE на Lite-BQ subset.

**Direct relevance к нашей работе**: ReFoRCE Self-Refinement is the **F3 self-refine** intervention we deferred к Phase 29. Their Format Restriction echoes наш closed-set plan-JSON output template.

#### AutoLink [arXiv 2511.17190, AAAI 2026]
Iterative schema exploration + expansion. Achieves **91.2% strict schema recall** на Spider2-Lite, **52.28% EX with DeepSeek-R1**, **54.84% EX Spider2-Snow**. Multi-round retrieval с LLM-guided expansion.

**Direct inspiration для нашего planned Phase 30 JOIN-graph BFS expansion**. AutoLink builds schema graph and expands seeds. Our Phase 30 plan reuses этот pattern using F2 SchemaGraphSQL-style real FK metadata.

#### LinkAlign [Wang et al., arXiv 2503.18596, github.com/Satissss/LinkAlign]
**Single most directly relevant paper для нашей Phase 27**. Quote from arXiv abstract:

> *"how to select the correct database from a large schema pool в multi-database settings, while filtering out irrelevant ones. Existing researches always assume single-database schemas."*

— **Описывает точно root cause нашей Phase 26 Snow 0% baseline**. Achieves 33.09 на Spider2-Lite с DeepSeek-R1.

LinkAlign solution: **iterative LLM-guided exploration** к выбору correct DB. Наш Phase 27 F1: **deterministic** `TABLE_CATALOG` filter using `task.db` metadata. Simpler approach since Spider 2.0 annotates `task.db`. LinkAlign's approach scales to production (no annotation), our approach faster для bench (deterministic).

#### SchemaGraphSQL [arXiv 2505.18363]
BFS over FK + name-heuristic edges after BM25 picks seeds. **+4-8 EX on BIRD with zero fine-tuning**. **Recipe для нашего planned Phase 30 F2** (Family C activation на BQ).

#### RASL [Amazon Science, arXiv 2507.23104]
Retrieval-Augmented Schema Linking для массивных DBs. Hybrid dense + sparse retrieval. **Не реализован у нас** — BM25 alone достаточен после per-task partitioning (Phase 27 measurement).

#### CHASE-SQL [Pourreza et al., ICLR 2025, arXiv 2410.01943]
**Multi-path reasoning** + preference-optimized candidate selection. Achieves SOTA on BIRD private test set. **Trains a 7B selector model** that outperforms simple majority voting by **+3-5 EX**.

Our candidate selector — simple priority order, не trained ranker. CHASE-SQL — proven direction для future Phase 31+ work (trained selector model from labeled candidate→correct-execution pairs).

#### Spider-Agent [xlang-ai/Spider2]
Baseline agent for Spider 2.0. ReAct-style loop с bash + filesystem tools. **Caps near 14.7% на DBT regardless of backbone** — это **scaffold ceiling evidence**.

Reference point: Spider-Agent + Qwen3-Coder achieves **31.08% Spider2-Snow**, наш model class direct comparison. Spider-Agent + Claude-3.7-Sonnet 24.50%, + QwQ-32B 8.96% Spider2-Snow.

#### Databao Agent [JetBrains, blog.jetbrains.com/databao/2026/02/]
**#1 на Spider2-DBT (58.82%)**. Methodology disclosed:
- Up-front DB overview.
- Restricted tool surface (no free bash).
- Verifier gate (no Terminate until green dbt run).

**Recipe для нашего planned Phase 31 DBT scaffold redesign**. Database explicit blog quote: *"We made it smarter not by replacing the model, but by changing the environment around it"* — direct evidence что scaffold > model class на DBT lane.

#### SWE-agent [Yang et al., NeurIPS 2024, arXiv 2405.15793, swe-agent.com]
General-purpose agent for software engineering tasks. **Edit-linter-revert ablation: +8 pp on SWE-bench Lite**. Universal lesson: staged verifier loop matters.

Inspirational для DBT lane scaffold (Phase 31), но не SQL-emit lane.

### Closing era 5

By 2026 May (наш cutoff date), Spider 2.0 family — **frontline benchmark** для NL2BI research. Closed-industrial top entries (Genloop 96.70 Snow, SOMA-SQL 72.02 Lite, Databao 58.82 DBT) — proprietary, no paper, no code.

**Reproducible-SOTA tier** anchored на:
- ReFoRCE (o3 backbone, closed reasoning model).
- AutoLink (DeepSeek-R1 685B, open но huge).
- LinkAlign (DeepSeek-R1 685B, open но huge).
- Spider-Agent variants (open ≤32B reference systems).

## Где наш проект сидит в этой evolution

Наша pipeline объединяет три эры:

1. **Эра 4 LLM in-context** наследие — closed-set plan-JSON + AST validator-feedback retry (MAC-SQL ancestry); PK/FK heuristic injection (CHESS ancestry); BM25 schema linking + synonym expansion (RAT-SQL / DTS-SQL ancestry).
2. **Эра 5 agentic** integration — per-task multi-DB partitioning (LinkAlign deterministic version); NUMBER/VARIANT date-cast post-processor (ReFoRCE-style dialect handling).
3. **Single architecture cross-bench** — claim novelty. ReFoRCE Snow-only, AutoLink multi-DB only, CHESS Spider1/BIRD only — каждая система specialized to one benchmark family. **Our single stack achieves non-trivial results on 5 of 6 lanes** (DBT — scaffold-bound).

## Gap acknowledgement: where наша архитектура fundamentally limited

### Limited 1: No iterative reasoning
ReFoRCE Self-Refinement, AutoLink iterative exploration, LinkAlign iterative selection — все используют **multi-call reasoning loops**. Наш pipeline — **single-pass plan→emit** с one validator retry. Это **deliberate simplification** (saves compute, simpler orchestration), но caps potential lift.

Phase 29 F3 self-refine planned — minimal extension к multi-call.

### Limited 2: Single-architecture multi-lane is double-edged
Не специализируется под each lane как ReFoRCE (Snow-optimized) или Databao (DBT-optimized). Trade-off: generalist competitive across multiple lanes but **never best-in-class на one lane**.

### Limited 3: No trained selector
CHASE-SQL trained 7B selector +3-5 EX. Наш simple priority order. **Out of scope** для Phase 28 closure но natural Phase 31+ extension.

### Limited 4: ≤30B param budget
Closed-API top (o3, GPT-5, Claude-3.5-Sonnet) achieve EX 2-4× above наш band. Cannot close с scaffolding alone — requires either larger open model (DeepSeek-R1 685B) или closed-API (out of scope).

См. detailed gap analysis в [09_RESULTS_ANALYSIS/07_publishability_assessment.md](../09_RESULTS_ANALYSIS/07_publishability_assessment.md).

## Cross-references

- Detailed per-system reviews: [02_sota_systems_2024_2026.md](./02_sota_systems_2024_2026.md)
- Open-source models survey: [03_open_source_text2sql_models.md](./03_open_source_text2sql_models.md)
- Agentic frameworks для DBT: [04_agentic_frameworks_for_dbt.md](./04_agentic_frameworks_for_dbt.md)
- Schema linking approaches deep-dive: [05_schema_linking_approaches.md](./05_schema_linking_approaches.md)
- Our pipeline architecture: [04_ARCHITECTURE/01_overview_single_architecture.md](../04_ARCHITECTURE/01_overview_single_architecture.md)
- Spider 2.0 benchmark overview: [03_BENCHMARKS/03_spider2_overview.md](../03_BENCHMARKS/03_spider2_overview.md)
- Phase 27 F1 derivation от LinkAlign: [06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md](../06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md)
- Methodological lessons (catalog probe etc.): [06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md](../06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md)

## Источники

| Утверждение | Источник |
|---|---|
| Spider 1.0 paper | Yu et al., EMNLP 2018, arXiv 1809.08887 |
| RAT-SQL | Wang et al., ACL 2020, arXiv 1911.04942 |
| PICARD | Scholak et al., EMNLP 2021, arXiv 2109.05093 |
| DIN-SQL "decomposed CoT hurts easy queries" | Pourreza & Rafiei, NeurIPS 2023, arXiv 2304.11015 |
| DAIL-SQL | Gao et al., VLDB 2024, arXiv 2308.15363 |
| MAC-SQL | Wang et al., COLING 2025, arXiv 2312.11242 |
| CHESS | Talaei et al., arXiv 2405.16755 |
| Spider 2.0 paper | Lei et al., ICLR 2025 Oral, arXiv 2411.07763 |
| ReFoRCE | Deng et al., arXiv 2502.00675; research dossier §4 |
| AutoLink | arXiv 2511.17190 (AAAI 2026); research dossier §4 |
| LinkAlign quote | Wang et al., arXiv 2503.18596; research dossier §4 |
| SchemaGraphSQL | arXiv 2505.18363; research dossier §4 |
| Databao Agent | JetBrains blog Feb 2026; research dossier §4 |
| SWE-agent | Yang et al., NeurIPS 2024, arXiv 2405.15793 |
| Spider2 leaderboard May 2026 | research dossier §1-3 |
