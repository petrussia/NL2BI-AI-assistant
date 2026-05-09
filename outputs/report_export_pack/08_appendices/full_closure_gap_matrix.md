# Full closure gap matrix
_Generated: 2026-04-30T19:42:44.668093+00:00_
_Total cells: 125_  
_done: 80  missing: 20  blocked: 25  not_applicable: 0_

Legend: ✅ done · ❌ missing · 🚫 blocked · ⚪ N/A

## Qwen2.5-Coder-7B-Instruct
| Benchmark | B0 | B1 | B2_v2 | B3_v2 | B4_v2 |
|---|---|---|---|---|---|
| smoke_10 | ✅ 1.00 | ✅ 1.00 | ✅ 0.80 | ✅ 0.80 | ✅ 0.80 |
| smoke_25 | ✅ 0.96 | ✅ 0.96 | ✅ 0.96 | ✅ 0.96 | ✅ 0.96 |
| multidb_30 | ✅ 0.93 | ✅ 0.77 | ✅ 0.80 | ✅ 0.73 | ✅ 0.73 |
| bird_minidev_30 | ✅ 0.27 | ✅ 0.20 | ✅ 0.20 | ✅ 0.20 | ✅ 0.20 |
| spider2lite_30 | ✅ 97% | ✅ 97% | ✅ 97% | ✅ 97% | ✅ 97% |

## Qwen2.5-Coder-14B-Instruct
| Benchmark | B0 | B1 | B2_v2 | B3_v2 | B4_v2 |
|---|---|---|---|---|---|
| smoke_10 | ✅ 1.00 | ✅ 1.00 | ❌ | ❌ | ❌ |
| smoke_25 | ✅ 0.96 | ✅ 0.92 | ❌ | ❌ | ❌ |
| multidb_30 | ✅ 0.87 | ✅ 0.77 | ❌ | ❌ | ❌ |
| bird_minidev_30 | ✅ 0.23 | ✅ 0.20 | ✅ 0.20 | ✅ 0.20 | ✅ 0.20 |
| spider2lite_30 | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |

## Llama-3.1-8B-Instruct
| Benchmark | B0 | B1 | B2_v2 | B3_v2 | B4_v2 |
|---|---|---|---|---|---|
| smoke_10 | ✅ 0.80 | ✅ 0.90 | ✅ 0.80 | ✅ 0.80 | ✅ 0.80 |
| smoke_25 | ✅ 0.60 | ✅ 0.72 | ✅ 0.80 | ✅ 0.76 | ✅ 0.76 |
| multidb_30 | ✅ 0.83 | ✅ 0.70 | ✅ 0.73 | ✅ 0.67 | ✅ 0.63 |
| bird_minidev_30 | ✅ 0.13 | ✅ 0.13 | ✅ 0.07 | ✅ 0.13 | ✅ 0.13 |
| spider2lite_30 | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |

## Qwen2.5-7B-Instruct
| Benchmark | B0 | B1 | B2_v2 | B3_v2 | B4_v2 |
|---|---|---|---|---|---|
| smoke_10 | ✅ 0.60 | ✅ 1.00 | ❌ | ❌ | ❌ |
| smoke_25 | ✅ 0.72 | ✅ 0.84 | ✅ 0.88 | ❌ | ❌ |
| multidb_30 | ✅ 0.80 | ✅ 0.70 | ✅ 0.73 | ❌ | ❌ |
| bird_minidev_30 | ✅ 0.20 | ✅ 0.17 | ✅ 0.17 | ❌ | ❌ |
| spider2lite_30 | ✅ 97% | ✅ 97% | ✅ 97% | ❌ | ❌ |

## DeepSeek-Coder-V2-Lite-Instruct
| Benchmark | B0 | B1 | B2_v2 | B3_v2 | B4_v2 |
|---|---|---|---|---|---|
| smoke_10 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |
| smoke_25 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |
| multidb_30 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |
| bird_minidev_30 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |
| spider2lite_30 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |

## Missing cells (in prioritized order)

### P0: Qwen2.5-Coder-14B-Instruct
- **MISSING** B2_v2 on smoke_10
- **MISSING** B3_v2 on smoke_10
- **MISSING** B4_v2 on smoke_10
- **MISSING** B2_v2 on smoke_25
- **MISSING** B3_v2 on smoke_25
- **MISSING** B4_v2 on smoke_25
- **MISSING** B2_v2 on multidb_30
- **MISSING** B3_v2 on multidb_30
- **MISSING** B4_v2 on multidb_30

### P1: Qwen2.5-7B-Instruct
- **MISSING** B2_v2 on smoke_10
- **MISSING** B3_v2 on smoke_10
- **MISSING** B4_v2 on smoke_10
- **MISSING** B3_v2 on smoke_25
- **MISSING** B4_v2 on smoke_25
- **MISSING** B3_v2 on multidb_30
- **MISSING** B4_v2 on multidb_30
- **MISSING** B3_v2 on bird_minidev_30
- **MISSING** B4_v2 on bird_minidev_30
- **MISSING** B3_v2 on spider2lite_30
- **MISSING** B4_v2 on spider2lite_30

### P2: DeepSeek-Coder-V2-Lite-Instruct
- **BLOCKED** B0 on smoke_10 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B1 on smoke_10 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B2_v2 on smoke_10 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B3_v2 on smoke_10 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B4_v2 on smoke_10 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B0 on smoke_25 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B1 on smoke_25 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B2_v2 on smoke_25 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B3_v2 on smoke_25 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B4_v2 on smoke_25 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B0 on multidb_30 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B1 on multidb_30 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B2_v2 on multidb_30 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B3_v2 on multidb_30 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B4_v2 on multidb_30 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B0 on bird_minidev_30 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B1 on bird_minidev_30 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B2_v2 on bird_minidev_30 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B3_v2 on bird_minidev_30 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B4_v2 on bird_minidev_30 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B0 on spider2lite_30 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B1 on spider2lite_30 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B2_v2 on spider2lite_30 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B3_v2 on spider2lite_30 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
- **BLOCKED** B4_v2 on spider2lite_30 — environmental: trust_remote_code ABI mismatch with transformers 5.0.0; needs fresh kernel with transformers==4.39.3
