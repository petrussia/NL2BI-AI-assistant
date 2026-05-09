# B4_final Design Decision

Date: 2026-04-29T15:05:41.968967+00:00

## Why B4_final
B4-lite was correct as a system but inherited B3's planner failures upstream. By moving its base from B3 to B3_v1, the upstream is now (we expect) reliable. Otherwise the design is unchanged from B4-lite.

## What B4_final implements
1. **SELECT-only AST guard** (`is_safe_select`) — same regex-based gate. Forbidden: INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/REPLACE/PRAGMA/ATTACH/DETACH/GRANT/REVOKE.
2. **Multi-candidate generation**: `num_return_sequences=3`, T=0.7, top_p=0.95.
3. **Execution-guided selection**: pick the candidate whose result row-multiset matches the most others (consistency); tie-break first executable.
4. **Bounded repair**: depth=1; if no executable candidate, regenerate ONCE with the SQLite error message appended to the prompt.

## Honest naming
This is still **B4-lite-style**: no true grammar-constrained decoding (XGrammar / Outlines / Guidance). The constrained decoding requirement is *approximated* by the post-hoc safety gate. Documented in `b4_final_validation_policy.md`.

## Acceptance for B4_final smoke10
- plan_valid_count = same as B3_v1 (B4_final does not change the planner).
- EX ≥ B3_v1's EX. Ideally ≥ 0.9.
- Validation gate triggers ≥ 0 times (sanity: should not trigger on benign Spider questions; if it does, something else is wrong).
