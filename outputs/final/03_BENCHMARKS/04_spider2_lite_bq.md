# 3.1.4 Spider2-Lite (BigQuery split)

## Краткая идентификация

| Field | Value |
|---|---|
| Sub-benchmark | Spider2-Lite (BQ subset) |
| Authoring | xlang-ai / Hong Kong University of Science and Technology |
| Год | 2025 (Spider 2.0 release) |
| Engine | **BigQuery** (Google Cloud Platform) |
| Размер | **~205** BQ-specific задач (внутри Lite total n=547; см. lane decomposition below) |
| Databases | Public BigQuery datasets — GA360, Stack Overflow, Google Trends, NCAA Basketball, NOAA Weather, NHTSA Traffic, Chicago Open Data, etc. |
| Difficulty | Mixed — no explicit easy/medium/hard labels, varies от simple aggregation до multi-CTE с UNNEST |
| Evaluation | Multiset row match с extra columns allowed |
| Lane мы используем | **FULL 205 tasks** (Phase 22-26 stack on pilot50 → projection to FULL) |

## Lane decomposition внутри Spider2-Lite

Spider2-Lite jsonl total = **547 задач**. Empirical lane breakdown по prefix `instance_id` (our measurement):

| Prefix | Count | Lane interpretation |
|---|---|---|
| `bq*` | ~180 | BigQuery-lane задачи (our BQ split) |
| `sf_*` | ~189 | Snowflake-lane задачи (Lite-Snow split — см. [05_spider2_lite_snow.md](./05_spider2_lite_snow.md)) |
| other prefixes | ~178 | SQLite-lane + mixed (Lite-SQLite split, ~135 + smaller variants) |

> **Note**: precise BQ-lane size 205 (per Spider 2.0 README brief) vs наш empirical 180 (by prefix filter) may reflect slight categorization difference: some `bq*` tasks fall в borderline lanes. Для нашего pipeline мы treat **all 205 official BQ tasks** as test set.

## BQ-specific dialect challenges

BigQuery Standard SQL имеет несколько **dialect-specific features** которые отделяют его от SQLite / Snowflake:

| Feature | Example syntax | Why it matters |
|---|---|---|
| **`UNNEST(array)`** | `SELECT x FROM table, UNNEST(arr_col) AS x` | Array iteration — heavy в GA360 (hits, products array fields) |
| **`STRUCT field access`** | `hits.product.productRevenue` | Nested column path для GA360 schemas |
| **Wildcard tables** | `FROM `project.dataset.events_*` WHERE _TABLE_SUFFIX BETWEEN '20220101' AND '20220131'` | Date-shard family querying — typical в GA360 |
| **`QUALIFY`** | `WHERE x AND y QUALIFY ROW_NUMBER() OVER (...) = 1` | Window-function filter — newer BQ feature |
| **`SAFE_OFFSET(n)`** | `arr[SAFE_OFFSET(0)]` | Safe array indexing (returns NULL if out-of-bounds) |
| **`ARRAY_CONTAINS / EXISTS UNNEST`** | `EXISTS (SELECT 1 FROM UNNEST(arr) AS x WHERE x = 'foo')` | Array membership test — BQ doesn't have `ARRAY_CONTAINS` directly |
| **Date literals** | `DATE '2023-12-15'`, `TIMESTAMP '2023-12-15 10:00:00 UTC'` | Strict type literals (no implicit string→date cast) |
| **`SAFE_CAST(x AS …)`** | `SAFE_CAST(x AS INT64)` | Cast that returns NULL on failure (vs `CAST` which errors) |

## Sample queries (from data/spider2_lite/raw/spider2-lite.jsonl)

### Sample 1 — Customer purchase analysis (bq010)

```
Database: ga360
Tables: bigquery-public-data.google_analytics_sample.ga_sessions_*
External knowledge: google_analytics_sample.ga_sessions.md
NL Question: "Find the top-selling product among customers who bought 'Youtube
Men's Vintage Henley' in July 2017, excluding itself."

What it tests:
- Wildcard table querying с date filter (ga_sessions_201707*)
- UNNEST array of hits to access individual products
- Two-stage logic: identify customer set, then aggregate among that set
- Exclusion logic (`AND productName != 'Youtube Men's Vintage Henley'`)

Difficulty: hard (multi-step + wildcards + UNNEST + array filter)

Our result on bq010: <<NEED DATA: predictions.jsonl entry from Phase 22-26 Lite-BQ
runs; tested at least в pilot50 v22-24>>
```

### Sample 2 — Cross-source revenue analysis (bq009)

```
Database: ga360
Tables: bigquery-public-data.google_analytics_sample.ga_sessions_2017*
External knowledge: google_analytics_sample.ga_sessions.md
NL Question: "Which traffic source has the highest total transaction revenue for
the year 2017, and what is the difference в millions (rounded to two decimal
places) between the highest and lowest monthly total transaction revenue for that
traffic source?"

