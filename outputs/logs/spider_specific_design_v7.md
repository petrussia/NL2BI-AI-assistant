# Spider-specific design memo v7 (S1 demo retrieval)

_Generated: 2026-05-04 23:21 UTC._

Architecture: B6_v7 controller (Phase 6 LLM-as-judge selector) + DAIL-style
demonstration retrieval. Top-3 train demos retrieved per dev question via
BM25 over question text + structural-feature jaccard + +0.5 same-db boost.
Demos are prepended only to the C0_anchor prompt (other candidates unchanged).

## Train pool
- train_spider.json (7000) + train_others.json (1659) = 8659 examples
- Per-db BM25 indices for fast same-db lookup
- Structural-feature jaccard (16 features inferred from gold SQL skeleton)

## Headline EX (FULL Spider 1034)

| Cell | EX | 95% CI | demo chars avg |
|---|---:|---:|---:|
| B0 | 72.53% | [69.7, 75.2] | 0 |
| B2_v5 | 74.76% | [72.0, 77.3] | 0 |
| B4_v5 | 76.69% | [74.0, 79.2] | 0 |
| B6_v7 | 76.79% | [74.1, 79.3] | 0 |
| S1_v7 | 76.31% | [73.6, 78.8] | 613 |

## Paired stats

| Bench | A | B | n | EX(A) | EX(B) | Δ pp | 95% CI pp | McNemar p | helpful | harmful |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Spider | B0 | S1_v7 | 1034 | 72.53% | 76.31% | +3.77 | [+1.74, +5.80] | 0.0003 | 77 | 38 |
| Spider | B2_v5 | S1_v7 | 1034 | 74.76% | 76.31% | +1.55 | [-0.10, +3.19] | 0.0764 | 44 | 28 |
| Spider | B4_v5 | S1_v7 | 1034 | 76.69% | 76.31% | -0.39 | [-1.84, +0.97] | 0.6835 | 25 | 29 |
| Spider | B6_v7 | S1_v7 | 1034 | 76.79% | 76.31% | -0.48 | [-1.84, +0.87] | 0.5758 | 23 | 28 |

## Source breakdown

| Cell | source | count | pct | EX rate |
|---|---|---:|---:|---:|
| S1_v7 | C0_anchor | 815 | 78.8% | 80.86% |
| S1_v7 | C1_retrieval_direct | 154 | 14.9% | 64.94% |
| S1_v7 | C3_planner_compiled | 45 | 4.3% | 46.67% |
| S1_v7 | C2_retrieval_evidence | 20 | 1.9% | 45.00% |
| B6_v7 | C0_anchor | 946 | 91.5% | 80.23% |
| B6_v7 | C3_planner_compiled | 60 | 5.8% | 38.33% |
| B6_v7 | C2_retrieval_evidence | 15 | 1.5% | 53.33% |
| B6_v7 | C1_retrieval_direct | 13 | 1.3% | 30.77% |

## Verdicts

- Spider B0 → S1_v7: **S1_v7 significantly beats B0** (Δ +3.77 pp, p=0.0003) (helpful 77 / harmful 38)
- Spider B2_v5 → S1_v7: no significant difference (p=0.0764) (helpful 44 / harmful 28)
- Spider B4_v5 → S1_v7: no significant difference (p=0.6835) (helpful 25 / harmful 29)
- Spider B6_v7 → S1_v7: no significant difference (p=0.5758) (helpful 23 / harmful 28)
