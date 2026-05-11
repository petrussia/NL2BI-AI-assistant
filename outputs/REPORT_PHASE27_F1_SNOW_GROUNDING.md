# Phase 27 F1 — Snow Identifier Grounding

**Date:** 2026-05-11
**Scope:** Spider2-Lite-Snow (207 tasks); Spider2-Snow (547 tasks) — pilot evidence only
**Status:** F1 grounding solved at schema level. Execute-rate **NOT** lifted to the 2/10 gate.
**Verdict:** STOP. Bottleneck has shifted from schema-coverage to Snow runtime dialect; Phase 28 territory.

---

## 1. Mission recap

Phase 26 left both Snow benchmarks effectively at 0% executable:

| Benchmark | n | plan_ok | schema_valid | parse_ok | execute_ok |
|---|---|---|---|---|---|
| Lite-Snow FULL v26 (S2 baseline) | 207 | 58 (28.0%) | 26 (12.6%) | 194 (93.7%) | **1 (0.48%)** |
| Spider2-Snow FULL v25 (S1, 91% done, 499/547) | 499 | 160 (32.1%) | 57 (11.4%) | 478 (95.8%) | **0 (0.00%)** |

Diagnostic on v26 Lite-Snow (see [tools/remote_scripts/_phase27_step1_diagnostic.py](../tools/remote_scripts/_phase27_step1_diagnostic.py)):

```
correct_only  (all FROM use task_db catalog):  18 (8.7%)
wrong/unknown (all FROM NOT task_db):         164 (79.2%)
no_catalog    (bare TABLE or SCHEMA.TABLE):     5 (2.4%)
mixed         (some correct + some wrong):     16 (7.7%)
VERDICT: 90.2% of tasks emit identifiers outside their task.db catalog
```

Root cause: `c.alias = ""` for every Snow catalog row → schema-pack builder couldn't partition by TABLE_CATALOG → BM25 was a single 587K-column global index → linker leaked competitor catalogs into the pack → planner emitted cross-DB three-part names → Snow rejected on EXPLAIN.

Phase 27 F1 target: lift Lite-Snow execute_ok 0.5% → ≥15%; absolute minimum gate after pilot10 = 2/10 exec.

---

## 2. What landed (3 corrections + AST guard + SELECT-alias fix)

### (a) Pack builder hard-partition by TABLE_CATALOG
[repo/src/evaluation/schema_pack_builder_v18.py](../repo/src/evaluation/schema_pack_builder_v18.py) — gated on `lane in ("snow","lite_snow")`:

```python
_snow_lane_active = (lane in ('snow', 'lite_snow') and alias)
_task_db_upper = (alias or '').upper() if _snow_lane_active else None
# in hits + all_catalog_cols loops:
if _snow_lane_active and c.db.upper() != _task_db_upper:
    continue
```

Defense at builder level: even if a leaky linker passes wrong-catalog hits, the pack drops them. Sanity verified by [tools/remote_scripts/_phase27_sanity_pack_build.py](../tools/remote_scripts/_phase27_sanity_pack_build.py): pack with `alias=PATENTS` returns `unique_dbs == {'PATENTS'}` whether or not the linker pre-filters.

### (b) Three-part identifier rendering in planner prompt
Same module, `pack_to_planner_prompt`: every table line for Snow lane is rendered as `{task_db}.{schema}.{table}`, with Snow dialect rules block (quote mixed-case, LATERAL FLATTEN, IFF, QUALIFY, JSON path).

### (c) Retrieval-side correction 1 — Phase 27 runner uses **per-task** BM25 index
[tools/remote_scripts/_phase27_snow_runner.py](../tools/remote_scripts/_phase27_snow_runner.py):

```python
cat_subset = catalog_by_db[task_db_upper]      # 200-5000 cols, not 587K
linker = SchemaLinker(cat_subset)              # fresh index per task
link = linker.query(question, db_filter=task_db, top_columns=200, top_tables=40)
```

