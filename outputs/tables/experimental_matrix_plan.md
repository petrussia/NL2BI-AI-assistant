# Experimental matrix plan (full-matrix closure)

_Generated: 2026-04-30T15:20:33.945730+00:00_

**Existing rows:** 29  |  **Planned new rows:** 11 (P0+P1)  |  **Optional (P2):** 4

| Baseline | Model | Subset | Prefix | Present | Priority | Why |
|---|---|---|---|---|---|---|
| B2_v2 | qwen2p5_coder_7b | smoke_25 | `b2v2_spider_smoke25` | ❌ | P0 | fill_primary |
| B3_v2 | qwen2p5_coder_7b | smoke_25 | `b3v2_spider_smoke25` | ❌ | P0 | fill_primary |
| B4_v2 | qwen2p5_coder_7b | smoke_25 | `b4v2_spider_smoke25` | ❌ | P0 | fill_primary |
| B0 | llama_3p1_8b_instruct | smoke_25 | `b0_llama_3p1_8b_instruct_smoke25` | ❌ | P1 | mandatory_compare |
| B1 | llama_3p1_8b_instruct | smoke_25 | `b1_llama_3p1_8b_instruct_smoke25` | ❌ | P1 | mandatory_compare |
| B0 | llama_3p1_8b_instruct | multidb_30 | `b0_llama_3p1_8b_instruct_multidb30` | ❌ | P1 | mandatory_compare |
| B1 | llama_3p1_8b_instruct | multidb_30 | `b1_llama_3p1_8b_instruct_multidb30` | ❌ | P1 | mandatory_compare |
| B0 | qwen2p5_coder_14b_instruct | smoke_25 | `b0_qwen2p5_coder_14b_instruct_smoke25` | ❌ | P1 | opt_big_model |
| B1 | qwen2p5_coder_14b_instruct | smoke_25 | `b1_qwen2p5_coder_14b_instruct_smoke25` | ❌ | P1 | opt_big_model |
| B2_v2 | llama_3p1_8b_instruct | smoke_10 | `b2v2_llama_3p1_8b_instruct_smoke10` | ❌ | P2 | llama_structured_if_time |
| B2_v2 | llama_3p1_8b_instruct | multidb_30 | `b2v2_llama_3p1_8b_instruct_multidb30` | ❌ | P2 | llama_structured_if_time |
| B2_v2 | qwen2p5_coder_14b_instruct | smoke_10 | `b2v2_qwen2p5_coder_14b_instruct_smoke10` | ❌ | P2 | opt_big_model_structured |
| B2_v2 | qwen2p5_coder_14b_instruct | multidb_30 | `b2v2_qwen2p5_coder_14b_instruct_multidb30` | ❌ | P2 | opt_big_model_structured |
| B0 | deepseek_coder_v2_lite_instruct | smoke_10 | `b0_deepseek_coder_v2_lite_instruct_smoke10` | ❌ | P1 | blocked_environment |
| B1 | deepseek_coder_v2_lite_instruct | smoke_10 | `b1_deepseek_coder_v2_lite_instruct_smoke10` | ❌ | P1 | blocked_environment |
