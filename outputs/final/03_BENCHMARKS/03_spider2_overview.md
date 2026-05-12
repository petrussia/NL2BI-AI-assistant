# 3.1.3 Spider 2.0 family — overview

## Краткая идентификация

| Field | Value |
|---|---|
| Полное название | **Spider 2.0: Evaluating Language Models on Real-World Enterprise Text-to-SQL Workflows** |
| Авторы | Lei et al. — xlang-ai (Hong Kong University of Science and Technology) |
| Год публикации | 2025 (ICLR Oral) |
| arXiv | 2411.07763 |
| Repository | github.com/xlang-ai/Spider2 |
| Leaderboard | spider2-sql.github.io (post-2025-10-29 evaluation fix) |
| **Sub-benchmarks** | Spider2-Lite (n=547), Spider2-Snow (n=547), Spider2-DBT (n=68), Spider2-full (interactive agent setting, n=632) |

Spider 2.0 — **самый сложный публично доступный NL2BI бенчмарк** на момент May 2026. Создавался **specifically** для evaluation на enterprise warehouse-scale задачах, после того как Spider 1.0 + BIRD стали substantially "solved" closed-API systems.

## Three sub-benchmarks мы используем

| Sub-benchmark | Engine | n | Notes |
|---|---|---|---|
| **Spider2-Lite (BQ split)** | BigQuery | 205 (BQ-specific) | Public BQ datasets (GA360, Stack Overflow, TheLook, Google Trends, NCAA, etc.) |
| **Spider2-Lite (Snow split)** | Snowflake | 207 (Snow-specific) | Snowflake Marketplace public databases (PATENTS, CYBERSYN, TCGA, GITHUB_REPOS, etc.) |
| **Spider2-Snow** | Snowflake | 547 (full Snow benchmark) | Same Snowflake Marketplace setup but larger and more diverse |
| **Spider2-DBT** | DuckDB local + DBT | 68 | Multi-file DBT projects + DuckDB execution |

Lite-SQLite split (n=135) — также часть Spider2-Lite, но мы не используем (наш scope — BI warehouse-relevant lanes). Spider2-full agent setting (n=632) — out of scope тоже (требует full agent loop с tools).

Подробно каждый sub-benchmark в:
- [04_spider2_lite_bq.md](./04_spider2_lite_bq.md)
- [05_spider2_lite_snow.md](./05_spider2_lite_snow.md)
- [06_spider2_snow.md](./06_spider2_snow.md)
- [07_spider2_dbt.md](./07_spider2_dbt.md)

## Почему Spider 2.0 был создан

Authors' motivation (из paper abstract): *"Existing benchmarks like Spider and BIRD focus on simplified database environments. Real-world enterprise text-to-SQL workflows differ fundamentally: complex SQL queries with hundreds of lines, multiple SQL dialects, immense schemas with thousands of tables, and intricate domain knowledge integration."*

Concrete gaps closed:

| Gap | Spider 1.0 / BIRD limit | Spider 2.0 enhancement |
|---|---|---|
| Schema scale | ≤50 tables/DB | **Thousands of tables/DB** (full INFORMATION_SCHEMA snapshot) |
| Dialect | SQLite only | **BigQuery + Snowflake + DuckDB** |
| Domain knowledge | minimal evidence field | **Rich domain knowledge documents** per database |
| SQL complexity | typically ≤20 lines | **Up to several hundred lines** |
| Multi-step workflow | none | **DBT pipeline editing** (Spider2-DBT lane) |
| Tool integration | single-shot SQL | **Optional agent setting** with bash/filesystem tools |

## Evaluation methodology

### Spider2-Lite + Spider2-Snow

**Execution Accuracy (EX)**:
1. Predicted SQL выполняется на real engine (BQ или Snow).
2. Result сравнивается с gold result via **multiset row match с extra columns allowed**.

«Extra columns allowed» означает: prediction может contain **additional columns** beyond gold (e.g., gold returns `name`, our prediction returns `name, id` — passes if gold columns subset present, в правильном порядке rows). Это **более forgiving** чем strict column-set match — позволяет minor differences без false-failure.

### Spider2-DBT

**task_success** binary metric:
1. Predicted DBT project edits applied.
2. `dbt build` execute.
3. Output tables compared **table+column-level** against golden DuckDB output.
4. Pass if all expected output tables present with matching columns + values.

**Не** multiset row match — это **table+column-level** match. Stricter в structural sense, потому что DBT может create multiple output tables (final + intermediate views).

## Fine-tuning prohibition

