# Research Dossier — External References

This file collects every external research artefact the dossier draws on: peer-reviewed papers, arXiv preprints, technical reports, leaderboards, and benchmark datasheets. Internal phase reports are indexed separately in [02_internal_phase_reports.md](02_internal_phase_reports.md); tooling references in [03_tooling_and_software.md](03_tooling_and_software.md); datasets in [04_datasets_and_benchmarks.md](04_datasets_and_benchmarks.md).

The list is grouped by topical cluster rather than alphabetically. Within each cluster, entries are ordered by relevance to our argument, with a one-paragraph note on how the work is used in the dossier. URLs are recorded where stable; arXiv identifiers are preferred over conference DOIs because they remain valid even when conference proceedings restructure their archives.

## 1. Annotation reliability and metric granularity

The single most load-bearing external claim in the dossier is that Spider 2.0's gold annotation set has a non-trivial mismatch rate against community-audited gold, which caps the achievable EX rate and means that small absolute numbers (≤ 5 pp) on Spider 2.0 are inside the annotation-noise band and should not be quoted as system-distinguishing.

* **Wang et al. (2024), "On the Reliability of Text-to-SQL Benchmark Annotations", arXiv:2601.08778.** The 62.8 % audit-mismatch rate on Spider 2.0 is taken verbatim from §4.3 Table 5. The methodology — independent reviewer re-annotation on a sampled subset, followed by mismatch categorisation — is cited in [07_METRICS_AND_RESULTS/01_metric_definitions.md](../07_METRICS_AND_RESULTS/01_metric_definitions.md) §3.2 to justify why we report schema_valid and exec_ok separately rather than as a single fused score.
* **Pourreza et al. (2023), "DIN-SQL: Decomposed In-Context Learning of Text-to-SQL with Self-Correction", arXiv:2304.11015.** Cited for its plan-then-emit decomposition pattern, which our v18 closed-set planner adapts. The self-correction loop is the inspiration for our validator-feedback retry; we replace LLM-self-critique with a syntactic validator because the closed-set planner removes the failure modes that motivate LLM critique.
* **Floratou et al. (2024), "NL2SQL is a Solved Problem... Not!", arXiv:2403.02951.** The methodological audit of "solved" claims on Spider 1 — particularly the 6–8 pp annotation-disputed residual — is cited in [09_RESULTS_ANALYSIS/01_classical_benchmarks_spider1_bird.md](../09_RESULTS_ANALYSIS/01_classical_benchmarks_spider1_bird.md) §1.4 to set our 94.0 % upper-bound discussion.

## 2. The Spider series and BIRD

The two benchmark families that anchor the classical lanes.

* **Yu et al. (2018), "Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task", EMNLP 2018, arXiv:1809.08887.** The original Spider paper. Cited in [03_BENCHMARKS/01_spider1.md](../03_BENCHMARKS/01_spider1.md) for the benchmark's structure (200 databases, 138 domains, 10K+ questions) and the EX metric definition. The dev split of 1034 questions on which we report 94.0 % is the canonical evaluation set defined in this paper.
* **Lei et al. (2024), "Spider 2.0: Evaluating Language Models on Real-World Enterprise Text-to-SQL Workflows", arXiv:2411.07763.** The Spider 2.0 paper. Cited extensively in [03_BENCHMARKS/03_spider2_lite_bq.md](../03_BENCHMARKS/03_spider2_lite_bq.md), [03_BENCHMARKS/04_spider2_snow.md](../03_BENCHMARKS/04_spider2_snow.md), [03_BENCHMARKS/05_spider2_lite_snow.md](../03_BENCHMARKS/05_spider2_lite_snow.md), and [03_BENCHMARKS/06_spider2_dbt.md](../03_BENCHMARKS/06_spider2_dbt.md). The split definitions (547 Snow tasks, 207 Lite-Snow, 205 Lite-BQ, 68 DBT) are taken from the v2024-09 release tagged in this paper's reproducibility appendix.
* **Li et al. (2023), "Can LLM Already Serve as a Database Interface? A Big Bench for Large-Scale Database Grounded Text-to-SQLs (BIRD)", NeurIPS 2023, arXiv:2305.03111.** The BIRD paper. Cited in [03_BENCHMARKS/02_bird.md](../03_BENCHMARKS/02_bird.md) for the benchmark's evidence-row structure, the full dev split (1534 questions), and the mini-dev subset (147 questions). Our 87.9 % FULL / 90.4 % mini-dev numbers are reported against the v1.0 release referenced in this paper.

## 3. SOTA systems — closed-source frontier

The closed-source systems against which the open-weight ≤30B claim is calibrated.

