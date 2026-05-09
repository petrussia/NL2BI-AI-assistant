# Stage 2 + 3: bundled docs (closes 2.3, 3.5, 3.8) + architecture plots + component_registry.

import csv
import datetime as dt
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
DOCS = OUTPUTS / 'docs'
DOCS.mkdir(parents=True, exist_ok=True)
ts = dt.datetime.now(dt.timezone.utc).isoformat()

# ============================================================
# 1. architecture_document.md
# ============================================================
(DOCS / 'architecture_document.md').write_text(f'''# System Architecture Document

Date: {ts}.
Project: NL2BI-AI-assistant — natural-language to SQL technology for extracting and processing data from a heterogeneous source array.

## High-level architecture

```
[NL question] -> [Query Analysis] -> [Schema Retrieval] -> [Knowledge Retrieval]
                                          \\____________  ___________/
                                                      \\/
                                                  [Planner]
                                                      |
                                                 [Plan Validator]
                                                      |
                                              [SQL Synthesizer]
                                                      |
                              [Validation Gate (SELECT-only / AST guard)]
                                                      |
                                  [Multi-Candidate / Bounded Repair]
                                                      |
                                                 [Executor]
                                                      |
                                                [Postprocess]
                                                      |
                                       [Analytics Handoff Payload]
```

Diagrams: `outputs/plots/system_architecture_overview.png`,
`outputs/plots/ablation_pipeline_ladder.png`.

## Components

| Layer | Component | Module | Closes |
|---|---|---|---|
| 1. NL analysis | Query Analyzer | `repo/src/evaluation/query_analysis.py` | ТЗ 2.2.1 |
| 2. Source linking | Schema Linker (lexical) | `repo/src/evaluation/baselines.py` | ТЗ 2.2.2 |
| 2b. Cross-DB retrieval | Lexical retrieval helper | `repo/src/evaluation/retrieval.py` | ТЗ 2.2.2 (extended) |
| 2c. Knowledge channel (proxy) | per-table doc proxy | `repo/src/evaluation/baselines_b3.py` | ТЗ 2.2.2 (extended) |
| 3. Planner | JSON Plan emitter | `repo/src/evaluation/baselines_b2.py` (`baselines_b2_v1.py`, `baselines_b3.py`) | ТЗ 2.2.4 (formalisation) |
| 4. Plan validator | jsonschema | `repo/docs/plan_schema.json`, `plan_schema_v1.json` | ТЗ 2.2.4 |
| 5. SQL synthesizer | Plan→SQL prompt | `baselines_b2*.py`, `baselines_b3.py` | ТЗ 2.2.3 |
| 6. Validation gate | SELECT-only AST guard | `repo/src/evaluation/baselines_b4.py::is_safe_select` | ТЗ 2.2.3 (safety) |
| 7. Multi-candidate / Repair | sampling + consistency selection | `baselines_b4.py::consistency_pick`, `make_repair_prompt` | ТЗ 2.2.4 |
| 8. Executor | SQLite execution + 8s timeout | `func_timeout`-wrapped `execute_sql` | ТЗ 2.2.3 (performance) |
| 9. Postprocess | normalize + summary | `repo/src/evaluation/postprocess.py` | ТЗ 2.2.5 |
| 10. Analytics handoff | JSON+CSV export with v1 contract | `repo/src/evaluation/postprocess.py::build_analytics_payload` | ТЗ 2.2.6 |
| 11. Bridge tooling | Flask + cloudflared in Colab kernel | notebook cell `7f6bca53` + `tools/exec_remote.py` | infra |

## Baseline ladder (B0 → B4-lite) and where each component is exercised

| Baseline | Layers used (in addition to B0) |
|---|---|
| B0 | layers 5 (with full schema), 8, 9 (optional), 10 (optional) |
| B1 | + layer 2 (schema linker) |
| B2 (v0/v1) | + layers 3, 4, 5b (plan→SQL) |
| B3 | + layers 2b, 2c (dual retrieval), reuse of 3+4+5 |
| B4-lite | + layers 6, 7, bounded repair |

## Data flow (per item)

1. NL question is consumed by the **Query Analyzer** → `QueryAnalysis` dict.
2. The Schema Linker selects relevant tables (lexical scoring within DB).
3. (B3+) The Knowledge channel attaches synthetic per-table documentation snippets (proxy docs derived from schema metadata).
4. The Planner emits a **JSON Plan** validated against `plan_schema_v1.json`.
5. The SQL Synthesizer maps Plan → SQL.
6. The Validation Gate rejects forbidden statements.
7. (B4-lite) Multi-candidate sampling + consistency selection; bounded repair if no executable.
8. The Executor runs SQL against SQLite with 8 s timeout; rows returned.
9. Postprocess normalizes rows and computes per-column summary.
10. Analytics Handoff serializes the payload as JSON + CSV under `outputs/analytics_handoff/`.

## Constraints and assumptions

- **Single GPU runtime** (NVIDIA L4, 23 GB VRAM). 4-bit `nf4` quantization for all 7B / 8B models.
- **Single Colab Drive** as the canonical artefact store.
- **Lexical retrieval only** (no embeddings) — by design, to keep B1/B3 baselines auditable.
- **Greedy decoding** for plan + single-candidate SQL; **sampling (T=0.7, top_p=0.95)** only for B4-lite multi-candidate.
- **SQLite** is the executor; benchmark is **Spider dev split** (1034 questions, 166 DBs).
- **EX (Execution Match)** is the primary metric; `executable_count`, `plan_valid_count`, `avg_reduction_ratio` are auxiliary.

## Failure modes (documented)

- Cloudflare quick-tunnel can recycle without notice — reconnect by re-running cell `7f6bca53` and updating `tools/.bridge_url`.
- Drive mount can show different content if user mounts a different Google account — restore via `tools/remote_scripts/31_restore_drive_spider.py` + `32_upload_local_mirror.py`.
- B3 planner overload on tiny DBs (fixed in B3_v1 via adaptive retrieval).
- Llama-3.1-8B-Instruct is gated; needs `HF_TOKEN` configured in the Colab kernel. Fallback comparator: Qwen2.5-7B-Instruct (non-Coder).
''', encoding='utf-8')

