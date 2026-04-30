# B4 (B4-lite) Design Decision

Date: 2026-04-29T14:33:22.366176+00:00

## Scope of "minimal viable full system"
Per ТЗ, B4 should close: validation + safety/SELECT-only constraints + bounded repair
+ multi-candidate generation + execution-guided selection + (ideally) constrained decoding.

## What this iteration implements (B4-lite)
1. **SELECT-only guard** (full): regex AST gate rejects SQL containing INSERT, UPDATE,
   DELETE, DROP, CREATE, ALTER, TRUNCATE, REPLACE, PRAGMA, ATTACH, DETACH, GRANT, REVOKE.
   Implemented in `is_safe_select`. Real test: blocks anything that mutates state.
2. **Bounded repair loop** (full, depth=1): if no candidate executes successfully,
   the agent regenerates ONCE with the error message appended to the prompt.
3. **Multi-candidate generation** (3 candidates): `model.generate` with
   `num_return_sequences=3`, temperature=0.7, top_p=0.95. Single forward batch.
4. **Execution-guided selection**: candidates are executed; selection picks the SQL
   whose result row-multiset agrees with the most other candidates (consistency).
   Tie-break: first executable. If none executable, repair once.
5. **Constrained decoding** (approximated): NOT true grammar-constrained generation
   (XGrammar / Outlines / Guidance is omitted in this iteration to keep scope honest).
   We approximate with the regex/AST guard (see #1). Item is documented in
   `outputs/logs/b4_validation_policy.md`.

## Why B4-lite, not full B4
- True grammar-constrained decoding requires patching the model's logits at
  generation time. The runtime stack (Qwen 4-bit + bitsandbytes) interacts
  awkwardly with grammar libraries; integration cost is non-trivial.
- The regex/AST guard catches the actually dangerous outputs (state mutation),
  which is the production-relevant subset of constrained decoding.
- Multi-candidate + consistency selection achieves much of what XGrammar
  buys at evaluation time: it filters out malformed SQL by execution, not by grammar.

This is an honest deviation from the proposal and is documented as such.

## Acceptance for B4-lite smoke10
- B4 plan_valid_count ≥ 9/10 (do not regress).
- B4 EX ≥ B2_v1 EX (0.8) on smoke10.
- Zero unsafe SQL pass through (≥1 candidate must clear SELECT-only guard per item or repair triggers).
