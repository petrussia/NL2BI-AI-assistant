# REPORT — Full-benchmark replication v11

_Generated: 2026-05-02 21:22 UTC._

This report replaces all earlier sample-based reports (smoke_10/25, multidb_30, bird_minidev_30) as the primary evidence for ВКР defence.

## What was run

- **Model**: Qwen/Qwen2.5-Coder-7B-Instruct (BF16, A100 80GB).
- **Benchmarks**: Spider dev (1034) ✅, BIRD Mini-Dev (500) ✅, Spider2-Lite (547, structural-only).
- **Baselines**: B0 (direct), B1_v3 (bidirectional schema linker), B3_v4 (hybrid retrieval + evidence), B2_v4 (planner v4) on BIRD.
- **Total generations**: 6196 across 9 cells.

## Reproducibility

- Predictions: `outputs/predictions/*qwen2p5_coder_7b*full*.jsonl` (per-item, resumable; runner = tools/remote_scripts/108_full_benchmark_runner.py).
- Master matrix: `outputs/tables/full_benchmark_master_matrix.{csv,md}`.
- Failure taxonomy: `outputs/tables/full_benchmark_failure_taxonomy.csv`.
- Paired stats (McNemar + bootstrap CI): `outputs/tables/full_benchmark_paired_stats.csv`.
- Planner diagnosis: `outputs/logs/full_benchmark_planner_diagnosis.md`.
- Retrieval diagnosis: `outputs/logs/full_benchmark_retrieval_diagnosis.md`.
- Scientific findings: `outputs/logs/full_benchmark_scientific_findings.md`.
- Production recommendation: `outputs/logs/full_benchmark_production_recommendation.md`.

## Headline metrics

| Bench | Baseline | EX | 95% Wilson CI | N |
|---|---|---:|---:|---:|
| spider_dev | B0 | 72.53% | [69.7, 75.2] | 1034 |
| spider_dev | B1_v3 | 70.89% | [68.0, 73.6] | 1034 |
| spider_dev | B3_v4 | 70.89% | [68.0, 73.6] | 1034 |
| bird_full | B0 | 20.40% | [17.1, 24.2] | 500 |
| bird_full | B1_v3 | 19.60% | [16.4, 23.3] | 500 |
| bird_full | B3_v4 | 29.00% | [25.2, 33.1] | 500 |
| bird_full | B2_v4 | 19.60% | [16.4, 23.3] | 500 |
| spider2lite_full | B0 | structural-only | — | 547 |
| spider2lite_full | B3_v4 | structural-only | — | 547 |

## Honest blockers

- Spider2-Lite EX not computed: requires BigQuery/Snowflake credentials not available in this kernel. Spider2-Lite numbers are structural quality only.
- DeepSeek-V2-Lite skipped in this kernel: bnb double-registration blocker (documented in earlier blocker_v10 logs). Requires a fresh kernel.
- BIRD official evaluator (R-VES, Soft F1) not run in this consolidation: official CLI drift; left as future work.
- The v4 planner produced 99.6% invalid plans on BIRD; this is a prompt / JSON-schema engineering bug, not an architectural conclusion.

## How to read this

Spider numbers are the most defensible (closed benchmark, full 1034 dev examples, no hidden randomness).
BIRD numbers exclude execution evaluator drift but use the same SQLite ground-truth as the official starter pack.
Spider2-Lite numbers are structural and **not comparable** to leaderboard EX.

See the scientific-findings document for paired-test interpretation and v9 cross-check.