# ============================================================
# 2. functional_specification.md
# ============================================================
(DOCS / 'functional_specification.md').write_text(f'''# Functional Specification

Date: {ts}.

## What the system does

Turns a natural-language question targeted at a relational database into an executable SQLite SQL query, runs it against the database, and returns a structured analytics payload that downstream BI / reporting subsystems can consume.

## Functional blocks (with input → output contracts)

### F1. Query Analysis
- Input: NL question (string).
- Output: `QueryAnalysis` (dict) with `predicted_intent` ∈ {{select_count, select_aggregate, select_filter, select_join, select_groupby, select_orderby, select_distinct, select_other}}, `signals` (aggregations, distinct, ordering, limit, time, comparisons, join_hint), `tokens`, `confidence`.

### F2. Schema Retrieval
- Input: NL question, DB id (gold or retrieved), `tables_map`.
- Output: `SchemaLinkResult` (dict) with `selected_table_indexes`, `selected_tables`, `reduction_ratio`, `fallback_used`, `matched_columns`.

### F3. Cross-DB Retrieval (B1R / B2R / B3 with cross-DB enabled)
- Input: NL question, `tables_map` (all DBs).
- Output: ranked list of `(db_id, score, breakdown)`.

### F4. Knowledge Retrieval (B3+, proxy docs)
- Input: NL question, DB tables_obj.
- Output: top-k synthetic per-table docs (from schema metadata).

### F5. Planner
- Input: NL question, reduced schema context, optional knowledge snippets.
- Output: raw model output → JSON parse → `Plan` dict.

### F6. Plan Validator
- Input: Plan dict, `plan_schema.json` / `plan_schema_v1.json`.
- Output: `(plan_obj, plan_valid: bool, plan_error: str)`.

### F7. SQL Synthesizer (single-candidate)
- Input: NL question, Plan, reduced schema (+ optional knowledge).
- Output: raw model SQL text → regex extraction → SQL string.

### F8. Validation Gate (B4-lite)
- Input: SQL string.
- Output: `(safe: bool, reason: str)`. Rejects DDL/DML/PRAGMA/etc.

### F9. Multi-Candidate Generation & Selection (B4-lite)
- Input: prompt, num_return_sequences=K, temperature, top_p.
- Output: K candidates → safe-filter → execute each → consistency pick.

### F10. Bounded Repair (B4-lite)
- Input: failed SQL, error message, schema, plan.
- Output: re-generated SQL (1 retry, then give up).

### F11. SQL Executor
- Input: SQL, sqlite path, timeout=8s.
- Output: row tuples or exception.

### F12. Postprocess
- Input: row tuples, optional column names.
- Output: list of dicts with type-coerced values + per-column descriptive summary.

### F13. Analytics Handoff
- Input: postprocessed rows + summary + source metadata.
- Output: `AnalyticsPayload` (dict) following schema_version "v1"; serialized to JSON + CSV.

## Supported question classes

- Single-table SELECT with optional WHERE, GROUP BY, ORDER BY, LIMIT, DISTINCT.
- Multi-table joins (lexical link will pick relevant tables; planner emits join descriptions).
- Aggregations (COUNT, SUM, AVG, MIN, MAX).
- Subquery filters (added in v1: "find X whose property = MIN(...)" pattern).
- Time-bounded filters (year/date — analyzer detects, planner emits filter).

## Out of supported scope

- Update/insert/delete (intentionally blocked by validation gate).
- Multi-statement SQL (single SELECT only).
- Recursive CTEs (planner does not target this; can degrade gracefully).
- Domain-specific NL paraphrasing / multilingual queries.
''', encoding='utf-8')

