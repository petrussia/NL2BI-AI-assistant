# Spider2-Lite agent_v7 — design memo

_Branch `experiments/denis`. Phase 9 of the multi-phase research arc;
follows the frozen B6_v7 controller (commit `8559379`). This memo
documents the architecture for the FULL 547-item Spider2-Lite agent
run, what it measures per lane, and the honest blockers carried
forward._

## 1. The problem

Spider2-Lite is the only benchmark in our coverage that cannot be
evaluated as a standard text-to-SQL EX run. The blockers, already
documented in `baseline_freeze_after_r2_phase_d.md`, are:

1. **Multi-dialect**: gold SQL is BigQuery (~205 items) or Snowflake
   (~207 items); 135 items are SQLite-style stubs. Our v5 pipeline
   emits SQLite by default and never wired the dialect-transpile hook.
2. **Multi-engine**: real EX needs a live BigQuery project + service
   account, or Snowflake credentials. The default Colab sandbox has
   neither.
3. **Schema scale**: enterprise BigQuery datasets ship with 50–200+
   tables and thousands of columns. Full schema does not fit in 8K
   context, so retrieval is mandatory.
4. **Stub format**: the bundled SQLite "databases" under
   `resource/databases/sqlite/` are NOT real `.sqlite` files; they
   are per-table sample-row JSONs plus a `DDL.csv`. They have to be
   materialized in-memory before queries can run.

A single-engine, single-dialect controller cannot serve all 547 items
without either silently falling back to structural-only or producing
EX numbers that mix incompatible execution semantics. Our solution
splits items by lane and runs different machinery per lane.

## 2. Lane assignment (`spider2_router_v7`)

The router decides the lane per item once, before the agent runs.
Decision ladder (first match wins):

| Priority | Condition | Lane | Rationale |
|---|---|---|---|
| 1 | dialect == snowflake | A_sf | No SF creds. Honest blocker (mode D). |
| 2 | dialect == bigquery AND BQ creds present | A_bq | Real EX possible — execute against BigQuery, compare against gold `exec_result` rows. |
| 3 | dialect == sqlite AND stub dir present | B_sqlite | Materialize in-memory SQLite; execute; compare structurally. Oracle-on-sample, not official EX. |
| 4 | dialect == bigquery AND no creds | C_struct | Parse + dialect-valid + schema-valid + structural features only. |
| 5 | unknown / other | C_struct | Same as 4. |

Dialect detection uses instance_id prefix:
- `sf*` → snowflake (e.g. `sf_bq029`)
- `bq*` or `ga*` → bigquery (e.g. `bq011`, `ga005`)
- `local*` → sqlite (e.g. `local002`)

Stub-dir matching uses normalized names so `sqlite-sakila` matches
`SQLITE_SAKILA` (`re.sub(r'[\\s_\\-]+', '', s.strip().lower())`).

**Verified split on the actual 547-item file (with our test BQ creds):**

| Lane | n |
|---|---:|
| A_bq | 205 |
| A_sf | 207 |
| B_sqlite | 135 |
| C_struct | 0 |
| **Total** | **547** |

The 0 C_struct count is a function of (a) all snowflake items going to
A_sf, (b) BQ creds being present so all bq/ga items going to A_bq, and
(c) all 135 local items having a stub dir match. With different creds
or a smaller stub coverage, C_struct would absorb the difference.

## 3. Per-lane machinery

### A_bq (BigQuery execution)
- **IR builder**: `build_ir_from_bq_db_dir(db_id, bq_dir)` walks
  `resource/databases/bigquery/<db>/<fully_qualified_dataset>/` and
  reads each `<table>.json` (containing `column_names`, `column_types`,
  `sample_rows`, `description`). The IR's `original_name` for each
  table is the full path
  `<project>.<dataset>.<table>` so the LLM emits correctly-qualified
  references.
