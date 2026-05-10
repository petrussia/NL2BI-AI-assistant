# Spider2 Phase 22 (STAGE A1+A2+A3: pack-thinness + join-aware Family C) — report

_Generated: 2026-05-10 | branch: `experiments/denis` | author: Denis_

> **Scope.** STAGE 0 baseline freeze + STAGE A1 failure audit + STAGE A2
> (extended pack with `all_columns` for validator; populated `join_hints`
> from co-occurring keys) + STAGE A3 (Family C deterministic multi-table
> JOIN renderer). No model swap.
>
> Stages A4 (engine-compat rewrite library), A5 (renderer-feedback
> retry), A6 (BQ oracle diagnostic), B (Snow), C (Lite-SF/SQLite),
> D (DBT v2), E (premium overlay), F (FULL runs) deferred per the
> brief's "одно семейство идей за раз" rule.

---

## 1. Hard status

| component | value |
|---|---|
| Branch | `experiments/denis` |
| HEAD before Phase 22 | `9c5f7f2` (Phase 21) |
| HEAD after Phase 22 | `<commit>` |
| Bridge / GPU / catalogs / models | ✅ same A100 80GB; both Qwen3-Coder-30B + Coder-7B still loaded |
| Push | NOT executed |

## 2. STAGE 0 — baseline freeze

| lane | best run | n | sv | exec | source |
|---|---|---:|---:|---:|---|
| Lite-BQ | `lite_bq_v18_1b_pilot50` | 50 | 52% | 46% | Phase 19 c9884ae |
| Lite-BQ | `lite_bq_v20a_pilot50_b` | 50 | 52% | 42% | Phase 20 643b230 |
| Lite-BQ | `lite_bq_v21_pilot50` | 50 | 50% | 44% | Phase 21 9c5f7f2 |
| Lite-Snow | — | — | — | — | catalog ready since Phase 18 |
| Lite-SQLite | — | — | — | — | not piloted |
| DBT FULL 68 | Phase 11 baseline | 68 | task_success 13.2% | — | only publishable Spider2 number |

## 3. STAGE A1 — failure audit on v21 pilot50

`outputs/logs/spider2_v22_bq_failure_audit.md` + `.csv`

Critical finding: **10 of the 24 chosen-failure ast_leak cases are
validator FALSE POSITIVES** — BigQuery dry_run accepts them but the
v21 AST validator marks `schema_invalid` because the referenced
columns (`event_timestamp`, `transactionRevenue`, `pageviews`, etc.)
are NOT in the BM25 top-K pack.

The pack was **too thin** for validator residency: bq009's pack had
only 8 columns total across 8 tables (token budget 1033) — the linker
correctly built it for prompt economy, but the validator misuses it
as a complete schema view.

| pattern | n | fix class |
|---|---:|---|
| ast_leak (validator FP — column not in pack but real) | 24 | **STAGE A2** |
| ok | 12 | wins |
| multi_table / unrecognized_name | 5 | **STAGE A3** Family C |
| multi_level_unnest | 2 | STAGE A4 |
| nested_aggregate | 2 | STAGE A4 |
| no_signature | 2 | STAGE A4 |
| function_not_found (`ARRAY_CONTAINS`) | 1 | STAGE A4 |
| group_by_window_raw | 1 | STAGE A4 |
| parse_error | 1 | edge case |

## 4. STAGE A2 — pack with `all_columns` + populated `join_hints`

### 4.1 Pack extension