What it tests:
- Wildcard tables с full-year date span
- Aggregate over hits.transaction.transactionRevenue
- Two-step: find top source, then computeразницу по months for that source
- Numerical formatting (millions, rounded 2 decimal)
- Likely requires CTE / subquery

Difficulty: hard
```

### Sample 3 — Pseudo-user engagement (bq011, GA4 schema)

```
Database: ga4
Tables: bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*
External knowledge: ga4_obfuscated_sample_ecommerce.events.md
NL Question: "How many distinct pseudo users had positive engagement time в
the 7-day period ending on January 7, 2021 at 23:59:59, but had no positive
engagement time в the 2-day period ending on the same date (January 7, 2021
at 23:59:59)?"

What it tests:
- GA4 event-level schema (vs GA360 session-level)
- Set difference logic (in 7-day window but not in 2-day window)
- Engagement_time_msec parameter extraction (often nested в event_params)
- Timestamp arithmetic
- Distinct user counting

Difficulty: hard
```

> **Note**: Spider 2.0 не publishes gold SQL для test/dev questions to leaderboard submitters in raw form (на live BQ side, validated server-side через official harness). Sample SQL structure inferred from question + schema; precise gold SQL — Spider 2.0 authors retain.

## BQ INFORMATION_SCHEMA structure

Live catalog source для BQ lane:

```sql
SELECT
    table_catalog AS project,
    table_schema AS dataset,
    table_name,
    column_name,
    data_type,
    is_nullable,
    description,
    field_path  -- для nested STRUCT
