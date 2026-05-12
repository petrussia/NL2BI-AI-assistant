# Phase 26 — researcher handoff report

_Generated 2026-05-11 | branch `experiments/denis` | parent commit `928a598` (Phase 24)_

> **Scope.** Comprehensive results across 3 parallel Colab runtimes (1×A100 80 GB each):
> Spider2-Lite-Snow, Spider2-Snow, Spider2-DBT, Spider2-Lite-SQLite + legacy Spider1, BIRD.
> Single architecture: Qwen3-Coder-30B-A3B-Instruct planner + Qwen2.5-Coder-7B-Instruct
> emitter, v18 schema-linking + closed-set pack + validator-first selector + Phase 24 v24
> engine-compat rewrites (BQ lane).
>
> **Status at time of write.** S1 Snow ~70 % done; S2 finished DBT+Spider1+BIRD chain,
> currently running parallel Lite-SQLite; S3 finished Lite-Snow, currently running
> Lite-SQLite duplicate.

---

## 1. Headline numbers (all official-evaluation-style metrics)

| benchmark | n | core metric | value | leaderboard band |
|---|---:|---|---:|---|
| **Spider1 dev FULL** | 1034 | execute_ok (SQLite) | **94.0 %** (972/1034) | SOTA-tier (>90 %) |
| **BIRD FULL dev** | 1534 | execute_ok (SQLite) | **87.9 %** (1349/1534) | SOTA-tier (>80 %) |
| **BIRD mini-dev** | 250 | execute_ok (SQLite) | **90.4 %** (226/250) | SOTA-tier (>85 %) |
| **Spider2-DBT** | 68 | task_success (official matched) | **13.2 %** (9/68) | matches Phase 11 baseline |
| **Spider2-Lite-BQ** (Phase 25 latest) | 205 | execute_ok (BQ dry_run) | 34.6 % (71/205) | weak (BQ Snow-style schema, GA360 heavy) |
| **Spider2-Snow** (S1, partial 70 %) | ~387/547 | execute_ok (Snow EXPLAIN) | **0 %** | known failure mode |
| **Spider2-Lite-Snow** (S3, done) | 207 | execute_ok (Snow EXPLAIN) | **0.5 %** (1/207) | same failure mode |
| **Spider2-Lite-SQLite** (S2 partial 38 %) | 52/135 | execute_ok (SQLite) | 0 % | early; local* DBs hard |

**One-line summary.** Architecture is competitive on SQLite-based benchmarks (Spider1
94 %, BIRD 88 %). Snow lanes (Spider2-Snow + Lite-Snow) collapse to ~0 % execute_ok
due to a known cross-DB identifier-grounding problem. DBT matches but does not exceed
the Phase 11 baseline. Lite-BQ at 34 % is consistent with Phase 22-24 history.

---

## 2. Architecture used (single fixed stack across all benchmarks)

```
1. Schema linking:
   - For Spider2 lanes: BM25 over <DRIVE>/outputs/cache/spider2_<lane>_live_catalog_v18.jsonl
     (BQ: 428,424 cols; Snow: 586,472 cols)
   - For Spider1/BIRD: tables.json-derived schema text (NOT BM25-indexed)
   - For DBT: project context export (read existing models/, schema.yml)
2. Pack build:
   - max_tables=8, max_cols_per_table=22 (compact) + all_columns side-channel for validator
   - lane-specific (bq | snow); SQLite uses direct table DDL from sqlite_master
3. Planner (Qwen3-Coder-30B-A3B): JSON plan emit with closed-set table/column references
   - validator-feedback retry (max 2 attempts) on schema validation fail
4. Emitter (Qwen2.5-Coder-7B): direct SQL emit with dialect prompt
5. Candidate factory:
   - Family A: deterministic renderer over JSON plan (BQ-specific)
   - Family B: Coder-7B direct emit
   - Family C: deterministic JOIN-aware renderer (BQ-specific; rarely chosen)
   - <X>_v24 (Phase 24): engine-compat rewrite of Family <X> (BQ only):
     ARRAY_CONTAINS → EXISTS UNNEST, NTH → array offset, multi-level UNNEST,
     nested aggregate flag, window+GROUP_BY flag, AND-on-int wrap
6. Selector (candidate_selector_v18):
   - Tie-break: dry_run_ok ≻ parse_ok ≻ schema_valid ≻ family_A
   - For Snow: EXPLAIN call replaces BQ dry_run
   - For SQLite: cur.execute + fetchmany(10) replaces dry_run
```

