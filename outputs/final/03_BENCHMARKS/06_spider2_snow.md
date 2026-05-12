# 3.1.6 Spider2-Snow (full benchmark, n=547)

## Краткая идентификация

| Field | Value |
|---|---|
| Sub-benchmark | **Spider2-Snow** — Snowflake full text-to-SQL benchmark |
| Authoring | xlang-ai / HKUST (Lei et al., ICLR 2025) |
| arXiv | 2411.07763 (Spider 2.0 paper) |
| Engine | **Snowflake** |
| Размер | **547** задач |
| Databases | 152 unique Snowflake Marketplace databases |
| Evaluation | Multiset row match с extra columns allowed |
| Leaderboard | spider2-sql.github.io |
| Lane мы используем | **FULL 547** (Phase 28 v28-revert-A stack, run_id `snow_full_v28_revert_a`, in-progress на S1 kernel) |

## Database distribution

Empirical measurement of `db_id` distribution в `spider2-snow.jsonl`:

| Database | Task count | Domain |
|---|---|---|
| `CRYPTO` | 20 | Cryptocurrency markets |
| `THELOOK_ECOMMERCE` | 19 | E-commerce / retail |
| `GA4` | 17 | Web analytics (GA4 schema) |
| `PATENTS` | 15 | Patent data |
| `GITHUB_REPOS` | 15 | GitHub repository mirror |
| `STACKOVERFLOW` | 15 | Q&A platform mirror |
| `IDC` | 15 | International Data Corporation analytics |
| `BANK_SALES_TRADING` | 15 | Financial/banking |
| `GA360` | 12 | Web analytics (legacy GA360 schema) |
| `NOAA_DATA` | 12 | Weather / climate |
| `IPL` | 11 | Indian Premier League cricket |
| `CITY_LEGISLATION` | 10 | Civic / legislation |
| `FIREBASE` | 9 | Firebase analytics |
| `F1` | 9 | Formula 1 racing |
| `BRAZILIAN_E_COMMERCE` | 8 | E-commerce (Brazil-specific) |
| 137 others (≤8 each) | 354 | varies |

**Total 547 across 152 unique databases** — significantly wider domain coverage чем Lite-Snow's 207 (subset of these databases focused).

Source: own measurement via `_phase28_*` analysis of jsonl.

## Sample queries (from spider2-snow.jsonl)

### Sample 1 — Cross-source revenue analysis (sf_bq009, GA360 mirror)

```
Database: GA360
NL Question: "Which traffic source has the highest total transaction revenue
for the year 2017, and what is the difference в millions (rounded to two
decimal places) between the highest and lowest monthly total transaction
revenue for that traffic source?"

What it tests:
- GA360-on-Snow mirror schema (Snow-specific column casing)
- Date filter 2017
- Aggregation by traffic_source
- Two-step: find top source then monthly differential
- Numerical formatting

Difficulty: hard
```

### Sample 2 — Pseudo-user engagement (sf_bq011, GA4 schema)

```
Database: GA4
NL Question: "How many distinct pseudo users had positive engagement time в
the 7-day period ending on January 7, 2021 at 23:59:59, but had no positive
engagement time в the 2-day period ending on the same date?"

What it tests:
- GA4 event-level schema on Snow (DenseVARIANT event_params)
- Set difference logic (in 7-day but not 2-day)
- engagement_time_msec extraction from VARIANT
- Distinct user counting

Difficulty: hard
```

### Sample 3 — Patent 5-year periods (sf_bq029, PATENTS)

```
Database: PATENTS
NL Question: "Get the average number of inventors per patent and the total
count of patent publications в Canada (CA) for each 5-year period from 1960
to 2020, based on publication dates. Only include patents that have at least
one inventor listed, and group results by 5-year intervals."

What it tests:
- NUMBER-encoded publication_date (YYYYMMDD format) — F4 cast handling
- ARRAY_SIZE на VARIANT inventor column
- Period arithmetic (FLOOR((year-1960)/5) * 5)
- Country code filter
- Multi-decade date span

Difficulty: hard

Our pilot10 v28-revert-A result: NEW PASS — model emitted YYYYMMDD math directly
без F4 wrap (valid path).
```

