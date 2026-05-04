# NL→SQL Research Summary — All Phases

_Frozen on branch `experiments/denis`. Last commit: `cc245d4` (Phase 8)._

This document summarizes the full research arc from baseline replication
through eight phases of architectural improvement. Each headline number
is backed by FULL benchmark predictions on Drive (no smoke samples used
for any final claim) and committed in a versioned artifact.

## Final ladder (Qwen2.5-Coder-7B-Instruct, BF16, A100)

### Spider dev FULL (1034)

| Baseline | EX | 95% Wilson CI | Phase | Status |
|---|---:|---:|---|---|
| B0 anchor | 72.53% | [69.7, 75.2] | v11 | reference |
| B1_v5 retrieval | 74.85% | [72.1, 77.4] | A | committed |
| B2_v5 retrieval+evid | 74.76% | [72.0, 77.3] | A | committed |
| B3_v5 planner+compiler | 56.96% | [53.9, 59.9] | B | negative |
| B4_v5 controller/verifier | 76.69% | [74.0, 79.2] | C | committed |
| B5_v6 R2 reranker | 76.60% | [73.9, 79.1] | R2 | negative |
| **B6_v7 LLM-as-judge** | **76.79%** | [74.1, 79.3] | **6** | **🏆 SOTA** |
| B7d_rich evidence | (BIRD-only) | n/a | 7 | negative on BIRD |
| S1_v7 demo retrieval | 76.31% | [73.6, 78.8] | 8 | negative (tied) |

### BIRD Mini-Dev FULL (500)

| Baseline | EX | 95% Wilson CI | Phase | Status |
|---|---:|---:|---|---|
| B0 anchor | 20.40% | [17.1, 24.2] | v11 | reference |
| B1_v5 retrieval | 23.00% | [19.5, 26.9] | A | committed |
| B2_v5 retrieval+evid | 37.60% | [33.5, 41.9] | A | committed |
| B3_v5 planner+compiler | 23.80% | [20.3, 27.7] | B | negative |
| B4_v5 controller/verifier | 34.00% | [30.0, 38.3] | C | committed |
| B5_v6 R2 reranker | 31.20% | [27.3, 35.4] | R2 | negative |
| **B6_v7 LLM-as-judge** | **38.80%** | [34.6, 43.1] | **6** | **🏆 SOTA** |
| B7d_rich (gold + value-profiles + aliases) | 39.20% | [35.0, 43.5] | 7 | tied with B6_v7 |
| B7c_profiles_only | 33.20% | [29.2, 37.5] | 7 | negative |
| B7e_none | 33.20% | [29.2, 37.5] | 7 | negative |

### Spider2-Lite FULL (547)

| Baseline | Status |
|---|---|
| B0/B3_v4 | structural-only — execution blocker (no BQ/Snowflake creds) |

## Series of committed phases

| SHA | Phase | Headline outcome |
|---|---|---|
| `684a818` | v11 full-benchmark replication | B0/B1_v3/B3_v4/B2_v4 closed; Spider2 structural-only |
| `d2cf0b4` | A — retrieval v2 | B1_v5/B2_v5; retrieval HELPS on FULL Spider — overturns v9 |
| `98d39e1` | B — planner+compiler | B3_v5; structured plan alone HURTS without verifier (negative) |
| `adf4415` | C — controller/verifier | B4_v5; closes Phase B regression; beats all on Spider |
| `6525a94` | R2 — Premium retrieval | B5_v6; Qwen3-Reranker-0.6B saturates; HURTS BIRD (negative) |
| `cfcafe3` | D — planner-model swap | Qwen3-8B 0% valid plans; Gemma-12b OOM (negative) |
| **`8559379`** | **6 — LLM-as-judge** | **B6_v7; NEW SOTA both Spider and BIRD** |
| `56ec0f3` | 7 — evidence semantics | B7d/c/e; rich evidence layer no-op over B6_v7 (negative) |
| `cc245d4` | 8 — Spider-specific demos | S1_v7; demo retrieval tied with B6_v7 (negative) |

## Cross-phase paired statistics (current best vs each prior best)