- **Executor**: `build_bq_executor(creds_path, project, max_bytes=10**9)`.
  Uses `dry_run=True` first (free; validates SQL + estimates bytes),
  then real query capped at 1 GB billed (~$0.005 worst case). On
  `bytesBilledExceeded` the item is logged as `executable=False` and
  the agent falls back to bounded repair.
- **Dialect target**: `bigquery`. The agent prompt explicitly asks
  for "BigQuery Standard SQL". `dialect_check` transpiles candidates
  via sqlglot when needed.
- **Execution match**: at consolidation time, predicted SQL is
  re-executed against BQ and result rows are compared against the
  multi-variant gold `evaluation_suite/gold/exec_result/<iid>_a.csv`,
  `_b.csv`, `_c.csv`. Any-variant match → `execution_match=True`. This
  is the only lane where we report official EX.

### B_sqlite (in-memory SQLite from JSON stubs)
- **IR builder**: `build_ir_from_stub_dir(db_id, stub_dir)` reads each
  `<name>.json` (`table_name`, `column_names`, `column_types`,
  `sample_rows`, `description`) → SchemaIR with proper types.
- **Materialization**: `materialize_sqlite_from_dir(stub_dir)` builds
  an in-memory `sqlite3.Connection`, runs `CREATE TABLE` per JSON
  (typed via `column_types` mapping), inserts every `sample_rows`
  entry. `check_same_thread=False` so `func_timeout` worker thread
  can use the connection.
- **Executor**: `build_sqlite_conn_executor(con)`.
- **Dialect target**: `sqlite`. Existing v5 prompts work unchanged.
- **Execution match**: NOT computed against gold. The stub data is a
  small sample; result rows generally won't match the gold rows
  computed against the full warehouse. The B_sqlite numbers are
  reported as "oracle-on-sample, non-comparable to official EX" —
  they show the pipeline produces SQL that runs on the stub schema
  with sample data, not that it produces correct answers.

### A_sf (Snowflake — blocked)
- No executor; agent loop is short-circuited. Per-item record carries
  `mode='blocked_snowflake'` and a structured row for the consolidation
  table. We do not generate SQL for these items in this pass — the
  agent is dialect-aware and Coder-7B doesn't reliably produce
  Snowflake-only idioms (`QUALIFY`, `FLATTEN`, `LATERAL` etc.) without
  test feedback. Treating as honest blocker is preferred to manufactured
  structural numbers that are misinterpretable.

### C_struct (parse-only fallback)
- Used when an item should have been A_bq but the BQ executor failed
  to initialize, or any other unforeseen routing escape. Agent runs
  candidate generation against a `NoopExecutor` that returns
  `parse_only_no_execute` from `dry_run`. We collect parse + safe +
  schema validity + structural features. No execution match.

## 4. Agent loop (`spider2_agent_v7.run_spider2_agent_step`)

Up to 4 candidate families per item. All are verified, scored, and
optionally judged before final selection.

| Source | Description |
|---|---|
| C0_anchor | Direct draft from full schema (or compact-rendered subset if schema > 4000 chars) |
| C1_retrieval_evidence | Reduced schema via `schema_linker_bidirectional_v2.link` + external_knowledge text |
| C2_cte_decomp | Prompts the LLM to decompose into named CTEs |
| C3_explore | Bounded ReAct loop (max_steps=3): action JSON over schema_search / metadata_doc_search / join_path_search / column_profile / sample_value_probe / draft_sql / submit_sql / give_up |

After candidates: heuristic ranking via composite score
(parse + safe + schema validity + executable + small source-risk
penalty). When top-2 margin is small (configurable; default 0.5 score
units) AND ≥2 candidates exist, the LLM judge is invoked using the
existing `llm_judge_v7.judge_candidates` infrastructure unchanged.

Bounded repair (1 round) on the chosen candidate if the executor
returned a non-OK result and the lane has an executor.

The action JSON contract is identical to the spec:
```json
{"action": "<name>", "args": {...}, "reason_short": "<≤80 chars>"}
```

## 5. What's measured (output schema)

