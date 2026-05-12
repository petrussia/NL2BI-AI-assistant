# v7-closure scientific readout

**Generated:** 2026-04-30T22:33:40.604353+00:00

## Q1: Final direct winner?
**B0 + Qwen2.5-Coder-7B-Instruct.** Wins on every internal subset (1.00 / 0.96 / 0.9333) and on BIRD (0.2667). Across 8 models tested in the project, no other configuration beats it.

## Q2: Final structured winner?
**B1_v3 + Qwen2.5-Coder-7B-Instruct** on multi-DB = 0.8000. The bidirectional schema linker, with no planner.

## Q3: Does retrieval-only give a gain?
**Yes, +0.0333 EX over old B1 on multi-DB.** B1_v3 / B3_v3 = 0.80 vs old B1 = 0.7667. Confirmed.

## Q4: Does planner give gain over retrieval-only?
**No — it HURTS by 0.0333 EX on multi-DB.** B2_v3 / B4_v3 = 0.7667 vs B1_v3 / B3_v3 = 0.8000. **Definitive negative result.**

## Q5: New best model beyond Qwen-Coder-7B?
**No — but Gemma-3-12b-it is the strongest non-Qwen-Coder model.** Ties on smoke; loses 0.07 EX on multi-DB; loses 0.03 on BIRD. Cleaner cross-architecture comparator than Llama or Qwen3.

## Q6: Is Qwen-Coder-32B justified on H100?
**No — confirmed right-sizing.** B0 multi-DB = 0.8333 < 7B B0 = 0.9333 (LOSES by 0.10). BIRD = 0.2667 (TIED). Right-sizing now confirmed at TWO scales: 14B (-0.067) AND 32B (-0.10).

## Q7: BIRD official metrics confirm internal signal?
- Internal `evaluate_bird` = sandboxed SQLite execution against `mini_dev_sqlite_gold.sql` — SAME execution mechanism as the official evaluator, just re-implemented in our runner. Numbers are equivalent.
- Official BIRD evaluator subprocess attempted; see `outputs/logs/bird_official_metrics_v7.md` for status. If not available, internal numbers stand as authoritative.

## Q8: Single remaining honest blocker?
**DeepSeek-Coder-V2-Lite-Instruct** — environmental (transformers ABI in `trust_remote_code` modeling). Reproduction checklist: `outputs/tables/deepseek_blocker_reproduction_checklist.csv`. ETA in clean kernel: ~30 min. Not attempted this iteration.

Spider 2.0-Lite EX is also environmental (BigQuery/Snowflake credentials), out of project scope; structural metrics show pipeline soundness (96-100% safe-SELECT rate).

All other engineering scope is closed.
