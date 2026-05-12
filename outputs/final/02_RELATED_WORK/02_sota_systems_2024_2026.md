# 2.2 SOTA системы 2024-2026 — detailed per-system review

## Назначение

Этот файл — **per-system catalog** ~17 систем relevant к нашей работе, ordered approximately by relevance. Каждая система описана в 4-6 блоках: citation header, core idea, metrics, techniques, **связь с нашей архитектурой**.

Источник большинства per-system summaries — research dossier `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md` секция 4. Heavy direct citation.

## 1. ReFoRCE

**Citation**: Deng, M. et al. *Self-Refinement Strategy for Robust ROC and Column Exploration*. arXiv 2502.00675 (Feb 2025).
**Repo**: github.com/Snowflake-Labs/ReFoRCE
**Venue**: arXiv preprint (Snowflake AI Research)

### Core idea

Three-component pipeline для NL2SQL: **Self-Refinement** (execution feedback retry) + **Format Restriction** (output template) + **Column Exploration** (iterative INFORMATION_SCHEMA probing). Designed для Snowflake dialect specifically.

### Best metrics

| Bench | Backbone | Score |
|---|---|---|
| Spider2-Snow | **o3** | **62.89%** (rank 23, top reproducible) |
| Spider2-Snow | o1-preview | 31.26% (paper version) |
| Spider2-Lite | o3 | 55.21% (rank 7) |
| Spider2-Lite | Qwen3 | 35.6% |

Research dossier §1, §2.

### Key techniques

- **Self-Refinement**: on engine error, feed error message back to LLM для one-shot fix attempt. Iterative.
- **Format Restriction**: output SQL constrained к specific template (e.g., starts with `WITH cte AS (...) SELECT ...`).
- **Column Exploration**: agent calls `SHOW COLUMNS FROM table` или `INFORMATION_SCHEMA.COLUMNS WHERE table_name = X` к find relevant columns progressively.
- Snow-dialect optimizations (LATERAL FLATTEN, VARIANT path syntax).

### Связь с нашей архитектурой

**Most directly relevant system для нашей Phase 27-28 work**.

- **Self-Refinement → our planned Phase 29 F3**. We deferred this k Phase 29 (out of dossier scope). ReFoRCE's measurement: Self-Refinement contributes significant fraction of their 62.89% Snow EX. Without F3, we cap ~30% EX zone.
- **Format Restriction → our closed-set plan-JSON**. Both establish output schema before SQL emit. Different mechanism (template constraint vs structured intermediate representation), similar effect.
- **Column Exploration → our BM25 + per-task partition** (Phase 27 F1). Different strategy (iterative LLM probing vs deterministic catalog filter). ReFoRCE more flexible но multi-call expensive. Our approach: cheap, fast, sufficient если `task.db` annotated.
- **Snow dialect specialization → our F4 wrap + F4c regex fallback**. ReFoRCE handles LATERAL FLATTEN / VARIANT через prompting; we handle через AST post-processor. Different mechanism, similar result.

ReFoRCE paper note quoted в research dossier:

> *"our prompts are primarily designed for the Snowflake dialect, leading to occasional errors when handling certain cases в the BigQuery dialect"*

— direct evidence that **dialect-specialized systems trade portability for depth**. Our single architecture sacrifices Snow-depth для cross-bench generality.

## 2. AutoLink

**Citation**: AAAI 2026, arXiv 2511.17190 (Nov 2025).
**Repo**: not publicly disclosed, paper artifact

### Core idea

Iterative schema exploration с LLM-guided expansion. Multi-round retrieval, where each round LLM analyzes current pack and suggests **what to expand** based on partial reasoning.

### Best metrics

| Bench | Backbone | Score |
|---|---|---|
| Spider2-Lite (strict schema recall) | DeepSeek-R1 | **91.2%** |
| Spider2-Lite (EX) | DeepSeek-R1 | **52.28%** |
| Spider2-Snow | DeepSeek-R1 | **54.84%** |

### Key techniques

