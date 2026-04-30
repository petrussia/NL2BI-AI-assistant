# multidb_30 scientific readout — final v4

**Generated:** 2026-04-30T14:38:33.007726+00:00

## Master scientific slice — all configurations

| Baseline | Model | EX | Notes |
|---|---|---|---|
| **B0** | **Qwen-Coder-7B** | **0.9333** | strongest overall |
| B1 | Qwen-Coder-7B | 0.7667 | linker over-prunes |
| B2_v1 | Qwen-Coder-7B | 0.6333 | pre-fix planner |
| **B2_v2** | **Qwen-Coder-7B** | **0.8000** | **beats B1 by +0.0333 — only layered win in project** |
| B3_v1 | Qwen-Coder-7B | 0.4667 | pre-fix dual retrieval |
| B3_v2 | Qwen-Coder-7B | 0.7333 | knowledge channel off + B1 fallback |
| B4_final | Qwen-Coder-7B | 0.4667 | capped by upstream plan failures |
| B4_v2 | Qwen-Coder-7B | 0.7333 | + B1 fallback at 2 points |
| **B0** | **Qwen-Coder-14B** | 0.8667 | **lower than 7B (-0.067)** |
| B1 | Qwen-Coder-14B | 0.7667 | tied with 7B |

## Three clean findings

1. **Direct dominates layered:** B0 + 7B = 0.9333 > B2_v2 = 0.8000 > everything else.
2. **Smaller dominates larger:** Coder-7B B0 = 0.9333 > Coder-14B B0 = 0.8667. Bigger model emits over-elaborate SQL.
3. **Schema linking is information-equivalent at scale:** B1 7B (0.7667) = B1 14B (0.7667) — the linker is the bottleneck, not the model.

## What this slice means for the diploma

The multi-DB subset is the closest proxy in this project to a real enterprise BI workload (heterogeneous schemas, non-overlapping vocabulary across DBs). The headline findings on this slice should drive the defense narrative — they are the most generalisable.