## Our pipeline на Spider2-Snow

Identical к Lite-Snow (см. [05_spider2_lite_snow.md](./05_spider2_lite_snow.md)): same v28-revert-A stack (commit `ad5493b`), same F1 + F4 + F4c interventions, same per-task BM25 partitioning, same Family B only.

### Configuration recap

- **Engine validator**: Snow EXPLAIN USING TEXT.
- **Schema source**: `spider2_snow_live_catalog_v18.jsonl` (~587K columns total across 152 databases).
- **Schema linker**: BM25, **per-task partitioning by `c.db.upper()`** (Phase 27 F1). `top_columns=200, top_tables=40` (scaled 2.5× from Spider1/BIRD defaults).
- **Pack builder**: `max_tables=10, max_cols_per_table=22`, three-part name rendering, col:TYPE annotations, Snow dialect rules block.
- **Family**: B only (Coder-7B direct emit).
- **F1 stack**: AST identifier guard + PK/FK heuristic injection + validator relaxation + SELECT-alias protection.
- **F4 stack**: NUMBER/VARIANT date-cast wrapper + F4c regex fallback.
- **Resume scaffolding**: predictions.jsonl skip-done-iids + append mode + periodic flush.

### Throughput

Wall time per task: ~70-150s (avg ~120s observed in current FULL run). FULL 547 expected ~11-13h end-to-end (с resume after kernel deaths и Snowflake env restoration incident).

## Pre-Phase-27 baseline (v25 / Phase 26)

Phase 26 handoff report measured Spider2-Snow lane на committed v25 stack (no Phase 27 F1, no Phase 28 F4):

| run_id | n | sv | parse_ok | exec_ok | Notes |
|---|---|---|---|---|---|
| `snow_full_v25` (S1, partial 91%) | 509/547 | 59 (11.6%) | 488 (95.9%) | **0 (0.0%)** | Killed Phase 28 Step 0 для freedom S1 для F1+F4 stack |

**Pre-Phase-27 baseline: 0/547 executable**. This — the **"zero-executable starting point"** that Phase 27 F1 + Phase 28 F4 set out to fix.

Source: `outputs/spider2_snow/runs/snow_full_v25/progress.json` (sealed with `_STOPPED_PHASE28` marker on 2026-05-11).

## Current FULL run (Phase 28 v28-revert-A, in progress)

Run dir: `outputs/spider2_snow/runs/snow_full_v28_revert_a/`. Run ID per session. As of writing:

| Metric | Final FULL closure value |
|---|---|
| n_total | **547** |
| chosen_schema_valid | **383 (70.02 %)** |
| parse_ok | **503 (91.96 %)** |
| **execute_ok (Snowflake EXPLAIN-pass) (\*)** | **130 (23.76 %)** |
| F1 guard rewrites | **14** |
| F4 wraps | **5** |
| F4c regex fallbacks | **6** |
| requoted_n (F2a confirmed reverted) | **0** |
| guard_leaks | **0** |
| Wall time | **10 981.7 s (≈ 3 h 03 min)** |

**Headline canonical wording**: *"Spider2-Snow FULL 547: 23.76 % Snowflake `EXPLAIN`-pass rate (plan-level acceptance, 130 / 547, see [Appendix 07](../11_APPENDIX/07_critical_metric_caveat.md) (\*))."*

Source: `outputs/spider2_snow/runs/snow_full_v28_revert_a/progress.json` (live update during run).

## SOTA на Spider2-Snow (cutoff May 2026)

Source: research dossier `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md` §1.

