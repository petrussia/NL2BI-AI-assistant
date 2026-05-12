# 3.1.5 Spider2-Lite (Snowflake split)

## Краткая идентификация

| Field | Value |
|---|---|
| Sub-benchmark | Spider2-Lite (Snow subset, prefix `sf_*` в Lite jsonl) |
| Authoring | xlang-ai / HKUST |
| Год | 2025 (Spider 2.0 release) |
| Engine | **Snowflake** |
| Размер | **207** Snowflake-lane задач (наш v26 FULL run had n=207) |
| Databases | Snowflake Marketplace public datasets: PATENTS, CYBERSYN, GA360 mirror, TCGA, GITHUB_REPOS, FINANCE__ECONOMICS, etc. |
| Evaluation | Multiset row match с extra columns allowed |
| Lane мы используем | **FULL 207 tasks** (v26 baseline + Phase 28 FULL revert-A run в Spider2-Snow runner с `instance_ids_set` filter) |

## Lane-specific characteristics

Spider2-Lite-Snow эффективно — **subset Spider2-Snow full benchmark** scoped to 207 представительных задач. Same Snowflake Marketplace databases.

| Aspect | Lite-Snow | Lite-BQ |
|---|---|---|
| Engine | Snowflake | BigQuery |
| Schema source | Snow `INFORMATION_SCHEMA.COLUMNS` | BQ `INFORMATION_SCHEMA.COLUMNS` |
| Dialect | Snowflake SQL | BQ Standard SQL |
| Database paradigm | Snowflake Marketplace (public catalogs) | GCP public datasets |
| FK metadata | typically absent | typically absent |
| Identifier case convention | **lowercase** (catalog-stored as-created with quoted lowercase identifiers) | mixed (most BQ public lowercase, some uppercase) |
| File renderer Family A | **not implemented** (deferred Phase 30) | implemented |
| Family C JOIN-aware | **not implemented for Snow** | implemented (BQ) |

## Snowflake-specific dialect challenges

| Feature | Example syntax | Why it matters |
|---|---|---|
| **Three-part identifiers** | `DATABASE.SCHEMA.TABLE` | Strict requirement; relative names требуют `USE DATABASE / USE SCHEMA` context |
| **`LATERAL FLATTEN`** | `FROM table, LATERAL FLATTEN(INPUT => arr_col) AS f` | Snow's array iteration (vs BQ's `UNNEST`) |
| **`IFF(c, a, b)`** | `IFF(x > 0, 'positive', 'negative')` | Conditional expression (vs SQLite/BQ `CASE WHEN`) |
| **`QUALIFY`** | `... WHERE x QUALIFY ROW_NUMBER() OVER (...) = 1` | Window-function row filter (also в BQ) |
| **JSON path syntax** | `payload:user.name::STRING` или `arr[0]:field` | **Colon**, не `->` like Postgres |
| **VARIANT type** | Type holding JSON object/array; access via colon paths | Common в Spider2-Snow для denormalized data |
| **Identifier case** | Unquoted → folded to UPPERCASE; quoted → preserved exactly | **Critical** — catalog probe Phase 28 §6 |

## Critical context: lowercase catalog storage в Spider2-Snow

**Empirical observation (Phase 28 §6)**: Spider2-Snow public Marketplace datasets store identifiers **lowercase**. PATENTS.PATENTS.PUBLICATIONS table has **37/37 columns stored lowercase**:

```
'family_id', 'publication_number', 'grant_date', 'country_code',
'assignee', 'assignee_harmonized', 'citation', 'fterm', ...
```

Не `FAMILY_ID`, `PUBLICATION_NUMBER`. Это **противоречит** common Snowflake convention (unquoted folding to uppercase, default storage uppercase). Дата creator likely использовал `CREATE TABLE "lower_case_name"` with quotes, preserving lowercase exactly.

**Implication для NL2SQL**:
- Model emitting `SELECT family_id FROM PUBLICATIONS` — Snow folds unquoted `family_id` to `FAMILY_ID` → "invalid identifier" because catalog has lowercase `family_id`.
- Model emitting `SELECT "family_id" FROM "PUBLICATIONS"` — exact-case match → works.
- F2a hypothesis (Phase 28) — auto-upper quoted identifiers — was based на wrong assumption (Snow stores upper). Falsified by catalog probe. Reverted.

См. полную story в [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md).

## Sample queries (from Spider2-Lite raw jsonl, Snow lane)

### Sample 1 — Patent analysis (sf_bq029)

```
Database: PATENTS
NL Question: "Get the average number of inventors per patent and the total count
of patent publications в Canada (CA) for each 5-year period from 1960 to 2020,
based on publication dates. Only include patents that have at least one inventor
listed, and group results by 5-year intervals (1960-1964, 1965-1969, etc.)."

What it tests:
- PATENTS.PUBLICATIONS table querying (37+ columns)
- NUMBER-encoded publication_date (YYYYMMDD as NUMBER(38,0) — F4 cast critical)
- 5-year period grouping arithmetic
- Array length для inventor list (VARIANT array)
- Country filter on country_code
- Multi-decade date span

Difficulty: hard (NUMBER date cast + VARIANT array length + period grouping)

Our pilot10 v28-revert-A result: NEW PASS — model emitted YYYYMMDD math directly
  `FLOOR(("publication_date" / 10000 - 1960) / 5) * 5 AS "five_year_period"`
  без F4 wrap (но valid в Snow as arithmetic on NUMBER).
```

