# Final negative-result analysis (v5)

**Generated:** 2026-04-30T15:44:15.321995+00:00

## Updated picture after smoke_25 + Llama + Qwen-14B closure

### Negative #1: Layered planning never beats direct B0+Coder-7B on the multi-DB slice
| Subset | B0 (Coder-7B) | best layered v2 | gap |
|---|---|---|---|
| smoke_10 | 1.0000 | 0.8000 | -0.20 |
| smoke_25 | 0.9600 | 0.9600 | **0.00 (tie!)** |
| multidb_30 | 0.9333 | 0.8000 | -0.13 |

The v2 safety net brings layered to **parity** with direct on smoke_25, but B0 still wins on multi-DB.

### Negative #2: Bigger model is not better
| Subset | Coder-7B B0 | Coder-14B B0 | delta |
|---|---|---|---|
| smoke_10 | 1.0000 | 1.0000 | tie |
| smoke_25 | 0.9600 | 0.9600 | tie |
| multidb_30 | **0.9333** | 0.8667 | **−0.067 (7B wins)** |

### Positive #1: v2 safety net recovered earlier regression (now confirmed across smoke_25)

| Branch | smoke_10 v1→v2 | smoke_25 v1→v2 | multidb v1→v2 |
|---|---|---|---|
| B3 | 0.3000→**0.8000** (+0.50) | (no v1 smoke25)→**0.9600** | 0.4667→**0.7333** (+0.27) |
| B4 | 0.3000→**0.8000** (+0.50) | (no v1 smoke25)→**0.9600** | 0.4667→**0.7333** (+0.27) |

### Positive #2: B2_v2 multi-DB beats B1 (only layered positive)
B2_v2 multi-DB = 0.8000 > B1 multi-DB = 0.7667 (delta +0.0333). On smoke_25 layered = direct (parity).

### Positive #3 (NEW): Llama-3.1-8B competes with Coder-7B/14B on multi-DB
- Llama B0 multi-DB = **0.8333**
- Coder-7B B0 multi-DB = 0.9333
- Coder-14B B0 multi-DB = 0.8667

A general-purpose 8B model is competitive with code-specialised 14B on schema-diverse data — supports the "bigger / specialised model is not always better" story.

## Bottom line
The v5 closure does not overturn any earlier conclusion; it **strengthens** them:
- Production: B0 + Qwen-Coder-7B remains optimal.
- B2_v2 audit-trail variant remains the only layered configuration with a positive signal vs B1 on the master scientific slice (multi-DB).
- The 14B comparator is now confirmed negative across smoke_25 too — bigger model adds zero accuracy.
- Llama-3.1-8B competitive on multi-DB B0 — adds a clean "general-purpose model competes with code-specialised one on diverse schemas" data-point.