- **LLM-guided expansion**: agent receives current pack, decides "expand table X with more columns" или "fetch table Y references in current pack".
- **Multi-round retrieval**: 3-7 rounds typical, expanding pack each turn.
- **DeepSeek-R1 685B** backbone — open-weight но massive scale.

### Связь с нашей архитектурой

- **Iterative expansion → our Phase 30 plan**. We plan JOIN-graph BFS expansion (SchemaGraphSQL-style) after initial BM25 pack. AutoLink's expansion is LLM-guided (more flexible); SchemaGraphSQL — deterministic FK-edge BFS (faster, smaller compute budget).
- **Strict schema recall 91.2% → benchmark ceiling**. If recall = 91.2%, EX = 52.28% — gap of 39 percentage points между recall и executable. Most of remaining gap due к SQL generation challenges, не schema linking.
- **685B model class → out of наш ≤30B constraint**. Not directly transferable.

Our trade-off: deterministic retrieval is faster and reproducible, но caps potential lift. AutoLink-style iterative — Phase 30+ direction если we relax ≤30B constraint.

## 3. LinkAlign

**Citation**: Wang, Y. et al. *LinkAlign: Multi-Database Schema Linking for Text-to-SQL*. arXiv 2503.18596 (Mar 2025).
**Repo**: github.com/Satissss/LinkAlign

### Core idea

**Iterative multi-DB schema linking**. Core problem statement (verbatim quote):

> *"how to select the correct database from a large schema pool в multi-database settings, while filtering out irrelevant ones. Existing researches always assume single-database schemas."*

— arXiv 2503.18596

### Best metrics

| Bench | Backbone | Score |
|---|---|---|
| Spider2-Lite | DeepSeek-R1 | **33.09%** |

### Key techniques

- **Iterative selection** через LLM: agent picks DB from candidate list based on partial reasoning.
- Filter irrelevant DBs early before column-level retrieval.
- Strong на multi-DB benchmarks where Spider 1.0 / BIRD don't test.

### Связь с нашей архитектурой

**Most direct intellectual ancestor нашей Phase 27 F1**.

LinkAlign quote was **the** insight что made Phase 27 F1 design clear:
> *"…select the correct database from a large schema pool…"*

— exactly described Spider2-Snow Phase 25 0% baseline root cause.

**Differences в implementation**:
- **LinkAlign**: iterative LLM-guided DB selection. Requires multiple LLM calls per task. Generalizes к scenarios where ground-truth DB не annotated (production deployment).
- **Phase 27 F1**: deterministic `c.db.upper() == task.db.upper()` filter. Single-pass, fast. Works only если bench annotates `task.db` (Spider 2.0 does).

Both reach same outcome (correct DB used для linking), different cost profiles. **For bench evaluation, deterministic wins**. For production, LinkAlign-style needed.

**Lift achieved**: LinkAlign **33.09 % row-match** Spider2-Lite (with DeepSeek-R1 685B). Our v28-revert-A **23.76 % Snowflake EXPLAIN-pass (\*)** on Spider2-Snow FULL 547 with 30B + 7B стек. Cross-metric situation (наш plan-acceptance vs leaderboard row-match) precludes direct ranking; canonical wording — "in the same band as the open-weight Spider-Agent baselines, pending row-match audit" (see [../11_APPENDIX/07_critical_metric_caveat.md](../11_APPENDIX/07_critical_metric_caveat.md)). Different model classes additionally complicate the comparison.

## 4. CHESS

**Citation**: Talaei, S. et al. *CHESS: Contextual Harnessing for Efficient SQL Synthesis*. arXiv 2405.16755.
**Repo**: scalingintelligence.stanford.edu/pubs/CHESSpaper/

### Core idea

Multi-stage pipeline: schema description generation → keyword extraction → candidate retrieval → query generation → consistency-based selection. Multi-agent with **schema-aware retrievals**.

### Best metrics

- Spider 1.0 dev: ~88% EX с GPT-4.
- BIRD: ~58-62% EX с GPT-4.

### Key techniques

