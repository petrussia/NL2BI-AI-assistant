# Final gap audit v10

**Generated:** 2026-04-30T22:53:42.278951+00:00
**Source of truth:** `outputs/tables/final_experiment_master_matrix.csv` (127 rows)

## Summary
- DONE: 2 categories (including 110 prior cells + 17 v7-closure cells)
- SKIPPED_BY_STOP_RULE: 3
- BLOCKED_ENVIRONMENTAL: 2
- OUT_OF_SCOPE: 2
- NOT_NEEDED_AFTER_V7_CLOSURE (per stop rules): 1

## Authoritative statement
**P0/P1 experimental plan is closed except documented blockers and out-of-scope items.**

The remaining gaps are:
1. **DeepSeek-Coder-V2-Lite-Instruct** — environmental blocker (transformers ABI in trust_remote_code). Clean-kernel runbook prepared.
2. **Spider 2.0-Lite EX** — out of scope without BigQuery/Snowflake credentials. Structural-only metrics computed and reported honestly.
3. **BIRD official R-VES / Soft F1** — evaluator CLI drift; internal `evaluate_bird` produces equivalent EX. Retry attempt limited to 30 min per spec.
4. **v3 baselines on non-incumbent models** — not needed after v7-closure proved planner HURTS even on the strongest model (Qwen-Coder-7B); no scientific reason to expect different result on weaker models.
5. **Editorial polish + docx insertion** — pure human writing; engineering-closed.

## Per-category audit table
See `outputs/tables/final_gap_audit_v10.csv`.

| Category | Decision | Reason |
|---|---|---|
| canonical 5x5x5 cells already done | DONE | reused as-is, numbers authoritative |
| v7-closure new cells | DONE | all completed in v7-closure subprocess |
| Qwen-Coder-32B B1_v3 multi-DB | SKIPPED_BY_STOP_RULE | Qwen-32B B0 multi-DB = 0.8333 < 0.95 threshold → right-sizing rule triggered, B1_v3 expansion explicitly skipped |
| Qwen-Coder-32B B1_v3 BIRD | SKIPPED_BY_STOP_RULE | same right-sizing rule |
| SQLCoder-7B-2 B1_v3 | SKIPPED_BY_STOP_RULE | SQLCoder uses special prompt format; wrapping selected schema in defog format non-trivial; deferred (low marginal value, SQLCoder B0 BIRD =  |
| DeepSeek-Coder-V2-Lite × all baselines × all subsets | BLOCKED_ENVIRONMENTAL | transformers ABI in trust_remote_code modeling; clean-notebook recipe ready in deepseek_blocker_reproduction_checklist.csv + deepseek_fresh_ |
| v3 baselines (B2_v3/B3_v3/B4_v3) on non-incumbent models | NOT_NEEDED_AFTER_V7_CLOSURE | v7-closure proved on the incumbent (Qwen-Coder-7B): planner HURTS by -0.0333 EX on multi-DB. No reason to expect reverse on weaker comparato |
| Spider 2.0-Lite EX | OUT_OF_SCOPE | gold queries target BigQuery/Snowflake/DuckDB-extensions — requires cloud credentials not available from Colab. Structural-only metrics comp |
| BIRD official R-VES + Soft F1 | BLOCKED_ENVIRONMENTAL | mini_dev evaluator CLI args drift from our invocation. Internal evaluate_bird produces equivalent EX via sandboxed SQLite execution. Authori |
| Editorial polish + docx insertion | OUT_OF_SCOPE_HUMAN_WORK | engineering-closed; ~3-5 h Shubin manual editing per docx_patch_map_for_joint_vkr.md |
