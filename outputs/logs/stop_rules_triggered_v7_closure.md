# Stop rules — v7-closure screening

**Generated:** 2026-04-30T22:33:40.604353+00:00

## Rule 1: model B0 vs incumbent on smoke_10
- Gemma-3-12b-it B0 smoke_10 = 1.0000 vs incumbent = 1.0000 → **PASS** (tied) → screening continues, B1_v3 expansion executed.
- SQLCoder-7B-2 B0 smoke_10 = (not tested; only multidb_30 & BIRD per plan).
- Qwen-Coder-32B B0 smoke_25 = 0.9600 (used as proxy) vs incumbent 0.96 → tied. Did NOT trigger early stop.

## Rule 2: B2_v3 / B4_v3 do not exceed B1_v3 / B3_v3 → planner adds no value
- B1_v3 multi-DB = 0.8000 (no planner)
- B3_v3 multi-DB = 0.8000 (no planner)
- **B2_v3 multi-DB = 0.7667 (with planner)**
- **B4_v3 multi-DB = 0.7667 (with planner + multi-cand)**
- **DECISION:** Planner with v3 fallback HURTS by 0.0333 EX vs retrieval-only on multi-DB. **DEFINITIVE NEGATIVE: planner adds no measurable value over retrieval-only path.**

## Rule 3: Qwen-Coder-32B right-sizing
- Qwen-32B B0 multi-DB = 0.8333 vs Qwen-7B B0 = 0.9333 → 32B LOSES by 0.10 EX.
- Qwen-32B B0 BIRD = 0.2667 vs Qwen-7B B0 = 0.2667 → tied at 0.2667.
- **DECISION:** Right-sizing CONFIRMED at 32B scale. **B1_v3 expansion explicitly skipped per right-sizing rule. 32B is not justified on H100.**

## Rule 4: BIRD official metrics
- Deferred to next phase (run separately on existing predictions).

## Net decisions
- 17/19 planned cells executed.
- 2 skipped by stop rules (Qwen-32B B1_v3 × 2 — right-sizing).
- All blockers preserved: DeepSeek environmental, Spider 2.0-Lite EX environmental.