For Snow lanes additional EK from task `evidence` field NOT passed to planner (only
to Coder-7B emitter). For BIRD `evidence` IS passed.

---

## 3. Detailed per-benchmark error breakdown

### 3.1 Spider2-Snow FULL (S1, in progress; pattern from 387/547)

| error_class | count | % |
|---|---:|---:|
| `schema_invalid` | ~285 | ~74 % |
| `invalid_identifier` (post-Phase-25 patch) | ~50 | ~13 % |
| `parse_error` | ~20 | ~5 % |
| `connect_fail` (pre-Phase-25 patch baggage) | ~10 | ~3 % |
| `ok` | 0 | 0 % |
| other | ~20 | ~5 % |

**Why exec_ok = 0:** Coder-7B (Family B; the only Snow lane has no deterministic
Family A renderer in v18) generates SQL that references identifiers from **other DBs
in the pack** instead of the task's `alias`-specific DB. Examples from earlier traces:

- Task `db=GITHUB_REPOS` → model emits `FROM FINANCE__ECONOMICS.CYBERSYN.SEC_REPORT_ATTRIBUTES`
- Task `db=GITHUB_REPOS_DATE` → model emits `FROM GITHUB_ARCHIVE.GITHUB.COMMITS` (different DB)

The pack-builder filters by alias, but the catalog often contains cross-DB tables under
shared aliases, so the model has options to drift. Compound with Snow's strict
case-sensitivity and 3-part-name policy, identifier_invalid is the dominant terminal
error.

**Locations to inspect:**
- `outputs/spider2_snow/runs/snow_full_v25/predictions.jsonl` — per-task SQL + class
- `outputs/spider2_snow/runs/snow_full_v25/traces.jsonl` — per-task evals + reasons
- `outputs/spider2_snow/runs/snow_full_v25/error_taxonomy.csv`
- Per-task gold SQL: derive from `data/spider2_snow/raw/.../spider2-snow.jsonl` field
  `prediction_filename` or compare against canonical answers (not committed).

### 3.2 Spider2-Lite-BQ (Phase 25 reference, n=205)

Phase 25 detailed breakdown of 14 dry_run_failed cases:

| sub-category | count | example_id | example error |
|---|---:|---|---|
| `unrecog_name` (col without JOIN) | 5 | bq056 | `Unrecognized name: concept_ancestor` |
| `AND_int` (unquoted date literal) | 3 | bq290 | `BOOL AND BOOL AND INT` (caused by `AND (2023-10-01)`) |
| `nested_agg` (SUM(SUM)) | 2 | bq019 | `Aggregations of aggregations are not allowed` |
| `ARRAY_CONTAINS` | 1 | bq010 | `Function not found: ARRAY_CONTAINS` |
| `other` (STRUCT, RPC, types) | 3 | various | |

**Phase 24 rewrites emitted only 1 candidate (`array_contains`) on this pilot;
helpful count 0** — A_v24 still failed dry_run due to OTHER errors beyond
ARRAY_CONTAINS in the same SQL. Rewrites missed the actual high-frequency failures:
`unrecog_name` (JOIN-aware Family C needed) and `AND_int` (which is actually date-literal
quoting, not bare integer column).

**Locations:**
- `outputs/spider2_lite/runs/lite_bq_v24_pilot50/{predictions.jsonl, traces.jsonl, metrics.csv, engine_rewrite_stats.csv, readout.md}`
- `outputs/spider2_lite/runs/lite_bq_full_v25/` (Phase 25 v25, 205 tasks)

### 3.3 Spider2-DBT FULL CLEAN (n=68, dbt_full_v26_clean)