This addresses the **second finding from this phase** (worth highlighting separately — see §6):
> Phase 1-16 BM25 defaults (top_columns=80, top_tables=20) were calibrated for Spider1/BIRD where databases have ≤30 tables. Spider2 Snowflake DBs have **thousands** of tables. The 80/20 window was systematically dropping the right columns even when the catalog was correctly partitioned.

### (d) Retrieval-side correction 2 — validator relaxed with task_db catalog cols
SchemaValidator's `cols_allowed` is built from the pack columns. Bug: SELECT-clause aliases like `AS "five_year_period"` then referenced in `ORDER BY "five_year_period"` were being rejected. Fix in `_snow_schema_valid_ast`:

```python
select_aliases = set()
for al in ast.find_all(E.Alias):
    a = al.alias_or_name
    if a: select_aliases.add(a.upper())
cols_allowed |= select_aliases
```

### (e) Retrieval-side correction 3 — PK/FK heuristic injection
Catalog rows don't tag PKs/FKs explicitly. After the pack is built, `_inject_pk_fk` scans each pack table for columns matching `id|<table_singular>_id|*_pk|*_fk|*_key|*_sk`, capped at 4 per table. This recovers join-key columns that BM25 ranked below the top-22 cut.

### (f) SQLGlot AST guard ([repo/src/evaluation/snow_identifier_guard_v27.py](../repo/src/evaluation/snow_identifier_guard_v27.py))
- `IdentifierLeakError` on any `exp.Table.catalog` not in `{task_db}`
- Auto-fill missing catalog with `task_db`
- CTE-aware: tables referencing a CTE alias are skipped (otherwise it would fill `task_db` over a CTE name)
- 6/6 self-tests pass; called just before `EXPLAIN` in selector

---

## 3. Pilot10 ladder: v27 → v27b → v27c

Same 10 Spider2-Lite-Snow tasks, identical planner/emitter (Qwen3-Coder-30B-A3B / Qwen2.5-Coder-7B). Differences are **only** in the F1 stack.

| run | description | plan_ok | **schema_valid** | parse_ok | **execute_ok** | guard_leaks | top error |
|---|---|---|---|---|---|---|---|
| v26 FULL 207 (baseline) | pre-Phase-27 | 28.0% | 26 (12.6%) | 194 (93.7%) | **1 (0.48%)** | n/a | schema_invalid 168 |
| pilot10 v27 | builder partition + AST guard | 5 | 2/10 | 9/10 | **1/10** | 0 | schema_invalid 7 |
| pilot10 v27b | + validator-with-task_db-cols | 4 | 2/10 | 9/10 | **1/10** | 0 | schema_invalid 7 |
| **pilot10 v27c** | **+ retrieval 200/40 + PK/FK + SELECT-alias fix** | **4** | **8/10** | **9/10** | **1/10** | **0** | invalid_identifier 4, dialect 3 |

**Reading:**
- `guard_leaks=0` across all three runs → linker + builder no longer leak cross-DB references. F1 grounding **works** at the retrieval+rendering level.
- v27 → v27c: schema_valid **2 → 8** (4×). The "200/40 + PK/FK + SELECT-alias" bundle was the decisive lift; the AST guard alone (v27) did very little because the failures were inside the pack, not in catalog identifier leaks.
- execute_ok stuck at **1/10** across all three. Acceptance gate (≥2) **not** cleared.

---

## 4. Per-task verdict on pilot10c

| iid | sv | parse | exec | failure mode |
|---|---|---|---|---|
| sf_bq026 | ✓ | ✓ | ✗ | mixed-case quoted column `"p"."date"` not in upper-case Snow catalog |
| sf_bq027 | ✓ | ✓ | ✗ | `"d13"."citation"` lowercase-quoted |
| sf_bq029 | ✓ | ✓ | ✗ | `"p"."country"` lowercase-quoted |
| sf_bq033 | ✓ | ✓ | ✗ | `DATE_TRUNC('MONTH', grant_date)` — grant_date is NUMBER(38,0), not DATE |
| sf_bq091 | ✓ | ✓ | ✗ | `"a"."assignee"` lowercase-quoted |
| sf_bq099 | ✓ | ✓ | ✗ | `EXTRACT(YEAR FROM publication_date)` — publication_date is NUMBER(38,0) |
| sf_bq209 | ✗ | ✓ | ✗ | schema_invalid: model emits table `CITATIONS` not in pack (hallucinated) |
| sf_bq210 | n/a | ✗ | ✗ | sqlglot parse error on `TABLE(LATERAL FLATTEN(INPUT => p.claims_localized))` — AST guard rejected before EXPLAIN |
| **sf_bq211** | **✓** | **✓** | **✓** | EXPLAIN ok — only execute_ok |
| sf_bq213 | ✓ | ✓ | ✗ | `EXTRACT(YEAR FROM fterm)` — fterm is VARIANT, needs `::date` cast |