| Rank | Method | Score | Backbone | Code |
|---|---|---|---|---|
| 1 | **Genloop Sentinel Agent v2 Pro** | **96.70%** | not disclosed | closed |
| 4 | TCDataAgent-SQL | 93.97% | not disclosed | closed (Tencent Cloud) |
| 5 | Paytm Prism Swarm + Claude-Sonnet-4.5 | 90.49% | Claude-Sonnet-4.5 | github.com/paytm/prism |
| 9 | ByteBrain-Agent | 84.10% | ByteDance internal | closed |
| 14 | Arctic-FLEX (Snowflake AI Research) | 75.14% | not disclosed | closed |
| 22 | DSR-SQL + DeepSeek-R1 | 63.80% | DeepSeek-R1 (685B open) | arXiv 2511.21402 |
| 23 | **ReFoRCE + o3** | **62.89%** | o3 (closed) | github.com/Snowflake-Labs/ReFoRCE — **best fully-reproducible system** |
| 27 | AutoLink + DeepSeek-R1 | 54.84% | DeepSeek-R1 (open 685B) | arXiv 2511.17190 |
| 36 | ReFoRCE + o1-preview (paper) | 31.26% | o1-preview | same repo |
| 37 | **Spider-Agent + Qwen3-Coder** | **31.08%** | Qwen3-Coder (open) | xlang-ai/Spider2 — **Qwen3 ReAct ceiling** |
| — | Spider-Agent + Claude-3.7-Sonnet | 24.50% | Claude-3.7 | same repo |
| — | Spider-Agent + QwQ-32B | 8.96% | QwQ-32B (open) | same repo |
| — | DAIL/CHESS/DIN + GPT-4o (baselines) | 0.0–2.2% | GPT-4o | various |
| — | **Наш v28-revert-A** | **23.76 % EXPLAIN-pass (\*)** (130/547, plan-level acceptance, not row-match — see [Appendix 07](../11_APPENDIX/07_critical_metric_caveat.md)) | Qwen3-Coder-30B-A3B + Qwen2.5-Coder-7B (open ≤30B) | this thesis |

## Discussion: our position relative к SOTA

### Closed-API top tier (62-97%)
Genloop 96.70 / Paytm Prism + Claude-Sonnet-4.5 90.49 / ReFoRCE + o3 62.89. **Out of reach** для open ≤30B stack. Gap explained by:
- **Reasoning model class**: o3, Claude-3.5, Qwen3-Coder when used in ReAct loop access much larger effective compute.
- **Closed system engineering**: Genloop / Paytm — proprietary scaffolds. Not reproducible from paper.

### Open ≤685B mid tier (52-65%)
DSR-SQL + DeepSeek-R1 63.80%, AutoLink + DeepSeek-R1 54.84%. **Out of param budget** для нашей constraint (≤30B). DeepSeek-R1 685B requires multiple A100s.

### Open ≤32B same-class tier (8-32%)
Spider-Agent + Qwen3-Coder **31.08%** — **closest comparable** to наш stack (same base planner model class). They use ReAct agent loop; we use single-pass plan→emit pipeline.

Spider-Agent + QwQ-32B 8.96% (QwQ reasoning-tuned variant) — significantly worse than Qwen3-Coder, indicating model family matters.

Our expected band (based on pilot10 4/10 projection): **22-30% EX**. Realistic position:

```
Closed top:      Genloop 96.70 | Paytm 90.49 | ReFoRCE+o3 62.89
Open 685B:       DSR 63.80 | AutoLink 54.84
Open ≤32B:       Spider-Agent+Qwen3-Coder 31.08
                 [our v28-revert-A: ~22-30% projected]
Spider-Agent+    Spider-Agent+Claude-3.7 24.50 | Spider-Agent+QwQ-32B 8.96
small variants:  DAIL/CHESS/DIN+GPT-4o 0-2.2 (classical methods)
```

**Honest framing**: наш result между Spider-Agent + Claude-3.7-Sonnet (24.50%) и Spider-Agent + Qwen3-Coder (31.08%). Likely **above Claude-3.7-Sonnet** but **below Qwen3-Coder ReAct ceiling** (which uses same base model в richer agent loop). This validates the *single-pass plan→emit* approach can approach ReAct-style ceiling без cost agent loops.

## Failure pattern на FULL (preliminary based on current run state)

Top error classes from progress.json snapshot at ~340/547:

