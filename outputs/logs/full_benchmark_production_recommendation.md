# Production recommendation — Qwen2.5-Coder-7B (full-benchmark evidence)

## TL;DR

- Spider-like queries → **B0 (full schema)**. Replication EX = 72.53% ± Wilson 95% [69.7, 75.2].
- BIRD-like queries (long schema + evidence) → **B3_v4 (hybrid retrieval)**. EX = 29.00% [25.2, 33.1], beating B0 (20.40%) by ~9 pp.
- Avoid the v4 planner — currently produces invalid JSON plans on >99% of BIRD items.

## Decision rule

```
if benchmark_has_domain_evidence and avg_table_count >= 8:
    pipeline = B3_v4_hybrid_retrieval_with_evidence
else:
    pipeline = B0_direct_full_schema
```

## What we did NOT prove

- We have not shown that the planner architecture is unviable in principle.
  We have only shown that **the v4 plan schema is too strict** for the current Qwen prompt template.
- Spider2-Lite results are structural-only; do not quote them as accuracy.
- Numbers are for a single model (Qwen2.5-Coder-7B). Do not generalise to other models without rerun.