- **PK/FK heuristic injection**: после BM25 picks columns, **force-append declared PK/FK + heuristic `*_id` columns**.
- Multi-agent validation (each stage separate LLM call).
- Consistency-based selection across multiple generation candidates.

### Связь с нашей архитектурой

**Direct ancestor PK/FK injection (наша Phase 27 correction 3)**. CHESS rule:

> Force-append PK/FK + heuristic `*_id` columns после BM25 ranking.

Наш `_inject_pk_fk` function в `_phase27_snow_runner.py` реализует именно этот pattern.

**Differences**:
- CHESS full multi-agent stack — multiple separate LLM calls. We use single-pass pipeline с inline injection.
- CHESS multi-agent consistency check — closer к ReFoRCE Self-Refinement в spirit. Naше — single retry on validator fail.

Heuristic patterns мы используем (`id`, `<table_singular>_id`, `*_pk`, `*_fk`, `*_id`, `*_key`, `*_sk`) — same family as CHESS.

## 5. MAC-SQL

**Citation**: Wang, B. et al. *MAC-SQL: A Multi-Agent Collaborative Framework for Text-to-SQL*. COLING 2025, arXiv 2312.11242.

### Core idea

**Multi-agent collaborative framework**: three agents с specialized roles — **decomposer** (break question), **selector** (pick tables), **refiner** (iterative SQL improvement).

### Best metrics

- Spider 1.0: 86.8% EX с GPT-4.
- Strong на BIRD challenging tier через refiner agent.

### Key techniques

- **Question decomposition** into sub-questions per agent role.
- **Schema selector agent** independent от generation.
- **Refiner agent** for iterative correction (ReFoRCE Self-Refinement ancestor).

### Связь с нашей архитектурой

**Direct ancestor нашей planner-emitter decomposition + validator-feedback retry**.

- **Decomposer + selector → our planner**. We collapse two MAC-SQL agents into one (Qwen3-Coder-30B-A3B handles both schema selection и question decomposition в single plan-JSON output).
- **Refiner agent → our planned Phase 29 F3 self-refine**. Currently we have single retry on AST validator fail; full Refiner agent (multi-turn engine error correction) — Phase 29.

**Simplification rationale**: MAC-SQL three separate LLM calls × multiple turns = expensive. Our single-pass + one retry = trade depth for compute. For open ≤30B stack, depth is expensive; for closed-API GPT-4, MAC-SQL approach can afford depth.

## 6. Spider-Agent

**Citation**: xlang-ai/Spider2 [Lei et al., ICLR 2025]. Baseline agent in original Spider 2.0 paper.

### Core idea

Baseline agent для Spider 2.0. **ReAct-style loop** с bash + filesystem tools. Agent navigates project files, calls `dbt run`, reads errors, iterates.

### Best metrics (different backbones)

| Backbone | Snow EX | Lite EX | DBT task_success |
|---|---|---|---|
| Qwen3-Coder (open) | 31.08% | n/a | n/a |
| Claude-3.7-Sonnet | 24.50% | n/a | 14.70% |
| o1-preview | n/a | n/a | 13.24% |
| QwQ-32B (open) | 8.96% | 11.33% | n/a |
| Qwen2.5-Coder-32B (open) | n/a | 5.85% | n/a |

Research dossier §1-3.

### Key techniques

- ReAct (Reason + Act) prompting.
- Bash + filesystem tools для project navigation.
- Iterative correction via engine error feedback.
- Backbone-agnostic — works с любой LLM.

### Связь с нашей архитектурой

**Reference point для open ≤30B Snow comparison**. Spider-Agent + Qwen3-Coder achieves 31.08% Spider2-Snow — using **same base model class as наш planner**. They use ReAct multi-step; we use single-pass plan→emit.

- **If наш final Snow FULL** result lands at 25-30%, **competitive с Spider-Agent + Qwen3-Coder**.
- **Above** Spider-Agent + Claude-3.7-Sonnet 24.50%.

Methodologically: **Spider-Agent agent loop vs our pipeline single-pass** — different cost profiles. Spider-Agent uses 5-20 LLM calls per task (ReAct iteration); we use 2-3 (planner + emitter + optional retry). Our compute budget значительно lower.