Critical methodological constraint: Spider 2.0 **publishes gold SQL** for train + dev. **Fine-tuning на released gold prohibited** for valid leaderboard submission. This forces systems to use **zero-shot / few-shot** approaches.

Implication for thesis: **наша constraint "no SFT"** aligns с Spider 2.0 evaluation policy. CodeS-15B fine-tuned achieves 84.9% Spider 1.0 но 0.73% Spider2-Lite — demonstrates **fine-tuning не generalizes** к enterprise scale.

## Annotation reliability — important caveat

Wang et al. (arXiv 2601.08778, *"Pervasive Annotation Errors Break Text-to-SQL Benchmarks and Leaderboards"*) report **62.8% mismatch rate** between Spider 2.0 audited gold и re-annotated gold. Implications:

- **No system result on Spider 2.0 should be presented as exact** without manual audit of failures.
- Comparative analysis between systems remains valid (relative ranking robust to annotation noise).
- For thesis: report **EX numbers с caveat** about annotation reliability + recommend manual audit of 20+ post-fix failures.

См. [09_RESULTS_ANALYSIS/07_publishability_assessment.md](../09_RESULTS_ANALYSIS/07_publishability_assessment.md) для full discussion.

## Position в landscape

Spider 2.0 — **самый сложный** публичный bench:

```
                    Difficulty / Real-world similarity
                    ─────────────────────────────────────►
  Spider 1.0  ←─  BIRD  ←─  Spider 2.0 family
   ~89-94%        ~70-78%      ~60-70% (top closed)
   ~85% (open)    ~58-65%      <40% (open ≤30B)
```

| Tier | Bench(es) saturated for closed API | Open ≤30B SOTA |
|---|---|---|
| Saturated | Spider 1.0 (~89-94%), BIRD (~73-76%) | CodeS-15B SFT Spider1 84.9%, our Spider 1.0 94.0% |
| Active research | Spider 2.0 family | Spider2-Snow: 31% (Spider-Agent + Qwen3-Coder); Spider2-Lite: 35-50% |

**Spider 2.0 is current research frontier** для NL2BI / text-to-SQL community as of May 2026. ICLR 2025 Oral status indicates academic prominence. Three closed-industry leaderboards (Genloop, Databao JetBrains, SOMA-SQL Oracle) attest commercial interest.

## Three closed-industry top systems (May 2026)

| System | Best lane | Best score | Company | Disclosed methodology |
|---|---|---|---|---|
| **Genloop Sentinel Agent v2 Pro** | Snow | 96.70% | Genloop | Closed; no paper, no code |
| **SOMA-SQL** | Lite | 72.02% | Oracle Cloud | Closed |
| **Databao Agent** | DBT | 58.82% | JetBrains | Closed; partial methodology в blog (blog.jetbrains.com/databao/2026/02/): up-front DB overview, restricted tool surface, verifier gate |

**Treatment в thesis**: discuss as data points но **anchor reproducible-SOTA discussion** на ReFoRCE / AutoLink / LinkAlign / Spider-Agent variants (open code, paper). Closed-industry numbers — context, not benchmark.

## Top reproducible Spider 2.0 systems (May 2026)

См. research dossier (`outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md`) для full per-system summaries. Quick map:

| System | Snow lane | Lite lane | DBT lane | Code |
|---|---|---|---|---|
| **ReFoRCE + o3** | 62.89% | 55.21% | — | github.com/Snowflake-Labs/ReFoRCE |
| **AutoLink + DeepSeek-R1** | 54.84% | 52.28% | — | arXiv 2511.17190 |
| **LinkAlign + DeepSeek-R1** | — | 33.09% | — | github.com/Satissss/LinkAlign |
| **Spider-Agent + Qwen3-Coder** | 31.08% | — | — | github.com/xlang-ai/Spider2 |
| **Spider-Agent + Claude-3.7-Sonnet** | 24.50% | — | 14.70% | github.com/xlang-ai/Spider2 |
| **Spider-Agent + o1-preview** | — | — | 13.24% | same |
| DSR-SQL + DeepSeek-R1 | 63.80% | — | — | arXiv 2511.21402 |

## Spider 2.0 lanes — our position

