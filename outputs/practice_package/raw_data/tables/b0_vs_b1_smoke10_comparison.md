# B0 vs B1 Comparison (Spider smoke10)

Checked at: 2026-04-25T15:46:39.430264+00:00
Subset: spider/smoke_10 (n=10)
Model: Qwen/Qwen2.5-Coder-7B-Instruct (4-bit nf4 bitsandbytes), greedy decode
B1 schema strategy: lexical schema linking (token overlap, stopwords removed, min_score=0.5)

| Metric | B0 (full schema) | B1 (reduced schema) |
|---|---|---|
| EX | 1.0000 | 1.0000 |
| executable count | 10 / 10 | 10 / 10 |

| Transitions B0 -> B1 | count |
|---|---|
| Improvements (B0 wrong, B1 right) | 0 |
| Regressions (B0 right, B1 wrong) | 0 |
| Unchanged (same EX outcome) | 10 |

Winner on smoke10: **tie**
