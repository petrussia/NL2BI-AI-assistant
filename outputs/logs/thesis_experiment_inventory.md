# Thesis Experiment Inventory

Updated 2026-04-25T17:55:21.925124+00:00.

## Baselines implemented
- **B0** — full-schema NL→SQL prompt, Qwen/Qwen2.5-Coder-7B-Instruct, 4-bit `nf4` bitsandbytes, greedy, max_new_tokens=192. SQL extracted by regex; executed via SQLite with 8 s timeout.
- **B1** — same model + decoding, but the schema in the prompt is reduced via *lexical schema linking* (token overlap, table-name x2, column-name x1, English stopwords removed, `min_score=0.5`). Tables with no signal trigger a fallback to the full schema.
- **B2** — same model + decoding, two-stage *Plan→SQL* pipeline. Stage A: planner emits a strict JSON Plan validated against `repo/docs/plan_schema.json` (intent, tables, operations required; columns/filters/aggregations/group_by/order_by/limit/joins optional, `additionalProperties: false`). Stage B: plan + reduced schema → SQL prompt → SQL → execute. Invalid plan is recorded as `error_type=plan_invalid`; no repair / retry yet.

## Subsets evaluated
- `smoke_10` (n=10, all `concert_singer`): B0 + B1 + B2 done.
- `smoke_25` (n=25, all `concert_singer`, smoke10 ⊂ smoke25): B0 + B1 done; B2 not yet.
- `smoke_50` exists on Drive; not evaluated.
- Spider dev (n=1034) not evaluated.

## Metrics
- **EX** — execution-match against gold SQL on SQLite.
- **executable_count** — predicted SQL parses and runs.
- **plan_valid_count (B2)** — JSON plan parsed and validated against `plan_schema.json`.
- **plan_parse_failures (B2)** — JSON could not even be parsed.
- **avg_reduction_ratio (B1, B2)** — mean fraction of full schema kept by the lexical linker.

## Comparisons produced
- B0 vs B1 on smoke10 and smoke25 (CSV/MD/PNG/case_diff).
- Aggregate progression smoke10→smoke25 (CSV/MD/PNG).
- Error taxonomy on smoke25 (8 buckets, per-cell breakdown).
- B0 vs B1 vs B2 on smoke10 (CSV/MD/PNG/case_diff).

## Reproducibility evidence
- Model + GPU + library versions: `outputs/logs/runtime_project_root_audit.md`.
- Spider source provenance: `data/spider/SOURCE_AND_AUDIT.md`.
- Subset audits: `outputs/logs/b0_loader_subsets_audit.md`, `outputs/logs/smoke25_subset_audit.md`.
- Per-run logs: `outputs/logs/{b0,b1,b2}_spider_*_runlog.txt`.
- Bridge tooling state: `outputs/logs/bridge_status_drive.md`, `outputs/logs/artifact_recheck_drive.md`.
- B2 design + plan schema authorship: `outputs/logs/b2_design_decision.md`, `outputs/logs/b2_preflight_drive.md`.
- Tooling audit: `tools/notebook_tooling_audit.md`, `tools/run_cell_changelog.md`, `tools/tool_manifest.md`.

## Limitations to disclose
- Single-DB subsets bound the schema-linking benefit. Multi-DB sample is the next critical experiment.
- 4-bit quantisation; numerical sensitivity not measured.
- Single greedy decoding (no sampling, no self-consistency, no multi-candidate selection).
- B2 has no repair / retry loop; invalid plan ⇒ no SQL ⇒ counts as wrong.
- EX is execution-only; logical-form / partial-credit metrics not computed.
