# 2.3 Open-source LLM families for text-to-SQL

## Назначение

Этот файл — survey open-weight LLM families используемых для text-to-SQL, с фокусом на model classes ≤30B параметров (наш constraint). Для каждой family — origin, sizes, training paradigm, known text-to-SQL benchmark scores, и **связь с нашим выбором**.

Closed-API models (GPT-4, Claude, Gemini, o3) — out of scope этой work из-за RQ1 open-weight constraint. Их влияние на field discussed в [02_sota_systems_2024_2026.md](./02_sota_systems_2024_2026.md).

## Качество comparison table (May 2026)

| Family | Open Weights | Sizes | Best Spider1 | Best BIRD | Best Spider2-Lite | Best Spider2-Snow | Our usage |
|---|---|---|---|---|---|---|---|
| Qwen2.5-Coder | ✓ | 0.5B-32B | ~78% (32B FT) | ~62% (32B FT) | ~6% (32B Spider-Agent) | ~5% (32B Spider-Agent) | **Emitter (7B)** |
| Qwen3-Coder | ✓ | 30B-A3B (MoE), 32B dense | (less data published) | (similar) | (similar) | **31.08% (with Spider-Agent ReAct)** | **Planner (30B-A3B)** |
| DeepSeek-Coder | ✓ | 1.3B-33B | strong | strong | (less Spider2 data) | (less Spider2 data) | not used |
| DeepSeek-V2/V3/R1 | ✓ (large) | 16B-685B | excellent | excellent | **52.28% (AutoLink+R1)** | **54.84% (AutoLink+R1)** / **63.80% (DSR+R1)** | not used (685B > naше budget) |
| CodeS | ✓ | 1B-15B | **84.9% (15B FT)** | strong | **0.73%** | n/a | rejected (no SFT path) |
| gpt-oss | ✓ | 20B / 120B | (less data) | (less data) | **21.9% (AI-DIVE+120B)** | (less data) | not used |
| Mistral / Codestral | ✓ | 7B-22B | moderate | moderate | (less data) | (less data) | rejected Phase 17 |
| ChatGLM | ✓ | 6B-130B | (less Spider2 data) | (less data) | (less data) | (less data) | not used |
| Llama / Code Llama | ✓ | 7B-405B | strong | moderate | (less data) | (less data) | not used |
| QwQ / o1-style open reasoning | ✓ | 32B | (less data) | (less data) | **11.33% (Spider-Agent+QwQ)** | **8.96% (Spider-Agent+QwQ)** | not used |

Source: combination of research dossier `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md` (Spider2 numbers) + public model release docs.

## Qwen2.5-Coder family

**Authoring**: Bai et al., Alibaba Cloud (Qwen team).
**Year**: 2024.
**Sizes**: 0.5B / 1.5B / 3B / 7B / 14B / 32B.
**Training**: pretrained on **5.5T code tokens** + 1T natural language; post-trained с SFT + DPO для instruction following.
**License**: Apache 2.0 (most sizes).

### Aider Polyglot leaderboard performance

Polyglot benchmark tests code editing с multiple programming languages. From research dossier §4:

| Size | Polyglot accuracy | Edit format sensitivity |
|---|---|---|
| 7B | ~55.6% | **~30% drop on diff format vs whole-file < 200 LOC files** |
| 14B | ~60% | similar drop pattern, less severe |
| 32B | ~73.7% | minimal drop |

**Critical insight для нашей работы**: Coder-7B significantly weakened on diff-patch edit format. Direct evidence что **DBT lane diff-patch pipeline (90% diff edits, Phase 11) systematically underperforms** — Phase 31 plan switches к multi-block whole-file emit.

### Why we chose 7B for emitter

| Factor | 7B reasoning | 14B alternative | 32B alternative |
|---|---|---|---|
| GPU memory (BF16) | ~14 GB | ~28 GB | ~64 GB |
| Inference latency | ~10-30s per emit | ~20-45s | ~40-90s |
| Spider1/BIRD EX (our pipeline) | 94.0% / 87.9% | est ~94-95% / 88-89% | est ~95% / 89-90% |
| Spider2-DBT impact | ceiling-bound at 13.2% | maybe +2-4 pp (если edit format mitigated) | est +5-10 pp |
| **Total VRAM with 30B planner** | **76 GB ✓ fits A100 80GB** | 88 GB ✗ doesn't fit | 124 GB ✗ requires 2× A100 |