**Spider2-DBT ceiling 14.7%** — regardless of backbone class. Confirms scaffold matters more than model on DBT lane.

## 7. Databao Agent

**Citation**: JetBrains. *Databao Agent — #1 on Spider2-DBT*. blog.jetbrains.com/databao/2026/02/ (Feb 2026).

### Core idea

DBT scaffold redesign. **#1 на Spider2-DBT leaderboard (58.82%)** — 4× lift over Spider-Agent baseline.

### Methodology (partially disclosed in blog)

- **Up-front DB overview**: agent first analyzes full DB schema + DBT project structure before editing.
- **Restricted tool surface**: no free `bash` access. Agent uses defined high-level operations.
- **Verifier gate**: no `Terminate` action until `dbt run` returns green.

Direct quote:

> *"We made it smarter not by replacing the model, but by changing the environment around it."*

— Databao blog Feb 2026, research dossier §4.

### Best metrics

- Spider2-DBT: **58.82%** (rank 1, closed)
- Lite: 69.65% (rank 3)

### Связь с нашей архитектурой

**Recipe для нашего Phase 31 DBT scaffold redesign** (out of dossier scope, planned future work).

- **Up-front DB overview** ↔ our read-before-write step (Phase 31 plan).
- **Restricted tool surface** ↔ our defined emit format (multi-block whole-file vs free filesystem).
- **Verifier gate** ↔ our staged `dbt parse → compile → run → test` с retry loop (Phase 31).

Estimated Phase 31 outcome: **13.2% → 22-32%** — partial Databao reproduction. Full 58.82% requires additional proprietary engineering not disclosed.

## 8. DAIL-SQL

**Citation**: Gao, D. et al. *Text-to-SQL Empowered by Large Language Models: A Benchmark Evaluation*. VLDB 2024, arXiv 2308.15363.
**Repo**: github.com/BeachWang/DAIL-SQL

### Core idea

**Masked-question retrieval** для few-shot examples. Mask domain tokens (table/column names) before similarity match by SQL skeleton. Plus **self-consistency voting**.

### Best metrics

- Spider 1.0 dev: ~85% EX с GPT-4.
- BIRD: ~57-60% EX.

### Key techniques

- **Masked-question retrieval**: replace specific table/column names с placeholders before computing question similarity к train examples. Avoids overfitting к syntactic match.
- **Self-consistency**: sample N times, pick majority. **+0.4% Spider1, +1% BIRD** over single-sample.

### Связь с нашей архитектурой

- **Self-consistency → naше planned Phase 29 enhancement**. Currently single emit. Multi-sample + voting low-cost addition.
- **Masked-question retrieval → not used by us**. We don't do few-shot example retrieval at inference time. Static prompt structure. Could be added Phase 30+.

DAIL-SQL widely cited prompting baseline. Our pipeline uses more sophisticated planning, но could benefit from DAIL-SQL-style few-shot exemplars для challenging tasks.

## 9. DIN-SQL

**Citation**: Pourreza, M., Rafiei, D. *DIN-SQL: Decomposed In-Context Learning of Text-to-SQL with Self-Correction*. NeurIPS 2023, arXiv 2304.11015.

### Core idea

Decomposed in-context learning + self-correction. Multi-step prompting: classification → schema linking → SQL generation → self-correction.

### Best metrics

- Spider 1.0: ~85% EX с GPT-4.
- BIRD: significant gains over baseline.

### Key ablation finding

> *"decomposed CoT hurts easy queries"*

— **Direct evidence** для observation we replicated: planner-emitter decomposition cost −0.033 EX на Spider 1.0 / BIRD.

### Связь с нашей архитектурой

- **Decomposition → our planner-emitter design**.
- **Ablation insight → our complexity router rationale** (планируемый Phase 30+: route простой задач к direct emit, complex к plan→emit).
- **Self-correction → our planned Phase 29 F3 self-refine**.

## 10. CHASE-SQL

