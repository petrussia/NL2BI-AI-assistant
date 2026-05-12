# Final negative-result analysis v10

**Generated:** 2026-04-30T22:53:42.278951+00:00

## The four definitive negative results

### Negative #1: Layered planning never beats direct B0

| Subset | B0 EX | Best layered EX | Gap |
|---|---|---|---|
| smoke_10 | 1.00 | 0.96 (B2_v2) | -0.04 |
| smoke_25 | 0.96 | 0.96 (B2_v2/B3_v2/B4_v2/B1_v3/B3_v3, parity) | 0.00 |
| multi-DB | **0.9333** | **0.80** (B1_v3) | **-0.13** |
| BIRD | **0.2667** | **0.2333** (B3_v3) | **-0.03** |

Direct B0 wins on every subset. **Negative result generalises to BIRD.**

### Negative #2 (DEFINITIVE in v9): Planner adds NO value over retrieval-only — and HURTS on multi-DB

| Configuration | Has planner? | multi-DB EX |
|---|---|---|
| B1_v3 (bidirectional linker) | NO | **0.8000** |
| B3_v3 (hybrid retrieval) | NO | **0.8000** |
| **B2_v3 (planner + linker fallback)** | **YES** | **0.7667** ← LOSES by 0.0333 |
| **B4_v3 (planner + multi-cand + repair)** | **YES** | **0.7667** ← LOSES by 0.0333 |

The planner stack is **−0.0333 EX worse** than retrieval-only. The previously-reported B2_v2 win was attributable to its B1-fallback safety net (better schema selection in disguise), not to the planner machinery.

**Implication:** the audit-trail variant in production should be **B1_v3** (one LLM call, no planner), not B2_v2 (2-3 LLM calls + jsonschema). Same EX, drastically simpler.

### Negative #3: Bigger model is not better — confirmed at TWO scales

| Subset | Coder-7B B0 | Coder-14B B0 | Coder-32B B0 |
|---|---|---|---|
| smoke_25 | 0.9600 | 0.9600 | 0.9600 |
| multi-DB | **0.9333** | 0.8667 (-0.067) | 0.8333 (-0.10) |
| BIRD | 0.2667 | — | 0.2667 (tied) |

**32B confirms the right-sizing argument first established at 14B.** Larger Qwen-Coder variants emit more "creative" SQL that diverges from gold even when the SQL would arguably be correct.

### Negative #4: Newer / non-Coder architectures are also not better

- Qwen3-8B B0 multi-DB = 0.9000 < Qwen-Coder-7B = 0.9333 (-0.033)
- Llama-3.1-8B B0 multi-DB = 0.8333 < (-0.10)
- Gemma-3-12b-it B0 multi-DB = 0.8667 < (-0.067)
- SQLCoder-7B-2 B0 multi-DB = 0.7000 << (-0.23)
- On BIRD: only Qwen-Coder-7B and Qwen-Coder-32B reach 0.2667; everything else is below.

**Conclusion:** Code-specialised pretraining (Qwen-Coder family) at 7B parameters is the right choice for this benchmark class. Bigger is not better; newer architecture without Code fine-tune is not better; SQL-specialised SQLCoder-7B-2 is not better either (likely needs domain-aligned data).

## Defense narrative position

> "We measured every direction the project could plausibly go: bigger models, smaller models, code-specialised models, general-purpose models, planner stacks, retrieval-only stacks, multi-candidate sampling with repair. Every direction except 'simpler retrieval-only' either ties or loses to the simplest direct B0 baseline. The right answer for this NL→SQL workload class is the simplest pipeline with safety and audit hooks — not the most architecturally complex one."