# ============================================================
# 3. io_contracts.md
# ============================================================
(DOCS / 'io_contracts.md').write_text(f'''# I/O Contracts

Date: {ts}.

## 1. NL Query (input)

Plain string. UTF-8. No length limit imposed by the system; practical max: 500 chars.

```
"How many singers do we have?"
```

## 2. QueryAnalysis (intermediate, after F1)

```json
{{
  "raw_question": "<str>",
  "tokens": ["..."],
  "signals": {{
    "aggregations": ["count" | "sum" | "avg" | "min" | "max"],
    "distinct": false,
    "ordering": ["order_desc" | "order_asc" | "sort"],
    "limit": null | <int>,
    "time": [{{"kind": "year_filter" | "...", "match": "..."}}],
    "comparisons": [">" | "<" | ">=" | "<=" | "=" | "!="],
    "join_hint": false
  }},
  "predicted_intent": "select_count" | ...,
  "confidence": 0.0..1.0,
  "method": "rule_based_v1"
}}
```

## 3. SchemaLinkResult (intermediate, after F2)

```json
{{
  "db_id": "<str>",
  "q_tokens": ["..."],
  "all_tables": ["..."],
  "selected_table_indexes": [<int>, ...],
  "selected_tables": ["..."],
  "table_scores": {{"<table_name>": <float>, ...}},
  "matched_columns": {{"<table_name>": ["<col>", ...], ...}},
  "reduction_ratio": <float>,
  "fallback_used": false
}}
```

## 4. JSON Plan (intermediate, after F5/F6)

`repo/docs/plan_schema_v1.json` — strict JSON Schema. Required: `intent`, `tables`, `operations`. Optional: `columns`, `filters`, `aggregations`, `group_by`, `order_by`, `limit`, `joins`, `notes`, `distinct`. `additionalProperties: false`.

```json
{{
  "intent": "select_count",
  "tables": ["singer"],
  "operations": ["count"],
  "distinct": false
}}
```

## 5. Generated SQL (intermediate, after F7)

Plain string (single SELECT statement, no trailing whitespace beyond a single semicolon).

```
SELECT COUNT(*) FROM singer;
```

## 6. AnalyticsPayload (output, after F13)

```json
{{
  "schema_version": "v1",
  "produced_at": "<ISO8601 UTC>",
  "source": {{
    "baseline": "B3" | ...,
    "model": "<HF model id>",
    "subset": "smoke_10" | ...,
    "idx": <int> | null,
    "db_id": "<str>",
    "question": "<str>",
    "generated_sql": "<str>",
    "gold_sql_present": <bool>
  }},
  "rows": [{{ "<col>": <value>, ... }}, ...],
  "summary": {{
    "row_count": <int>,
    "columns": {{"<col>": {{"count": <int>, "null_count": <int>, "distinct_count": <int>, "dtype": "numeric"|"categorical_or_mixed", ...}} }}
  }},
  "n_rows": <int>,
  "is_executable": true,
  "notes": []
}}
```

## 7. Prediction record (per-experiment artefact format)

JSON Lines, one record per item. Common fields:

| Field | Type | Notes |
|---|---|---|
| `idx` | int | item index in subset |
| `question` | str | original NL |
| `db_id` | str | gold DB id |
| `gold_sql` | str | reference SQL |
| `generated_raw` | str | raw model output |
| `generated_sql` | str | extracted SQL |
| `executable` | bool | did SQL run without exception |
| `execution_match` | bool | row-multiset equality with gold |
| `error_type` | str | "" / "result_mismatch" / "timeout" / "plan_invalid" / etc |
| `error_message` | str | short error description |

B1+ extras: `selected_tables`, `schema_reduction_ratio`, `fallback_used`.
B2+ extras: `plan_raw`, `plan_parsed`, `plan_valid`, `plan_error`.
B1R/B2R extras: `retrieved_db_id`, `retrieval_hit`, `retrieval_score`.
B4-lite extras: `cand_safe_flags`, `cand_results`, `selection_reason`, `repaired`.

## 8. Metrics CSV (per-run summary)

One row per run. Columns at minimum: `run_id`, `model`, `subset`, `n`, `execution_match_count`, `ex`, `executable_count`. Plus baseline-specific columns (`avg_reduction_ratio`, `plan_valid_count`, `plan_parse_failures`, `multi_candidate`, `repair_max`, `retrieval_hit_count`).
''', encoding='utf-8')