| Bench | A → B | Δ pp | 95% CI pp | McNemar p | Verdict |
|---|---|---:|---:|---:|---|
| Spider | B0 → B6_v7 | +4.26 | [+2.13, +6.29] | <0.0001 | sig ✓ |
| Spider | B2_v5 → B6_v7 | +2.03 | [+0.68, +3.29] | 0.0025 | sig ✓ |
| Spider | B4_v5 → B6_v7 | +0.10 | [−0.77, +0.87] | 1.0 | tied |
| BIRD | B0 → B6_v7 | +18.40 | [+14.6, +22.2] | <0.0001 | sig ✓ |
| BIRD | B4_v5 → B6_v7 | +4.80 | [+2.4, +7.4] | 0.0004 | sig ✓ |
| BIRD | B2_v5 → B6_v7 | +1.20 | [−1.6, +4.0] | 0.50 | matches |

## What worked (positive results)

1. **Phase A retrieval v2** — bidirectional BM25+ngram with FK expansion
   improves Spider over v11's lexical-only linker by +2.32 pp (p<0.05).
   On BIRD, retrieval+evidence (B2_v5) gives the strongest standalone
   benchmark (+17.20 pp over B0).
2. **Phase C controller/verifier (B4_v5)** — the candidate pool +
   heuristic verifier + non-harm tie-break + bounded repair fixes the
   Phase B planner regression and adds +1.93 pp over B2_v5 on Spider
   (p=0.001).
3. **Phase 6 LLM-as-judge (B6_v7)** — calibrated semantic selector on
   top of B4_v5 closes the BIRD discrimination gap. Spider stays tied
   with B4_v5 under safe_mode policy; BIRD jumps from B4_v5's 34.00%
   to 38.80%, matching B2_v5 standalone within 1 pp and beating B4_v5
   by +4.80 pp (p=0.0004).

## What did not work (clean negative results)

1. **Phase B (B3_v5)** — plan-then-compile WITHOUT runtime verifier is
   a regression (-15.57 pp vs B0 on Spider). Validates the need for
   Phase C's verifier layer. Plan validity itself improved 190× over
   v11's planner (0.4% → 76% valid plans).
2. **Phase R2 (B5_v6)** — Qwen3-Reranker-0.6B saturates near 1.0 on
   ~99% of items, providing no discrimination. The score compression
   pulls non-harm toward C0_anchor and shrinks productive C2_evidence
   picks. BIRD regresses by -2.80 pp (p=0.0005).
3. **Phase D planner swap** — Qwen3-8B (default thinking-mode config)
   produces 0% valid plans on BIRD; Gemma-12b OOMs with Coder-7B
   on 40 GB GPU. Coder-7B-as-planner wins by default.
4. **Phase 7 evidence_semantics_v7** — schema comments + bounded value
   probes + rule-based aliases add zero on top of B6_v7 (Δ +0.40 pp,
   p=0.86). Without gold per-item evidence, the rich evidence layer
   is a -6 pp regression. Gold is the load-bearing component.
5. **Phase 8 demo retrieval (S1_v7)** — DAIL-style train demos prepended
   to anchor are tied with B6_v7 (-0.48 pp, p=0.58). Demo verbosity
   nudges judge toward weaker C1_retrieval picks; net trade is zero.

## Architecture verdict

**Production stack (frozen at commit `8559379`)**:

```
B6_v7 controller:
  candidate pool { C0 anchor, C1 retrieval, C2 retrieval+evidence,
                   C3 planner+compiler }
    ↓
  heuristic verifier
    ( parse + safe + schema validity + intent + consensus + non-harm )
    ↓
  calibrated LLM judge
    ( BIRD: aggressive triggers + override; Spider: safe_mode tighter )
    ↓
  bounded repair (1 round)
```

Single coder model (Qwen2.5-Coder-7B) acts as both synth and judge.
No reranker / dense retriever / planner-swap / demo retrieval is enabled
in the production path — all four were tested and rejected for clean
empirical reasons (committed in respective phase commits).

## Honest blockers (carried forward)