---

## 5. Top-5 dialect-failure categories (Phase 28 candidates)

These are the residual blockers after F1; none can be fixed at the grounding layer.

### 1. Mixed-case lowercase quoting (4/10) — biggest single ROI
Emitter renders `"p"."country"`, `"d13"."citation"`, `"a"."assignee"`, `"p"."date"`. Snow upcases unquoted identifiers, so the **catalog has them as `COUNTRY`, `CITATION`, `ASSIGNEE`, `DATE`** — the double-quoted lowercase form fails to resolve.
- **Fix vector:** strip identifier quotes when the column is not actually mixed-case in the catalog. Either a deterministic post-processor (regex on column references) or train the emitter prompt to upcase before quoting. Catalog already has the answer — every column is stored upper.
- **Expected uplift:** +4/10 on pilot10 = +40pp. Single biggest dialect fix.

### 2. Date function on NUMBER column (2/10) — type-cast wrapper
`DATE_TRUNC('month', grant_date)` and `EXTRACT(YEAR FROM publication_date)` where catalog says `DATA_TYPE = NUMBER(38,0)` (epoch seconds, or YYYYMMDD encoding). Snow refuses implicit cast.
- **Fix vector:** detect column DATA_TYPE in pack (catalog rows already carry it but pack-builder drops the field), inject `TO_DATE(TO_VARCHAR(col), 'YYYYMMDD')` or `TO_TIMESTAMP(col)` wrapper at emission time, or feed type into planner prompt.
- **Expected uplift:** +2/10 on pilot10.

### 3. Date function on VARIANT column (1/10) — JSON path cast
`EXTRACT(YEAR FROM fterm)` where fterm is VARIANT. Needs `fterm::date` or `fterm:value::date`.
- **Fix vector:** same as (2) but VARIANT branch.
- **Expected uplift:** +1/10.

### 4. SQLGlot LATERAL FLATTEN parse rejection (1/10) — guard fallback
sf_bq210: model emits valid Snow `TABLE(LATERAL FLATTEN(INPUT => p.claims_localized))`. SQLGlot's snowflake dialect parser cannot parse it (`ParseError: Expecting ). Line 8, Col: 19.`). Our AST guard then raises `parse_error_guard` and rejects the candidate.
- **Fix vector:** on `parse_error_sqlglot`, fall back to a regex-only catalog-leak check (no AST) rather than failing closed. The SQL itself was probably runnable.
- **Expected uplift:** +1/10 best case (only if Snow then accepts).

### 5. Schema-coverage / hallucinated table (1/10)
sf_bq209: model emits `PATENTS.PATENTS.CITATIONS` (table not in pack). Two possibilities — table doesn't exist in catalog at all (genuine hallucination), or BM25 ranked it below the cut even at 200/40. The schema_invalid signal already flags it, but we have no self-refine loop (Phase 28 F3 territory).
- **Fix vector:** Phase 28 F3 self-refine: feed the schema_invalid message back to the planner for one retry. Or pack expansion to 300/60.
- **Expected uplift:** +1/10 best case.

**Cumulative theoretical ceiling if all 5 fix vectors land cleanly:** 1 + 4 + 2 + 1 + 1 + 1 = **10/10 on this pilot10**. Realistic mid-band after partial fixes: 5-6/10. This matches the Phase 27 mission target (15-25% on FULL) **only if Phase 28 actually lands** — Phase 27 alone is not sufficient.