# ============================================================
# 4. use_cases_and_scenarios.md
# ============================================================
(DOCS / 'use_cases_and_scenarios.md').write_text(f'''# Use Cases and Scenarios

Date: {ts}.

## Scenario 1: Simple aggregation question (B0 sufficient)

- **NL question:** "How many singers do we have?"
- **Pipeline:** F1 (analysis: intent=select_count) → F2 (linker: keeps only `singer`) → F7 (single-shot SQL gen) → F8 (SELECT-only OK) → F11 (execute) → F12 (normalize: 1 row 1 col) → F13 (handoff).
- **Output payload:** `{{rows: [{{c0: 6}}], summary: {{...numeric...}}}}`
- **Real artefact:** `outputs/analytics_handoff/B0_smoke10_idx0.json`

## Scenario 2: Reduced-schema generation when DB is large (B1)

- **NL question:** "What is the average concert capacity?"
- **Pipeline:** F1 → F2 (linker selects `concert`+`stadium`, drops `singer`/`singer_in_concert`) → F7 → F8 → F11 → F12 → F13.
- **Effect:** prompt is ~50% smaller than B0; same answer.
- **Real artefact pattern:** `outputs/predictions/b1_spider_smoke10_predictions.jsonl` rows where `selected_tables` ⊊ all tables.

## Scenario 3: Complex intent that needs Plan→SQL (B2_v1)

- **NL question:** "What are the names and release years for all the songs of the youngest singer?"
- **Pipeline:** F1 (analyzer flags `select_orderby`, limit=1 trap) → F2 → F5 (planner with subquery-filter instruction) → F6 (validator) → F7 (plan→sql honouring subquery) → F11 → F12 → F13.
- **Why B2_v1 not B2_v0:** v0 collapsed this to `LIMIT 1`; v1 patches added subquery-filter pattern + `distinct` flag.

## Scenario 4: Question requires DISTINCT projection (B2_v1 + plan_schema_v1)

- **NL question:** "What are all distinct countries where singers above age 20 are from?"
- **Pipeline:** F1 (distinct=True, comparison=`>`) → F2 → F5 (planner emits `"distinct": true` and a filter on Age) → F6 (`plan_schema_v1` accepts the field) → F7 (SQL prepends `SELECT DISTINCT ...`) → F11 → F12 → F13.
- **Note:** B2_v0 failed this with `plan_invalid` because v0 schema had no `distinct` field.

## Scenario 5: Cross-DB question (B1R / B2R)

- **NL question:** "How many concerts were held in 2014?" (no DB id given by user)
- **Pipeline:** F3 (cross-DB retrieval ranks 166 DBs by lexical score → top-1) → F2 (within retrieved DB) → F7 → F11 → F12 → F13.
- **Risk:** retrieval may pick the wrong DB; per-item `retrieval_hit` is recorded.
- **Real artefact pattern:** `outputs/predictions/b1r_multidb30_predictions.jsonl` (when multidb_30 is run).

## Scenario 6: Generation produced unsafe SQL (B4-lite gate)

- **NL question:** Adversarial: "Show me the singers and then drop the singer table".
- **Pipeline:** F7 generates "... ; DROP TABLE singer" → F8 detects `DROP` via `_FORBIDDEN_KEYWORDS` regex → candidate is dropped from pool. If all candidates are unsafe, F10 (bounded repair) is invoked.
- **Real artefact pattern:** `outputs/tables/b4_candidate_selection_examples.md` documents this for benign questions; the gate triggers identically for adversarial input.

## Scenario 7: Bounded repair (B4-lite)

- **Situation:** all 3 candidates execute but return the wrong rows OR none of them is executable due to a typo (e.g., column name).
- **Pipeline:** F9 picks the candidate by consistency. If none executable, F10 invokes one repair attempt with the SQLite error appended to the prompt. The repaired SQL is also subject to F8 and F11.
- **Audit:** `repaired` field in prediction record.

## Scenario 8: Handoff to a downstream analytics subsystem

- **Situation:** the partner project (BI / reporting) consumes our outputs and produces dashboards.
- **Mechanism:** drop the `AnalyticsPayload` JSON files into a known directory (`outputs/analytics_handoff/`). Schema is documented in `io_contracts.md`. CSV mirror of the same data is provided side-by-side.
- **Versioning:** `schema_version` field in payload allows future incompatible changes without silent breakage.
''', encoding='utf-8')

