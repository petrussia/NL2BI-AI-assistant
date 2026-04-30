# Multi-DB Ablation (multidb_30)

Generated at: 2026-04-29T15:30:22.102213+00:00
Subset: multidb_30 (n=30, 6 unique DBs).
Model: Qwen2.5-Coder-7B-Instruct (4-bit nf4 bitsandbytes).

| Baseline | EX | Executable | Plan valid | Avg reduction | n | Notes |
|---|---|---|---|---|---|---|
| B0 | 0.9333 | 30/30 | — | — | 30 | — |
| B1 | 0.7667 | 29/30 | — | 0.5527777777777777 | 30 | — |
| B2_v1 | 0.6333 | 26/30 | 28/30 | 0.5527777777777777 | 30 | parse_fail=0 |
| B3_v1 | 0.4667 | 18/30 | 18/30 | 0.5527777777777777 | 30 | parse_fail=0 |
| B4_final | 0.4667 | 18/30 | 18/30 | 0.5527777777777777 | 30 | parse_fail=0 repaired=0 rejected_unsafe=0 |

**Winner on multidb_30:** B0

## Interpretation
- B0 has access to gold db_id (so it does not perform retrieval). Same for B1/B2_v1/B3_v1/B4_final on this subset.
- Multi-DB benchmark stresses the schema-linker and (partially) the planner: questions span 6 different DBs.
- If B1 keeps EX close to B0, the linker is information-equivalent (not harmful).
- If B3_v1 EX > B2_v1 EX, the dual-retrieval channel is contributing on multi-DB.
- If B4_final EX > B3_v1 EX, the multi-candidate + safety + repair stack is paying off.