| Lane | Pre-Phase 27 baseline | Current (post Phase 28 closure) | Top reproducible (May 2026) |
|---|---|---|---|
| Spider2-Lite-BQ | 34.6% (Phase 22-26 stack on pilot50 → FULL projection) | unchanged (Phase 27-28 не touched BQ) | AutoLink+DeepSeek-R1 52.28% |
| Spider2-Lite-Snow | 0.5% (v26, 1/207) | partial n=40/207 (\*) — full closure deferred to Phase 28b; pilot10 v28-revert-A trends 4/10 EXPLAIN-pass | (Lite-Snow split rarely reported separately; в band с ReFoRCE / AutoLink full Lite) |
| Spider2-Snow | 0.0% (v25 baseline, 509/547 exec=0) | **23.76 % Snowflake EXPLAIN-pass (\*) (130/547)** — plan-level acceptance, row-match audit Phase 28b | ReFoRCE+o3 62.89% row-match, AutoLink 54.84% row-match, Spider-Agent+Qwen3-Coder 31.08% row-match |
| Spider2-DBT | 13.2% (Phase 11 baseline reproduction, n=68 = 9/68) | unchanged | Databao 58.82% (closed); Spider-Agent ceiling ~14.7% |

## Three sub-benchmark architectural differences

| Aspect | Spider2-Lite-BQ | Spider2-Lite-Snow | Spider2-Snow | Spider2-DBT |
|---|---|---|---|---|
| n | 205 | 207 | 547 | 68 |
| Engine | BigQuery | Snowflake | Snowflake | DuckDB + DBT |
| Live catalog source | INFORMATION_SCHEMA.COLUMNS (BQ projects) | INFORMATION_SCHEMA.COLUMNS (Snow databases) | same | n/a — agent reads project files |
| Catalog scale | ~428K columns total | subset of ~587K | full ~587K | per-project repo |
| Dialect | BQ Standard SQL | Snowflake | Snowflake | DuckDB SQL (DBT-compiled) |
| Family A renderer | ✓ implemented | ✗ not implemented | ✗ not implemented | n/a |
| Family B emitter | ✓ | ✓ (only) | ✓ (only) | ✓ (multi-block whole-file) |
| F1 AST guard | not used | ✓ | ✓ | n/a |
| F4 date-cast wrap | not used | ✓ | ✓ | n/a |
| Our priority в Phase 27-28 | secondary | primary on pilot10/50 | primary on FULL | unchanged (Phase 31 territory) |

## Methodological claims permissible based on Spider 2.0 family

Что **можем** заявлять (с annotation-reliability caveat):
- Architecture works на real enterprise warehouse-scale BI queries.
- Open-weight ≤30B стэк может match or exceed Spider-Agent + similar-class open models on Snow и Lite-BQ.
- F1 grounding intervention + F4 dialect wrap together enable measurable non-zero EX on Snow lane (where prior was 0%).

Что **нельзя** заявлять:
- Absolute SOTA without official leaderboard submission.
- Match closed-API tier (ReFoRCE+o3 vs наш open ≤30B — fundamental gap).
- Production readiness — even our best Spider2 result has 60-80% queries unsolved.

## Cross-references

- Каждый sub-benchmark detail:
  - [04_spider2_lite_bq.md](./04_spider2_lite_bq.md)
  - [05_spider2_lite_snow.md](./05_spider2_lite_snow.md)
  - [06_spider2_snow.md](./06_spider2_snow.md)
  - [07_spider2_dbt.md](./07_spider2_dbt.md)
- Pipelines: [05_PIPELINES/03_spider2_lite_bq_pipeline.md](../05_PIPELINES/03_spider2_lite_bq_pipeline.md), [04_spider2_snow_pipeline.md](../05_PIPELINES/04_spider2_snow_pipeline.md), [05_spider2_dbt_pipeline.md](../05_PIPELINES/05_spider2_dbt_pipeline.md)
- Comparative table: [08_comparative_table.md](./08_comparative_table.md)
- Leaderboard position discussion: [09_RESULTS_ANALYSIS/05_leaderboard_position.md](../09_RESULTS_ANALYSIS/05_leaderboard_position.md)
- Methodological claims: [01_INTRODUCTION/04_thesis_contributions.md](../01_INTRODUCTION/04_thesis_contributions.md)
- Schema linking approaches comparison: [02_RELATED_WORK/05_schema_linking_approaches.md](../02_RELATED_WORK/05_schema_linking_approaches.md)

## Источники

| Утверждение | Источник |
|---|---|
| Spider 2.0 paper | Lei et al., ICLR 2025 Oral, arXiv 2411.07763 |
| Sub-benchmark sizes | `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md` §1-3 |
| ReFoRCE 62.89% Snow / 55.21% Lite | research dossier §1-2 |
| Closed-industry top entries | research dossier §1-3 |
| Annotation reliability | Wang et al., arXiv 2601.08778 (research dossier §6) |
| Three industrial closed top | research dossier §8 |