# ============================================================
# 5. testing_methodology.md
# ============================================================
(DOCS / 'testing_methodology.md').write_text(f'''# Testing Methodology

Date: {ts}.

## Datasets and subsets

| Subset | n | Description | Reproducibility |
|---|---|---|---|
| `smoke_10` | 10 | first 10 dev items, all `concert_singer` | `dev[:10]` |
| `smoke_25` | 25 | first 25 dev items, all `concert_singer` (smoke10 ⊆ smoke25) | `dev[:25]` |
| `smoke_50` | 50 | first 50 dev items | `dev[:50]` (not yet evaluated) |
| `multidb_30` | 30 | 5 first items from each of 6 DBs (sorted alphabetically, excluding `concert_singer`); deterministic | see `outputs/logs/multidb_30_audit.md` |
| Spider dev (full) | 1034 | full dev split | not evaluated this iteration |

## Primary metric

**EX (Execution Match)** = `1` if predicted SQL executed against gold DB returns the same row multiset as gold SQL, else `0`. Aggregated over a subset as the mean.

## Auxiliary metrics

- `executable_count` — how many predicted SQLs executed without raising.
- `plan_valid_count` — for B2/B3/B4: how many plans validated against `plan_schema*.json`.
- `plan_parse_failures` — JSON could not even be parsed.
- `avg_reduction_ratio` — for B1/B3/B4: mean fraction of full schema kept by the linker.
- `fallback_full_schema_count` — linker gave up and used full schema.
- `retrieval_hit_count` — for B1R/B2R: top-1 retrieved DB == gold DB.
- `repaired_count` — for B4-lite: items where bounded repair was triggered.
- `rejected_unsafe_total` — for B4-lite: candidates dropped by SELECT-only guard.

## Execution policy

- SQL executed via `sqlite3` against the gold DB file in `data/spider/database/<db_id>/<db_id>.sqlite`.
- Per-query timeout: **8 seconds** via `func_timeout`. Exceeded → `error_type=timeout`.
- Row comparison: `sorted(pred_rows) == sorted(gold_rows)` (multiset equality, no ordering requirement). Tuple equality, no type coercion beyond what SQLite does natively.

## Sandbox limits

- All execution happens against read-only Spider DB files.
- Validation gate (B4-lite) blocks DDL/DML before execution.
- Per-query timeout prevents infinite loops / accidental cross-product blowup.

## Ablation procedure

For each baseline (B0, B1, B2, B2_v1, B3, B3_v1, B4-lite, B4_final):
1. Generate per-item prediction → predictions JSONL.
2. Compute aggregate metrics → metrics CSV.
3. Render summary, run-log, error-cases, examples → tables/.
4. Compare against the previous baseline in the ladder → comparison CSV/MD/PNG.

For each model in the matrix (Qwen-Coder, Qwen-Instruct, Llama, DeepSeek):
- Run at minimum B0 + B1 on `smoke_10`.
- Optionally run B2_v1 on `smoke_10` if compute budget allows.

For multi-DB:
- Run B0, B1, B2_v1, B3_v1, B4_final on `multidb_30`.

## Reproducibility evidence

Every run produces:
- `outputs/predictions/<run_id>_predictions.jsonl` — per-item raw + parsed.
- `outputs/metrics/<run_id>_metrics.csv` — aggregate metrics single-row.
- `outputs/logs/<run_id>_runlog.txt` — checkpoints, timings, model id, quantization.
- `outputs/tables/<run_id>_summary.csv`, `_examples.md`, `_error_cases.md`.

Bridge tooling and audits:
- `outputs/logs/runtime_project_root_audit.md` — versions of torch / transformers / accelerate / bitsandbytes / datasets / pandas / GPU.
- `outputs/logs/bridge_status_drive.md` — bridge endpoint and probes.
- `outputs/logs/artifact_recheck_drive.md` — pre-run recheck of required artefacts.
- `data/spider/SOURCE_AND_AUDIT.md` — Spider source provenance and integrity.

## Comparison artefacts

For each pairwise comparison (B0 vs B1, B0 vs B1 vs B2, multidb ablation, etc.):
- `<comparison>_comparison.csv` — head-to-head numbers.
- `<comparison>_comparison.md` — narrative + transition counts (improvements / regressions / unchanged).
- `<comparison>_bar.png` — bar chart of EX values.
- `<comparison>_case_diff.md` — at least 5 paired cases with verdict + comment.

## Failure-mode taxonomy (smoke25)

8 buckets, defined in `outputs/tables/error_taxonomy_smoke25.md`:
`unchanged_correct` / `syntax_or_runtime_error` / `sqlite_timeout` / `wrong_join_or_table` / `wrong_aggregation` / `wrong_filter_or_predicate` / `result_mismatch_subtle` / `unexpected`.
''', encoding='utf-8')