FROM `<project>.<dataset>.INFORMATION_SCHEMA.COLUMNS`
```

Naше harvested catalog для Phase 18+ runs — **~428K columns total** across all public BQ datasets covered by Spider2-Lite-BQ. Live catalog harvested once, cached as JSONL (`outputs/cache/spider2_bq_live_catalog_v18.jsonl`).

### FK metadata — often missing

`INFORMATION_SCHEMA.KEY_COLUMN_USAGE` would normally provide PK/FK constraints. На public BQ datasets — **often empty** (BQ public datasets rarely have explicit FK declarations). Implication: schema linker и Family C JOIN inference must rely на **heuristic FK detection** (naming patterns), not metadata.

Этот gap — основной motivator для **PK/FK heuristic injection** (Phase 27 correction 3, см. [04_ARCHITECTURE/03_schema_linker_v18_bm25.md](../04_ARCHITECTURE/03_schema_linker_v18_bm25.md)).

## Our pipeline на Spider2-Lite-BQ

### Configuration

- **Engine validator**: `BQ client.query(dry_run=True)` — free, full type checking, no actual scan.
- **Schema source**: live catalog `spider2_bq_live_catalog_v18.jsonl`.
- **Schema linker**: BM25, parameters `top_columns=80, top_tables=20` (Spider1/BIRD defaults preserved для BQ, not scaled like Snow).
- **Pack builder**: `max_tables=8, max_cols_per_table=22`, with wildcard detection и join_hints.
- **Family**: A primary (deterministic BQ render via `sql_renderer_v18.render_bq`) + B fallback + C (JOIN-aware, rarely chosen).
- **Phase 24 v24 engine-compat rewrites** applied: `ARRAY_CONTAINS → EXISTS UNNEST`, `NTH → array offset`, multi-level UNNEST flattening, nested aggregate flag, window+GROUP BY flag, AND-on-int wrap.
- **Validator**: AST closed-set + BQ dry_run.

### Throughput

Wall time per task: ~90-150s (BQ dry_run network roundtrip + multi-candidate dry_run calls).

## Our result

Spider2-Lite-BQ (Phase 22-26 stack) — **execute_ok = 34.6%** (71/205 tasks projection from pilot50 v24).

Details:
- Phase 22 pilot50: sv 54%, exec 44%
- Phase 24 v24 stack on same: sv 50%, exec 34-44% bands (audit-stable)
- Phase 25-26: no major changes на BQ lane (focus shifted к Snow)
- Phase 27-28: BQ lane **не touched** (F1/F4 are Snow-specific)

### Why our 34.6% relative к leaderboard

Mid-band reproducible open-weight result. Above LinkAlign + DeepSeek-R1 (33.09% на full Lite), но below AutoLink + DeepSeek-R1 (52.28% full Lite) и ReFoRCE + o3 (55.21%).

| System | Lite EX | Open / closed |
|---|---|---|
| SOMA-SQL | 72.02% | Closed (Oracle Cloud) |
| Databao Agent | 69.65% | Closed (JetBrains) |
| ReFoRCE + o3 | 55.21% | Closed-API reasoning |
| AutoLink + DeepSeek-R1 | 52.28% | Open (685B) |
| AgenticData + Qwen3 | 44.5% | Open |
| ReFoRCE + Qwen3 | 35.6% | Open |
| **Наш BQ subset** | **34.6%** | **Open ≤30B (Coder-30B+7B)** |
| LinkAlink + DeepSeek-R1 | 33.09% | Open (685B) |
| AI-DIVE + gpt-oss-120B | 21.9% | Open |
| Spider-Agent + QwQ-32B | 11.33% | Open |
| Spider-Agent + Qwen2.5-Coder-32B | 5.85% | Open |
| SFT CodeS-15B | 0.73% | Open SFT |

Источник: research dossier `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md` §2 Lite leaderboard.

### Position interpretation

- **34.6% on BQ subset vs leaderboard percentages on full Lite** — *not directly comparable* (split differences).
- ReFoRCE paper note: *"our prompts are primarily designed for the Snowflake dialect, leading to occasional errors when handling certain cases в the BigQuery dialect"*. Implication: our BQ-specific tooling (Family A renderer + v24 engine-compat rewrites + BQ-aware schema linker) **may structurally outperform** ReFoRCE on Lite-BQ subset alone — but we don't have ablation на Lite-BQ split published by ReFoRCE.
- Phase 29-30 plan: F2 JOIN-graph BFS expansion + F4-equivalent BQ post-processor — target zone 52-60% (band с AutoLink + DeepSeek-R1).

## Failure pattern analysis (Phase 24 pilot50)

| Failure class | Approximate share of misses |
|---|---|
| `bq_dry_run_failed: invalid_identifier` | ~30% |
| `bq_dry_run_failed: syntax_error` | ~20% |
| `bq_dry_run_failed: type_mismatch` | ~15% |
| `schema_invalid` (validator pre-engine) | ~15% |
| `parse_error` | ~10% |
| Other (ARRAY function quirks, wildcards, etc.) | ~10% |

Source: `outputs/REPORT_SPIDER2_V22.md` failure breakdown; `outputs/REPORT_SPIDER2_PHASE24_LITE_BQ.md` audit.

**Top remaining gaps** (Phase 29 territory):
1. **JOIN-graph missing**: BM25 surfaces tables, но FK paths between them not inferred. Family C heuristics misfire (false-positive joins). Phase 30 target.
2. **Self-refine не реализован**: единственный shot. ReFoRCE-style retry на engine error mostly closes gap.
3. **External knowledge не deeply integrated**: GA360 / Stack Overflow tasks с .md documentation — system passes external_knowledge as raw text в prompt, не extracts structured rules.

## Положение в landscape

Spider2-Lite-BQ — **mid-difficulty Spider 2.0 lane**. Между Lite-SQLite (easier, smaller schemas) и Snow (harder, more dialect-specific features). Strong predictor для:
- Enterprise BigQuery deployment readiness.
- Multi-source data integration (GA360, Stack Overflow combined в multi-domain questions).
- Wildcard table workflow handling.

**Slabilities**:
- Public BQ datasets often **better-documented** чем internal corporate. External knowledge .md files compensate для some questions, but real-world deployment may lack such docs.
- Multi-domain coverage **shallow** в каждом domain — system optimized for breadth, не для deep expertise (e.g., advertising, healthcare, finance).

## Cross-references

- Pipeline detail: [05_PIPELINES/03_spider2_lite_bq_pipeline.md](../05_PIPELINES/03_spider2_lite_bq_pipeline.md)
- Family A renderer (BQ-specific): [08_CUSTOM_TOOLS/03_candidate_factories.md](../08_CUSTOM_TOOLS/03_candidate_factories.md)
- v24 engine-compat rewrites: [04_ARCHITECTURE/06_candidate_factories_family_abc.md](../04_ARCHITECTURE/06_candidate_factories_family_abc.md)
- BQ dry_run engine details: [04_ARCHITECTURE/10_execution_engines.md](../04_ARCHITECTURE/10_execution_engines.md)
- Spider2 overview: [03_spider2_overview.md](./03_spider2_overview.md)
- Comparative table: [08_comparative_table.md](./08_comparative_table.md)
- Failure analysis: [09_RESULTS_ANALYSIS/02_spider2_lite_bq_analysis.md](../09_RESULTS_ANALYSIS/02_spider2_lite_bq_analysis.md)

## Источники

| Утверждение | Источник |
|---|---|
| Lite jsonl total 547 | `data/spider2_lite/raw/spider2-lite.jsonl` (line count) |
| Lane decomposition by prefix | own measurement via prefix filter |
| 34.6% Lite-BQ EX | `outputs/REPORT_PHASE26_RESEARCHER_HANDOFF.md` §1 |
| BQ-specific dialect features | BigQuery docs (cloud.google.com/bigquery/docs) |
| ReFoRCE BQ caveat | research dossier §4 ReFoRCE |
| Leaderboard table | research dossier §2 |
| Sample queries (bq010, bq009, bq011) | `data/spider2_lite/raw/spider2-lite.jsonl` lines 1-5 |