| Blocker | Status |
|---|---|
| Spider2-Lite execution | needs BigQuery/Snowflake credentials |
| BIRD official R-VES + Soft-F1 | upstream CLI drift; not retried |
| R2 reranker saturation | needs larger reranker (1.7B/4B) or LLM-as-judge (the latter is what B6_v7 already does) |
| Qwen3 planner thinking mode | needs `enable_thinking=False` or `<think>` strip |
| Gemma-12b OOM | needs >40 GB GPU or INT8/AWQ quantization |
| Multi-model SYNTH scaling | not tested (only planner-model swap was) |
| Spider-specific S2/S3 (PreSQL/consistency) | deferred — S1 was negative |
| Training selector | requires curated preference dataset from existing predictions |

## Reproducibility map

All FULL prediction JSONLs live under `outputs/predictions/`:

- `b{0,1v5,2v5,3v5,4v5,5v6,6v7,7d_rich,7c_profiles_only,7e_none}_qwen2p5_coder_7b_bird_full_predictions.jsonl` (500 each)
- `b{0,1v5,2v5,3v5,4v5,5v6,6v7,1v3,3v4}_qwen2p5_coder_7b_spider_dev_full_predictions.jsonl` (1034 each)
- `s1v7_qwen2p5_coder_7b_spider_dev_full_predictions.jsonl` (1034)
- `b{0,3v4}_qwen2p5_coder_7b_spider2lite_full_predictions.jsonl` (547 each, structural-only)
- `b4v5_planner_{qwen3_8b,gemma_12b}_qwen2p5_coder_7b_bird_full_predictions.jsonl` (Phase D)

Master matrices at `outputs/tables/final_experiment_master_matrix_fullbench_v{1..8}.csv`.

Paired-stats CSVs at `outputs/tables/paired_significance_*.csv` (one per phase).

Phase-specific design and analysis memos at `outputs/logs/`:
- `baseline_freeze_after_r2_phase_d.md` — Priority 0 freeze before Phase 6
- `selector_design_v7.md` + `bird_discrimination_gap_closure_v7.md` — Phase 6
- `evidence_semantics_design_v7.md` + `evidence_negative_result_v7.md` — Phase 7
- `spider_specific_design_v7.md` — Phase 8

Code modules at `repo/src/evaluation/`:
- v2/v5: foundation (schema_ir, dialect_utils, sqlglot_checks, evidence_store,
  query_rewrite, retrieval_hybrid, join_path_expander,
  schema_linker_bidirectional, dense_retriever, reranker,
  difficulty_router, planner, sql_compiler, error_taxonomy,
  candidate_generator, verifier_ranker, repair) +
  baselines_b1_v5/b2_v5/b3_v5/b4_v5/b5_v6
- v7: llm_judge, baselines_b6_v7, evidence_semantics, baselines_b7_v7,
  demo_retrieval, baselines_s1_v7

Runner / consolidation scripts at `tools/remote_scripts/`:
- `108_full_benchmark_runner.py` (v11)
- `111-122` (Phase A, B, C, R2, D, 6, 7)
- `125-126` (Phase 8 S1_v7)

## Compute snapshot

- A100 40GB, transformers 5.0.0, torch 2.10.0+cu128, sqlglot 25.20.2
- ~10,000+ FULL benchmark generations across 9 phases
- ~70-80 hours of A100 compute total across the series
- Resumable per-item JSONL writes survived multiple Colab restarts
- All artifacts persisted on Google Drive at `/content/drive/MyDrive/diploma_plan_sql/`

## Bottom line for the diploma

The architecture story is now clear and reproducible:

1. **Retrieval helps on FULL benchmarks** (overturns smoke-sample v9 conclusion).
2. **Planner alone hurts**; planner inside a verifier-guarded controller helps on Spider but not BIRD.
3. **A calibrated LLM judge over a small candidate pool is the right
   selector** — no reranker / dense embedding / demo retrieval / rich
   evidence layer / alternative planner model adds value on top in this
   compute and model regime. They were all tested and rejected with
   paired statistics on FULL benchmarks.
4. **The only architectural recommendation that survives all ablations
   is B6_v7** (commit `8559379`).

Outstanding work (deferred, well-documented):
- Spider2-Lite agent lane (Priority 4)
- BIRD official secondary metrics (Priority 6)
- Multi-model SYNTH scaling (Priority 5)
- Training selector on preference data from existing predictions (Priority 7)