---

## 6. Side finding: BM25 retrieval window was undersized for warehouse-scale catalogs

This isn't strictly an F1 result but it surfaced in pilot10c diagnosis and is worth flagging because it likely affects the whole Spider2 family, not just Snow:

- Phase 1-16 defaults: `top_columns=80`, `top_tables=20`. Calibrated against Spider1/BIRD where each database has ≤30 tables.
- Spider2 Snowflake catalogs: thousands of tables per database (e.g. PATENTS.PATENTS alone has hundreds of tables; GITHUB_REPOS has the entire GitHub mirror).
- At 80/20, even with correct catalog partitioning, the relevant join key for a 5-table query often sits at rank 90+.
- Phase 27 widened to 200/40 specifically for Snow. **BQ and SQLite were not changed** — leaving them at 80/20 because (a) BQ catalogs are smaller, (b) we have no evidence of the same bottleneck there, and (c) widening retrieval changes ablation comparability with v25/v26 BQ runs.
- **Recommendation:** if any future phase rebuilds the BM25 stage, parameterise the window by `lane` and benchmark whether 200/40 helps BQ as well.

---

## 7. Sample SQL emissions (pilot10c)

### sf_bq026 — mixed-case quoting failure
```sql
SELECT "assignee", LISTAGG("country_code", ',') AS "top_five_jurisdictions"
FROM (
  SELECT "p"."assignee", "p"."country_code",
         YEAR("p"."date") AS "patent_year",
         ROW_NUMBER() OVER (PARTITION BY "p"."assignee", YEAR("p"."date")
                            ORDER BY COUNT(*) DESC) AS "rn"
  FROM "PATENTS"."PATENTS"."PUBLICATIONS" AS "p"
  WHERE "p"."kind_code" = 'A61'
  GROUP BY "p"."assignee", "p"."country_code", YEAR("p"."date")
) ...
```
Catalog correctly partitioned (`PATENTS.PATENTS.PUBLICATIONS`), three-part name correct, all columns exist — but quoted lowercase. Snow rejects at line 1 col 138.

### sf_bq099 — date function on NUMBER
```sql
SELECT "a"."assignee", COUNT("a"."application_number") AS "total_applications", ...
FROM "PATENTS"."PATENTS"."PUBLICATIONS" AS "p"
JOIN "PATENTS"."PATENTS"."DISCLOSURES_13" AS "d" ON "p"."family_id" = "d"."family_id"
JOIN (SELECT EXTRACT(YEAR FROM "publication_date") AS "year_with_most_apps", ...
```
`publication_date` is `NUMBER(38,0)` — Snow rejects `EXTRACT(YEAR FROM NUMBER)`. Schema is grounded; runtime types are not.

### sf_bq211 — the one execute_ok
```sql
SELECT COUNT(DISTINCT "p"."family_id")
FROM "PATENTS"."PATENTS"."PUBLICATIONS" AS "p"
WHERE "p"."grant_date" BETWEEN '2010-01-01' AND '2023-12-31'
  AND "p"."assignee" LIKE '%CN%'
GROUP BY "p"."family_id"
HAVING COUNT(DISTINCT "p"."family_id") > 1
```
No mixed-case columns referenced (`family_id`, `grant_date`, `assignee` happen to be lowercase in the catalog — this is the path of least resistance). No date arithmetic on NUMBER. No FLATTEN. Trivial joins.

---

## 8. Honest assessment

**What Phase 27 F1 did:**
- Solved cross-DB identifier drift at the retrieval+rendering level: from 90.2% drift on v26 → 0 guard_leaks across three pilot10 runs.
- Lifted schema_valid on the same 10 tasks from 2/10 → 8/10 (the bigger jump came from retrieval window + PK/FK injection + SELECT-alias fix, not the AST guard).
- Identified that the AST guard, while correctly implemented and tested, is doing very little defensive work in practice — the upstream linker + builder partition already prevents leaks. The guard remains valuable as belt-and-braces but is not a key driver.