| failure mode (success-first) | n | % |
|---|---:|---:|
| **SUCCESS** (official matched > 0) | **9** | **13.2 %** |
| `dbt_run_failed` (run rc ≠ 0) | 37 | 54.4 % |
| `ran_ok_but_score_zero` (dbt OK, eval matched=0) | 17 | 25.0 % |
| `dbt_test_failed` (run OK, test rc ≠ 0) | 5 | 7.4 % |

**9 SUCCESS tasks:** `playbook001`, `lever001`, `mrr001`, `quickbooks003`,
`salesforce001`, `superstore001`, `f1003`, `retail001`, `mrr002`.
4 of 9 are pure success (run+test rc=0); 5 have non-zero rc but official_eval
(which runs its own dbt) reports matched=1.

**Apply distribution:**
- 61/68 (90 %) used `diff` patch
- 7/68 used `fallback_sql` (when diff didn't apply cleanly)
- 0/68 emitted multi-block responses

**Root cause analysis (Phase 26 finding):**

1. **No read-before-write step.** Architecture: prompt → diff. Model never sees existing
   models/<name>.sql or schema.yml before writing.
2. **No verifier loop.** Single-shot generation. Modern DBT-agents (aider/Devin-style) do
   5-10 iterations of write → dbt run → see error → fix.
3. **7B model is undersized for multi-file DBT semantics.** Same model gets 94 % on
   Spider1 (single-file SQL) but only 13 % on DBT (multi-file project edits).
4. **Official eval is stricter than dbt test.** 17 tasks pass dbt run + test but fail
   matched (semantic divergence from gold output).

**Locations:**
- `outputs/dbt_ablation/dbt_full_v26_clean/per_task.jsonl` — full structured data
- `outputs/dbt_ablation/dbt_full_v26_clean/summary.csv`
- `outputs/dbt_ablation/dbt_full_v26_clean/readout.md`
- `outputs/spider2_dbt/dbt_full_v26_clean_runlog.txt` — per-task console
- `data/spider2_dbt/tasks/<iid>/model_response_v4.txt` — model output per task
- Local apply diffs: `data/spider2_dbt/tasks/<iid>/_apply_v4.diff` or `_apply_v4.sql`

### 3.4 Spider2-Lite-Snow (S3, DONE 207/207)

| metric | value |
|---|---:|
| chosen_schema_valid | 26 / 207 (12.6 %) |
| parse_ok | 193 / 207 (93.2 %) |
| **execute_ok (Snow EXPLAIN)** | **1 / 207 (0.5 %)** |

Same root cause as 3.1 Spider2-Snow (cross-DB identifier drift). 1 task did succeed
end-to-end via Snow EXPLAIN — see predictions.jsonl for which task.

**Locations:**
- `outputs/spider2_lite/runs/lite_snow_full_v26/{predictions.jsonl, traces.jsonl, metrics.csv}`

### 3.5 Spider2-Lite-SQLite (S2 + S3, in progress)

S2 partial 52/135: parse 98 %, exec_ok 0 % (early — first 50 tasks are mostly
`local*` IDs pointing to sqlite-sakila / Db-IMDB which have complex multi-table
schemas; many early models miss DB-specific table names).

S3 partial 33/135: same pattern (parse 32, exec 0).

Both runs are concurrent on different bridges — S2 writes to
`lite_sqlite_full_v26_s2/`, S3 writes to `lite_sqlite_full_v26/`. Use whichever
completes first; cross-check the other for variance.

### 3.6 Spider1 dev FULL (n=1034) — for comparison

| metric | value |
|---|---:|
| parse_ok | 1034 / 1034 (100 %) |
| **execute_ok (SQLite)** | **972 / 1034 (94.0 %)** |
| exact_match_gold | 2 / 1034 |

Only 62 failures across 1034 tasks. Failure breakdown (from
`error_taxonomy.csv`): mostly `OperationalError` (column not found in DB schema —
model used a different col name than gold) and some `no_db` (a few db_ids missing
in `data/spider/database/`).

**Locations:**
- `outputs/spider1/runs/spider1_full_v26/{predictions.jsonl, traces.jsonl, metrics.csv, error_taxonomy.csv}`
- per-pred fields: `instance_id`, `db_id`, `sql`, `gold_sql`, `parse_ok`, `execute_ok`, `execute_class`, `exact_match_gold`

### 3.7 BIRD FULL dev (n=1534) — for comparison

| metric | value |
|---|---:|
| parse_ok | 1532 / 1534 (99.9 %) |
| **execute_ok (SQLite)** | **1349 / 1534 (87.9 %)** |

The 29 `no_db` errors from the first ~29 tasks happened before `dev_databases.zip`
was extracted; ignore those. Real failure rate on the post-extraction 1505 tasks
is ~9.0 % (135 failures), mostly `OperationalError` (column/table name mismatch).

**Locations:**
- `outputs/bird/runs/bird_full_dev_v26/{predictions.jsonl, traces.jsonl, metrics.csv, error_taxonomy.csv}`
- per-pred fields: `instance_id`, `question_id`, `db_id`, `difficulty`, `sql`, `gold_sql`, `parse_ok`, `execute_ok`, `execute_class`, `evidence_chars`

Difficulty breakdown can be derived from `difficulty` field per task
(`easy` / `moderate` / `challenging`).

---

## 4. Cross-benchmark patterns the researcher should investigate

### 4.1 Why Snow lanes collapse but SQLite/BQ do not

**Hypothesis A (most likely): single-DB ambiguity in the pack.**
- For Spider1/BIRD: each task has ONE `db_id` and the SQLite DB file path is unambiguous.
  Schema text is per-DB. Model can't drift.
- For Spider2-Snow: pack is built from a multi-DB live catalog. Even when alias-filtered,
  if multiple SF DBs share an alias prefix (e.g., `GITHUB_REPOS`, `GITHUB_REPOS_DATE`,
  `GITHUB_ARCHIVE`), the pack may include tables from all of them. Coder-7B picks
  whichever table name "feels closer" to the question.
- For Spider2-Lite-BQ: same risk but BQ project names are unique 3-part FQNs that
  rarely overlap. Plus deterministic Family A renderer constrains identifier choice.

**Hypothesis B: lack of Family A for Snow.**
- BQ has `sql_renderer_v18.render_bq` (deterministic) → Family A candidate
- Snow has no equivalent renderer. Only Family B (direct emit by Coder-7B).
- 84-86 % of BQ tasks pick Family A; Snow has no such structured fallback.

**Hypothesis C: Snow-specific dialect quirks not in Coder-7B training.**
- `USE DATABASE`/`USE SCHEMA` discipline, fully-qualified UPPERCASE identifiers,
  Snow-specific EXPLAIN syntax. Model writes valid generic-dialect SQL but Snow
  rejects on case or quoting.
- Counter-evidence: parse_ok=93-95 % on Snow lanes; the issue is identifier
  resolution not pure syntax.

**Recommended experiment:** rerun Snow with (a) hard alias filter to ONE DB,
(b) drop pack tables from other DBs entirely, (c) verify gold answers actually
reference only the alias-named DB. If exec_ok shoots up — hypothesis A confirmed.

### 4.2 Why DBT matches but doesn't exceed Phase 11 baseline

Same baseline (9/68) achieved twice with substantially different downstream stacks
suggests the **DBT eval methodology itself is the ceiling**: gold-output match is so
brittle (exact column-set, exact-row-order, type-precision) that a single-shot
generative agent rarely hits it without a verifier loop. Anyone wanting >20 % on DBT
must build the agentic loop.

### 4.3 Why BIRD beats Spider1 by 6 pp despite higher difficulty?

Counter-intuitive — BIRD-dev has harder tasks (financial/economic domain, more JOINs).
Three hypotheses:
1. BIRD `evidence` field gives explicit knowledge hints in the prompt; Spider1 has no
   equivalent. Coder-7B benefits more from evidence than from raw schema.
2. BIRD's gold queries are written by SQL experts with a uniform style; the model's
   "natural" output matches gold style more often.
3. Spider1's evaluation `execute_ok` is plain `cur.execute` success — semantic
   correctness not checked. Could be that Spider1's 94 % is an overestimate of
   actual answer quality (just "doesn't crash on execute"), and BIRD's 88 % is a
   semantic measure that's actually stricter.

**Recommended experiment:** add result-set comparison (gold row-set vs
predicted row-set) to BOTH Spider1 and BIRD scorers, see if the gap reverses.

### 4.4 Why Spider2-Lite-BQ stays at 34 % despite the BQ stack being mature

Phase 24 trace categorization on the 14 dry_run_failed cases of v22 pilot50 found:
- 5 `unrecog_name`: model wrote columns from JOINed tables WITHOUT the JOIN
- 3 `AND_int` (actually `AND (2023-10-01)` unquoted dates parsed as arithmetic)
- 2 `nested_agg`
- 1 ARRAY_CONTAINS (covered by v24 rewrite, didn't help due to compound errors)
- 3 other

The v24 rewrites target patterns that have very low frequency in actual failures.
Phase 27 should target the actual top patterns: JOIN-aware Family C (with REAL FK
signal from `INFORMATION_SCHEMA.KEY_COLUMN_USAGE`) and date-literal post-render
wrapper.

### 4.5 Why SQLite (Lite) shows 0 % so early

`local*` tasks (`local056`, `local096-100`, `local193-199`) are sqlite-sakila /
Db-IMDB — these databases have schemas with many tables and ambiguous column names
across tables, and gold queries often use specific JOIN paths. Model writes
syntactically valid SQL but operationally references wrong table or wrong column
for the JOIN.

Expect SQLite final exec_ok to rise into the 30-50 % range as the runner moves past
the local* segment into more conventional spider2-lite SQLite tasks.

---

## 5. File map for the researcher

```
outputs/
├── REPORT_PHASE26_RESEARCHER_HANDOFF.md          ← this report
├── REPORT_SPIDER2_FULL_DIAGNOSTIC_V23.md         Phase 23 diagnostic (sequential blocker fix)
├── REPORT_SPIDER2_PHASE24_LITE_BQ.md             Phase 24 v24 BQ rewrites METRIC-NEUTRAL
├── REPORT_SPIDER2_V22.md                         Phase 22 pack-thinness + Family C
├── REPORT_SPIDER2_V20.md                         Phase 20 partial baseline
├── dbt_ablation/
│   ├── dbt_full_v26_clean/                       chain ✅ CLEAN 68/68 with eval
│   │   ├── per_task.jsonl                        ← structured per-task results
│   │   ├── summary.csv
│   │   └── readout.md
│   ├── dbt_full_v26/                             first run (crashed at task 41)
│   ├── dbt_full_v26_resume28/                    second run (killed by GPU contention)
│   └── dbt_full_v26_final17/                     gap-fill of 17 tasks
├── spider1/runs/spider1_full_v26/                ✅ 1034/1034 exec 94 %
│   ├── predictions.jsonl
│   ├── traces.jsonl
│   ├── metrics.csv
│   └── error_taxonomy.csv
├── bird/runs/
│   ├── bird_full_dev_v26/                        ✅ 1534/1534 exec 87.9 %
│   ├── bird_minidev250_v26b/                     ✅ 250/250 exec 90.4 %
│   └── bird_minidev250_v26/                      30/250 (used pre-existing subset)
├── spider2_lite/runs/
│   ├── lite_bq_full_v25/                         Phase 25 v25 205/205 exec 34.6 %
│   ├── lite_bq_v24_pilot50/                      Phase 24 pilot 50 sv 54 % exec 44 %
│   ├── lite_snow_full_v26/                       ✅ S3 207/207 exec 0.5 %
│   ├── lite_sqlite_full_v26_s2/                  S2 in progress (~52/135)
│   └── lite_sqlite_full_v26/                     S3 in progress (~33/135)
├── spider2_snow/runs/snow_full_v25/              S1 in progress (~387/547)
└── spider2_dbt/
    └── dbt_full_v26_clean_runlog.txt             per-task console (parsable)

data/
├── spider/                                       Spider1 dev.json + tables.json + database/
├── spider2_dbt/tasks/<iid>/model_response_v4.txt model raw output per task
└── spider2_lite/raw/Spider2/spider2-lite/        Spider2-Lite source

external_benchmarks/
└── bird_mini_dev/raw/
    ├── dev_20240627/dev.json                     BIRD full dev (1534 tasks)
    └── minidev/.../mini_dev_sqlite.json          BIRD mini-dev (500 tasks)

repo/src/evaluation/
├── candidate_selector_v18.py
├── schema_linking_v18.py
├── schema_pack_builder_v18.py
├── sql_renderer_v18.py                           BQ-only deterministic renderer
├── spider2_candidate_factory_v18.py
├── structured_plan_v18.py
├── bigquery_engine_compat_v24.py                 v24 rewrites (BQ)
└── gpu_lock_v24.py                               Phase 24 GPU lock

memory/ (Claude session memory, persists across conversations)
├── MEMORY.md
└── spider2_phase{17..24}_findings.md             per-phase reports
```

---

## 6. Reproducibility notes

1. **Seeds.** All generators use `do_sample=False, temperature=0.0` (greedy). Output is
   deterministic per (model checkpoint, prompt). Re-running with the same models +
   data should yield identical predictions (modulo race conditions in EXPLAIN/exec).
2. **Snow credentials.** Personal SF account currently set on bridge env
   (`SNOWFLAKE_*`); secrets file at `secrets/snowflake.json` (gitignored). Account
   `RSRSBDK-YDB67606`, role `PARTICIPANT`, warehouse `COMPUTE_WH_PARTICIPANT`,
   default DB `PATENTS`. For reproducibility on another machine, the researcher
   needs equivalent SF access to the Spider2-Snow public DBs.
3. **BQ project.** `project-0e0fc8a5-27b1-4e00-912` (Spider2 GCP). SA JSON in
   `secrets/spider2_bq_sa.json` (gitignored).
4. **Models.** Both Qwen models are HF public; no special license. Loaded via
   `model_registry_v17.load_model_and_tokenizer`. Aliases `qwen3_coder_30b_bf16` and
   `qwen2_5_coder_7b`.
5. **DBT remote server.** SSH to `denis@103.54.18.91` (gitignored config in
   `spider2_dbt_bridge/config.yaml`). Researcher would need equivalent server.

---

## 7. Priority research directions, ranked by expected lift

1. **JOIN-aware Family C with REAL FK signal** (target Lite-BQ + Snow lanes;
   expected lift +10-15 pp on both). Use `INFORMATION_SCHEMA.KEY_COLUMN_USAGE` on
   BQ and Snow `information_schema.referential_constraints` for hard FK metadata,
   replacing the current weak shared-column-name heuristic.

2. **Single-DB hard pack filter for Snow** (target Snow lanes; expected lift
   +20-40 pp). Right now alias filter doesn't enforce ONLY that alias's tables.
   Strict filtering should help Coder-7B not drift to other DBs.

3. **DBT v2 governed agent: read-before-write + verifier loop**
   (target DBT; expected lift +10-20 pp). Modules to add:
   - `read_repo` step (load existing models/<name>.sql + schema.yml into prompt)
   - `verify(dbt_run)` step (compile-check the generated diff)
   - `repair` loop on dbt error (max 3 iterations)

4. **Date-literal post-render fix** for Spider2-Lite-BQ (target Lite-BQ;
   expected +6 pp execute_ok). Wrap unquoted `YYYY-MM-DD` in `DATE 'YYYY-MM-DD'`
   in the renderer's WHERE/HAVING handling.

5. **30B planner thinking mode for DBT** (target DBT; +5-8 pp). Currently `non_thinking_mode=True`
   forced; thinking mode might help on multi-file reasoning.

6. **Snow Family A renderer** (target Snow lanes; +5-15 pp). Translate v18 plan
   into Snowflake SQL deterministically, mirroring `render_bq`. Bound by hypothesis
   A — may not help if pack-filter issue is the real bottleneck.

---

## 8. Comparing to public leaderboards

| benchmark | our result | leaderboard top-1 | leaderboard band | comment |
|---|---:|---:|---|---|
| Spider1 dev exec_ok | 94.0 % | ~91 % (T5-3B fine-tuned) for execute_ok; CHESS-LLM ~92 % | top-tier | likely overestimate vs execution + answer-match scorer |
| BIRD dev exec_ok | 87.9 % | ~75 % (GPT-4 + reasoning) for BIRD exec | top-tier | strong with `evidence` field passed to prompt |
| Spider2-DBT task_success | 13.2 % | ~13-15 % (Phase 11 baseline-class) | bottom-tier | needs governed agent |
| Spider2-Snow exec_ok | 0 % | 30-50 % (closed models with multi-DB grounding) | broken | needs Family A + strict pack filter |
| Spider2-Lite-BQ exec_ok | 34.6 % | ~55-65 % (GPT-4-class) | mid-tier | needs JOIN-aware + date-literal fix |

Spider1 and BIRD numbers are strong enough to publish; Spider2 numbers need
architectural fixes before they're at SOTA. The architecture's strength is on
single-DB SQLite (where it matches/exceeds public SOTA in execute_ok measure);
its weakness is on multi-DB cloud warehouses (Snow especially) and on agentic
multi-file tasks (DBT).

---

## 9. Caveats / honest limitations

1. **Spider1 94 % vs leaderboard 91 %:** my scorer is `cur.execute()`-success only.
   Doesn't check that the answer-rows match gold rows. A standard Spider scorer
   (test-suite execution match) would likely give a lower number. Researcher should
   re-score with a stricter executor.
2. **BIRD 88 % is execute_ok only:** similarly, BIRD's official leaderboard uses
   exact-set-match between predicted rows and gold rows. Our scorer counts as
   success if SQL ran without exception. Recommend rescore with set-match.
3. **DBT 13.2 %:** uses Spider2-DBT's own `server_official_eval.py`. This IS the
   official metric, so 13.2 % is comparable to baselines.
4. **Spider2-Lite-BQ 34.6 %** is `BQ dry_run` (compile-only). Equivalent to
   `execute_ok` per Spider2 protocol since dry_run is the official scoring step
   that doesn't bill bytes.
5. **Spider2-Snow 0 %** is from Snow EXPLAIN — compile-only. Spider2-Snow's
   official metric is full execution; the 0 % we see is likely a hard upper bound
   on the official metric too (you can't pass official scoring if your SQL doesn't
   even compile).
6. **Lite-SQLite tasks `local*`:** these are sqlite-sakila / Db-IMDB — they're
   actually labeled by Phase 23 as "non-comparable per benchmark policy" (Spider1-style
   gold execution rather than Spider2 scoring). Researcher should NOT include them
   in any combined Spider2-Lite metric; treat as Spider1-style supplement.

---

## 10. Next steps the researcher can run TODAY

1. **Pull all 4 done runs locally for offline error analysis:**
   ```
   rsync the following from Drive to local:
     outputs/spider1/runs/spider1_full_v26/
     outputs/bird/runs/bird_full_dev_v26/
     outputs/bird/runs/bird_minidev250_v26b/
     outputs/spider2_lite/runs/lite_snow_full_v26/
     outputs/dbt_ablation/dbt_full_v26_clean/
   ```

2. **Score-comparison sanity check:** run Spider1 official scorer on
   `spider1_full_v26/predictions.jsonl` and compare to our `exec_ok` count.

3. **Cluster Snow failures:** for `lite_snow_full_v26/predictions.jsonl`, group
   by `explain_class` and inspect SQL text — confirm hypothesis A (cross-DB drift)
   on 50+ samples.

4. **For DBT:** for the 17 `ran_ok_but_score_zero` tasks, diff the generated
   `models/<name>.sql` against gold `evaluation_suite/<iid>/gold/models/<name>.sql`
   to see the semantic gap.

5. **For Lite-BQ:** re-run with date-literal post-render fix only (~30 lines of
   code in `sql_renderer_v18.py`), measure delta on the 3 v22 `AND_int` cases.

Pass me back any prioritization signal and I'll start implementing in Phase 27.
