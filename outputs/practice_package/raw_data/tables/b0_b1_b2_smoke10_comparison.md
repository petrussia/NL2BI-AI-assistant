# B0 vs B1 vs B2 Comparison (Spider smoke10)

Checked at: 2026-04-25T17:55:13.622968+00:00
Subset: spider/smoke_10 (n=10)
Model: Qwen/Qwen2.5-Coder-7B-Instruct (4-bit nf4 bitsandbytes), greedy decode

| Metric | B0 (full schema) | B1 (reduced schema) | B2 (Plan->SQL) |
|---|---|---|---|
| EX | 1.0000 | 1.0000 | 0.7000 |
| executable_count | 10 / 10 | 10 / 10 | 9 / 10 |
| avg_reduction_ratio | — | 0.4750 | 0.4750 |
| plan_valid_count | — | — | 9 / 10 |
| plan_parse_failures | — | — | 0 / 10 |

Winner on smoke10: **tie (B0 = B1)**

## Notes
- B2 schema strategy: lexical schema linking (reused from B1) + planner producing JSON Plan validated against `repo/docs/plan_schema.json` + plan->SQL prompt.
- B2 schema reduction ratio reuses the same lexical linker as B1 — they should match closely on the same questions.
- B2 EX upper bound is `plan_valid_count / n` (questions whose plan failed validation are recorded as `error_type=plan_invalid` and skip SQL generation).
