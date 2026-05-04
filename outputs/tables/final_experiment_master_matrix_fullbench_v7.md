# Master matrix v18 — Phase 7 (B7 evidence ablations on FULL BIRD)

B0/B2_v5/B4_v5 from prior phases. B6_v7 from Phase 6 (LLM-as-judge selector).
B7 = B6_v7 controller + evidence_semantics_v7 layer with mode flags.

| Baseline | Bench | N | EX | 95% CI | Exec | Judge inv | Judge ovr | Evidence chars avg | Avg LM calls |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 | bird_full | 500 | 20.40% | [17.1, 24.2] | 79.80% | 0.00% | 0.00% | 0 | 1.00 |
| B2_v5 | bird_full | 500 | 37.60% | [33.5, 41.9] | 84.20% | 0.00% | 0.00% | 0 | 1.00 |
| B4_v5 | bird_full | 500 | 34.00% | [30.0, 38.3] | 98.40% | 0.00% | 0.00% | 0 | 4.90 |
| B6_v7 | bird_full | 500 | 38.80% | [34.6, 43.1] | 96.20% | 65.20% | 38.00% | 0 | 5.56 |
| B7d_rich | bird_full | 500 | 39.20% | [35.0, 43.5] | 92.80% | 63.40% | 37.40% | 546 | 5.57 |
| B7c_profiles_only | bird_full | 500 | 33.20% | [29.2, 37.4] | 96.60% | 64.60% | 29.80% | 528 | 5.53 |
| B7e_none | bird_full | 500 | 33.20% | [29.2, 37.4] | 95.80% | 66.00% | 27.00% | 0 | 5.56 |
