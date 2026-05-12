# Master matrix consistency audit v10

**Generated:** 2026-04-30T22:53:42.278951+00:00

## Verifications
| Check | Status | Detail |
|---|---|---|
| Row count == 127 | ✅ | 127 |
| All prediction files referenced exist | ✅ | missing 0: none |
| All metrics files referenced exist | ✅ | missing 0: none |
| No duplicate run_ids | ✅ | dupes: none |
| Final winner — production direct | ✅ | `b0_multidb30_v2` EX=0.9333333333333333 |
| Final winner — production layered | ✅ | `b1v3_qwen2p5_coder_7b_multidb30` EX=0.8 |

## Subset normalization (5 canonical)
[
  "bird_minidev_30",
  "multidb_30",
  "smoke_10",
  "smoke_25",
  "spider2lite_30"
]

## Model count
8 distinct models in matrix.

## Final winner identification (derivable from matrix)
- **Production direct:** `b0_multidb30_v2` — B0 + Qwen2.5-Coder-7B-Instruct, EX = 0.9333333333333333 on multi-DB.
- **Production layered (revised in v9):** `b1v3_qwen2p5_coder_7b_multidb30` — B1_v3 + Qwen2.5-Coder-7B-Instruct, EX = 0.8 on multi-DB; one LLM call, no planner.

## Stale-row check
The matrix contains the full evolutionary record (B2_v0, B2_v1, B2_v2, B3, B3_v1, B3_v2, B4-lite, B4_final, B4_v2 etc.) as **historical evidence** — these rows are NOT marked as final winners. Final-winner identification is derivable from the audit table above.

## Verdict
**Master matrix v9 (127 rows) is internally consistent. No fixes required.**
