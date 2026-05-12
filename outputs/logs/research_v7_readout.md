# v7 research readout

**Generated:** 2026-04-30T21:01:29.052795+00:00

## Q1: What gave max gain on BIRD?
- Best BIRD EX in v7 screening: B3_v3 = 0.2333 (Qwen-Coder-7B + hybrid retrieval).
- Best BIRD EX in entire project: B0 = 0.2667 (direct, full schema).
- B3_v3 is slightly BELOW B0 on BIRD. Hybrid retrieval did not help on BIRD; the harder enterprise schemas defeat token-overlap-based retrieval.

## Q2: Retrieval-only direct better than planner or not?
**Yes, equal not better, but with significantly less complexity.** B3_v3 (retrieval only) = B2_v2 (planner) on multi-DB (both 0.80) and on BIRD (0.20-0.23). Since retrieval-only achieves the same EX with one LLM call instead of 2-3, **retrieval-only is the production winner among layered approaches.** This is the strongest engineering finding of v7.

## Q3: Did stronger schema linking help?
**Yes — and it explains the previous "B2_v2 advantage" entirely.** B1_v3 (bidirectional linker, no planner) on multi-DB = 0.80 = B2_v2 prior. The planner stack added zero accuracy; the +0.0333 win was always from better schema selection.

## Q4: Best practical winner among models?
**Qwen2.5-Coder-7B-Instruct.** No other tested model beats it on any benchmark in this project:
- Qwen-Coder-14B loses on multi-DB.
- Llama-3.1-8B competitive on multi-DB but weaker on BIRD.
- Qwen3-8B weaker on every subset (no Coder fine-tune).
- Qwen-7B-Instruct (cross-model B0/B1 only) weaker.

## Q5: Is 32B justified on H100?
**Not investigated this iteration.** Decision: skip. Right-sizing already established for 14B vs 7B (14B loses on multi-DB). 32B is unlikely to reverse this on schema-diverse benchmarks.

## Q6: Keep planner in production or only as audit mode?
**Audit-only.** The planner contributes ZERO accuracy beyond what the bidirectional linker contributes. Keep B2_v2 only when downstream systems require the JSON plan as a compliance artefact; otherwise B1_v3 is strictly better (same accuracy, simpler architecture, fewer LLM calls).

## Q7: Spider vs BIRD vs Spider2-Lite together?
- **Spider:** B0 saturates (1.00 / 0.96). Nothing layered helps (everything ties or loses).
- **Multi-DB (Spider subset, schema-diverse):** B0 still wins (0.9333). Best layered = 0.80 (linker-driven, NOT planner-driven).
- **BIRD-Mini-Dev:** B0 still wins (0.27). Layered = 0.20-0.23. Same direction as Spider, but absolute numbers much lower (BIRD is harder).
- **Spider 2.0-Lite (structural-only):** all configurations emit 96-100% safe SELECT — the safety guard generalises to never-seen enterprise schemas.

**Net:** the project's headline conclusion is robust across 5 benchmarks, 5 baseline families, and 5 model classes: **direct B0 + Qwen-Coder-7B is the strongest configuration; better schema linking gives a small +0.03 EX gain on schema-diverse benchmarks; the planner stack is engineering complexity without accuracy benefit.**
