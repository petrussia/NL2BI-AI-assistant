# Master matrix v19 — Phase 8 (S1_v7 demo retrieval on FULL Spider)

B0/B1_v5/B2_v5/B4_v5/B6_v7 from prior phases. S1_v7 = B6_v7 controller +
DAIL-style demonstration retrieval (top-3 same-db demos prepended to anchor).

| Baseline | Bench | N | EX | 95% CI | Exec | Judge inv | Judge ovr | Demo chars avg | Avg LM calls |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 | spider_dev | 1034 | 72.53% | [69.7, 75.2] | 94.87% | 0.00% | 0.00% | 0 | 1.00 |
| B1_v5 | spider_dev | 1034 | 74.85% | [72.1, 77.4] | 94.87% | 0.00% | 0.00% | 0 | 1.00 |
| B2_v5 | spider_dev | 1034 | 74.76% | [72.0, 77.3] | 94.97% | 0.00% | 0.00% | 0 | 1.00 |
| B4_v5 | spider_dev | 1034 | 76.69% | [74.0, 79.2] | 98.36% | 0.00% | 0.00% | 0 | 4.83 |
| B6_v7 | spider_dev | 1034 | 76.79% | [74.1, 79.3] | 98.16% | 37.14% | 4.93% | 0 | 5.20 |
| S1_v7 | spider_dev | 1034 | 76.31% | [73.6, 78.8] | 98.74% | 42.07% | 9.19% | 613 | 5.25 |