**Citation**: Pourreza, M. et al. *CHASE-SQL: Multi-Path Reasoning and Preference Optimized Candidate Selection*. ICLR 2025, arXiv 2410.01943.

### Core idea

**Multi-path reasoning** + **trained 7B selector model** для preference-optimized candidate selection. Generate multiple SQL candidates через different reasoning paths, train 7B model к pick best.

### Best metrics

- SOTA на BIRD private test set.
- **+3-5 EX over simple majority voting** (research dossier §4).

### Key techniques

- Multi-path reasoning: 3-7 distinct prompt strategies, each producing candidate.
- **Trained 7B selector**: classifier model preferring candidate-A vs candidate-B based на pack + question features.
- Training data: bench train set, labeled by which candidate produced correct execution.

### Связь с нашей архитектурой

**Direct evolution path для нашего candidate selector**.

Currently: priority order `dry_run_ok ≻ parse_ok ≻ schema_valid ≻ Family A tie-break` (см. [08_CUSTOM_TOOLS/07_candidate_selector.md](../08_CUSTOM_TOOLS/07_candidate_selector.md)). Pure rule-based.

CHASE-SQL **trained selector** = future Phase 31+ extension. Requirements:
- Labeled selection data (Spider 2.0 train set — published gold, but fine-tuning on gold forbidden by leaderboard rule).
- Additional 7B model loaded в memory (~14 GB VRAM).
- Inference cost: extra LLM call per task.

**Out of current scope but logical next step**.

## 11. RSL-SQL

**Citation**: Cao, L. et al. *RSL-SQL: Robust Schema Linking with Multi-Turn Correction*. arXiv 2411.00073.
**Repo**: github.com/Laqcce-cao/RSL-SQL

### Core idea

Robust schema linking. **Multi-turn correction**: detect schema linking errors через partial SQL generation, repair, retry.

### Best metrics

**+2-5 EX from one-round repair feedback** на BIRD (research dossier).

### Key techniques

- Initial schema linking → SQL generation → identifies missing entities в emitted SQL → repair linking → re-generate.
- One-round repair suffices for most cases.

### Связь с нашей архитектурой

- **Repair pattern → ancestor нашей planned Phase 29 F3**.
- Currently we have **validator-feedback retry** (single retry on AST validator fail). RSL-SQL pattern extends к **engine-error retry** (post-execution feedback).

## 12. MCS-SQL

**Citation**: Lee, S. et al. *MCS-SQL: Multiple Prompts and Multiple Choice Selection*. COLING 2025, arXiv 2405.07467.

### Core idea

Multiple prompts + multiple-choice selection. Generate N SQL candidates с different prompts, ranked selection.

### Best metrics

**+2.1% over plain self-consistency** на BIRD.

### Связь с нашей архитектурой

- Similar к CHASE-SQL multi-path direction но simpler (no trained selector).
- **Marginal gain (+2%)** для significant compute cost — not высокий ROI.
- Our priority-order selector simpler equivalent.

## 13. CodeS

**Citation**: Li, H. et al. *CodeS: Towards Building Open-Source Language Models for Text-to-SQL*. SIGMOD 2024, arXiv 2402.16347.
**Repo**: github.com/RUCKBReasoning/codes

### Core idea

**Open-source fine-tuned model family** для text-to-SQL specifically. Sizes 1B / 3B / 7B / 15B.

### Best metrics

- Spider 1.0 dev: **84.9%** EX с CodeS-15B fine-tuned (best open-source SFT 2024).
- Spider2-Lite: **0.73%** EX with CodeS-15B (research dossier §4).

### Связь с нашей архитектурой

**Negative example — why we didn't go SFT route**.

CodeS demonstrates:
1. **SFT can achieve top open-source result on Spider 1.0** (84.9% > GPT-4 zero-shot ~73%).
2. **SFT does NOT generalize across benchmarks** — same model 0.73% on Spider2-Lite. **Transferability failure**.

