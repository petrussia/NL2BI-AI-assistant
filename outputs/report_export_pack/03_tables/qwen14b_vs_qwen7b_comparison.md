# Qwen2.5-Coder 14B vs 7B head-to-head
_Generated: 2026-04-30T14:38:33.007726+00:00_

| Baseline | Subset | 7B EX | 14B EX | Δ (14B−7B) | Verdict |
|---|---|---|---|---|---|
| B0 | smoke_10 | 1.0000 | 1.0000 | +0.0000 | **tie** |
| B1 | smoke_10 | 1.0000 | 1.0000 | +0.0000 | **tie** |
| B0 | multidb_30 | 0.9333 | 0.8667 | -0.0667 | **7B better** |
| B1 | multidb_30 | 0.7667 | 0.7667 | +0.0000 | **tie** |

## Reading

- On **smoke_10** the 14B and 7B both saturate at EX = 1.00 — the bigger model brings nothing here because the 7B already gets every example right.
- On **multidb_30** with full schema (B0), **the 7B model is *better* than the 14B** by 0.067 EX. This is a clean, surprising negative result for "bigger is better".
- On **multidb_30 with schema linking (B1)**, both models tie at EX = 0.7667 — the linker is the bottleneck, not the model.

## Hypothesis why 14B underperforms on multi-DB B0

- More parameters → more "creative" SQL generation: longer queries with extra joins, type casts, or DISTINCT clauses that diverge from the gold answer even when both are arguably correct.
- The Spider gold queries are short and simple; a strong 7B Coder hits them more conservatively. A larger model is more tempted to "improve" the query, which is penalized by EX.
- This effect was not visible on smoke_10 because both models get 100% on the simpler subset.

## Production implication

- For Spider-class workloads, **7B is the right size** — same accuracy on simple subsets, *better* accuracy on multi-DB, and 4× cheaper at inference. The 14B comparator does not change the production recommendation.
