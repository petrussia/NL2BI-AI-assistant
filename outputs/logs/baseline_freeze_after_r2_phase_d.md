# Baseline freeze after Phase R2 + Phase D

_Frozen on branch `experiments/denis`. All numbers verified against
predictions JSONLs on Drive (`/content/drive/MyDrive/diploma_plan_sql/outputs/predictions`)._

This document is the immutable contract for the next sprint. New methods
must beat or honestly tie these numbers using paired statistics on the
FULL Spider/BIRD/Spider2-Lite splits — partial runs are not admissible
as final evidence.

## Series of committed phases

| SHA | Phase | Headline outcome |
|---|---|---|
| 684a818 | v11 full-benchmark replication | B0/B1_v3/B3_v4 closed on Spider+BIRD; Spider2-Lite structural-only |
| d2cf0b4 | Phase A retrieval v2 | B1_v5/B2_v5; retrieval helps on FULL Spider — overturns v9 |
| 98d39e1 | Phase B planner+compiler | B3_v5; structured plan alone hurts without verifier (clean negative ablation) |
| adf4415 | Phase C controller/verifier | B4_v5; closes Phase B regression, beats all baselines on Spider |
| 6525a94 | Phase R2 Premium retrieval | B5_v6; clean negative — Qwen3-Reranker-0.6B saturates and slightly hurts BIRD |
| cfcafe3 | Phase D planner-model swap | clean negative — Qwen3-8B 0% valid plans; Gemma-12b OOM on 40 GB |

## Frozen ladder (Qwen2.5-Coder-7B-Instruct, BF16, A100)

### Spider dev FULL (1034)

| Baseline | EX | 95% Wilson CI | Source |
|---|---:|---:|---|
| B0 anchor | **72.53%** | [69.7, 75.2] | v11 |
| B1_v5 retrieval | 74.85% | [72.1, 77.4] | Phase A |
| B2_v5 retrieval+evidence | 74.76% | [72.0, 77.3] | Phase A |
| B3_v5 planner+compiler | 56.96% | [53.9, 59.9] | Phase B (negative) |
| **B4_v5 controller/verifier** | **76.69%** ← current best | [74.0, 79.2] | Phase C |
| B5_v6 R2 (controller + reranker) | 76.60% | [73.9, 79.1] | Phase R2 (neutral) |

### BIRD Mini-Dev FULL (500)

| Baseline | EX | 95% Wilson CI | Source |
|---|---:|---:|---|
| B0 anchor | 20.40% | [17.1, 24.2] | v11 |
| B1_v5 retrieval | 23.00% | [19.5, 26.9] | Phase A |
| **B2_v5 retrieval+evidence** | **37.60%** ← current best | [33.5, 41.9] | Phase A |
| B3_v5 planner+compiler | 23.80% | [20.3, 27.7] | Phase B (negative) |
| B4_v5 controller/verifier | 34.00% | [30.0, 38.3] | Phase C |
| B5_v6 R2 (controller + reranker) | 31.20% | [27.3, 35.4] | Phase R2 (worse) |
| B4_v5 + planner=Qwen3-8B | 27.60% | [23.9, 31.7] | Phase D (negative) |
| B4_v5 + planner=Gemma-12b *partial 253* | 24.11% | n/a partial | Phase D blocker |

### Spider2-Lite FULL (547)

| Baseline | EX | Note |
|---|---|---|
| B0 anchor | structural-only | no execution engine — no BQ/Snowflake creds |
| B3_v4 hybrid retrieval | structural-only | same blocker |

## Paired statistical tests (frozen)

Source: `outputs/tables/paired_significance_*_v*.csv` (committed across phases).

Significant differences vs current best:

- **Spider B0 → B4_v5**: Δ +4.16 pp, McNemar p<0.0001 (paired bootstrap CI [+2.22, +6.19])
- **Spider B2_v5 → B4_v5**: Δ +1.93 pp, p=0.0012 ([+0.77, +3.09])
- **Spider B3_v5 → B4_v5**: Δ +19.73 pp, p<0.0001 (regression fixed)
- **Spider B4_v5 → B5_v6**: Δ −0.10 pp, p=1.0 (statistically identical)
- **BIRD B0 → B2_v5**: Δ +17.20 pp, p<0.0001
- **BIRD B0 → B4_v5**: Δ +13.60 pp, p<0.0001
- **BIRD B2_v5 → B4_v5**: Δ −3.60 pp, p=0.063 (marginal not-significant — the named gap)
- **BIRD B4_v5 → B5_v6**: Δ −2.80 pp, p=0.0005 (R2 hurt)
- **BIRD B4_v5 → B4_v5+planner=Qwen3-8B**: Δ −6.40 pp, p<0.0001
- **BIRD B2_v5 → B4_v5+planner=Qwen3-8B**: Δ −10.00 pp, p<0.0001
- **BIRD B2_v5 → B4_v5+planner=Gemma-12b partial**: Δ −13.83 pp, p=0.00003