Per-item record in `spider2lite_agent_v7_full_predictions.jsonl`:

| Field | Type | Lane semantics |
|---|---|---|
| `instance_id`, `db_id`, `lane`, `route_reason`, `dialect` | meta | all lanes |
| `generated_sql` | string | empty for A_sf |
| `executable` | bool/None | True for A_bq+B_sqlite if exec succeeded; None for A_sf |
| `execution_match` | bool/None | populated only for A_bq at consolidation; None elsewhere |
| `parses`, `safe_select`, `all_known` | bool | all lanes (parse-only for A_sf is False) |
| `unknown_tables_n`, `unknown_columns_n` | int | structural-validity counters |
| `final_source`, `mode`, `top_score`, `top2_margin` | meta | all lanes that ran |
| `judge_invoked`, `judge_overrode`, `judge_chose_source`, `judge_confidence` | judge state | all lanes |
| `repair_used`, `repair_rounds` | repair state | all lanes that ran |
| `bytes_billed`, `bytes_processed` | int | non-zero only for A_bq |
| `lm_calls`, `latency_ms`, `completion_tokens` | LLM stats | all lanes |
| `candidates` | list[dict] | per-candidate score + verifier features |

Per-step trace lives in `spider2lite_agent_v7_traces.jsonl` for items
that triggered the explore loop (C3).

## 6. Cost / safety guards (BQ lane)

- `maximum_bytes_billed=10**9` (1 GB) per query — prevents accidental
  TB scans
- `dry_run=True` validation before every real exec
- All access via service account; key persisted privately in
  `/content/drive/MyDrive/diploma_plan_sql/secrets/` (never committed)
- 1 LLM repair round, no retry beyond
- 547 items × ~9 LLM calls + ~2 BQ jobs each → upper bound on cost
  even with 1 GB max ≈ $5 worst case

## 7. Differences from B6_v7 production controller

| Aspect | B6_v7 (Spider/BIRD) | agent_v7 (Spider2) |
|---|---|---|
| Schema scale | small (≤30 tables) | huge (≤200 tables); retrieval mandatory |
| Dialect | sqlite only | sqlite OR bigquery, lane-decided |
| Executor | local sqlite per-db | BQ + materialized in-memory sqlite + noop |
| Tool loop | none | bounded ReAct over 8 actions (C3 only) |
| CTE candidate | none | dedicated C2_cte_decomp prompt |
| Judge | enabled (BIRD-aggressive, Spider-safe) | enabled, lane-agnostic; safe defaults |
| Repair | repair_v2 (Spider/BIRD-tuned) | bounded_repair (lane-agnostic, dialect-aware) |
| Eval | direct EX per row | per-lane: A_bq EX vs gold-rows; B_sqlite parse+exec; A_sf blocker |

The frozen production stack on Spider/BIRD is unchanged. Spider2 lives
in its own module path (`spider2_*_v7.py`); nothing in the existing
v5/v7 modules was modified.

## 8. Honest limitations

- **B_sqlite numbers are non-comparable** to any official Spider2 score.
  They prove the pipeline can produce executable SQL on a small sample
  schema; nothing more.
- **A_sf 207 items remain blocked.** The diploma report must list this
  as a residual blocker, not paper over it with structural-only numbers.
- **Snapshot-bound BQ access**: the test service account has access to
  `bigquery-public-data.*` (free public data). Some Spider2 datasets
  (e.g. `isb-cgc.*`, `spider2-public-data.*`) may or may not be in
  this whitelist; runtime errors are recorded per-item.
- **No retrieval over external_knowledge docs yet**: we read the doc
  filename pointed to by each item and pass up to 1500 chars as
  evidence_text. We do NOT (yet) parse the doc structure — that's
  a deferred refinement.
- **Tool loop is bounded at 3 steps.** Items needing more exploration
  (e.g. join-path discovery across multiple datasets) will run out of
  budget; the C3 candidate then falls back to whatever it had at the
  cap. We expect most successful items to be solved by C0/C1/C2.