`schema_pack_builder_v18.build_pack` now accepts an optional
`all_catalog_cols` argument (the linker's full column list). For each
pack table it stores a side-channel `all_columns: list[str]` —
the **complete** column-name set for that table from the live
catalog. The compact `tables[*].columns` (BM25 top-K) is
unchanged for the planner prompt; `all_columns` is consumed only by
the validator.

### 4.2 Validator union

`candidate_selector_v18._normalize_pack_names` now unions
`pack.tables[*].columns` AND `pack.tables[*].all_columns` for
residency sets. Phantom columns (truly invented identifiers not in
the live schema) are still rejected — local smoke confirms.

### 4.3 join_hints heuristic

For each pair of tables in the pack, two FK-like signals are checked
against the FULL column lists:
1. Shared exact column name with key shape (`*_id`, `*_key`, `id`).
2. FK-like naming: column `<table>_id` in B referencing `id` in A.

Hints capped at 10 per pack. Each hint records the `reason` for
diagnostics. Used by Family C (§5).

## 5. STAGE A3 — Family C deterministic multi-table JOIN renderer

`sql_renderer_v18.render_bq_with_joins` + `spider2_candidate_factory_v18.
family_C_join_aware`. Emitted only when:
- plan picks ≥ 2 distinct bare tables, AND
- pack has ≥ 1 join hint, AND
- a join hint connects the first two tables

When conditions don't hold, the function falls back to single-table
`render_bq` so Family C never emits broken multi-table SQL with a
guessed join.

The selector evaluates Family C alongside A and B; selection policy
unchanged: `dry_run_ok ≻ parse_ok ≻ schema_valid ≻ family_A`.

## 6. v22 BQ pilot10 sanity

`outputs/spider2_lite/runs/lite_bq_v22_pilot10/`

| metric | v21 | **v22** | delta |
|---|---:|---:|---:|
| plan_validation_ok | 5/10 | 5/10 | 0 |
| chosen_schema_valid | 4/10 | **5/10** | **+1** |
| parse_ok | 10/10 | 10/10 | 0 |
| execute_ok | 3/10 | 3/10 | 0 |
| Family A | 8/10 | 8/10 | 0 |
| Family B | 2/10 | 2/10 | 0 |
| Family C chosen (new) | — | 0/10 | — |

## 7. v22 BQ pilot50 — FULL gate measurement

`outputs/spider2_lite/runs/lite_bq_v22_pilot50/`

| metric | v18.1b | v20a | v21 | **v22** | gate | status |
|---|---:|---:|---:|---:|---|---|
| plan_validation_ok | 42% | 54% | 54% | **54%** | — | unchanged |
| chosen_schema_valid | 52% | 52% | 50% | **54%** | ≥ 60% | **+4pp**, gate ❌ 6pp short |
| parse_ok | 96% | 96% | 98% | **98%** | — | stable |
| execute_ok | 46% | 42% | 44% | **44%** | ≥ 50% | gate ❌ 6pp short |
| ok bucket (sv+parse+dr) | — | — | 12 | **13** | — | +1 task fully clean |
| Family A chosen | 80% | 82% | 86% | **86%** | — | unchanged |
| Family B chosen | 20% | 18% | 14% | 14% | — | unchanged |
| Family C emitted | — | — | — | **17/50** | — | new (when ≥2 tabs + join_hints) |
| Family C chosen | — | — | — | **0/50** | — | weak heuristic |

**Gate composite:**
- chosen_schema_valid ≥ 60%: ❌ 54% (6pp short)
- dry_run_ok ≥ 50%: ❌ 44% (6pp short)
- **FULL launch decision: NOT launched.**

### 7.1 Honest read on STAGE A2 lift size

The audit predicted +20pp sv from validator FP rejection of 10
ast_leak cases that BQ accepts. Reality: +4pp sv (50→54%) and 'ok'
bucket +1. Two interpretations:

1. The chosen candidate per task changed between v21 and v22 (because
   pack content changed), so the audit's "10 false positives" no
   longer maps cleanly to the same tasks.
2. Many of those v21 SQL strings reference columns NOT in the live
   catalog either (e.g. derived/aliased columns, columns from
   sub-queries) — `all_columns` from `INFORMATION_SCHEMA` doesn't
   help those.

The smaller-than-predicted lift is recorded as the honest lesson:
trace-derived predictions can over-count when the trace SQL doesn't
reference real-catalog identifiers exclusively.

### 7.2 Honest read on Family C

Family C was emitted on **17/50 pilot50 tasks** (planner picked ≥ 2
tables AND pack had join_hints). It was **chosen 0 times** — the
selector preferred A or B every time. Two diagnoses:

1. **Heuristic too weak**: shared column name + `_id`/`_key` shape
   is a coarse FK proxy. BQ public datasets often share generic
   column names (e.g. `name`, `country`) that are NOT join keys; the
   resulting JOIN ON clauses fail the dry_run.
2. **Selector tie-breaker prefers A**: when A and C produce
   equal-quality candidates (both schema-valid + dry_run), A wins.

Fix queue (deferred to v22.1+): replace shared-name heuristic with
true FK signal (where BigQuery exposes it), or train a simple
co-occurrence-weighted scoring on existing successful queries.

## 8. ВКР-disciplined claims

- Phase 22 commit may contribute to ВКР as the **architecturally
  decisive engineering iteration** that distinguished pack-thinness
  from architectural ceiling.
- DBT FULL 68 = 13.2% remains the only publishable Spider2 number
  unless v22 pilot50 clears the FULL gate AND a FULL run is launched.

## 9. Operational status

- v16/v17 modules untouched.
- Patched: `schema_pack_builder_v18.py` (all_columns + join_hints),
  `sql_renderer_v18.py` (`render_bq_with_joins`),
  `spider2_candidate_factory_v18.py` (Family C dispatch),
  `candidate_selector_v18.py` (validator union BM25+all_columns),
  `tools/run_spider2_v18_bq_pilot.py` (pass `all_catalog_cols`).
- No `git push`.
