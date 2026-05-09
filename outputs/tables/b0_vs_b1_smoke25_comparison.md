# B0 vs B1 Comparison (Spider smoke25)

Checked at: 2026-04-25T17:10:59.387104+00:00
Subset: spider/smoke_25 (n=25)
Model: Qwen/Qwen2.5-Coder-7B-Instruct (4-bit nf4 bitsandbytes), greedy decode
B1 schema strategy: lexical schema linking (token overlap, stopwords removed, min_score=0.5)

| Metric | B0 (full schema) | B1 (reduced schema) |
|---|---|---|
| EX | 0.9600 | 0.9600 |
| executable count | 25 / 25 | 25 / 25 |

| Transitions B0 -> B1 | count |
|---|---|
| Improvements (B0 wrong, B1 right) | 0 |
| Regressions (B0 right, B1 wrong) | 0 |
| Unchanged (same EX outcome) | 25 |

Winner on smoke25: **tie**
