# Final negative-result analysis (v8)

**Generated:** 2026-04-30T21:01:29.052795+00:00

## v7 added two clean negative results AND one re-attribution

### Negative #1 (PERSISTING): Layered planning never beats direct B0 on Spider with code-aware base model
- B0 multi-DB = 0.9333 (Qwen-Coder-7B)
- Best layered v3 multi-DB = 0.8000 (B1_v3 / B3_v3)
- Gap = 0.13 in favour of direct B0.
- **Generalises to BIRD:** B0 = 0.2667, B3_v3 = 0.2333.

### Negative #2 (NEW v7): Bigger / newer architecture is not enough without Code fine-tune
- Qwen3-8B B0 multi-DB = 0.9000 vs Qwen-Coder-7B B0 = 0.9333
- Qwen3-8B B0 smoke_25 = 0.7600 vs Qwen-Coder-7B B0 = 0.96
- Qwen3-8B B0 BIRD = 0.1333 vs Qwen-Coder-7B B0 = 0.2667
- **Conclusion:** The Qwen3 architecture (newer, more general) does NOT beat Qwen2.5-Coder fine-tune. Coder fine-tune is the real lever.

### POSITIVE re-attribution (NEW v7): The B2_v2 multi-DB win was MISattributed to the planner

Until v7 the project reported B2_v2 + Qwen-Coder-7B = 0.80 multi-DB as "only layered configuration that beats B1". The implicit attribution was: "the planner stack with v2 safety net helps".

The v7 retrieval/linker baselines (B1_v3, B3_v3) achieve the **same** EX = 0.80 on multi-DB **without any planner**:
- No JSON plan generation.
- No jsonschema validation.
- No B1-fallback hierarchy.
- No multi-LLM-call orchestration.
- Just a bidirectional schema linker (table-first AND column-first BM25+ngram, merged with link_confidence).

**The +0.0333 win came from better schema selection.** B2_v2's planner contributed nothing to accuracy; it contributed only audit-trail value at the cost of additional LLM calls.

This is the strongest scientific re-attribution in the project: **complexity ≠ value.** A simpler architecture (B1_v3) achieves the same accuracy as the multi-component planner stack (B2_v2).

## Defense narrative update

Old narrative (v6): "B2_v2 multi-DB = 0.80 beats B1, the only positive layered signal."

New narrative (v8): "B1_v3 = B3_v3 = 0.80 multi-DB. The +0.0333 win is from a deterministic bidirectional schema linker, not from the planner stack. The previously-reported B2_v2 win was actually a schema-linking win in disguise."

This is a stronger, more honest, and more defensible scientific position.