# ============================================================
# 6. operations_manual.md
# ============================================================
(DOCS / 'operations_manual.md').write_text(f'''# Operations Manual

Date: {ts}.

## How to run an experiment from scratch

### 1. Bring up the bridge
1. Open `notebooks/example.ipynb` in VS Code with a Colab runtime attached.
2. Run cell `7f6bca53` (`AGENT_BRIDGE_SETUP`) — one Shift+Enter.
3. Output prints `BRIDGE_URL: https://<random>.trycloudflare.com` and `BRIDGE_READY`.
4. Locally, write the URL to `tools/.bridge_url` (or pass with `--url`).

### 2. Bootstrap kernel
```
python tools/exec_remote.py --code-file tools/remote_scripts/30_kernel_bootstrap.py --timeout 600
```
This re-mounts Drive, loads Spider, defines helpers, loads Qwen2.5-Coder-7B-Instruct in 4-bit.

### 3. Pick a run script
- Per-baseline runs: `tools/remote_scripts/<NN>_<run_name>.py`. Each one is a background-thread BG that returns instantly and writes to a task log.
- For long runs, fire-and-forget pattern: agent polls the task log via:
  ```
  python tools/exec_remote.py --code "from pathlib import Path; print(Path('/content/drive/.../bg_task_log.txt').read_text(encoding='utf-8')[-1500:])"
  ```

### 4. Verify run
- After `..._BG_DONE` marker appears, `outputs/metrics/<run_id>_metrics.csv` and `outputs/predictions/<run_id>_predictions.jsonl` are populated.
- Final ablation refresh:
  ```
  python tools/exec_remote.py --code-file tools/remote_scripts/38_final_ablation.py
  ```

## How to restore the bridge after it dies

The cloudflared quick-tunnel has no SLA; it can die after hours of uptime.

1. In notebook, re-run cell `7f6bca53`. Capture the new `BRIDGE_URL`.
2. Update `tools/.bridge_url` with the new URL.
3. Verify: `python tools/exec_remote.py --health` returns `{{"ok": true, ...}}`.
4. If kernel was also restarted (different `pid`), re-run the bootstrap script.

## How to restore Drive content (in case of mount-account mix-up)

If `/content/drive/MyDrive/diploma_plan_sql/` shows mostly empty content unexpectedly:

1. Verify by `python tools/exec_remote.py --code "from pathlib import Path; print(sorted(Path('/content/drive/MyDrive/diploma_plan_sql').iterdir()))"`.
2. If the tree is reduced to a few files, the user mounted a different Google account. Re-mount in the Colab UI under the correct account.
3. If the tree is gone for real, re-upload from the local mirror:
   ```
   python tools/exec_remote.py --code-file tools/remote_scripts/32_upload_local_mirror.py --timeout 300
   python tools/exec_remote.py --code-file tools/remote_scripts/31_restore_drive_spider.py --timeout 300
   ```
4. Re-bootstrap kernel.

## How to reproduce a published artefact (e.g., `outputs/tables/final_ablation_summary.md`)

1. Ensure all underlying metrics CSVs exist: `ls outputs/metrics/`.
2. Run `python tools/exec_remote.py --code-file tools/remote_scripts/38_final_ablation.py`.
3. The script reads `outputs/metrics/<prefix>_metrics.csv` for each baseline / subset and re-derives the ablation.

## Failure handling

- **Bridge HTTP 524 (Cloudflare timeout)** → cell may still be running on Colab side; check task log.
- **Kernel disconnect** → re-fire bootstrap. Predictions saved incrementally survive partial runs.
- **OOM during model load** → swap model strategy: free current model with `del model; gc.collect(); torch.cuda.empty_cache()`, then load smaller candidate.
- **HF gated repo (Llama)** → set `HF_TOKEN` in Colab kernel `os.environ["HF_TOKEN"] = "..."` BEFORE loading.
- **SQLite ProgrammingError on subset items** → check `error_message` field in predictions JSONL; usually the model produced syntax-invalid SQL.
- **Plan parse failures spike for B2/B3** → planner over-prompted; reduce knowledge channel verbosity (B3_v1 fix).

## Daily checklist

1. Bridge alive? `python tools/exec_remote.py --health`.
2. Kernel state? `python tools/exec_remote.py --code-file tools/remote_scripts/_check_kernel_state.py`.
3. Drive content sane? `python tools/exec_remote.py --code "from pathlib import Path; r=Path('/content/drive/MyDrive/diploma_plan_sql'); print({{p.name: sum(1 for _ in p.rglob('*') if _.is_file()) for p in r.iterdir() if p.is_dir()}})"`.
4. Local mirror up to date? `Get-ChildItem D:\\HSE\\Диплом\\NL2BI-AI-assistant\\outputs -Recurse | Measure-Object`.
''', encoding='utf-8')