## Architecture verdicts (frozen)

1. **Spider winner**: B4_v5 (controller + verifier + repair) on Coder-7B
   single-model setup. Adding R2 reranker is neutral-to-slightly-harmful.
   Adding alternative planners is harmful.
2. **BIRD winner**: B2_v5 (retrieval+evidence direct). The B4_v5 controller
   does NOT close the discrimination gap to B2_v5 — verifier picks C0_anchor
   too aggressively over C2_evidence on BIRD close-call items.
3. **Phase B negative**: plan-then-compile alone is a regression vs free-form
   LLM drafting; needs runtime verifier to be safe (which Phase C added).
4. **Phase R2 root cause**: Qwen3-Reranker-0.6B saturates near 1.0:
   Spider 99.0% items in [0.95, 1.01], BIRD 96.8% — adds no discrimination
   signal, compresses score range, biases toward C0_anchor.
5. **Phase D root cause**: Qwen3-8B in default chat-template config produces
   thinking-mode wrapped output that fails JSON parse → 0/500 valid plans;
   Gemma-12b CUDA OOM on 40 GB with Coder-7B co-resident.

## Known blockers (carried forward)

| Blocker | Detail | Required to fix |
|---|---|---|
| Spider2-Lite execution | no BQ/Snowflake credentials in sandbox | service account + project ID + billing |
| BIRD official R-VES/Soft-F1 | upstream CLI drift; not retried in v11/Phase A-D | inspect evaluator code, adapt wrapper |
| R2 reranker saturation | Qwen3-Reranker-0.6B too coarse | larger reranker (1.7B/4B) or LLM-as-judge |
| Qwen3 planner thinking mode | default config wraps output, breaks JSON parse | `enable_thinking=False` or strip `<think>` tags |
| Gemma-12b OOM | Coder-7B + Gemma-12b + KV cache > 40 GB on big BIRD DBs | larger GPU or INT8/AWQ load |
| Repair noise | 22 Spider repairs / 4 success (18%); 9 BIRD / 0 success | tighten triggers or remove from cost path |

## Frozen artifact paths (do not overwrite)

### Predictions JSONL

`outputs/predictions/`:
- `b{0,1v5,2v5,3v5,4v5,5v6}_qwen2p5_coder_7b_spider_dev_full_predictions.jsonl` (1034 each)
- `b{0,1v5,2v5,3v5,4v5,5v6}_qwen2p5_coder_7b_bird_full_predictions.jsonl` (500 each)
- `b0_qwen2p5_coder_7b_spider2lite_full_predictions.jsonl` (547, structural-only)
- `b3v4_qwen2p5_coder_7b_spider2lite_full_predictions.jsonl` (547, structural-only)
- `b4v5_planner_qwen3_8b_qwen2p5_coder_7b_bird_full_predictions.jsonl` (500 — Phase D negative)
- `b4v5_planner_gemma_12b_qwen2p5_coder_7b_bird_full_predictions.jsonl` (253 — Phase D blocker)

### Master matrices

`outputs/tables/`:
- `final_experiment_master_matrix_fullbench_v1.csv` — Phase A
- `final_experiment_master_matrix_fullbench_v2.csv` — Phase A+B
- `final_experiment_master_matrix_fullbench_v3.csv` — Phase A+B+C
- `final_experiment_master_matrix_fullbench_v4.csv` — Phase A+B+C+R2
- `final_experiment_master_matrix_fullbench_v5.csv` — through Phase D

### Paired significance

`outputs/tables/`:
- `paired_significance_fullbench_v1.csv` — Phase A
- `paired_significance_fullbench_v2.csv` — Phase B
- `paired_significance_fullbench_v3.csv` — Phase C
- `paired_significance_fullbench_v4.csv` — Phase R2
- `paired_significance_phase_d_v1.csv` — Phase D

### Diagnostic / analysis logs

`outputs/logs/`:
- `retrieval_gain_analysis_fullbench_v1.md`
- `planner_harm_analysis_fullbench_v1.md`
- `controller_analysis_fullbench_v1.md`
- `r2_premium_analysis_fullbench_v1.md`
- `planner_swap_analysis_fullbench_v1.md`
- `full_benchmark_scientific_findings.md`
- `full_benchmark_planner_diagnosis.md`
- `full_benchmark_retrieval_diagnosis.md`
- `full_benchmark_production_recommendation.md`

