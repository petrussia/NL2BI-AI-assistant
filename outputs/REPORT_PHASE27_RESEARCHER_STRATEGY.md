# Spider2 SOTA Analysis — Research Dossier (May 2026)

**Purpose:** Single source-of-truth для thesis dossier preparation (related work, leaderboard positioning, comparative analysis sections). Data fetched May 2026 from spider2-sql.github.io leaderboard (post-2025-10-29 evaluation-bug fix) и из публикаций арXiv 2024-2026. Reproducible-SOTA anchored on ReFoRCE / AutoLink / LinkAlign / Databao / Spider-Agent variants. Closed industrial top-of-leaderboard entries (Genloop, SOMA-SQL, Native mini) трактуются с осторожностью — no code, no paper.

---

## 1. Spider2-Snow Leaderboard (n=547 tasks)

| Rank | Method | Score | Backbone | Code | Notes |
|---|---|---|---|---|---|
| 1 | Genloop Sentinel Agent v2 Pro | 96.70 | not disclosed | closed | industrial, no paper |
| 4 | TCDataAgent-SQL | 93.97 | not disclosed | closed | Tencent Cloud Big Data |
| 5 | Paytm Prism Swarm + Claude-Sonnet-4.5 | 90.49 | Claude-Sonnet-4.5 | github.com/paytm/prism | multi-agent swarm |
| 9 | ByteBrain-Agent | 84.10 | ByteDance internal | closed | — |
| 14 | Arctic-FLEX (Snowflake AI Research) | 75.14 | not disclosed | closed | |
| 22 | DSR-SQL + DeepSeek-R1 | 63.80 | DeepSeek-R1 (open) | arXiv 2511.21402 | zero-shot, no FT |
| 23 | **ReFoRCE + o3** | **62.89** | o3 (closed) | github.com/Snowflake-Labs/ReFoRCE | **best fully-reproducible system** |
| 27 | AutoLink + DeepSeek-R1 | 54.84 | DeepSeek-R1 (open) | arXiv 2511.17190 | iterative schema-linking agent |
| 36 | ReFoRCE + o1-preview (paper) | 31.26 | o1-preview | same repo | paper-era benchmark |
| 37 | Spider-Agent + Qwen3-Coder | 31.08 | Qwen3-Coder (open) | xlang-ai/Spider2 | Qwen3 ReAct ceiling |
| — | Spider-Agent + Claude-3.7-Sonnet | 24.50 | Claude-3.7 | xlang-ai/Spider2 | |
| — | Spider-Agent + QwQ-32B | 8.96 | QwQ-32B (open) | xlang-ai/Spider2 | ≤32B open entry |
| — | DAIL/CHESS/DIN + GPT-4o (baselines) | 0.0–2.2 | GPT-4o | various | classical methods fail on Spider2 |
| **наша система v28-revert-A** | — | **~22-25% (FULL 547 in progress)** | Qwen3-Coder-30B-A3B + Qwen2.5-Coder-7B (open) | — | F1+F4 stack |

**Положение нашей системы:** at projected 22-25%, выше Spider-Agent + Claude-3.5-Sonnet и Spider-Agent + Claude-3.7-Sonnet, в band с Spider-Agent + Qwen3-Coder (31.08). Gap до ReFoRCE + o3 (62.89) — это разница closed-vs-open reasoning, преодолима частично через Phase 29 F3 self-refine.

---

## 2. Spider2-Lite Leaderboard (n=547, mixed BQ+Snow+SQLite splits)

Наша система запускается только на BQ split (n=205) — Lite-Snow split (n=207) и Lite-SQLite split (n=135) измеряются отдельно.

| Rank | Method | Score | Backbone | Code |
|---|---|---|---|---|
| 1 | SOMA-SQL (Oracle Cloud) | 72.02 | not disclosed | closed |
| 3 | Databao Agent (JetBrains) | 69.65 | not disclosed | jb.gg/gerk69 |
| 7 | ReFoRCE + o3 | 55.21 | o3 | github.com/Snowflake-Labs/ReFoRCE |
| 9 | AutoLink + DeepSeek-R1 | 52.28 | DeepSeek-R1 (open) | arXiv 2511.17190 |
| 12 | AgenticData + Qwen3 | 44.5 | Qwen3 (open) | arXiv 2508.05002 |
| 14 | ReFoRCE + Qwen3 | 35.6 | Qwen3 (open) | arXiv 2508.05002 |
| 15 | LinkAlign + DeepSeek-R1 | 33.09 | DeepSeek-R1 (open) | arXiv 2503.18596 |
| **наш Lite-BQ subset** | — | **34.6** | Qwen2.5-Coder-7B + 30B planner | — |
| 26 | AI-DIVE + gpt-oss-120B | 21.9 | gpt-oss-120B (open) | not disclosed |
| 29 | Spider-Agent + QwQ-32B | 11.33 | QwQ-32B (open) | xlang-ai/Spider2 |
| 32 | Spider-Agent + Qwen2.5-Coder-32B | 5.85 | Qwen2.5-Coder-32B (open) | xlang-ai/Spider2 |
| 36 | SFT CodeS-15B | 0.73 | CodeS-15B (open) | — |