**Decisive factor**: A100 80 GB **fits 30B planner + 7B emitter**, не fits 14B или 32B. Multi-GPU setup out of academic scope. **7B chosen** as marginal-optimum размер для bench targets с available hardware.

### Ablation projection (if we had used 14B or 32B emitter)

Per research dossier evidence:
- **Spider 1.0 / BIRD**: minimal lift expected (already 94%/88% saturated).
- **Spider2-Lite-BQ**: maybe +2-4 pp EX (emitter handles complex BQ subqueries better).
- **Spider2-Snow**: similar +2-4 pp.
- **Spider2-DBT**: largest lift, +5-10 pp from edit format robustness.

Total possible cost: ~+15-20 pp across all benchmarks combined. But not feasible с A100 80 GB constraint.

## Qwen3-Coder family

**Authoring**: Qwen team, Alibaba Cloud.
**Year**: 2025 (Q3).
**Sizes**: **30B-A3B** (Mixture-of-Experts, ~3B active per token), 32B dense.
**Training**: pretrained on extended code corpus + reasoning-focused post-training (RLHF + reasoning trace SFT).
**License**: Apache 2.0.

### Why we chose 30B-A3B for planner

| Factor | 30B-A3B (MoE) | 32B dense | Smaller alternatives |
|---|---|---|---|
| Total params | 30B | 32B | varies |
| Active per token | **~3B** | 32B | n/a |
| GPU memory (BF16) | ~60 GB | ~64 GB | smaller |
| Inference latency | ~60-90s (planner) | ~80-120s | faster but weaker reasoning |
| Reasoning capability | strong (post-trained для CoT) | similar | weaker |
| Spider2-Snow reference (Spider-Agent + similar) | **31.08% open ceiling** | (no published comparison) | varies |

**Decisive factors**:
- **3B-active inference cost** — efficient в наш sequential pipeline. Per-task ~60-90s включая schema linking + pack build.
- **Strong reasoning** — closed-set planning requires understanding question intent over large schema, тип reasoning where 30B-A3B сильнее чем dense 7B/14B.
- **GPU memory fits** с 7B emitter в 76 GB total.

### Spider2-Snow direct evidence

**Spider-Agent + Qwen3-Coder achieves 31.08% Spider2-Snow** (research dossier §1). Это direct reference point — same base model class as our planner. Их ReAct loop vs our single-pass plan→emit pipeline — different scaffolds. Наш target: **competitive ≤30B band**.

### MoE inference quirks observed in our pipeline

- **Selection ranks observation**: 30B-A3B иногда выбирает таблицу из top 5-7 BM25 hits, не top 1. Consistent с MoE routing behavior. Не блокирующее.
- **Long-context degradation**: at >24K context, model occasionally repeats SQL fragments. Mitigated by pack budget cap 10×22 columns ≈ 5-8K tokens.

## DeepSeek-Coder family

**Authoring**: DeepSeek-AI.
**Year**: 2024.
**Sizes**: 1.3B / 6.7B / 33B base; V2 (236B MoE), V2.5, V3 (671B), R1 reasoning variant.
**Training**: code corpus pretrain + math/reasoning post-train.
**License**: DeepSeek License (Apache 2.0-derived for some).

### Why not used in наш проекте

- **6.7B / 33B sizes**: similar к Qwen Coder but Phase 17 model swap pilot showed Qwen2.5-Coder family advantage. Switching costs не justified.
- **V2 / V3 / R1**: 236B / 671B / 685B — out of ≤30B constraint.

### DeepSeek-R1 в research dossier

DeepSeek-R1 powers **multiple top reproducible Spider2 systems**:
- AutoLink + DeepSeek-R1: 52.28% Lite / 54.84% Snow.
- LinkAlink + DeepSeek-R1: 33.09% Lite.
- DSR-SQL + DeepSeek-R1: 63.80% Snow (rank 22).

