# B4_final Validation Policy

Date: 2026-04-29T15:05:41.968967+00:00

## SELECT-only guard
Implemented as `is_safe_select` in `baselines_b4_final.py`. Forbidden keywords (case-insensitive, word-boundary):
INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, REPLACE, PRAGMA, ATTACH, DETACH, GRANT, REVOKE.

A candidate must:
- Be non-empty after stripping whitespace and trailing semicolon.
- NOT contain any forbidden keyword as a word.
- Start with `SELECT` (optionally preceded by `WITH ... AS (...)` CTE block).

If a candidate fails, it is dropped from the pool.

## Repair policy
Triggered only when zero candidates execute successfully. One retry per item (bounded). The retry prompt embeds the previous SQL and SQLite error (truncated to 300 chars). The retry candidate is also subject to the safety gate and execution check.

## Selection policy
Group executable candidates by their result (sorted row tuple). Pick the SQL whose result group is largest (consistency). Tie-break: first executable candidate in original generation order.

## Out of policy scope (deferred to next iterations)
- True grammar-constrained decoding via XGrammar/Outlines/Guidance.
- Cost-based query planning checks (no EXPLAIN cost analysis).
- Schema-aware AST validation (rejection of unknown tables/columns by AST).
- Query rewriting beyond regex-based replacement.