Our decision: **no SFT**, **prompt engineering + scaffolding only**. Reasoning:
- Spider 2.0 prohibits SFT on gold для valid leaderboard submission.
- Generalization across multi-benchmarks goal directly conflicts с SFT specialization.
- Compute cost SFT (multiple A100 GPUs × days) — out of academic budget.

## 14. DSR-SQL

**Citation**: Hao, X. et al. *DSR-SQL: Decoupled Schema-aware Reasoning for Text-to-SQL*. arXiv 2511.21402 (Nov 2025).

### Core idea

Decoupled schema-aware reasoning. Zero-shot, no fine-tuning. Uses DeepSeek-R1 685B backbone.

### Best metrics

- Spider2-Snow: **63.80%** (rank 22) с DeepSeek-R1.

### Key techniques

- Reasoning model handles schema awareness implicitly.
- No external schema linker — model uses extended context.

### Связь с нашей архитектурой

- **685B model class — out of наш ≤30B constraint**.
- DSR-SQL approach validates **reasoning-class models can replace schema linker entirely** at sufficient context window. Naше use of explicit BM25 schema linker — necessary trade-off для ≤30B без reasoning capability.

## 15. SchemaGraphSQL

**Citation**: Liu, X. et al. *SchemaGraphSQL: Graph-Based Schema Linking via FK Reachability*. arXiv 2505.18363.

### Core idea

**BFS over FK + name-heuristic edges** after BM25 picks seeds. Expands schema linking graph по FK reachability.

### Best metrics

**+4-8 EX on BIRD with zero fine-tuning** (research dossier).

### Связь с нашей архитектурой

**Direct recipe для нашего planned Phase 30 F2 (Family C activation на BQ)**.

Currently our `join_hints` heuristic в pack builder uses name-matching only (e.g., shared `*_id` columns). SchemaGraphSQL uses **real FK metadata** when available + heuristic as fallback. BFS expansion ensures multi-hop joinability surfaced.

Phase 30 plan: replace `join_hints` heuristic с SchemaGraphSQL-style FK BFS. Expected lift +6-10 EX Lite-BQ based на research dossier.

## 16. RASL

**Citation**: Eben, R. et al. *RASL: Retrieval-Augmented Schema Linking*. Amazon Science, arXiv 2507.23104.

### Core idea

Retrieval-Augmented Schema Linking для массивных DBs. **Hybrid dense + sparse retrieval**.

### Связь с нашей архитектурой

- **Not used in нашей pipeline**.
- After Phase 27 per-task partitioning, BM25 alone проявил sufficient recall. Dense retrieval — incremental upgrade с diminishing returns at this scale.
- Possible Phase 30+ exploration if BQ lane plateaus.

## 17. DTS-SQL

**Citation**: Pourreza, M., Rafiei, D. *DTS-SQL: Decomposed Text-to-SQL for Small Language Models*. EMNLP-F 2024, arXiv 2402.01117.

### Core idea

Two-stage decomposition specifically для small LLMs (≤15B). Schema linking → SQL generation.

### Best metrics

**79.9% Spider 1.0 с CodeLlama-13B fine-tuned**.

### Связь с нашей архитектурой

**Confirms decomposition strategy для small emitter**. Validates наш planner (30B-A3B) + emitter (Coder-7B) split — same family of approach как DTS-SQL CodeLlama-13B + decomposed reasoning.

## 18. Other systems (brief)

- **Arctic-Text2SQL-R1** [Snowflake AI Research, arXiv 2505.20315] — Snowflake's fine-tuned R1-style reasoner. Hybrid model + agent. Powers Arctic-FLEX (75.14% Snow). Closed.
- **XiYan-SQL** [arXiv 2507.04701] — Alibaba's text-to-SQL model. Multi-generator + consistency-based selection.
- **TCDataAgent-SQL** — Tencent Cloud's NL2BI agent. Spider2-Snow rank 4 (93.97%). Closed.
- **Paytm Prism Swarm** — multi-agent swarm с Claude-Sonnet-4.5. Spider2-Snow rank 5 (90.49%). Open code: github.com/paytm/prism.
- **ByteBrain-Agent** — ByteDance internal. Spider2-Snow rank 9 (84.10%). Closed.

