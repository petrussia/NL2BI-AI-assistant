# Schema linking / retrieval diagnosis (full benchmarks)

| Baseline | Bench | N | fallback_used % | EX in fallback | EX no-fallback |
|---|---|---:|---:|---:|---:|
| B1_v3 | spider_dev | 1034 | 84.4% | 76.17% | 42.24% |
| B3_v4 | spider_dev | 1034 | 80.1% | 76.69% | 47.57% |
| B1_v3 | bird_full | 500 | 47.8% | 17.15% | 21.84% |
| B3_v4 | bird_full | 500 | 43.0% | 15.35% | 39.30% |
| B2_v4 | bird_full | 500 | 99.6% | 19.48% | 50.00% |
| B3_v4 | spider2lite_full | 547 | 100.0% | 0.00% | 0.00% |

## Reading

- "Fallback" means the linker/retriever escalated to the full schema due to low confidence or over-pruning.
- For B1_v3 and B3_v4 on Spider, the no-fallback subset performs **substantially worse** than the full-schema fallback path.
  This indicates that, on Spider, the linker tends to cause harm when it commits to a reduced schema.
- On BIRD, B3_v4 in the no-fallback subset performs **better** than B0, because retrieval + benchmark evidence pays off when schemas are large and domain hints are available.
- Practical implication: retrieval is worth keeping on BIRD; on Spider the safer policy is to default to B0 (full schema) unless retrieval confidence is very high.