**Положение:** 34.6% на BQ-only subset — уже выше LinkAlign + DeepSeek-R1 на полном Lite (33.09) и AgenticData + Qwen3 (44.5 на полном Lite — но они включают Lite-Snow split где у нас 0.5%, поэтому apples-to-oranges). Target после Phase 29-30 (F2 + F3 + F4 BQ): 52-60%, в band с AutoLink + DeepSeek-R1 (52.28).

---

## 3. Spider2-DBT Leaderboard (n=68)

| Rank | Method | Score | Backbone |
|---|---|---|---|
| 1 | Databao Agent (JetBrains) | **58.82** | not disclosed |
| 2 | SignalPilot Agent | 51.56 | not disclosed |
| 3 | Shadowfax-DBT-Agent + GPT-5 | 41.18 | GPT-5 |
| 4 | Spider-Agent-Extended + GPT-5 | 39.71 | GPT-5 |
| 8 | Spider-Agent + Claude-3.7-Sonnet | 14.70 | Claude-3.7 |
| 9 | Spider-Agent + o1-preview | 13.24 | o1-preview |
| **наша система** | — | **13.2** | 30B planner + 7B emitter |

**Реinterpretation:** vanilla Spider-Agent scaffold caps near 14.7% regardless of model class. Наша 13.2% = Spider-Agent ceiling. Every system above 25% replaced the scaffold (Databao blog Feb 2026: "We made it smarter not by replacing the model, but by changing the environment around it"). Phase 31 target: 22-32% через scaffold redesign.

---

## 4. Key Systems — Per-Method Summary

### Schema linking / multi-DB retrieval

**LinkAlign** (Wang et al., arXiv 2503.18596, github.com/Satissss/LinkAlign).
Iterative multi-DB schema linking. Core insight: "how to select the correct database from a large schema pool in multi-database settings, while filtering out irrelevant ones. Existing researches always assume single-database schemas." Это **точно описывает root cause Phase 26 Snow 0% baseline**. Achieves 33.09 на Spider2-Lite с DeepSeek-R1.

**AutoLink** (arXiv 2511.17190, AAAI 2026). Iterative schema exploration + expansion с reach 91.2% strict schema recall на Spider2-Lite, 52.28 EX с DeepSeek-R1, 54.84 EX на Spider2-Snow. Multi-round retrieval с LLM-guided expansion. Direct inspiration для our future Phase 30 JOIN-graph BFS.

**SchemaGraphSQL** (arXiv 2505.18363). BFS over FK + name-heuristic edges after BM25 picks seeds. +4-8 EX on BIRD with zero fine-tuning. Recipe для нашего planned Phase 30 F2 (Family C activation на BQ).

**CHESS** (Talaei et al., arXiv 2405.16755, scalingintelligence.stanford.edu/pubs/CHESSpaper/). Forces injection PK/FK columns into pack (rule: после BM25 picks columns, force-append declared PK/FK + heuristic `*_id` columns). Это recipe для PK/FK heuristic injection реализованного в нашем Phase 27 pack-builder.

**RASL** (Amazon Science, arXiv 2507.23104). Retrieval-Augmented Schema Linking для массивных DB. Hybrid dense + sparse retrieval. Не реализуется у нас — BM25 alone достаточен после per-task partitioning.

### Decomposition / multi-agent

**MAC-SQL** (Wang et al., COLING 2025, arXiv 2312.11242). Multi-agent collaborative framework: decomposer + selector + refiner agents. Achieves 86.8% on Spider1 EX (с GPT-4). Influenced our planner-emitter decomposition + validator-feedback retry design.

**DIN-SQL** (Pourreza & Rafiei, NeurIPS 2023, arXiv 2304.11015). Decomposed in-context learning + self-correction. Important ablation finding: *"decomposed CoT hurts easy queries"* — это explains наш own observation что planner hurts Spider1/BIRD by 0.033 EX. Direct relevance к нашему планируемому complexity router.