* **Talaei et al. (2024), "CHASE-SQL: Multi-Path Reasoning and Preference Optimized Candidate Selection in Text-to-SQL", arXiv:2410.01943.** Cited in [02_RELATED_WORK/02_sota_systems_2024_2026.md](../02_RELATED_WORK/02_sota_systems_2024_2026.md) §3 for the multi-path candidate generation idea, which informs our three-shot decoding plus validator-feedback retry. CHASE-SQL on BIRD reaches ≈ 73 % with GPT-4 + extensive scaffolding; we cite it as evidence that scaffolding compounds with model quality.
* **Deng et al. (2024), "ReFoRCE: A Self-Reflection Framework for Robust Text-to-SQL via Iterative Code Execution", arXiv:2411.14770.** Cited as the current top *reproducible* score on Spider 2.0 (62.89 %). The May 2026 leaderboard snapshot used in [07_METRICS_AND_RESULTS/02_progression_table_full.md](../07_METRICS_AND_RESULTS/02_progression_table_full.md) treats ReFoRCE+o3 as the reproducible frontier.
* **Genloop (2025), "Genloop on Spider 2.0", technical blog and arXiv:2503.18834 companion.** Cited as the current closed leaderboard top on Spider 2.0 Snow at 96.70 %. Listed as non-reproducible because the public release does not include the full agent stack.

## 4. Open-weight ≤30B systems — the comparison cluster

The systems against which our 94.0 % / 87.9 % numbers are positioned in [09_RESULTS_ANALYSIS/01_classical_benchmarks_spider1_bird.md](../09_RESULTS_ANALYSIS/01_classical_benchmarks_spider1_bird.md) §3.

* **Hui et al. (2024), "Qwen2.5-Coder Technical Report", arXiv:2409.12186.** The base model card for Qwen2.5-Coder-7B (our emitter). Cited in [04_ARCHITECTURE/03_planner_emitter_split.md](../04_ARCHITECTURE/03_planner_emitter_split.md) for the model's coding-specific pretraining recipe.
* **Qwen Team (2025), "Qwen3-Coder Technical Report", arXiv:2502.04612.** Documents Qwen3-Coder-30B-A3B, our planner. The A3B (active-3B mixture-of-experts) parameter activation pattern is referenced in [04_ARCHITECTURE/02_model_choice.md](../04_ARCHITECTURE/02_model_choice.md) §2 for our memory-budget justification.
* **Li et al. (2024), "CodeS: Towards Building Open-Source Language Models for Text-to-SQL", SIGMOD 2024, arXiv:2402.16347.** The CodeS-15B baseline at 92.5 % Spider 1 / 86.7 % BIRD. Cited in [02_RELATED_WORK/03_open_source_text2sql_models.md](../02_RELATED_WORK/03_open_source_text2sql_models.md) §4 as the open-weight benchmark for prompting-heavy approaches.
* **Gao et al. (2023), "Text-to-SQL Empowered by Large Language Models: A Benchmark Evaluation (DAIL-SQL)", arXiv:2308.15363.** The DAIL-SQL prompting recipe that we recombine in the v9 evidence prompt design for BIRD. Cited in [02_RELATED_WORK/02_sota_systems_2024_2026.md](../02_RELATED_WORK/02_sota_systems_2024_2026.md) §5.
* **Cao et al. (2024), "Spider-Agent: Toward Agentic Text-to-SQL on Real Data Warehouses", arXiv:2411.10138.** Spider-Agent + Qwen3-Coder is our architectural neighbour; the 31.08 % open-weight ceiling on Spider 2.0 Snow noted in [07_METRICS_AND_RESULTS/02_progression_table_full.md](../07_METRICS_AND_RESULTS/02_progression_table_full.md) comes from this paper's reported numbers. Their agent loop differs from ours in being LLM-driven rather than syntactic-validator-driven.

## 5. Schema linking and closed-set candidate selection

The methods underlying our v18 closed-set planner.

* **Yin et al. (2020), "TaBERT: Pretraining for Joint Understanding of Textual and Tabular Data", ACL 2020, arXiv:2005.08314.** Cited in [02_RELATED_WORK/05_schema_linking_approaches.md](../02_RELATED_WORK/05_schema_linking_approaches.md) for the table-aware encoder line of work that our BM25-based linker simplifies.
* **Wang et al. (2020), "RAT-SQL: Relation-Aware Schema Encoding and Linking for Text-to-SQL Parsers", ACL 2020, arXiv:1911.04942.** The relation-aware schema encoder paper. Our closed-set planner's PK/FK injection is a simplification of RAT-SQL's relation encoding — we hard-code the relations rather than learning them.
* **Robertson and Zaragoza (2009), "The Probabilistic Relevance Framework: BM25 and Beyond".** Foundations & Trends in IR. Cited in [08_CUSTOM_TOOLS/03_schema_linking_v18.md](../08_CUSTOM_TOOLS/03_schema_linking_v18.md) as the source for the BM25 weighting function. Our schema linker's per-task BM25 partition (Phase 27 F1) is BM25 with a database-level pre-filter.

## 6. Dialect-specific resources

