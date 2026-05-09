# B2 Implementation Plan (scaffolding)

Updated: 2026-04-25T17:11:23.195349+00:00.
**Scope: minimal.** No retrieval indexes built yet, no repair loop yet, no fine-tuning.
This document defines the minimum viable B2 (Plan -> SQL) so it can be run on smoke10
the moment the user gives the go-ahead. Nothing here gets executed by this script.

## Files to add
| Path on Drive | Purpose |
|---|---|
| `repo/src/evaluation/planner.py` | `make_plan_prompt(question, reduced_schema)`; `parse_plan(raw)` (JSON-fenced extraction + schema validation against `plan_schema.json`); `make_plan_sql_prompt(plan, reduced_schema)`; `extract_sql_from_plan_run(raw)`. |
| `repo/src/evaluation/baselines_b2.py` | `run_b2_on_subset(items, model, tokenizer, tables_map, db_paths)`; reuses `lexical_schema_linking`, `build_reduced_schema_context`, `extract_sql`, `execute_sql` from `baselines.py`. |
| `tools/remote_scripts/10_b2_smoke10_bg.py` | Background-thread inference dispatcher analogous to `04b_smoke25_b0_and_b1_bg.py`, but for B2. |

## Notebook cells to add
1. `B2_SETUP` — imports planner, defines `make_plan_prompt`, `parse_plan`, `make_plan_sql_prompt`. Side-effect-free (no inference). One Shift+Enter at the start of a B2 session.
2. `B2_INFERENCE_SMOKE10` — kicks off `run_b2_on_subset(smoke10, …)` in a background thread (mirrors `04b`). Saves predictions incrementally.
3. `B2_VS_B0_VS_B1_SMOKE10` — three-way comparison after the BG thread finishes. Outputs `outputs/tables/baseline_progression_b0_b1_b2_smoke10.{csv,md}`, `outputs/plots/baseline_progression_b0_b1_b2_smoke10.png`.

## Artifacts B2 must produce (smoke10 first run)
- `outputs/predictions/b2_spider_smoke10_predictions.jsonl` (with extra fields: `plan_raw`, `plan_parsed`, `plan_valid`, `selected_tables`, `schema_reduction_ratio`, `executable`, `execution_match`, `error_type`)
- `outputs/metrics/b2_spider_smoke10_metrics.csv` (with extra columns: `plan_valid_count`, `plan_parse_failures`)
- `outputs/tables/b2_spider_smoke10_summary.csv`
- `outputs/logs/b2_spider_smoke10_runlog.txt`
- `outputs/tables/b2_spider_smoke10_error_cases.md`
- `outputs/tables/b2_spider_smoke10_examples.md`
- Optional: `outputs/tables/b2_plan_examples_smoke10.md` showing 5 question -> plan -> SQL traces.

## Plan schema (already in repo)
The existing `plan_schema.json` defines the JSON Plan contract — reuse it to validate `parse_plan` output before invoking `make_plan_sql_prompt`. If a plan fails validation, record `plan_valid=False` and skip SQL generation (count as `error_type='plan_invalid'`).

## Decoding choices for B2
- Same model: `Qwen/Qwen2.5-Coder-7B-Instruct`, 4-bit `nf4`, greedy.
- `max_new_tokens` for plan: 256.
- `max_new_tokens` for SQL: 192 (same as B0/B1).
- Two sequential generations per question; ~3-4 s total → smoke10 = ~40 s. Comfortably within Cloudflare timeout, but use the bridge-bg pattern anyway for parity with B1 smoke25.

## Acceptance for "B2 first run done"
- Predictions JSONL has 10 rows with all expected fields populated.
- Metrics CSV has `ex` and `plan_valid_count`.
- Three-way progression CSV/PNG produced.
- `outputs/logs/b2_first_run_notes.md` written with observations.

## Out of scope for first B2 run
- Schema retrieval across DBs (future).
- Repair / retry loop (future).
- Multi-candidate execution-guided selection (future).
- Fine-tuning (out of scope altogether).