**DAIL-SQL** (Gao et al., VLDB 2024, arXiv 2308.15363, github.com/BeachWang/DAIL-SQL). Masked-question retrieval для few-shot examples. Mask domain tokens (table/column names), match by SQL skeleton similarity. ~+0.4% Spider1, +1% BIRD with self-consistency.

**DTS-SQL** (Pourreza & Rafiei, EMNLP-F 2024, arXiv 2402.01117). Decomposed text-to-SQL for small LLMs. Two-stage: schema linking → SQL generation. Achieves 79.9% на Spider1 с CodeLlama-13B fine-tuned. Confirms что decomposition помогает small models.

### Verifier / self-refine

**ReFoRCE** (Deng et al., arXiv 2502.00675, github.com/Snowflake-Labs/ReFoRCE). Three-component: Self-Refinement (execution feedback retry) + Format Restriction (output template) + Column Exploration (iterative INFORMATION_SCHEMA probing). Best fully-reproducible Spider2 system — 62.89 Snow, 55.21 Lite с o3. Note: ReFoRCE's own paper: *"our prompts are primarily designed for the Snowflake dialect, leading to occasional errors when handling certain cases in the BigQuery dialect"* — наш BQ-specific tooling структурно может outperform на Lite-BQ split.

**CHASE-SQL** (Pourreza et al., ICLR 2025, arXiv 2410.01943). Multi-path reasoning + preference-optimized candidate selection. Achieves SOTA on BIRD private test set. Trains a 7B selector model that outperforms simple majority voting by 3-5 EX.

**MCS-SQL** (Lee et al., COLING 2025, arXiv 2405.07467). Multiple prompts + multiple-choice selection. +2.1% over plain self-consistency on BIRD.

**RSL-SQL** (arXiv 2411.00073, github.com/Laqcce-cao/RSL-SQL). Robust schema linking with multi-turn correction. +2-5 EX from one-round repair feedback.

### Agentic systems

**Spider-Agent** (xlang-ai/Spider2). Baseline agent для Spider2. ReAct-style loop with bash + filesystem tools. Caps near 14.7% on DBT regardless of backbone model — это **scaffold ceiling** evidence.

**Databao Agent** (JetBrains, blog.jetbrains.com/databao/2026/02/). #1 on Spider2-DBT (58.82%). Methodology disclosed: (a) up-front DB overview, (b) restricted tool surface (no free bash), (c) verifier gate (no Terminate until green dbt run). Recipe для нашего planned Phase 31 DBT scaffold redesign.

**SWE-agent** (Yang et al., NeurIPS 2024, arXiv 2405.15793, swe-agent.com). Edit-linter-revert ablation: +8 pp on SWE-bench Lite. Universal lesson: staged verifier loop matters.

**aider** (aider.chat). Edit format research: Polyglot leaderboard shows Qwen2.5-Coder-7B drops ~30% accuracy when forced into diff vs whole-file format on files <200 LOC. Это **direct evidence** что наш Phase 11/26 DBT pipeline (90% diff-patch, 0% multi-block) systematically underperforms.

### Open-source models tuned for text-to-SQL

**CodeS** (Li et al., SIGMOD 2024, arXiv 2402.16347, github.com/RUCKBReasoning/codes). 1B/3B/7B/15B family fine-tuned для text-to-SQL. Best open-source SFT result of 2024. 84.9% on Spider1 dev с CodeS-15B fine-tuned. На Spider2-Lite — 0.73% (CodeS-15B), показывает что SFT на Spider1 не переносится на enterprise warehouses.

**Arctic-Text2SQL-R1** (Snowflake AI Research, arXiv 2505.20315). Snowflake's fine-tuned R1-style reasoner. Hybrid model + agent. Powers Arctic-FLEX (75.14 on Spider2-Snow).

**XiYan-SQL** (arXiv 2507.04701). Alibaba's text-to-SQL model. Multi-generator + consistency-based selection.

---

## 5. Five Highest-Leverage Fixes (F-series) — Mapping к нашим Phase Reports