### Sample 2 — Disclosures + citations join (sf_bq027)

```
Database: PATENTS
NL Question: "Получить for each publication: the count of backward citations
that have standard ('SEA') in the discsoures_13 table, joined on publication_number
to spif_publication_number, filtered to grant_date BETWEEN '2010-01-01' AND '2018-12-31'"

What it tests:
- Multi-table JOIN: PUBLICATIONS ⋈ DISCLOSURES_13 (on different join keys —
  spif_publication_number ≠ publication_number)
- COUNT DISTINCT aggregation
- Date range filter (NUMBER format)
- Mixed-case quoting (column 'citation' in d13)

Difficulty: hard (cross-table join с heterogeneous key naming)

Our pilot10 v28-revert-A result: still fails — model emits LATERAL FLATTEN with
  invalid `"c"."value"` reference (LATERAL FLATTEN не handled correctly for
  this VARIANT path)
```

### Sample 3 — Time-range entity status filter (sf_bq211)

```
Database: PATENTS
NL Question: "How many granted patents с status='Granted' filed by Chinese
applicants ('CN' anywhere в assignee string) от 2010-2023, что have multiple
family members (family_id appearing >1 times)?"

What it tests:
- Filtering on entity_status text column
- LIKE pattern matching on VARIANT assignee column
- HAVING aggregate filter (COUNT > 1)
- GROUP BY family_id
- DATE range filter

Difficulty: medium

Our pilot10 v28-revert-A result: PASS — the one task executable since v25 baseline.
  Final SQL (post Phase 28 revert-A):
  SELECT COUNT(DISTINCT "p"."family_id") FROM "PATENTS"."PATENTS"."PUBLICATIONS" AS "p"
  WHERE "p"."entity_status" = 'Granted'
    AND "p"."grant_date" BETWEEN 20100101 AND 20231231
    AND "p"."assignee" LIKE '%CN%'
  GROUP BY "p"."family_id"
  HAVING COUNT(DISTINCT "p"."family_id") > 1
```

## Our pipeline на Spider2-Lite-Snow

### Configuration (Phase 28 v28-revert-A stack, committed `ad5493b`)

- **Engine validator**: `Snow EXPLAIN USING TEXT` (no warehouse credit).
- **Schema source**: live catalog `spider2_snow_live_catalog_v18.jsonl` (~587K columns).
- **Schema linker**: BM25, **per-task partitioning by `c.db.upper()`** (Phase 27 F1). `top_columns=200, top_tables=40` (scaled 2.5× from Spider1/BIRD defaults for warehouse-scale).
- **Pack builder**: `max_tables=10, max_cols_per_table=22`, with three-part name rendering + col:TYPE annotations + Snow dialect rules block.
- **Family**: **B only** (Coder-7B direct emit). Family A renderer for Snow not implemented; Family C JOIN-aware also Snow-deferred.
- **Phase 27 F1 stack**: AST identifier guard + PK/FK heuristic injection + validator relaxation with task_db catalog cols + SELECT-alias protection.
- **Phase 28 F4 stack**: NUMBER/VARIANT date-cast wrapper (`snow_dialect_fixer_v28.wrap_date_fn_on_nondate`) + F4c guard regex fallback на SQLGlot ParseError.

### Throughput

Wall time per task: ~70-120s (planner + emitter inference dominates; Snow EXPLAIN <1-2s typically).

## Our results — progression

| Version | run_id | n | sv | parse_ok | exec_ok | Comments |
|---|---|---|---|---|---|---|
| **v26 baseline** | `lite_snow_full_v26` | 207 | 26 (12.6%) | 194 (93.7%) | **1 (0.48%)** | Pre-Phase-27 stack |
| Pilot10c (Phase 27 closure) | `lite_snow_pilot10_v27c` | 10 | 8/10 | 9/10 | **1/10** | F1 grounding only — schema gate cleared, exec stuck |
| Pilot10 v28 (Phase 28 initial) | `lite_snow_pilot10_v28` | 10 | 7/10 | 9/10 | **0/10** | **REGRESSION** — F2a + prompt rule broke sf_bq211 |
| **Pilot10 v28-revert-A** | `lite_snow_pilot10_v28_revertA` | 10 | 6/10 | 10/10 | **4/10** | **Closure** — F2a reverted, F4 load-bearing |
| **FULL 207 v28-revert-A** | `lite_snow_full_v28_revert_a` | **partial n=40 of 207** | partial | partial | partial — full closure deferred to Phase 28b (\*) | kernel-death event during run; supervisor auto-handoff did not fire; manual restart deferred per dossier deadline. Pilot10 v28-revert-A trends consistent with 4/10 EXPLAIN-pass. |

