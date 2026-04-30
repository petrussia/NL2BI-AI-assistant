# B4 Validation Policy

Date: 2026-04-29T14:33:22.366176+00:00

## SELECT-only guard
Implemented as a regex AST gate (`is_safe_select` in `baselines_b4.py`).
Forbidden keywords (case-insensitive, word-boundary):
- INSERT, UPDATE, DELETE
- DROP, CREATE, ALTER, TRUNCATE, REPLACE
- PRAGMA, ATTACH, DETACH, GRANT, REVOKE

A candidate SQL must:
- Be non-empty after stripping whitespace and trailing semicolon.
- NOT contain any forbidden keyword as a word.
- Start with `SELECT` (optionally preceded by a CTE `WITH ... AS (...)` block).

If a candidate fails, it is dropped from the candidate pool. If no candidate
clears the guard, repair is invoked once.

## Repair policy
- Triggered only when zero candidates execute successfully.
- One retry per item (bounded to 1).
- The retry prompt includes the previous SQL and the SQLite error message
  (truncated to 300 chars).
- The retry candidate is also subject to the SELECT-only guard and execution check.
- If retry also fails, the item is recorded as `error_type=no_executable_candidate`.

## Selection policy
- Group executable candidates by their result (sorted row tuple).
- Pick the SQL whose result-group is largest (consistency).
- Tie-break: first candidate in original generation order.
- This favours answers that multiple decodings agree on, which is a cheap
  proxy for self-consistency.

## What this policy does NOT do (deferred)
- True grammar-constrained decoding (XGrammar/Outlines/Guidance) — approximated by post-hoc guard.
- Cost-based query planning checks (no EXPLAIN cost analysis).
- Schema-aware AST validation (no rejection of unknown tables/columns by AST).
- Differential testing vs gold (production gate would, evaluator does).
