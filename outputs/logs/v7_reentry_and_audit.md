# v7 reentry and audit

**Generated:** 2026-04-30T19:58:28.697652+00:00

## Recovery state (verified)
- Bridge: live (`tools/.bridge_url` → /health 200, pid 1622)
- GPU: NVIDIA A100-SXM4-80GB (84.65 GB free)
- HF_TOKEN: SET
- Drive: mounted, all artefacts intact
- Master matrix: 98 rows (62 internal_core + 36 external_validation)
- Repo modules: 16 (`baselines.py` + B1r/B2/B2_v1/B2_v2/B2r/B3/B3_v1/B3_v2/B4/B4_final/B4_v2 + postprocess + query_analysis + retrieval + external_benchmark_adapters)
- External benchmarks: bird_mini_dev (raw + processed + manifests), spider2_lite (raw + processed + manifests)

## Reuse policy
- All 98 existing master-matrix cells **reused as-is** (numbers authoritative).
- v7 adds **new baseline family** (B1_v3 / B3_v3 first; B2_v3 / B4_v3 only if screening signals warrant).
- v7 adds **new model** (Qwen3-8B as priority new comparator; Gemma + 32B + SQLCoder gated by signal).

## v7 plan (realistic, prioritized)
1. **Adapters v2** — BIRD: use evidence + database_description csvs as retrieval-doc source. Spider2-Lite: oracle-tables note (no fake EX).
2. **Retrieval hybrid** — BAAI/bge-m3 dense + BM25 sparse + RRF fusion (cheap default; Qwen3-Embedding-8B premium deferred to expansion if cheap is insufficient).
3. **Bidirectional schema linking** — table↔column dual-pass with link_confidence.
4. **B1_v3 + B3_v3 modules** — the *key* retrieval-only ablation. B2_v3 / B4_v3 added only if B1_v3/B3_v3 signal expansion.
5. **Screening BG** — Qwen-Coder-7B × {B1_v3, B3_v3} × {smoke_25, multidb_30, bird_minidev_30} = 6 cells. Then Qwen3-8B × {B0, B1_v3} × same 3 subsets = 6 more cells. Total 12 screening runs.
6. **Stop rule check** — apply user-specified rules before expansion.
7. **Expansion** if any model/baseline passes screening.
8. **Statistics + plots + master matrix v8 + REPORT v8 + tarball.**

## Out-of-scope this iteration (honest)
- DeepSeek runs — environmental blocker stands; will not retry without fresh kernel.
- Qwen2.5-Coder-32B — only if signal demands it; heavy load on A100, low scientific marginal value (right-sizing already shown for 14B vs 7B).
- Gemma-3-12b-it — gated; will probe access, skip if blocked.
- SQLCoder-7B-2 — special prompt format needed; will adapt only if Lane D screening signal demands.
- Qwen3 thinking-mode escalation — test only on hard cases if warranted by signal.
- Premium Qwen3-Embedding-8B + Qwen3-Reranker-8B retrieval — only if cheap stack exhausted.

## Authoritative source preserved
`outputs/tables/final_experiment_master_matrix.csv` — 98 rows, NOT to be overwritten;
v7 cells append cleanly with `_v3` suffix in baseline names + new `baseline_version=v3` column.
