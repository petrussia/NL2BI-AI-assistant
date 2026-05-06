# Spider2-DBT metrics contract

_Single source of truth for the JSONL fields every variant run must
produce. Phase 0 freezes this; later variants can ADD fields but must
NEVER rename or remove existing ones._

## Per-(task, variant) row schema (`per_task.jsonl` and `result.json`)

### Identity & versioning

| Field | Type | Notes |
|---|---|---|
| `instance_id` | str | from `spider2-dbt.jsonl` |
| `variant` | str | one of `v0_floor`, `v1`, ..., `v10`, `v3_react` |
| `run_id` | str | timestamped, unique per variant run |
| `commit_hash` | str | `git rev-parse HEAD` at run time |
| `model_id` | str | e.g. `Qwen/Qwen2.5-Coder-7B-Instruct` |
| `model_dtype` | str | e.g. `bfloat16` |
| `prompt_template_hash` | str | sha1 of the templated prompt (NOT including the question) |
| `seed` | int | inference seed; `do_sample=False` so deterministic |
| `utc` | str | ISO8601 of run start |

### Stage status

| Field | Type | Notes |
|---|---|---|
| `status` | str | `done` / `inference_failed` / `apply_failed` / `eval_failed` / `skipped_taxonomy` |
| `apply_kind` | str | `sql_file` / `diff` / `fallback_sql` / `none` / `refused_no_target` |
| `pushed_files` | list[str] | files we wrote to the workspace |
| `dbt_apply_rc` | int? | rc of `git apply` / `patch` if diff |
| `dbt_deps_rc` | int? | rc of `dbt deps` |
| `dbt_run_rc` | int? | rc of `dbt run` |
| `dbt_test_rc` | int? | rc of `dbt test` |
| `dbt_test_pass_n` | int | parsed from log "PASS=N" |
| `dbt_test_err_n` | int | parsed from log "ERROR=N" |
| `dbt_test_warn_n` | int | parsed from log "WARN=N" |
| `dbt_test_skip_n` | int | parsed from log |

### Official evaluator

| Field | Type | Notes |
|---|---|---|
| `evaluator_artifact_exists` | bool | did we produce the file the gold spec points at? |
| `evaluator_rc` | int | `evaluate.py` exit code |
| `evaluator_score_rate` | float? | `0.0` or `1.0` for binary tasks |
| `evaluator_score_matched` | int | numerator |
| `evaluator_score_total` | int | denominator (usually 1) |
| `evaluator_stdout_tail` | str | last 1500 chars |

### Patch / change shape

| Field | Type | Notes |
|---|---|---|
| `target_file_existed_in_upstream` | bool | upstream had this file |
| `created_new_file` | bool | apply created a new file |
| `touched_schema_yml` | bool | any `*.yml` changed |
| `touched_macros` | bool | any `macros/*.sql` changed |
| `touched_dbt_project_yml` | bool | top-level config changed |
| `patch_size_added_lines` | int | ≈ number of `+` lines |
| `patch_size_removed_lines` | int | `-` lines |
| `patch_size_total` | int | added + removed |

### Action / planner

| Field | Type | Notes |
|---|---|---|
| `planner_invoked` | bool | did we call the planner LLM? |
| `planner_action_type` | str | one of {`patch_existing_model`, `fill_stub_model`, `create_new_model`, `fix_ref_or_source`, `edit_schema_yml`, `unsupported`} |
| `planner_target_file` | str? | what planner named |
| `planner_expected_columns_n` | int? | planner's contract |
| `planner_expected_grain` | str? | planner's contract |
| `planner_target_match` | bool | did our applied edit touch planner's named file? |
| `planner_parse_ok` | bool | planner JSON parsed cleanly |

### Repair

| Field | Type | Notes |
|---|---|---|
| `repair_used` | bool | any repair round triggered |
| `repair_rounds` | int | 0 / 1 / 2 |
| `repair_helpful` | bool | repair brought `dbt_run_rc` from non-0 to 0 |
| `repair_harmful` | bool | repair turned 0 into non-0 |
| `repair_buckets` | list[str] | error buckets seen across rounds |

### Candidate pool / judge (Phase 6+)

