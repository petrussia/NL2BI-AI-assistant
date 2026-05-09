# B3_v1 Design Decision

Date: 2026-04-29T15:05:41.968967+00:00

## Why B3_v1
B3 (knowledge proxy on top of B2_v1) regressed on smoke10: EX dropped to 0.2 with 8/10 plan_invalid. The longer prompt confused the planner more than it helped on tiny `concert_singer` (4 tables).

## What changes in v1
1. **Adaptive knowledge channel**: if `n_tables(db) < 5`, the knowledge channel is OMITTED entirely; the prompt is identical to B2_v1's reduced-schema prompt.
2. **Compact knowledge snippets**: when enabled, top-1 snippet (not top-3), one line per table with name + cols + PK/FK flags. No prose.
3. **Compact planner prompt**: no embedded "Knowledge (synthetic proxy docs derived from schema metadata):" verbose preamble. Just `Schema:` + (optional) `Knowledge:` block.
4. **Same content for synthesizer**: same context object reused; no separate "richer" version this iteration (separating context per stage was deferred — current change already addresses the over-prompt issue).

## Acceptance for B3_v1 smoke10
- plan_valid_count ≥ 9/10 (recover from B3 = 2/10).
- EX ≥ B2_v1's EX (≥ 0.8). Ideally ≥ 0.9.

## Out of v1 scope
- Embedding-based retrieval.
- Cross-DB retrieval (kept in retrieval.py for B1R/B2R baselines).
- Real domain documentation ingestion.
