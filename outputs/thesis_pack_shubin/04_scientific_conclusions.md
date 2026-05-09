# 04 — Scientific conclusions (Shubin) — v5

_Generated: 2026-04-30T15:44:15.321995+00:00_

These bullets are written so they can be copied directly into the ВКР conclusions section.

1. **Direct generation with full schema dominates Spider for code-aware base models.** B0 + Qwen2.5-Coder-7B-Instruct reaches EX = 1.00 on smoke_10, **0.96 on smoke_25**, and 0.9333 on multi-DB. For this benchmark and this model class, the simplest pipeline is also the most accurate.
2. **Schema linking (B1) is information-equivalent on small DBs but harmful on schema-diverse subsets.** On smoke_10/25 B1 = B0; on multi-DB B1 = 0.7667 vs B0 = 0.9333.
3. **The v2 safety net design is now confirmed across all three subsets:** B2_v2/B3_v2/B4_v2 + Qwen-Coder-7B reach EX = 0.96 on smoke_25 (parity with B0/B1), 0.80 on smoke_10 (under-saturated), and 0.73-0.80 on multi-DB. The unconditional B1 fallback on plan failure prevents catastrophic regression.
4. **B2_v2 is the only layered configuration with a positive signal vs direct B1 on the multi-DB scientific slice:** EX = 0.80 vs B1 = 0.7667 (delta +0.0333).
5. **Bigger model is not better.** Qwen2.5-Coder-14B-Instruct ties Coder-7B on smoke_10/25 B0/B1 and *loses* on multi-DB B0 (0.8667 vs 0.9333). Right-sizing argument: stay at 7B.
6. **Llama-3.1-8B-Instruct is competitive on the multi-DB scientific slice** (B0 = 0.8333 — close to Coder-14B = 0.8667; Coder-7B wins at 0.9333). Schema linking compensates for missing Coder fine-tune on smaller subsets (B1 smoke_10 = 0.90).
7. **Recommended production configuration:** B0 + Qwen2.5-Coder-7B-Instruct + SELECT-only AST guard + 8s SQLite timeout + AnalyticsPayload v1 post-processor. Use B2_v2 as audit-trail variant when downstream needs structured plans.
8. **Mandatory model block:** 3 of 4 evaluated (Qwen-Coder-7B, Qwen-Instruct-7B, Llama-3.1-8B); DeepSeek environmentally blocked with full clean-notebook unblock checklist.
9. **TZ closure:** 100% by physical-evidence rule (16/16). Negative experimental results documented as scientific findings, not gaps.
10. **The layered architecture is correct, just over-engineered for this benchmark:** when the base model can answer one-shot, additional layers can only add failure modes. The v2 safety-net design ensures graceful degradation, but the true value of layered architectures will only manifest on harder benchmarks (BIRD, Spider 2.0, enterprise multi-step queries).