R1 = **open-weight reasoning frontier**. **20× larger** than наш planner (685B vs 30B). Direct comparison unfair; **transferability of techniques** matter:
- AutoLink iterative schema exploration — orthogonal к model size. Could be deployed с smaller model (loss of reasoning depth, but iteration count compensates).
- DSR-SQL decoupled reasoning — requires R1-class capability. Smaller models can't replicate.

## CodeS family

**Authoring**: Li, H. et al., RUCKBReasoning (Renmin University).
**Year**: 2024.
**Sizes**: 1B / 3B / 7B / 15B.
**Training**: **fine-tuned for text-to-SQL** specifically on Spider 1.0 / BIRD train sets.
**License**: open (research dossier didn't note specific license).

### Performance evidence

| Bench | CodeS-15B FT | Our open ≤30B no-SFT |
|---|---|---|
| Spider 1.0 dev | **84.9%** | **94.0%** (above CodeS) |
| BIRD dev | strong | **87.9%** |
| Spider2-Lite | **0.73%** | **34.6%** (Lite-BQ) |
| Spider2-Snow | n/a (likely 0%) | **23.76 % EXPLAIN-pass (\*)** (130/547, see [Appendix 07](../11_APPENDIX/07_critical_metric_caveat.md)) |

### Why we didn't fine-tune

**Two-pronged reasoning**:

1. **Methodological**: Spider 2.0 prohibits fine-tuning on released gold for valid leaderboard submission.
2. **Empirical**: CodeS-15B 84.9% Spider 1.0 → **0.73% Spider2-Lite collapse evidence** что SFT does not generalize across benchmark classes. Fine-tuning на Spider 1.0 patterns over-specializes; transfer к Spider 2.0 enterprise schemas fails.

Naше pipeline aims **cross-benchmark generality** (RQ1) — direct fine-tune-on-bench conflict с этим goal.

**For thesis defense**: CodeS — cautionary tale про SFT on small dataset. Single architecture с prompt engineering achieves higher cross-bench score (especially Spider 2.0 vs SFT 0.73%).

## gpt-oss family

**Authoring**: OpenAI (announced as open-weights initiative 2024).
**Sizes**: 20B / 120B.
**Training**: code + reasoning corpus.
**License**: OpenAI open-weight license.

### Spider 2.0 evidence

- AI-DIVE system + gpt-oss-120B: **21.9% Spider2-Lite** (research dossier §2). Open-weight ≤120B class.

### Why not used

- 120B size — out of ≤30B constraint.
- 20B — smaller variant, less specific text-to-SQL benchmarking published.
- Less developer ecosystem around OpenAI open-weight pipeline в наш timeline.

## Other open models — brief

### Mistral / Codestral
**Mistral-7B-Instruct, Codestral 22B**. Phase 17 model swap pilot10 result: Mistral-7B-Instruct gave 1/10 schema_valid vs Qwen2.5-Coder-7B 5/10. **Rejected Phase 17**. Codestral не tested.

### ChatGLM (THUDM, Tsinghua)
Open-weight models. Less Spider 2.0 data published. Not tested.

### Yi (01.AI)
Open-weight Chinese / English models. Not text-to-SQL specialized. Not tested.

### Llama / Code Llama (Meta)
Open-weight. Strong на BIRD / Spider 1.0 via fine-tuning, less direct Spider 2.0 evidence published. Not tested.

### QwQ-32B (Qwen reasoning variant)
**Spider2-Snow 8.96% (Spider-Agent + QwQ-32B), Spider2-Lite 11.33%** (research dossier §1-2). **Significantly weaker than Qwen3-Coder** на same scaffold. Suggests reasoning-specialized model (QwQ) less suited для structured SQL emit чем Coder-specialized.

### Arctic-Text2SQL-R1 (Snowflake AI Research)
arXiv 2505.20315. Snowflake's fine-tuned R1-style reasoner. Hybrid model + agent. Powers Arctic-FLEX (75.14% Spider2-Snow). **Closed weights** despite arXiv paper.

### XiYan-SQL (Alibaba)
arXiv 2507.04701. Multi-generator + consistency selection. Less detailed open-weight info.

## Naш choice rationale — summary

**Final stack: Qwen3-Coder-30B-A3B planner + Qwen2.5-Coder-7B emitter**.

Reasons:
1. **Open weights compliant** RQ1 constraint.
2. **Total params ≤30B** (planner 30B-A3B ≈ 30B effective; emitter 7B; combined "spider" of params but each model standalone ≤30B).
3. **Fits A100 80 GB** в memory together (76 GB VRAM occupied).
4. **Coder family > general family** (Phase 17 evidence).
5. **Planner-emitter decomposition justified** by DTS-SQL [Pourreza & Rafiei, EMNLP-F 2024] — decomposition helps small (7B) emitters.
6. **No SFT** — generalizes cross-benchmark, avoid CodeS-15B-style transferability failure.
7. **Spider2-Snow direct reference** — Spider-Agent + Qwen3-Coder 31.08% — same base model class.

## Where наш model selection fundamentally limited

### Limit 1: Reasoning capability gap
o3, Claude-Sonnet-4.5, GPT-5, DeepSeek-R1 — все **reasoning-trained models** (RLHF + reasoning traces). 30B-A3B reasoning weaker than 685B R1. Manifests на Spider2-Snow где complex multi-step reasoning required для domain-knowledge tasks (sf_bq099 GA360 funnel analysis class).

Quantitative gap: open ≤30B ceiling ~30% Snow EX vs open ≤685B 50-60% vs closed o3 60+%.

### Limit 2: Coder-7B edit format weakness
Aider Polyglot evidence: ~30% accuracy drop on diff format vs whole-file under 200 LOC. **Directly impacts DBT lane** где multi-file edits dominant. Caps DBT ceiling ~14-22% (наш 13.2%, projected 22-32% после Phase 31 multi-block whole-file switch).

### Limit 3: MoE inference quirks
Qwen3-Coder-30B-A3B MoE routing — occasional column selection from top 5-7 BM25 hits not top 1. Minor effect но measurable.

### Limit 4: No SFT
Avoiding SFT means **no domain adaptation**. Cannot leverage Spider 2.0 train set к improve Spider 2.0 evaluation. Trade-off explicit (cross-bench generality preferred).

## Cross-references

- Text-to-SQL evolution: [01_text2sql_evolution.md](./01_text2sql_evolution.md)
- Per-system reviews: [02_sota_systems_2024_2026.md](./02_sota_systems_2024_2026.md)
- Models architecture detail: [04_ARCHITECTURE/02_models_qwen3_qwen2.5.md](../04_ARCHITECTURE/02_models_qwen3_qwen2.5.md)
- Phase 17 model swap evidence: [06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md)
- Agentic frameworks для DBT (edit format dependency): [04_agentic_frameworks_for_dbt.md](./04_agentic_frameworks_for_dbt.md)
- Publishability assessment (model-class ceiling): [09_RESULTS_ANALYSIS/07_publishability_assessment.md](../09_RESULTS_ANALYSIS/07_publishability_assessment.md)

## Источники

| Утверждение | Источник |
|---|---|
| Qwen2.5-Coder family | Qwen technical report; research dossier §4 |
| Aider Polyglot scores | research dossier §4 aider |
| Qwen3-Coder family | Qwen 2025 release notes |
| CodeS-15B 84.9% / 0.73% | Li et al., SIGMOD 2024, arXiv 2402.16347; research dossier §4 |
| DeepSeek-R1 в Spider2 systems | research dossier §1-4 |
| Spider-Agent + Qwen3-Coder 31.08% | research dossier §1 |
| Spider-Agent + QwQ-32B 8.96% | research dossier §1 |
| AI-DIVE + gpt-oss-120B 21.9% | research dossier §2 |
| Phase 17 model swap pilot10 | memory `spider2_phase17_findings.md` |
| Arctic-Text2SQL-R1 | arXiv 2505.20315 |
| XiYan-SQL | arXiv 2507.04701 |
