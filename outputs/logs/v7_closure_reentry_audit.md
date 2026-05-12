# v7-closure reentry audit

**Generated:** 2026-04-30T21:21:25.078371+00:00

## Recovery state (verified)
- Bridge live, A100 80 GB free
- HF_TOKEN set, Drive mounted
- Existing master matrix: 110 rows
- Existing repo modules: 20 (incl. v3: retrieval_hybrid, schema_linking_bidirectional, baselines_b1_v3, baselines_b3_v3)

## v7-closure planned cells
- Total planned: 20
- Already present (reuse): 0
- Missing (to compute): 20

## Per-priority breakdown
- **P0 (architecture closure):** B2_v3 + B4_v3 × Qwen-Coder-7B × 3 subsets = 6 cells
- **P1 (model screening):**
  - Gemma-3-12b-it: B0 × 4 subsets + B1_v3 × 2 = 6 cells
  - SQLCoder-7B-2: B0 × 2 + B1_v3 × 1 = 3 cells
  - Qwen-Coder-32B: B0 × 3 + B1_v3 × 2 = 5 cells

## Reuse policy
All 110 prior cells reused as-is (numbers authoritative). No re-runs.

## Skip policy (explicit)
- DeepSeek: environmental blocker stands; no fresh-kernel attempt this iteration.
- Spider 2.0-Lite for new models: skip — structural-only metrics already shown for Qwen-7B/Llama; B2_v3/B4_v3 on Spider2-Lite have low marginal value (would only confirm safety guard works).
- Qwen3-8B expansion: stop-rule 1 triggered in v7 (0.20 EX gap on smoke_25); preserved 6 cells only.

## Skip rationale for missing cells if model fails screening
- Gemma B0 smoke_10 < incumbent - 0.20 → skip Gemma B1_v3 expansion
- SQLCoder B0 multidb_30 < 0.50 → skip B1_v3
- Qwen-32B B0 smoke_25 < incumbent - 0.05 → skip B1_v3 expansion (right-sizing)