| Fix | Source | Effort | Expected lift | Status |
|---|---|---|---|---|
| **F1** — Hard per-task `TABLE_CATALOG` filter + 3-part names + SQLGlot AST guard | LinkAlign + ReFoRCE | 6-10 h | Snow 0%→15-25% | **DONE Phase 27** |
| **F4** — NUMBER/VARIANT date-cast wrapper | Snow dialect specific (own finding) | 2-3 h | Snow +3-5 EX | **DONE Phase 28** |
| **F4c** — Guard fail-open on SQLGlot parse error | Own bug | 0.5 h | Edge case fix | **DONE Phase 28** |
| **F3** — EXPLAIN error → planner one-shot self-refine | ReFoRCE / RSL-SQL / MAC-SQL Refiner | 3-5 d | +3-8 EX every lane | **PLANNED Phase 29** |
| **F4** — SQLGlot-based BQ post-processor (date literals, ARRAY_CONTAINS, nested aggregates, SAFE_OFFSET) | Own (BQ dialect specific) | 1 wk | Lite-BQ +4-6 EX | **PLANNED Phase 29 or 30** |
| **F2** — JOIN-graph schema expansion + Family C activation | SchemaGraphSQL + AutoLink | 2-3 wk | Lite-BQ +6-10 EX | **PLANNED Phase 30** |
| **F6** — DBT scaffold redesign (multi-block whole-file + read-before-write + staged verifier) | Databao + SWE-agent + aider | 6-8 d | DBT 13%→25-32% | **PLANNED Phase 31** |

**F2a (mixed-case quoting auto-rewrite)** — DROPPED. Phase 28 regression evidence: catalog probe revealed Snow Spider2 public datasets store columns lowercase, not UPPERCASE. The "mixed-case quoting" failure category в Phase 27 §5 был mis-classification: real failures были column-name hallucinations (`country` vs `country_code`). Methodological lesson documented в Phase 28 closure.

---

## 6. Methodological Insights From Phase 27-28

### Catalog probe before dialect heuristic