# ============================================================
# 7. installation_and_runtime.md
# ============================================================
(DOCS / 'installation_and_runtime.md').write_text(f'''# Installation and Runtime Profile

Date: {ts}.

## Local (Windows) prerequisites

- Python 3.11+ (`C:\\Users\\<user>\\AppData\\Local\\Programs\\Python\\Python311\\python.exe`).
- VS Code with the Microsoft Jupyter extension.
- Internet access to Cloudflare quick-tunnel domains (`*.trycloudflare.com`).
- Local clone / working tree at `D:\\HSE\\Диплом\\NL2BI-AI-assistant\\`.

Local Python deps: only `urllib`/`json`/`pathlib`/`subprocess` (standard library). No third-party packages required for the agent-side tools.

## Colab runtime

- Recommended GPU: NVIDIA L4 (23 GB VRAM) or T4 (16 GB VRAM, may force smaller batch sizes / single model at a time).
- Recommended runtime: Python 3.12, CUDA 12.x.

Pip dependencies (auto-installed by `30_kernel_bootstrap.py`):
- `torch>=2.10`
- `transformers>=4.45`
- `accelerate>=0.34`
- `bitsandbytes>=0.43.3`
- `sentencepiece`
- `safetensors`
- `func_timeout`
- `jsonschema`
- `gdown` (for Spider re-download)
- `flask` (for bridge cell)

## Model loading

All 7B/8B models are loaded in 4-bit `nf4` via `bitsandbytes`:
- `Qwen/Qwen2.5-Coder-7B-Instruct` — primary, ~5.3 GB VRAM.
- `Qwen/Qwen2.5-7B-Instruct` — comparator, ~5.3 GB VRAM.
- `meta-llama/Llama-3.1-8B-Instruct` — gated; needs `HF_TOKEN`. ~6 GB VRAM.
- `deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct` — 16B MoE, ~12 GB VRAM in 4-bit; tight on L4.

Sequential load only (free previous before loading new):
```python
del model; gc.collect(); torch.cuda.empty_cache()
```

## GPU / RAM profile during inference

- **B0** (single SQL gen): ~5.5 GB VRAM peak per item, ~2-5 sec/item.
- **B1** (single SQL gen): same as B0; small extra string ops.
- **B2 / B2_v1** (planner + SQL gen): two model.generate calls, ~5-10 sec/item.
- **B3** (dual retrieval + planner + SQL): same as B2; CPU-side retrieval is ~milliseconds.
- **B4-lite** (multi-candidate, K=3, sampling): one batched model.generate with `num_return_sequences=3`, ~10-15 sec/item; bounded repair adds one more gen on failure.

## Drive layout (canonical)

```
/content/drive/MyDrive/diploma_plan_sql/
├── data/spider/      # dataset (re-downloadable via 31_restore_drive_spider.py)
│   ├── dev.json
│   ├── tables.json
│   ├── database/<db_id>/<db_id>.sqlite (166 DBs)
│   └── subsets/      # smoke_10, smoke_25, smoke_50, multidb_30
├── outputs/
│   ├── predictions/  # .jsonl per run
│   ├── metrics/      # .csv per run
│   ├── tables/       # comparisons, summaries, error_cases, examples, ablations
│   ├── logs/         # design docs, runlogs, audits, bg task logs, tz coverage
│   ├── plots/        # PNGs
│   ├── docs/         # bundled documentation
│   ├── analytics_handoff/  # analytics payloads
│   └── REPORT.md
├── practice/         # practice-side worklog/checklist/mapping
├── repo/
│   ├── docs/plan_schema*.json
│   └── src/evaluation/baselines*.py + retrieval.py + postprocess.py + query_analysis.py
└── exports/          # tarball backups
```

## Config flags (per script)

Most run scripts accept implicit defaults; high-impact knobs:
- `MODEL_ID` — set in each baseline script; not a CLI flag this iteration.
- `max_new_tokens` — 192 for SQL, 256-320 for planner.
- `temperature`, `top_p` — only B4-lite uses sampling (T=0.7, p=0.95); others greedy.
- `num_return_sequences` — B4-lite K=3.
- `min_score` for schema linker — 0.5 (lexical baseline).
- `top_k_knowledge` — B3 default 3.
- `repair_max` — B4-lite bounded to 1.
- `func_timeout` — SQLite per-query 8 s.
''', encoding='utf-8')

# ============================================================
# Architecture diagrams (matplotlib)
# ============================================================
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

PLOTS = OUTPUTS / 'plots'
PLOTS.mkdir(parents=True, exist_ok=True)


def draw_box(ax, x, y, w, h, text, fc='#E8F0FE', ec='#1F4E79', fontsize=9):
    box = FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.02,rounding_size=0.05',
                         facecolor=fc, edgecolor=ec, linewidth=1.2)
    ax.add_patch(box)
    ax.text(x + w/2, y + h/2, text, ha='center', va='center', fontsize=fontsize, wrap=True)


def draw_arrow(ax, x1, y1, x2, y2, fc='#444'):
    arr = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle='->,head_width=0.15,head_length=0.20',
                          mutation_scale=10, color=fc, linewidth=1.2)
    ax.add_patch(arr)


# Plot 1: system_architecture_overview.png
fig, ax = plt.subplots(figsize=(11, 7))
ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.set_aspect('equal'); ax.axis('off')

# Layer boxes
boxes = [
    (0.5, 8.5, 2.0, 0.7, 'NL question'),
    (3.0, 8.5, 2.2, 0.7, 'Query Analysis\n(query_analysis.py)'),
    (5.7, 8.5, 2.0, 0.7, 'Schema Linker\n(baselines.py)'),
    (8.0, 8.5, 1.8, 0.7, 'Cross-DB\nretrieval'),
    (5.7, 7.2, 2.0, 0.7, 'Knowledge Proxy\n(baselines_b3.py)'),
    (3.0, 5.8, 2.2, 0.7, 'Planner\n(baselines_b2_v1.py)'),
    (5.7, 5.8, 2.0, 0.7, 'Plan Validator\n(jsonschema)'),
    (3.0, 4.4, 2.2, 0.7, 'SQL Synthesizer\n(plan→sql)'),
    (5.7, 4.4, 2.0, 0.7, 'Validation Gate\n(SELECT-only)'),
    (3.0, 3.0, 2.2, 0.7, 'Multi-Cand. + Repair\n(baselines_b4.py)'),
    (5.7, 3.0, 2.0, 0.7, 'Executor\n(SQLite, 8s timeout)'),
    (3.0, 1.6, 2.2, 0.7, 'Postprocess\n(postprocess.py)'),
    (5.7, 1.6, 2.0, 0.7, 'Analytics Handoff\n(JSON+CSV v1)'),
    (8.0, 1.6, 1.8, 0.7, 'BI / reporting\n(downstream)'),
]
for x, y, w, h, t in boxes:
    draw_box(ax, x, y, w, h, t)