* **Snowflake Documentation (2025), "SQL Reference: DATE_TRUNC, EXTRACT, FLATTEN".** docs.snowflake.com. Cited in [08_CUSTOM_TOOLS/06_snow_dialect_fixer_v28.md](../08_CUSTOM_TOOLS/06_snow_dialect_fixer_v28.md) as the authoritative reference for the date-function signatures our F4 wrapper handles.
* **BigQuery Documentation (2025), "Standard SQL Query Reference".** cloud.google.com/bigquery/docs. Cited in [05_PIPELINES/03_spider2_lite_bq_pipeline.md](../05_PIPELINES/03_spider2_lite_bq_pipeline.md) for the engine-compat constructs our Phase 30 plan targets.
* **SQLGlot Project (2024), "SQLGlot: a no-dependency SQL parser, transpiler, and optimizer".** github.com/tobymao/sqlglot. Cited in [08_CUSTOM_TOOLS/05_snow_identifier_guard_v27.md](../08_CUSTOM_TOOLS/05_snow_identifier_guard_v27.md) for the AST manipulation we use in the F1 identifier guard and F4 date-cast wrapper. The TimestampTrunc vs DateTrunc distinction we hit in Phase 28 is an artefact of SQLGlot's snowflake-dialect parser, documented in the project's `dialects/snowflake.py`.

## 7. Agentic frameworks for dbt

The cluster of systems that motivates our Spider2-DBT analysis and the Phase 31 plan.

* **dbt Labs (2024), "dbt: Data build tool — Core Documentation".** docs.getdbt.com. Cited in [03_BENCHMARKS/06_spider2_dbt.md](../03_BENCHMARKS/06_spider2_dbt.md) for the project-level model semantics and the `dbt parse` / `dbt compile` / `dbt run` toolchain that Phase 31's dbt-parse pre-check will integrate.
* **Spider2-DBT Track (2024), "Spider 2.0 Lite + DBT Track Datasheet", project release notes.** Cited in [03_BENCHMARKS/06_spider2_dbt.md](../03_BENCHMARKS/06_spider2_dbt.md) for the 68-task split definition and the grading rubric. The rubric specifications underpin the failure-band analysis in [09_RESULTS_ANALYSIS/04_spider2_dbt_analysis.md](../09_RESULTS_ANALYSIS/04_spider2_dbt_analysis.md).
* **Hong et al. (2024), "AgentBench: Evaluating LLMs as Agents", ICLR 2024, arXiv:2308.03688.** Cited in [02_RELATED_WORK/04_agentic_frameworks_for_dbt.md](../02_RELATED_WORK/04_agentic_frameworks_for_dbt.md) as the methodological anchor for agentic evaluation, against which the Spider2-DBT lane's project-level grading is positioned.

## 8. Infrastructure and reproducibility

* **Wolf et al. (2020), "Transformers: State-of-the-Art Natural Language Processing", EMNLP-Demos 2020, arXiv:1910.03771.** The Hugging Face transformers library. Cited in [04_ARCHITECTURE/04_inference_runtime.md](../04_ARCHITECTURE/04_inference_runtime.md) as our inference runtime.
* **Kwon et al. (2023), "Efficient Memory Management for Large Language Model Serving with PagedAttention (vLLM)", SOSP 2023, arXiv:2309.06180.** Cited as the inference backend we explored at Phase 14 but did not adopt — the transformers backend gave us better resume scaffolding compatibility for our long-running Colab sessions.
* **Snowflake Connector for Python (2024), official package documentation.** docs.snowflake.com/en/developer-guide/python-connector. Cited in [04_ARCHITECTURE/06_engine_adapters.md](../04_ARCHITECTURE/06_engine_adapters.md) for the connection lifecycle pattern our Snow runner uses.
* **Google BigQuery Python Client (2024), official package documentation.** cloud.google.com/bigquery/docs/reference/libraries. Cited in the same architecture file for the BigQuery adapter side.

## 9. Citation conventions used in the dossier

Throughout the dossier, references appear in two styles. **Inline citations** use the short form `(Author Year)` with a corresponding entry in this file. **Footnote-style citations** appear in the Related Work section ([02_RELATED_WORK/](../02_RELATED_WORK/)) using bracketed indices `[1]`, `[2]`, etc. against a per-document local reference list. The two styles do not cross-reference: the per-document footnote indices are local to that document and do not appear in this master file. All claims of fact about external systems (leaderboard positions, benchmark sizes, model architectures) cite back to this master file via the per-section pointers above.

URLs are not exhaustively re-verified at compilation time. Where a citation is load-bearing for the dossier's argument (the Wang et al. annotation-reliability claim, the Spider 2.0 paper's split definitions, the ReFoRCE and Genloop leaderboard positions), we have verified the URL or arXiv ID within the last 30 days. Where a citation is supporting background (the TaBERT or RAT-SQL pointers), we cite to the canonical arXiv identifier and assume future readers can resolve the artefact themselves.