**Insight:** error-message inspection без catalog ground-truth → wrong hypothesis. Phase 27 §5 classified 4/10 failures as "mixed-case quoting" by parsing `invalid identifier '"p"."country"'` error format. Phase 28 catalog probe revealed PUBLICATIONS table has 37/37 columns stored lowercase — `"p"."country"` was actually column-name hallucination (`country` instead of catalog's `country_code`), not case mismatch. F2a fix flipping lowercase → UPPERCASE actively broke the one task previously executable.

**Lesson:** any dialect heuristic над enterprise warehouse should be preceded by direct catalog inspection (case distribution probe, type distribution probe, naming convention probe). This is методологическое contribution of our thesis.

### BM25 hyperparameter mismatch Spider1→Spider2

**Insight:** Phase 1-16 BM25 defaults (top_columns=80, top_tables=20) calibrated для Spider1/BIRD schemas (≤30 tables/DB) systematically under-recall on Spider2 warehouse-scale catalogs (thousands of tables/DB). Once cross-DB noise eliminated (Phase 27 F1 catalog filter), retrieval window remained too narrow to surface enough relevant tables from the correct DB. Resolution: scale retrieval window 2.5× для Snow (80→200, 20→40), while keeping final pack budget unchanged (max_tables=10, max_cols_per_table=22).

**Lesson:** hyperparameters tuned on classical benchmarks не переносятся automatically на enterprise scale — explicit recalibration необходима per-benchmark-class.

### Layered fixes — composition reveals dormant value

**Insight:** F4 (date-cast wrapper) appeared "zero ROI" в Phase 28 regression because exec_ok dropped to 0/10. Catalog probe + revert experiment revealed F2a was actively breaking sf_bq211 (the one task executable since v25). When F2a removed, F4 contribution emerged: pilot10 1/10 → 4/10. F4 was load-bearing; F2a-induced regression masked its value.

**Lesson:** ablation analysis должна изолировать каждый fix через revert experiment, не just inclusion. Negative interactions между fixes (one fix breaking the dataset another fix targets) common in complex pipelines.

### Spider2 annotation reliability

**Insight:** Wang et al. (arXiv 2601.08778) report **62.8% mismatch rate** between Spider2 audited gold and re-annotated gold. Implications: any Spider2 result reported should include caveat про annotation reliability; manual audit of 20+ post-fix failures recommended before final reporting.

---

## 7. References

### Benchmarks
- Lei, F. et al. *Spider 2.0: Evaluating Language Models on Real-World Enterprise Text-to-SQL Workflows.* ICLR 2025 Oral, arXiv 2411.07763.
- Spider 2.0 leaderboard: spider2-sql.github.io (post-2025-10-29 evaluation fix).
- Spider2 repo: github.com/xlang-ai/Spider2.
- Yu et al. *Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task.* EMNLP 2018.
- Li, J. et al. *Can LLM Already Serve as a Database Interface? A BIg Bench for Large-Scale Database Grounded Text-to-SQLs.* NeurIPS 2023.

### Top Spider2 Methods
- Deng, M. et al. *ReFoRCE.* arXiv 2502.00675.
- Wang et al. *AutoLink.* AAAI 2026, arXiv 2511.17190.
- Wang, Y. et al. *LinkAlign.* arXiv 2503.18596.
- Cao et al. *RSL-SQL.* arXiv 2411.00073.
- Hao et al. *DSR-SQL.* arXiv 2511.21402.
- Pourreza et al. *CHASE-SQL.* ICLR 2025, arXiv 2410.01943.
- Liu et al. *SchemaGraphSQL.* arXiv 2505.18363.
- Eben et al. *RASL.* Amazon Science, arXiv 2507.23104.

### Classical Methods
- Talaei et al. *CHESS.* arXiv 2405.16755.
- Wang et al. *MAC-SQL.* COLING 2025, arXiv 2312.11242.
- Gao et al. *DAIL-SQL.* VLDB 2024, arXiv 2308.15363.
- Li et al. *CodeS.* SIGMOD 2024, arXiv 2402.16347.
- Pourreza & Rafiei. *DIN-SQL.* NeurIPS 2023, arXiv 2304.11015.
- Dong et al. *C3-SQL.* arXiv 2307.07306.
- Pourreza & Rafiei. *DTS-SQL.* EMNLP-F 2024, arXiv 2402.01117.
- Lee et al. *MCS-SQL.* COLING 2025, arXiv 2405.07467.
- Maamari et al. *The Death of Schema Linking?* arXiv 2408.07702.

### Agent Frameworks
- Yang, J. et al. *SWE-agent.* NeurIPS 2024, arXiv 2405.15793.
- Wang, X. et al. *OpenHands.* ICLR 2025, arXiv 2407.16741.
- Mikhailovskii & Zolotarev (JetBrains). *Databao Agent — #1 on Spider2-DBT.* blog.jetbrains.com/databao/2026/02/.

### Industrial / Tools
- Snowflake. *Cortex Analyst.*
- Snowflake AI Research. *Arctic-Text2SQL-R1.* arXiv 2505.20315.
- Pinterest. *How We Built Text-to-SQL at Pinterest.*
- Uber. *QueryGPT.* uber.com/blog/query-gpt/.
- aider. aider.chat (Polyglot leaderboard).
- SQLGlot. github.com/tobymao/sqlglot.

### Surveys
- Hong et al. *Next-Generation Database Interfaces: A Survey of LLM-based Text-to-SQL.* arXiv 2406.08426.
- Liu et al. *A Survey of Text-to-SQL in the Era of LLMs.* arXiv 2408.05109.
- Huang et al. *Exploring the Landscape of Text-to-SQL with LLMs.* arXiv 2505.23838.

### Annotation Reliability
- Wang et al. *Pervasive Annotation Errors Break Text-to-SQL Benchmarks and Leaderboards.* arXiv 2601.08778.

### Snowflake Documentation
- Snowflake docs: docs.snowflake.com/en/sql-reference/ (identifiers, name-resolution, info-schema, EXPLAIN, FLATTEN, identifier-literal).

### BigQuery Documentation
- BigQuery docs: cloud.google.com/bigquery/docs/ (INFORMATION_SCHEMA, primary-foreign-keys, dry-run, standard-sql).

---

## 8. Caveats for thesis defense

- **Live leaderboard volatility:** Spider2 numbers shift monthly. Re-fetch spider2-sql.github.io at submission date. Lock the version used.
- **ReFoRCE numbers shifted:** pre-fix (April 2025) ReFoRCE numbers были Snow 31.26 / Lite 30.35; post-fix (current) с o3 — Snow 62.89 / Lite 55.21. Cite the version matching your thesis cutoff.
- **Closed industrial top:** Genloop 96.70 на Snow, SOMA-SQL 72.02 на Lite, Databao 58.82 на DBT — no code, no paper. Treat with skepticism; anchor reproducible-SOTA discussion на ReFoRCE / AutoLink / LinkAlign / Spider-Agent variants.
- **Spider2 annotation 62.8% mismatch:** manually audit ~20 of post-fix failures before final reporting. Surface annotation reliability as a methodological discussion point.
- **Open-weight ≤30B fundamental gap:** Spider2-Lite top-tier (>65%) and Spider2-Snow top-tier (>60%) require either o3-class reasoning or 685B-class open weights (DeepSeek-R1). Our 30B-A3B + 7B stack fundamentally one order of magnitude smaller; honestly acknowledge.

---

**Production note:** этот файл — distilled summary исходного research dossier (~25KB markdown) который содержал также per-method techniques deep-dive, per-fix engineering plans, and per-lane stacked-outcome projections. Для расширенного анализа любого пункта — re-derive from listed sources.
