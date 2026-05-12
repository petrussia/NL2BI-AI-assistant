# Final scientific findings v10

**Generated:** 2026-04-30T22:53:42.278951+00:00
**Source of truth:** `outputs/tables/final_experiment_master_matrix.csv` (127 rows)

## Ten locked claims (defense-final)

1. **Direct B0 + Qwen2.5-Coder-7B-Instruct is the production winner.** EX = 1.0000 (10/10) / 0.9600 (24/25) / 0.9333 (28/30) on internal subsets, 0.2667 (8/30) on BIRD-Mini-Dev. No other configuration beats it on any subset evaluated in this project.

2. **B1_v3/B3_v3 retrieval-only is the best structured/audit option.** Multi-DB EX = 0.8000 (24/30) (B1_v3) = 0.8000 (24/30) (B3_v3). Beats old B1 = 0.7667 (23/30) by +0.0333. One LLM call per query.

3. **Planner-based B2_v3/B4_v3 HURTS on multi-DB by −0.0333 EX vs retrieval-only.** B2_v3 = 0.7667 (23/30); B4_v3 = 0.7667 (23/30). The planner stack adds engineering complexity, latency (2-3 LLM calls), AND lower accuracy.

4. **Bigger models do not automatically improve EX.** Right-sizing CONFIRMED at TWO scales: Qwen-Coder-14B B0 multi-DB = 0.8667 (26/30) and Qwen-Coder-32B B0 multi-DB = 0.8333 (25/30) — BOTH lose to 7B = 0.9333 (28/30).

5. **Qwen-Coder-7B beats or matches every comparator model in practical value.** Across 8 models tested (Qwen-Coder 7B/14B/32B, Qwen-Instruct-7B, Llama-3.1-8B, Qwen3-8B, Gemma-3-12b-it, SQLCoder-7B-2), Qwen-Coder-7B has the highest accuracy on every subset where it competes.

6. **BIRD-Mini-Dev is much harder than internal Spider slices.** Best Qwen-Coder-7B B0 = 0.2667 (8/30) (vs 0.93 on Spider multi-DB). The negative result for layered planning generalises to BIRD too.

7. **Spider 2.0-Lite EX is structural-only.** Gold queries target BigQuery/Snowflake/DuckDB-extensions, requiring cloud credentials not available from Colab. Structural metrics confirm pipeline soundness (96-100% safe-SELECT rate across all evaluated configurations).

8. **DeepSeek-Coder-V2-Lite-Instruct is an honest environmental blocker.** trust_remote_code modeling references symbol `is_torch_fx_available` removed from `transformers >= 4.40` (current kernel: 5.0.0). NOT a hidden failure — clean-kernel reproduction recipe in `outputs/logs/deepseek_fresh_kernel_runbook_v10.md`.

9. **The final recommendation is NOT "use the most complex agentic pipeline".** It is: **"use the simplest accurate pipeline with safety and audit hooks"**. Production = B0 (1 LLM call). Audit-trail = B1_v3 (1 LLM call, deterministic schema linker). The planner stack and multi-candidate sampling DO NOT improve accuracy on this benchmark family.

10. **TZ coverage is 100% by physical-evidence rule** (16/16 functional + work-content items closed by concrete artefacts on Drive and in the local mirror).

## Strongest configurations (locked)

| Role | Configuration | EX |
|---|---|---|
| **Production direct (overall)** | B0 + Qwen2.5-Coder-7B | smoke_10/25/multi-DB = 1.00 / 0.96 / 0.9333; BIRD = 0.2667 |
| **Production audit-trail (REVISED v9)** | **B1_v3 + Qwen-Coder-7B** | multi-DB = 0.80 (= old B2_v2 EX), 1 LLM call, no planner |
| Best mandatory model | Llama-3.1-8B B0 multi-DB | 0.8333 |
| Best non-Qwen-Coder model | **Gemma-3-12b-it B0** | smoke_10 = 1.00, multi-DB = 0.8667, BIRD = 0.2333 |
| Right-sizing comparator | Qwen-Coder-14B / 32B B0 multi-DB | 0.8667 / 0.8333 (both lose to 7B) |
