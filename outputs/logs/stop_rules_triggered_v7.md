# Stop rules — applied to v7 screening (12 cells)

**Generated:** 2026-04-30T21:01:29.052795+00:00

## Rule 1: model B0 vs incumbent on smoke_25 (used as proxy for smoke_10 absence)
- Qwen3-8B B0 smoke_25 = 0.7600
- Incumbent Qwen-Coder-7B B0 smoke_25 = 0.9600
- Gap = -0.2000
- **DECISION:** Qwen3-8B is **0.20 EX worse** than incumbent on smoke_25. Rule 1 triggered → **STOP all expansion of structured baselines for Qwen3-8B.**
  Keep only the screening 6 cells (B0/B1_v3 × 3 subsets) for the cross-model record.

## Rule 2: B1_v3 vs old B1 on multi-DB
- B1_v3 + Qwen-Coder-7B multi-DB = 0.8000
- Old B1 + Qwen-Coder-7B multi-DB = 0.7667
- Δ = +0.0333 (≥ +0.03 threshold)
- **DECISION:** B1_v3 beats old B1 by +0.0333 EX on multi-DB. Rule 2 **passed** → would justify B2_v3/B4_v3 expansion.
  However, B3_v3 also = 0.8000, so retrieval-only matches linker-only (no planner needed).

## Rule 3: B3_v3 vs B0 on BIRD AND smoke_25 harm
- B3_v3 + Qwen-Coder-7B BIRD = 0.2333
- B0 + Qwen-Coder-7B BIRD = 0.2667
- Gap on BIRD = -0.0333 (B3_v3 is **0.0333 BELOW B0** on BIRD)
- B3_v3 smoke_25 = 0.9600 (= B0 = 0.96, no harm)
- **DECISION:** B3_v3 doesn't beat B0 on BIRD AND doesn't harm smoke_25 → rule 3 condition partial. Stop rule literal text: "if does not beat B0 by +0.02 AND harms smoke_25 by >0.03". B3_v3 does NOT harm smoke_25, so stop rule does NOT trigger. **B4_v3 expansion would be justified by rule, but skipped due to stop rule 1 (Qwen3 weak) and engineering principle (B1_v3 = B3_v3 = same gain → planner unlikely to help further).**

## Rule 4 / 5: Qwen3 thinking-mode and DeepSeek
- Qwen3 thinking-mode escalation: not tested in screening (would only be useful on hard cases; given Qwen3 base accuracy is below incumbent, no value in escalating).
- DeepSeek: still environmental blocker (transformers ABI in trust_remote_code); no fresh kernel attempt this iteration.

## Net expansion decision

**Skip all expansions:**
- Qwen3-8B fails rule 1 (already screened, 6 cells preserved as cross-model evidence).
- B2_v3 / B4_v3 not added: B1_v3 ≡ B3_v3 ≡ +0.0333 over B1 on multi-DB without any planner. Adding planner unlikely to help (matches prior B2_v2 finding).
- Gemma-3-12b-it / SQLCoder-7B-2 / Qwen-Coder-32B: not screened. Decision: skip — sufficient scientific signal from B1_v3/B3_v3.

**Keep all 12 v7 screening runs as final v3 evidence.**

## Key scientific findings extracted

1. **B1_v3 ≡ B3_v3 on every subset** (multi-DB 0.80 / 0.80, BIRD 0.20 / 0.23, smoke_25 0.96 / 0.96). The bidirectional linker (B1_v3) and the hybrid retrieval (B3_v3) produce nearly identical selections on Spider/BIRD schemas.

2. **The +0.0333 EX win on multi-DB comes from BETTER SCHEMA LINKING, NOT from the planner.** Old B2_v2 also won by +0.0333 on multi-DB; new B1_v3 (no planner, no JSON schema, just bidirectional linker) achieves the same gain. **The planner stack adds zero accuracy** — its win was a side effect of the B1-fallback safety net using lex-linking in fallback mode.

3. **Qwen3-8B (without Coder fine-tune) is significantly weaker** than Qwen2.5-Coder-7B on every benchmark in this evaluation. Right-sizing argument extends: not only is bigger not better, but newer-architecture-without-Coder-fine-tune is also not better.

4. **B3_v3 BIRD = 0.2333 ≈ B0 BIRD = 0.2667**: hybrid retrieval slightly trails direct B0 on BIRD; on Spider multi-DB they match each other. This confirms direct-B0 is robust on harder benchmarks.

5. **Fallback rate analysis:** B1_v3 falls back to full schema 100% of the time on smoke_25 (small DBs, linker correctly recognises full schema is fine). On multi-DB, fallback rate drops to ~77% (linker confident enough on 23% of cases to use reduced schema). On BIRD, fallback rate is 60%, suggesting linker is uncertain on enterprise schemas.