### Plots

`outputs/plots/`:
- `fullbench_overview.png` — Phase A
- `controller_overview_fullbench.png` — Phase C
- `r2_overview_fullbench.png` — Phase R2 ladder
- `phase_d_planner_swap.png` — Phase D
- `retrieval_ablation_fullbench.png`, `planner_vs_anchor_fullbench.png`

### Code modules (committed; do NOT modify in place — use new vN files)

`repo/src/evaluation/`:
- v2/v5/v6 stack: `schema_ir_v2`, `dialect_utils_v2`, `sqlglot_checks_v2`,
  `evidence_store_v2`, `query_rewrite_v2`, `retrieval_hybrid_v2`,
  `join_path_expander_v2`, `schema_linker_bidirectional_v2`,
  `dense_retriever_v2`, `reranker_v2`,
  `difficulty_router_v2`, `planner_v2`, `sql_compiler_v2`,
  `error_taxonomy_v2`, `candidate_generator_v2`, `verifier_ranker_v2`,
  `repair_v2`,
  `baselines_b1_v5`, `baselines_b2_v5`, `baselines_b3_v5`,
  `baselines_b4_v5`, `baselines_b5_v6`

`tools/remote_scripts/`:
- `108_full_benchmark_runner.py` — v11
- `111_phase_a_runner.py`, `112_phase_a_consolidation.py`
- `113_phase_b_runner.py`, `114_phase_b_consolidation.py`
- `115_phase_c_runner.py`, `116_phase_c_consolidation.py`
- `117_phase_r2_runner.py`, `118_phase_r2_consolidation.py`
- `119_phase_d_runner.py`, `120_phase_d_consolidation.py`

## Next-sprint constraints (binding)

1. **No new method may overwrite** any frozen JSONL, table, log, or plot path.
2. New modules must use **`v7` / `b6_v7` / similar** naming.
3. **No partial runs** as final evidence. Partial = debug only.
4. **All claims** must include paired stats vs the relevant frozen baseline.
5. **BIRD discrimination gap** is the named target: B2_v5 = 37.60% must be
   beaten or matched with lower harm by any new BIRD-targeted method.
6. **Spider regression guard**: B4_v5 = 76.69% must not drop. If a method
   helps BIRD but hurts Spider significantly, it must be gated by
   benchmark profile, not deployed unconditionally.
7. **Spider2-Lite numbers** are structural-only until execution credentials
   appear; any execution claim requires the official evaluator path.

## Working environment snapshot

- A100-SXM4-40GB; 39.5 GB free at freeze time
- transformers 5.0.0; torch 2.10.0+cu128; sqlglot 25.20.2
- Bridge URL is ephemeral (rotates per Colab session)
- HF_TOKEN must be re-entered per session
- All v5/v6 modules persisted in `/content/drive/MyDrive/diploma_plan_sql/tools/eval_v2/`
- Predictions persisted in `/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/`

## Spider2-Lite blocker explanation (for new contributors)

Spider2-Lite cannot be measured as standard text-to-SQL EX in this
environment for several layered reasons:

1. **Dialect mismatch**: gold SQL uses BigQuery / Snowflake idioms
   (`EXTRACT`, `DATE_TRUNC`, `ARRAY_AGG`, `STRUCT`, `QUALIFY`, BQ types)
   that SQLite cannot parse or execute. Our pipeline emits SQLite-style
   SQL by default. We have `dialect_utils_v2.transpile()` hooks but they
   are not yet wired into the v5 baselines.
2. **No data warehouse access**: real Spider2-Lite execution requires
   a live BigQuery project with the loaded benchmark datasets and a
   service-account JSON or Snowflake credentials. None are present in
   the Colab sandbox.
3. **Schema scale**: Spider2 DBs have 50–200+ tables and thousands of
   columns; full schema does not fit in 8K context, so retrieval is
   mandatory; lexical retrieval works less well on enterprise camelCase
   identifiers.
4. **Spider2 official evaluator**: ships with the benchmark but expects
   live BQ/SF execution.
5. What we have published: B0 and B3_v4 structural-only metrics
   (safe%, has_select%, avg joins/where/group/order/aggs/subq, avg len)
   for 547 items — useful as "pipeline produces plausible SQL" signal,
   not as accuracy.

The next-sprint Spider2 lane (Priority 4) must declare upfront which
mode it operates in: official-execution (only with creds), oracle-tables
(non-comparable), structural-compatible (no official-score claim), or
blocker-report (when nothing can run).