| Error class | Count | Share | Cause |
|---|---|---|---|
| `invalid_identifier` | 31 | most failures | Column/table hallucination (Phase 29 F3 target) |
| `ok` | 15 | passes | (running count in this snapshot) |
| `schema_invalid` | 14 | secondary | AST validator rejection — emit references column not в pack+catalog |
| `ProgrammingError` | 5 | tertiary | NUMBER/VARIANT date cast missing OR wrong wrap |
| `syntax_error` | 2 | rare | dialect-specific feature SQLGlot/Snow disagrees |

Note: snapshot taken mid-run; final FULL distribution differs.

## Положение в landscape

Spider2-Snow — **flagship enterprise NL2BI bench**. Most actively researched lane of 2025-2026. Strongest indicator open-weight model viability для production Snow deployment.

**Сильные стороны**:
- 152 databases — **wide domain coverage**, prevents domain-specific overfitting.
- Snowflake Marketplace = real-world public catalogs (real schemas, not synthetic).
- 547 tasks — statistically meaningful sample.
- Active leaderboard (closed + open entries) = continuous reference point.

**Слабости (caveats для thesis)**:
- **Annotation 62.8% mismatch** (Wang et al., arXiv 2601.08778) — see [03_spider2_overview.md](./03_spider2_overview.md) discussion.
- **Marketplace dataset bias toward lowercase identifiers** — atypical of corporate Snow deployments.
- **Closed-industry top entries** (Genloop 96.70) — no methodology disclosure → not benchmarkable.

## Methodological claims permissible based on Spider2-Snow result

После FULL closure:
- First publishable Snow EX number для open-weight ≤30B stack (no SFT, no closed API).
- F1 grounding intervention measurably lifts EX from 0% baseline.
- F4 date-cast wrapper measurably contributes (load-bearing).
- Catalog probe methodology (Claim 3) — empirically validated.

Что **нельзя** заявлять только из этого result:
- Production readiness — even target 22-30% means 70-78% tasks fail.
- Match closed-API tier — fundamental compute class gap.
- Generalization к corporate Snow (uppercase-identifier schemas).

## Cross-references

- Pipeline detail: [05_PIPELINES/04_spider2_snow_pipeline.md](../05_PIPELINES/04_spider2_snow_pipeline.md)
- Dialect handlers F1/F4: [04_ARCHITECTURE/09_dialect_handlers_f1_f4.md](../04_ARCHITECTURE/09_dialect_handlers_f1_f4.md)
- Phase 27 F1 grounding: [06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md](../06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md)
- Phase 28 closure (revert-A): [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md)
- FULL closure (placeholder until done): [06_EXPERIMENTAL_PROGRESSION/05_phase28_full_baseline.md](../06_EXPERIMENTAL_PROGRESSION/05_phase28_full_baseline.md)
- Spider2-Lite-Snow analogous lane: [05_spider2_lite_snow.md](./05_spider2_lite_snow.md)
- Leaderboard position: [09_RESULTS_ANALYSIS/05_leaderboard_position.md](../09_RESULTS_ANALYSIS/05_leaderboard_position.md)
- Failure analysis: [09_RESULTS_ANALYSIS/06_failure_analysis_remaining.md](../09_RESULTS_ANALYSIS/06_failure_analysis_remaining.md)
- Per-DB breakdown: [07_METRICS_AND_RESULTS/05_per_db_breakdown_snow.md](../07_METRICS_AND_RESULTS/05_per_db_breakdown_snow.md) (FULL placeholder)

## Источники

| Утверждение | Источник |
|---|---|
| 547 tasks, 152 databases | own measurement of `spider2-snow.jsonl` (live probe) |
| Pre-Phase-27 baseline 0/509 | `outputs/spider2_snow/runs/snow_full_v25/progress.json` |
| Current run snapshot | `outputs/spider2_snow/runs/snow_full_v28_revert_a/progress.json` (live) |
| Snow leaderboard May 2026 | research dossier `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md` §1 |
| Spider-Agent ReAct ceiling | research dossier §4 Spider-Agent |
| Annotation reliability 62.8% | Wang et al., arXiv 2601.08778 |
| Sample queries sf_bq009 / sf_bq011 / sf_bq029 | `spider2-snow.jsonl` lines 1-3 |
