| Подход | Метод | Семейство | Sample | run_id | Роль |
| --- | --- | --- | --- | --- | --- |
| B0 | B0_rule_based | Детерминированный baseline | 200 | stage4_cpu_sample200 | Правила без LLM |
| B1 | B1_constraint_ranker | Детерминированный baseline | 200 | stage4_cpu_sample200 | Ограничения и ранжирование кандидатов |
| B2 | B2_partial_recommender | Подход в стиле существующих инструментов | 200 | stage5_partial_sample200 | Частичный recommender fallback |
| B3 | B3_local_llm_qwen3_8b | Локальная LLM | 50 | stage6_qwen3_8b_fast_sample50 | Один кандидат Qwen3-8B |
| B4 | B4_llm_validator_reranker | Локальная LLM + validation | 20 | stage7_b4_sample20_tokens384 | 3 кандидата + validator/reranker |
| B5a | B5_stage8_qwen3_14b | Stage 8 LLM + strict JSON validator | 20 | stage8_qwen3_14b_sample20 | Qwen3-14B, один кандидат, validator retry |
| B5b | B5_stage8_mistral_small_32_24b_bnb4 | Stage 8 LLM + strict JSON validator | 20 | stage8_mistral_small_32_24b_bnb4_sample20 | Mistral Small 3.2 24B bnb-4bit, один кандидат |
| B5c | B5_stage8_gemma3_12b_it | Stage 8 LLM + strict JSON validator | 20 | stage8_gemma3_12b_it_sample20 | Gemma 3 12B IT, gated HF model |
| B5d | B5_stage8_gemma4_e2b_it | Stage 8 LLM + strict JSON validator | 20 | stage8_gemma4_e2b_it_sample20 | Gemma 4 E2B IT, малый контрольный LLM baseline |