Источник: Phase 27 + 28 reports в `outputs/REPORT_PHASE2*.md`.

## Position relative to leaderboard (May 2026)

Spider2-Lite-Snow split rarely reported separately by other systems — большинство reports на full Lite (mixed split):

| System | Full Lite EX | Lite-Snow inferred share |
|---|---|---|
| SOMA-SQL (Oracle) | 72.02% | proprietary breakdown |
| Databao Agent | 69.65% | proprietary |
| ReFoRCE + o3 | 55.21% | likely higher on Snow split (Snow-prompted) |
| AutoLink + DeepSeek-R1 | 52.28% | varies |
| AgenticData + Qwen3 | 44.5% | open |
| ReFoRCE + Qwen3 | 35.6% | open |
| **Наш v28-revert-A — Lite-Snow FULL 207** | partial n=40/207 (\*) — full closure deferred to Phase 28b | direct measurement on partial; cross-metric (наш EXPLAIN-pass vs leaderboard row-match) |
| Spider-Agent + Qwen2.5-Coder-32B | 5.85% (full Lite) | open ≤32B reference |

**Critical context**: per ReFoRCE paper (research dossier §4): *"our prompts are primarily designed for the Snowflake dialect"* → ReFoRCE's full Lite 55.21% likely **higher на Snow** than on BQ within the same 547. Если ReFoRCE achieves ~62-65% Snow split, наш result would still meaningfully lag (open ≤30B vs closed o3 reasoning).

## Failure pattern на pilot10 v28-revert-A (post-closure)

| Task | Failure mode | F4 wrap status | Phase 29 target? |
|---|---|---|---|
| sf_bq026 | **PASS** (F4 wrapped DATE col) | wrapped 1 | resolved |
| sf_bq027 | LATERAL FLATTEN "c"."value" rejected | 0 | yes — SQLGlot upgrade / fallback |
| sf_bq029 | **PASS** (model wrote YYYYMMDD math directly) | 0 | resolved |
| sf_bq033 | Hallucinated "Publications" mixed-case alias | 2 | yes — F3 self-refine |
| sf_bq091 | F4 over-wrapped VARIANT `assignee` (JSON object, не date) | 2 | yes — F4 false-positive guard |
| sf_bq099 | F4 wrap altered SQL such что validator rejected | 1 | yes — validator-aware F4 |
| sf_bq209 | Hallucinated CITATIONS table | 1 | yes — F3 self-refine |
| sf_bq210 | LATERAL FLATTEN SQLGlot ParseError downstream of guard | 0 | yes — sqlglot upgrade |
| **sf_bq211** | **PASS** (recovered после revert) | 0 | n/a |
| sf_bq213 | **PASS** (F4 wrapped VARIANT fterm) | 2 | resolved |

Источник: `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §10.

## Положение в landscape

Spider2-Lite-Snow — **most direct measurement** open ≤30B Snow performance с фокусом на 207 tasks where annotation tests fully validated. Tighter sample chем full Spider2-Snow 547 → faster iteration, more reliable per-DB pattern analysis.

Strong predictor для:
- Open-weight Snow deployment с aktive Marketplace datasets.
- Dialect post-processor effectiveness (F4 wraps measurably).
- Identifier grounding (F1 closes the cross-DB drift gap).

**Slabilities**:
- Snow Marketplace datasets predominantly **lowercase identifier storage** — atypical of corporate Snow deployments (which often use uppercase quoted or unquoted-folded-to-upper). Generalization к corporate Snow uncertain.
- Limited domain coverage в 207 tasks — heavy on PATENTS, CYBERSYN, TCGA, GA360 mirror. Other industry verticals underrepresented.

## Cross-references

- Pipeline detail: [05_PIPELINES/04_spider2_snow_pipeline.md](../05_PIPELINES/04_spider2_snow_pipeline.md)
- Dialect handlers F1/F4: [04_ARCHITECTURE/09_dialect_handlers_f1_f4.md](../04_ARCHITECTURE/09_dialect_handlers_f1_f4.md)
- Phase 27 F1 grounding: [06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md](../06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md)
- Phase 28 F2a revert: [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md)
- Spider2-Snow full benchmark: [06_spider2_snow.md](./06_spider2_snow.md)
- Failure analysis: [09_RESULTS_ANALYSIS/03_spider2_snow_analysis.md](../09_RESULTS_ANALYSIS/03_spider2_snow_analysis.md)
- Snow engine: [04_ARCHITECTURE/10_execution_engines.md](../04_ARCHITECTURE/10_execution_engines.md)

## Источники

| Утверждение | Источник |
|---|---|
| 207 Snow-lane tasks в Lite | `outputs/spider2_lite/runs/lite_snow_full_v26/` (predictions count) |
| Lowercase identifier storage finding | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §6 |
| Pilot10c → pilot10 v28 → revert-A progression | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §10 |
| Sample queries sf_bq029 / sf_bq027 / sf_bq211 | `data/spider2_lite/raw/spider2-lite.jsonl` + pilot10 trace details |
| Per-task failure analysis | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §10 |
| ReFoRCE Snow-prompted preference | research dossier §4 |