| Field | Type | Notes |
|---|---|---|
| `candidate_count` | int | how many candidates generated |
| `candidate_action_types` | list[str] | per-candidate action_type from planner |
| `selected_candidate_idx` | int | index of chosen candidate |
| `selected_via` | str | `hard_filter` / `soft_score` / `judge` |
| `judge_invoked` | bool | LLM judge called |
| `judge_overrode_top_score` | bool | judge picked non-top-soft-score candidate |
| `judge_confidence` | float? | from judge's JSON output |

### Cost / latency

| Field | Type | Notes |
|---|---|---|
| `wall_time_s` | float | end-to-end per task |
| `inference_time_s` | float | LLM only |
| `dbt_time_s` | float | dbt deps + run + test |
| `eval_time_s` | float | evaluator wrapper |
| `prompt_chars` | int | length of inference prompt |
| `response_chars` | int | length of model response |
| `tokens_generated_estimate` | int? | if exposed by inference |

### Error taxonomy

| Field | Type | Notes |
|---|---|---|
| `error_bucket` | str | one of: `none`, `compile_missing_ref`, `compile_missing_source`, `compile_missing_column`, `compile_syntax`, `compile_macro`, `compile_package`, `run_type_mismatch`, `run_relation_missing`, `run_dependency_order`, `test_data_quality`, `test_schema`, `test_upstream_pre_existing`, `eval_artifact_missing`, `eval_columns_mismatch`, `eval_rows_mismatch`, `eval_grain_mismatch`, `eval_ordering_mismatch`, `apply_failed_traversal`, `apply_failed_target_missing`, `unclear` |
| `error_message_short` | str | first 240 chars from logs/eval |

### Floor markers (Phase 0 produces)

| Field | Type | Notes |
|---|---|---|
| `floor_marker` | str? | `upstream_already_produces_gold` / `upstream_broken` / `null` |
| `taxonomy_primary` | str | from `task_taxonomy.csv` |
| `taxonomy_secondary` | list[str] | optional |

## Run-level manifest schema (`manifest.json`)

```json
{
  "variant": "v6",
  "run_id": "ablation_<ts>",
  "commit_hash": "<sha>",
  "config": {
    "max_new_tokens": 1500,
    "do_sample": false,
    "temperature": 0.0,
    "max_repair_rounds": 2,
    "max_candidates": 4,
    "judge_enabled": false,
    "char_budget": 14000,
    "planner_enabled": true,
    "graph_retrieval_enabled": false
  },
  "task_set": "dev_20",
  "n_tasks": 20,
  "started_utc": "...",
  "ended_utc": "...",
  "wall_time_s": 1234,
  "model_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
  "bridge_url_marker": "<short hash, NOT the URL>",
  "ssh_host_marker": "denis@<short>",
  "secrets_check": "passed"
}
```

## Aggregate-level summary schema (`summary.csv`)

Columns:
```
instance_id, variant, taxonomy_primary, floor_marker,
status, apply_kind,
dbt_run_rc, dbt_test_pass_n, dbt_test_err_n,
evaluator_score_matched, evaluator_score_total,
patch_size_total, target_file_existed_in_upstream, created_new_file,
planner_action_type, planner_target_match,
repair_used, repair_rounds, repair_helpful,
candidate_count, selected_via,
error_bucket, wall_time_s
```

This is the file that paired-statistics scripts ingest.

## Paired-comparison output schema (`paired_<a>_vs_<b>.csv`)

Columns:
```
instance_id, taxonomy_primary, floor_marker,
score_a, score_b,
run_rc_a, run_rc_b,
discordance, helpful_b, harmful_b,
notes
```

Where `discordance` ∈ {`tied_match`, `helpful_for_b`, `harmful_for_b`, `tied_miss`}.

## Compatibility rule

Variants `v_n` and `v_{n+1}` MUST produce the same set of fields. New fields can be added in `v_{n+1}` only if all `v_n` rows fill them with `null` or default. Renames require version bump on the contract itself (`metrics_contract_v2.md`).

## Self-check on commit

Before committing a new variant's outputs, run:

```bash
python tools/check_metrics_contract.py outputs/dbt_<variant>/<run_id>/per_task.jsonl
```

(to be implemented in Phase 0 — single script that loads the JSONL,
verifies every required field is present, and reports any extra
fields). Refuse to commit if check fails.
