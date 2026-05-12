# 5.3 Phase 27 — F1 Snow identifier grounding

## Opening question

After Phase 26 handoff identified **cross-DB identifier drift** as the root cause of Spider2-Snow 0% baseline, **can we close the gap to non-zero EX через F1 intervention alone — without F3 self-refine?**

Phase 27 was the focused engineering phase to answer this. F1 fix: TABLE_CATALOG filter + three-part name rendering + SQLGlot AST guard, designed directly from LinkAlign / ReFoRCE methodology insights.

Acceptance criteria: pilot10 schema_valid ≥ 5/10 (gate), execute_ok ≥ 2/10 (gate), target 3-4/10.

## The Snow 0% baseline state going in

Phase 25 + Phase 26 handoff report measured:

| Run | n | sv | parse_ok | exec_ok | Notes |
|---|---|---|---|---|---|
| `snow_full_v25` (Phase 25, S1 partial 91%) | 509/547 | 59 (11.6%) | 488 (95.9%) | **0 (0.0%)** | Pre-Phase-27 baseline — zero executable |
| `lite_snow_full_v26` (Lite-Snow analog, FULL 207) | 207 | 26 (12.6%) | 194 (93.7%) | **1 (0.48%)** | Same architecture, 0.5% accidentally executable (sf_bq211) |

`parse_ok = 93.7-95.9%` indicates **SQL is syntactically valid**. `schema_valid = 11-12%` low — **AST validator rejects many** because identifiers не в pack. But **exec_ok = 0%** despite many `schema_valid = True` — это main puzzle.

## Diagnostic step 1: catalog drift probe

Phase 27 Step 1 — direct probe of v26 Lite-Snow predictions classifying each task's catalog usage:

```python
# tools/remote_scripts/_phase27_step1_diagnostic.py
import re
FROM_RE = re.compile(r'\b(?:FROM|JOIN)\s+([\w\."`]+)', re.IGNORECASE)

for task в lite_snow_v26_predictions:
    sql = task['sql']
    refs = FROM_RE.findall(sql)
    for ref в refs:
        parts = ref.replace('"','').split('.')
        if len(parts) == 3:
            cat = parts[0].upper()
            if cat == task_db: tag = 'correct'
            elif cat in valid_snow_dbs: tag = 'wrong'
            else: tag = 'unknown'
        else:
            tag = 'no_cat'  # bare TABLE or SCHEMA.TABLE
```

### Result

```
correct_only  (all FROM use task_db catalog):  18 (8.7%)
wrong/unknown (all FROM NOT task_db):         164 (79.2%)
no_catalog    (bare TABLE or SCHEMA.TABLE):     5 (2.4%)
mixed         (some correct + some wrong):     16 (7.7%)
VERDICT: (wrong + no_catalog + mixed) = 90.2%
```

**90.2% of tasks emit identifiers outside their task.db catalog**. Direct alignment с LinkAlign §1 problem statement.

## Root cause: empty alias field на Snow catalog rows

Diagnostic deeper: `c.alias` field в `CatalogColumn` dataclass — populated **only для BQ** by catalog harvester. Snow rows have `c.alias == ''`. The `SchemaLinker.query(alias_filter='PATENTS')` filter was **no-op** на Snow rows because no row matched.

Effect: BM25 ranking happened over **entire 587K columns across 152 databases**. Top-K hits leaked competitor catalogs (e.g., `FINANCE__ECONOMICS`, `CYBERSYN`) into pack для tasks where `task_db = 'PATENTS'`. Planner emitted three-part names referencing wrong catalog.

This was the **invisible architectural bug**, lying undetected since Phase 18 (when alias field was first introduced).

## Three F1 corrections

Phase 27 implemented three layered fixes:

### Correction 1: TABLE_CATALOG filter at runner level

```python
# tools/remote_scripts/_phase27_snow_runner.py
full_catalog = sl.load_catalog_jsonl(cat_path, 'snow')
cat_by_db = defaultdict(list)
for c in full_catalog:
    cat_by_db[c.db.upper()].append(c)

