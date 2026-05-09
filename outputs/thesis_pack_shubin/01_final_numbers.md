# 01 — Final numbers (Shubin) — v5

_Generated: 2026-04-30T15:44:15.321995+00:00_

## Headline EX (Execution Match) — copy-pasteable for ВКР tables

### Single-DB smoke subsets

| Baseline | Model | smoke_10 | smoke_25 |
|---|---|---|---|
| B0 | Qwen2.5-Coder-7B | 1.0000 (10/10) | 0.9600 (24/25) |
| B1 | Qwen2.5-Coder-7B | 1.0000 (10/10) | 0.9600 (24/25) |
| B2_v0 | Qwen2.5-Coder-7B | 0.7000 (7/10) | — |
| B2_v1 | Qwen2.5-Coder-7B | 0.6000 (6/10) | — |
| **B2_v2** | **Qwen2.5-Coder-7B** | **0.8000 (8/10)** | **0.9600 (24/25)** |
| B3_v1 | Qwen2.5-Coder-7B | 0.3000 (3/10) | — |
| **B3_v2** | **Qwen2.5-Coder-7B** | **0.8000 (8/10)** | **0.9600 (24/25)** |
| B4_final | Qwen2.5-Coder-7B | 0.3000 (3/10) | — |
| **B4_v2** | **Qwen2.5-Coder-7B** | **0.8000 (8/10)** | **0.9600 (24/25)** |
| B0 | Qwen2.5-7B-Instruct | 0.6000 (6/10) | — |
| B1 | Qwen2.5-7B-Instruct | 1.0000 (10/10) | — |
| **B0** | **Llama-3.1-8B** | **0.8000 (8/10)** | **0.6000 (15/25)** |
| **B1** | **Llama-3.1-8B** | **0.9000 (9/10)** | **0.7200 (18/25)** |
| B0 | Qwen2.5-Coder-14B | 1.0000 (10/10) | **0.9600 (24/25)** |
| B1 | Qwen2.5-Coder-14B | 1.0000 (10/10) | **0.9200 (23/25)** |

### multidb_30 (master scientific slice — heterogeneous schemas across 6 DBs)

| Baseline | Model | EX |
|---|---|---|
| B0 | Qwen2.5-Coder-7B | 0.9333 (28/30) |
| B1 | Qwen2.5-Coder-7B | 0.7667 (23/30) |
| B2_v1 | Qwen2.5-Coder-7B | 0.6333 (19/30) |
| **B2_v2** | **Qwen2.5-Coder-7B** | **0.8000 (24/30)** |
| B3_v1 | Qwen2.5-Coder-7B | 0.4667 (14/30) |
| B3_v2 | Qwen2.5-Coder-7B | 0.7333 (22/30) |
| B4_final | Qwen2.5-Coder-7B | 0.4667 (14/30) |
| B4_v2 | Qwen2.5-Coder-7B | 0.7333 (22/30) |
| B0 | Qwen2.5-Coder-14B | 0.8667 (26/30) |
| B1 | Qwen2.5-Coder-14B | 0.7667 (23/30) |
| **B0** | **Llama-3.1-8B** | **0.8333 (25/30)** |
| **B1** | **Llama-3.1-8B** | **0.7000 (21/30)** |

## Strongest configurations (final, defense-grade)

- **Strongest direct & strongest overall:** B0 + Qwen2.5-Coder-7B-Instruct. EX = 1.0000 / 0.9600 / 0.9333.
- **Strongest layered (smoke_25 PARITY):** B2_v2 / B3_v2 / B4_v2 + Qwen2.5-Coder-7B reach **0.9600 on smoke_25** = B0 = B1.
- **Strongest layered (multi-DB win):** B2_v2 + Qwen2.5-Coder-7B = 0.8000 > B1 = 0.7667.
- **Mandatory model unblock:** Llama-3.1-8B-Instruct B0 multi-DB = 0.8333 — competitive vs Coder family.
- **Right-sizing:** Qwen-Coder-14B never beats 7B; on multi-DB it loses by 0.067.