**What Phase 27 F1 did NOT do:**
- Lift execute_ok. On pilot10c it stayed at 1/10. The 1 success (sf_bq211) is also the one in v26, v27, and v27b — i.e. we have not surfaced a single *new* executable task across three runs. The schema gate now passes for 6 more tasks, but they all die at the Snow runtime layer for reasons orthogonal to grounding.
- Clear the 2/10 gate. Strictly we failed acceptance.

**Why the gate miss is not a verdict against F1:**
The failure modes that block exec on pilot10c (mixed-case quoting, NUMBER→DATE cast, VARIANT→DATE cast, LATERAL FLATTEN parse) are all things the grounding subsystem could not have fixed. F1 was a necessary but not sufficient layer. The data here directly motivates Phase 28 F2/F4 dialect post-processing.

**No FULL run launched.** Per brief: do not extend Phase 27 scope. The 547-task Spider2-Snow FULL on S1 is currently the **v25** baseline (not v26 as previously labelled in todos) and is 91% complete with execute_ok still at 0. Whether to launch a v27c FULL Lite-Snow 207 is the user's call given the pilot10 evidence.

---

## 9. Recommendation

1. **Stop Phase 27.** Do not push v27c. Do not launch FULL 207 on the strength of pilot10c — we'd consume ~9h of S2 wall to surface ~16/207 ≈ 8% execute_ok at best (extrapolating sf_bq211-pattern density), and that's not a publishable bump.
2. **Open Phase 28 with Mixed-case Quoting as the first sub-task** (`F2a` rather than the originally-planned F2 JOIN-graph). It's the single largest residual win — fixes ~40% of grounded-but-failing tasks — and is a deterministic post-processor, not a model swap.
3. **Then Phase 28 F4: NUMBER/VARIANT date-cast wrapper.** Requires pack-builder to surface DATA_TYPE (a one-line addition); emitter rule + post-processor to wrap.
4. **Then Phase 28 F3: self-refine on schema_invalid signal.** Cheapest way to claw back the hallucinated-table cases.
5. **Hold the F1 stack as committed** (local only; no push per brief). It's load-bearing for every future Snow run.

---

## Appendix: files touched

- [repo/src/evaluation/schema_pack_builder_v18.py](../repo/src/evaluation/schema_pack_builder_v18.py) — F1 catalog filter + three-part Snow rendering + dialect rules
- [repo/src/evaluation/snow_identifier_guard_v27.py](../repo/src/evaluation/snow_identifier_guard_v27.py) — **new** AST guard module (6/6 self-tests pass)
- [tools/remote_scripts/_phase27_snow_runner.py](../tools/remote_scripts/_phase27_snow_runner.py) — per-task BM25 + retrieval 200/40 + PK/FK injection + validator relax + AST guard wiring
- [tools/remote_scripts/_phase27_step1_diagnostic.py](../tools/remote_scripts/_phase27_step1_diagnostic.py) — v26 catalog-drift baseline
- [tools/remote_scripts/_phase27_sanity_pack_build.py](../tools/remote_scripts/_phase27_sanity_pack_build.py) — pack-partition unit test
- [tools/remote_scripts/_phase27_probe_pilot10c.py](../tools/remote_scripts/_phase27_probe_pilot10c.py) — run-state probe
- [tools/remote_scripts/_phase27_pull_pilot10c.py](../tools/remote_scripts/_phase27_pull_pilot10c.py) — predictions + traces pull
- [tools/remote_scripts/_phase27_compare_v27_v27b_v27c.py](../tools/remote_scripts/_phase27_compare_v27_v27b_v27c.py) — side-by-side metrics
- [tools/remote_scripts/_phase27_trace_detail.py](../tools/remote_scripts/_phase27_trace_detail.py) — per-task failure classification

**Pilot10 run directories on Drive** (all 10 preds + traces + progress + metrics, local copies under `/_pull_phase27`):
- `outputs/spider2_lite/runs/lite_snow_pilot10_v27/`
- `outputs/spider2_lite/runs/lite_snow_pilot10_v27b/`
- `outputs/spider2_lite/runs/lite_snow_pilot10_v27c/` ← final