for task in tasks:
    task_db = task.get('db').upper()
    cat_subset = cat_by_db.get(task_db, [])   # 5K-50K cols subset
    linker = sl.SchemaLinker(cat_subset)        # fresh BM25 over subset
    link = linker.query(question, db_filter=task_db,
                          top_columns=200, top_tables=40)
```

**Per-task fresh BM25 build** на subset corresponding к `task.db`. **Catalog leak impossible** because foreign-DB rows literally not in BM25 index.

Defense in depth: `schema_pack_builder_v18.build_pack` also filters within itself (Phase 27 STAGE F1 patch).

### Correction 2: Three-part name rendering для Snow

```python
# schema_pack_builder_v18.pack_to_planner_prompt:
_snow_lane = pack.get('lane') in ('snow', 'lite_snow')
_task_db = (pack.get('alias') or '').upper() if _snow_lane else None

for t in pack['tables']:
    db_render = (_task_db if _snow_lane and _task_db else t["db"])
    lines.append(f'  - `{db_render}.{t["schema"]}.{t["table"]}` columns=[{cols}]')
```

**Forces correct catalog name** в rendered schema (override any residual `t['db']` leak). Plus added explicit "Snow rules" block to planner prompt:

```
Snowflake SQL rules:
- ALWAYS use three-part identifiers: DATABASE.SCHEMA.TABLE.
- Available database for this query: PATENTS.
- Do NOT reference any other database. Tables from other databases will be rejected at validation.
- Quote mixed-case identifiers: "ParticipantBarcode".
- Use LATERAL FLATTEN(INPUT => col) for array unnest, NOT UNNEST.
- Use IFF(c,a,b) or CASE WHEN. Use QUALIFY for window-row filtering.
- JSON path: payload:user.name::STRING (colon, not arrow).
```

### Correction 3: SQLGlot AST guard

New module `repo/src/evaluation/snow_identifier_guard_v27.py` (~140 lines initially). Walks SQL AST после emitter, checks each `exp.Table.catalog`:
- If in allowed set → keep.
- If outside allowed set → raise `IdentifierLeakError`.
- If absent → auto-fill `task_db`.

CTE-aware: skips `exp.Table` matching CTE name (those are aliases, не real tables).

6/6 self-tests pass: `three_part_correct`, `two_part_fill`, `one_part_fill`, `foreign_catalog_leak`, `cte_and_join`, `subquery_leak`.

### Additional Phase 27 corrections (added during pilot10 iteration)

**Correction 4 (Phase 27 v27c)**: validator relaxation — `extra_allowed_cols=task_db_all_cols` parameter. Accepts SQL references to columns в task_db catalog даже если не в pack BM25 top-K. Reduces false-positive `schema_invalid`.

**Correction 5 (Phase 27 v27c)**: SELECT-clause alias protection в `_snow_schema_valid_ast`. SQL like `SELECT FLOOR(...) AS "five_year_period" ORDER BY "five_year_period"` was rejected pre-Phase-27 (alias не в catalog cols). Fix: collect `exp.Alias` names into `cols_allowed` set.

**Correction 6 (Phase 27 v27c)**: retrieval window scaling 80→200 / 20→40 — addressed BM25 hyperparameter mismatch hypothesis from Phase 26 §6.

**Correction 7 (Phase 27 v27c)**: PK/FK heuristic injection — force-inject columns matching `id`, `<table_singular>_id`, `*_pk`, `*_fk`, `*_id`, `*_key`, `*_sk` into pack. Cap 4 per table.

## Pilot ladder v27 → v27b → v27c

### Pilot10 v27 (corrections 1+2+3 only)

`run_id: lite_snow_pilot10_v27` — 10-task sample (same iids as Lite-Snow baseline v26 for direct comparison):

| Metric | v26 (10-task subset) | v27 |
|---|---|---|
| schema_valid | 1/10 (10%) | 2/10 |
| parse_ok | 9/10 | 9/10 |
| exec_ok | 1/10 (sf_bq211) | 1/10 (sf_bq211) |
| guard_leaks | n/a | 0 (no false-positive guard activations) |
| guard_rewrites | n/a | 0 (no auto-fills needed — pack already three-part) |
| Top err | schema_invalid 7 | schema_invalid 7 |

Result: F1 catalog filter worked **structurally** (0 guard_leaks, 0 cross-DB hits in pack), но schema_valid only marginally moved (2/10 vs 1/10). Major issue clearly elsewhere.

### Pilot10 v27b (+ correction 4 validator relaxation)

Identical to v27 except `extra_allowed_cols`. No measurable difference на 10-task sample. Conclusion: relaxation handles edge cases но не the dominant issue.

### Pilot10 v27c (+ corrections 5+6+7)

`run_id: lite_snow_pilot10_v27c` — all Phase 27 fixes active:

| Metric | v27c |
|---|---|
| plan_ok | 4/10 |
| **schema_valid** | **8/10** (4× lift over v27 2/10) |
| parse_ok | 9/10 |
| **exec_ok** | **1/10** (same as v27 — only sf_bq211) |
| guard_leaks | 0 |
| guard_rewrites | 0 |
| Top err | invalid_identifier 4, ProgrammingError 3, schema_invalid 1, parse_error_guard 1, ok 1 |

**Schema gate cleared** (8/10 ≥ 5/10 acceptance). **Exec gate barely missed** (1/10 < 2/10 acceptance).

### Key insight from v27c

`guard_leaks = 0` across all v27/v27b/v27c runs — F1 grounding **structurally works**. The remaining failures **after schema is correctly grounded** indicate the bottleneck has **shifted from grounding к dialect runtime**:
- `invalid_identifier 4` — columns/tables emit hallucination (model invents names не в catalog).
- `ProgrammingError 3` — Snow-specific dialect errors (NUMBER/VARIANT date function on non-DATE columns).
- `parse_error_guard 1` — SQLGlot LATERAL FLATTEN parse failure (sf_bq210).

## Secondary finding: BM25 hyperparameter undersized

Phase 27 v27c also confirmed Phase 26 §6 hypothesis. Phase 1-16 defaults `top_columns=80, top_tables=20` — calibrated for Spider1/BIRD (≤30 tables/DB).

Spider2-Snow PATENTS — hundreds of tables/DB, thousands of columns. At 80/20, BM25 misses critical join key columns (PK/FK имеют low semantic similarity к natural language question → rank низко). Widening к 200/40 surfaces 2-3× more candidates per query, with `_inject_pk_fk` heuristic backstop.

Empirical: v27 → v27b (no widening) → no schema_valid lift. v27c с widening + PK/FK injection → +6 pp schema_valid.

This **secondary finding** was as impactful as F1 catalog filter — without window widening, F1 alone would have given 2/10 schema_valid не 8/10.

## What worked

- **F1 catalog filter** — eliminated cross-DB drift entirely (0 guard_leaks across all v27 variants).
- **Retrieval scale 200/40** — surfaces enough relevant columns post-partition.
- **PK/FK injection** — covers join keys BM25 misses.
- **Validator relaxation** — reduces false-positive schema_invalid.
- **SELECT-alias protection** — fixes specific class of false-positive rejections (sf_bq029 case).
- **AST guard** — defensive layer (rarely fires but ready).

## What didn't (gaps surfaced)

- **Column-name hallucination** — most remaining errors `invalid_identifier '"p"."country"'` etc. Closing this requires **F3 self-refine** (Phase 29 territory).
- **Snow dialect runtime errors** — NUMBER/VARIANT date cast missing. **F4 territory** (Phase 28).
- **SQLGlot LATERAL FLATTEN parse failure** — sf_bq210 wasn't reachable via guard. **F4c regex fallback** (Phase 28).
- **Exec gate not cleared** — 1/10 same as baseline. Phase 28 needed.

## Why

Phase 27 closure documented **Phase 27 §5 failure-mode analysis** for remaining 9 of 10 pilot10c misses. **Critically, four of these 9 were classified as "mixed-case quoting"** based on error-message format `invalid identifier '"p"."country"'`. This **classification later proved wrong** в Phase 28 catalog probe — column `country` simply doesn't exist в `PATENTS.PUBLICATIONS` (column is `country_code`). Classification was column-name hallucination misread as case mismatch. См. [04_phase28_f2a_regression_and_revert.md](./04_phase28_f2a_regression_and_revert.md).

## Lessons learned (Phase 27)

### Lesson 1: Architectural hypotheses можно validate quickly с pilot10

LinkAlign §1 → F1 design → pilot10 v27 в same week. **Empirical hypothesis testing** quick.

### Lesson 2: One fix often surfaces another

F1 closed grounding layer (0 leaks). Failure classes shifted: schema_invalid count dropped, invalid_identifier rose. **Bottleneck moved**, не disappeared.

### Lesson 3: Defaults from prior work не universally portable

Phase 1-16 BM25 settings worked для Spider1/BIRD. Spider2-Snow — different category problem. **Hyperparameter calibration per benchmark class** important methodological point.

### Lesson 4: Layered defenses justify themselves

F1 catalog filter at runner + builder + AST guard — three layers. Even if one fails, others catch. **Defense in depth** ≠ over-engineering when failure modes have similar shape.

### Lesson 5: Empirical pilot ablation tells when work is "done"

v27 → v27b → v27c — pilot10 progression. `schema_valid 2/10 → 2/10 → 8/10`. Last fix (corrections 5+6+7) — major contributor. Without explicit pilot ladder discipline, individual fix contribution unknown.

## Transition к Phase 28

By end of Phase 27:
- Snow lane no longer 0% blocked by cross-DB drift. Schema-level grounding works.
- **Exec gate not cleared** — 1/10 vs target 2/10+. Bottleneck shifted to **Snow dialect runtime**.
- **4 of 10 pilot10c failures classified as "mixed-case quoting"** — this classification was about to be empirically falsified.

Phase 28 plan:
- **F4** — NUMBER/VARIANT date-cast wrapper для 3 of 10 ProgrammingError cases.
- **F4c** — SQLGlot ParseError regex fallback для sf_bq210 LATERAL FLATTEN.
- **F2a** — mixed-case quoting auto-uppercase для 4 of 10 invalid_identifier cases.

**F2a — the hypothesis that turned out to be wrong.** Continue к [04_phase28_f2a_regression_and_revert.md](./04_phase28_f2a_regression_and_revert.md).

## Cross-references

- Phase 27 main report: `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md`
- Snow pipeline configuration: [05_PIPELINES/04_spider2_snow_pipeline.md](../05_PIPELINES/04_spider2_snow_pipeline.md)
- Snow identifier guard implementation: [08_CUSTOM_TOOLS/05_snow_identifier_guard_v27.md](../08_CUSTOM_TOOLS/05_snow_identifier_guard_v27.md)
- Pack builder F1 patches: [08_CUSTOM_TOOLS/01_schema_pack_builder_v18.md](../08_CUSTOM_TOOLS/01_schema_pack_builder_v18.md)
- Schema linker per-task partition: [08_CUSTOM_TOOLS/02_schema_linker_v18.md](../08_CUSTOM_TOOLS/02_schema_linker_v18.md)
- Phase 26 dossier seed: [02_phase26_research_handoff.md](./02_phase26_research_handoff.md)
- Phase 28 follow-up: [04_phase28_f2a_regression_and_revert.md](./04_phase28_f2a_regression_and_revert.md)
- Snow analysis (post-Phase-28 state): [09_RESULTS_ANALYSIS/03_spider2_snow_analysis.md](../09_RESULTS_ANALYSIS/03_spider2_snow_analysis.md)

## Источники

| Утверждение | Источник |
|---|---|
| 90.2% cross-DB drift | `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` §1 + Step 1 diagnostic |
| Three F1 corrections | `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` §2 |
| Pilot10 v27 → v27b → v27c metrics | `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` §3 |
| 0 guard_leaks across runs | same §3 |
| BM25 retrieval scaling | same §6 side finding |
| PK/FK injection origin | CHESS [Talaei et al., arXiv 2405.16755] — research dossier §4 |
| SELECT-alias protection | own discovery during v27c diagnosis |