# Arrows
arrows = [
    (2.5, 8.85, 3.0, 8.85),
    (5.2, 8.85, 5.7, 8.85),
    (7.7, 8.85, 8.0, 8.85),
    (6.7, 8.5, 6.7, 7.9),
    (5.7, 7.55, 4.1, 6.5),
    (6.7, 7.2, 4.1, 6.5),
    (5.2, 6.15, 5.7, 6.15),
    (4.1, 5.8, 4.1, 5.1),
    (5.2, 4.75, 5.7, 4.75),
    (4.1, 4.4, 4.1, 3.7),
    (5.2, 3.35, 5.7, 3.35),
    (6.7, 3.0, 6.7, 2.3),
    (5.2, 1.95, 5.7, 1.95),
    (7.7, 1.95, 8.0, 1.95),
]
for a in arrows: draw_arrow(ax, *a)

ax.text(5.0, 9.6, 'NL2BI System Architecture (B0 → B4-lite)', ha='center', va='center', fontsize=14, fontweight='bold')
ax.text(0.2, 0.3, f'Generated {ts}', fontsize=7, color='#666')

plt.savefig(PLOTS / 'system_architecture_overview.png', dpi=140, bbox_inches='tight')
plt.close(fig)


# Plot 2: ablation_pipeline_ladder.png
fig, ax = plt.subplots(figsize=(11, 5))
ax.set_xlim(0, 11); ax.set_ylim(0, 5); ax.axis('off')

ladder = [
    (0.3, 'B0', '#4C72B0', 'NL → SQL\n(full schema)'),
    (2.3, 'B1', '#55A868', '+ schema linker\n(reduced schema)'),
    (4.3, 'B2', '#C44E52', '+ planner\n(JSON Plan + validator)'),
    (6.3, 'B3', '#8172B2', '+ dual retrieval\n(schema + knowledge proxy)'),
    (8.3, 'B4-lite', '#CCB974', '+ validation gate\n+ multi-cand + repair'),
    (10.3, '...', '#888888', '(true B4 / fine-tuning\nleft for next iteration)'),
]
for x, name, color, desc in ladder:
    draw_box(ax, x, 2.5, 1.6, 1.2, f'{name}\n{desc}', fc=color, ec='#222', fontsize=8)
    if name != '...':
        next_x = x + 1.6
        if next_x < 10.0:
            draw_arrow(ax, next_x, 3.1, next_x + 0.4, 3.1)

ax.text(5.5, 4.6, 'Baseline Ladder (additive)', ha='center', va='center', fontsize=14, fontweight='bold')
ax.text(0.2, 0.4, f'Each step ADDS a component over the previous; B0 alone reaches EX=1.0 on smoke10 because the data is small,\n'
                 f'but real value of B1/B3 retrieval and B4-lite validation appears on multidb_30+ subsets.', fontsize=8, color='#444')
ax.text(0.2, 0.05, f'Generated {ts}', fontsize=7, color='#888')

plt.savefig(PLOTS / 'ablation_pipeline_ladder.png', dpi=140, bbox_inches='tight')
plt.close(fig)


# ============================================================
# component_registry.csv
# ============================================================
comp_path = OUTPUTS / 'tables' / 'component_registry.csv'
comp_path.parent.mkdir(parents=True, exist_ok=True)
with comp_path.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['layer','component','module_or_artifact','closes_tz_item','status'])
    rows = [
        ('1. NL analysis','Query Analyzer','repo/src/evaluation/query_analysis.py','2.2.1','done'),
        ('2. Source linking','Lexical Schema Linker','repo/src/evaluation/baselines.py','2.2.2','done'),
        ('2b. Cross-DB retrieval','Lexical retrieval','repo/src/evaluation/retrieval.py','2.2.2','done'),
        ('2c. Knowledge channel','Per-table doc proxy','repo/src/evaluation/baselines_b3.py','2.2.2 (extended)','done'),
        ('3. Planner','JSON Plan emitter','repo/src/evaluation/baselines_b2.py + b2_v1.py','2.2.4','done'),
        ('4. Plan validator','jsonschema','repo/docs/plan_schema_v1.json','2.2.4','done'),
        ('5. SQL synthesizer','plan→sql prompt','baselines_b2*.py + baselines_b3.py','2.2.3','done'),
        ('6. Validation gate','SELECT-only AST guard','baselines_b4.py::is_safe_select','2.2.3 (safety)','done'),
        ('7. Multi-candidate + Repair','sampling + consistency','baselines_b4.py','2.2.4','done'),
        ('8. Executor','SQLite + 8s timeout','func_timeout-wrapped execute_sql','2.2.3 (performance)','done'),
        ('9. Postprocess','normalize + summary','postprocess.py','2.2.5','done'),
        ('10. Analytics handoff','v1 JSON+CSV contract','postprocess.py::build_analytics_payload','2.2.6','done'),
        ('11. Bridge tooling','Flask + cloudflared + exec_remote','notebook cell 7f6bca53 + tools/exec_remote.py','infra','done'),
    ]
    for r in rows: w.writerow(r)

print('docs created:', sorted(p.name for p in DOCS.iterdir()))
print('plots created:', [PLOTS / 'system_architecture_overview.png', PLOTS / 'ablation_pipeline_ladder.png'])
print(f'WROTE {comp_path}')
print('STATUS=DONE')