## Closing section: open-source vs closed model-class ceiling

Comparing reproducible numbers (Spider2-Snow lane, May 2026):

| Tier | Reference systems | EX range |
|---|---|---|
| Closed industrial top | Genloop 96.70, TCDataAgent 93.97, Paytm Prism 90.49 | 84-97% |
| Closed reasoning model | ReFoRCE + o3 62.89%, Arctic-FLEX 75.14% | 60-75% |
| Open ≤685B reasoning | DSR-SQL + DeepSeek-R1 63.80%, AutoLink + DeepSeek-R1 54.84% | 50-65% |
| Open ≤32B reference | Spider-Agent + Qwen3-Coder 31.08%, + Claude-3.7-Sonnet 24.50% | 25-31% |
| Open ≤30B + our scaffold | **23.76 % Snowflake EXPLAIN-pass (\*)** (130/547, plan-level acceptance — see [Appendix 07](../11_APPENDIX/07_critical_metric_caveat.md)) | cross-metric — row-match audit Phase 28b |
| Spider-Agent + small | Spider-Agent + QwQ-32B 8.96% | <10% |
| Classical zero-shot | DAIL/CHESS/DIN + GPT-4o | 0-2% |

### Honest gap acknowledgement

**Closed model class** (o3, Claude-Sonnet-4.5, GPT-5) achieves consistently **2-4× higher Snow EX** than open ≤30B. This **cannot be closed scaffolding alone**:
- Closed reasoning models have **much larger effective compute** per inference (ReAct loops, deep CoT).
- Closed corporate tooling — proprietary scaffold engineering (Genloop, Databao, Paytm).
- Closed academic benchmarks (ReFoRCE на o3) — accessible через paid API.

**Bridgeable** через open weights only if model class shifts (DeepSeek-R1 685B is **20×** params наш planner). 

For ≤30B constraint, **ceiling estimate ~30-40% Snow EX** even with full F1+F2+F3+F4 scaffold stack (Phase 28 + 29 + 30 combined). Closed top 90%+ remains structurally out of reach.

This is the **honest position** для thesis defense — our work pushes state-of-the-art **within open-weight ≤30B class**, не absolute SOTA.

## Cross-references

- Text-to-SQL evolution narrative: [01_text2sql_evolution.md](./01_text2sql_evolution.md)
- Open-source models survey: [03_open_source_text2sql_models.md](./03_open_source_text2sql_models.md)
- Agentic frameworks for DBT: [04_agentic_frameworks_for_dbt.md](./04_agentic_frameworks_for_dbt.md)
- Schema linking approaches deep-dive: [05_schema_linking_approaches.md](./05_schema_linking_approaches.md)
- Our pipeline architecture: [04_ARCHITECTURE/01_overview_single_architecture.md](../04_ARCHITECTURE/01_overview_single_architecture.md)
- Phase 27 F1 derivation от LinkAlign: [06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md](../06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md)
- Leaderboard position: [09_RESULTS_ANALYSIS/05_leaderboard_position.md](../09_RESULTS_ANALYSIS/05_leaderboard_position.md)
- Publishability assessment: [09_RESULTS_ANALYSIS/07_publishability_assessment.md](../09_RESULTS_ANALYSIS/07_publishability_assessment.md)

## Источники

| Утверждение | Источник |
|---|---|
| All system per-system summaries | research dossier `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md` §4 |
| Leaderboard May 2026 numbers | research dossier §1, §2, §3 |
| LinkAlign verbatim quote | arXiv 2503.18596 abstract; research dossier §4 |
| Databao Agent verbatim quote | JetBrains blog Feb 2026; research dossier §4 |
| ReFoRCE BQ caveat quote | research dossier §4 ReFoRCE entry |
| DIN-SQL "decomposed CoT hurts easy queries" | Pourreza & Rafiei, NeurIPS 2023; arXiv 2304.11015 |
| Annotation reliability caveat | Wang et al., arXiv 2601.08778 |
