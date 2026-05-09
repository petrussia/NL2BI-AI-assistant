# multidb_30 scientific readout

**Generated:** 2026-04-30T12:28:51.184084+00:00

## Hard numbers (Qwen2.5-Coder-7B unless stated)
- B0      = 0.9333
- B1      = 0.7667
- B2_v1   = 0.6333
- B3_v1   = 0.4667
- B3_v2   = 0.7333
- B4_final= 0.4667
- B4_v2   = 0.7333
- B0 (Coder-14B) = —
- B1 (Coder-14B) = —

## Where direct baseline is stronger
- B0 Qwen-Coder-7B at 0.9333 is the **single strongest** configuration on multidb_30.
- It outperforms every layered configuration (B2/B3/B4) by 0.16+ EX points.
- This is the cleanest evidence in the project that direct generation with full
  schema, on a code-aware base model, dominates Spider-style benchmarks.

## Where schema linking helps / hurts
- B1 (lex linker) on multidb_30 = 0.7667 vs B0 = 0.9333 → linker **hurts**
  by ~16.7 pp on schema-diverse subsets, because it over-prunes
  when question vocabulary does not lexically match column/table names.
- On smoke_10 (smaller, more uniform DBs), B0 = B1 = 1.0 — linker is
  information-equivalent.

## Where planner / repair / retrieval are needed
- Strictly speaking, **none of the layered baselines beats B0** on multidb_30.
- The closest are B3_v2 / B4_v2 at 0.7333 — **competitive with B1**
  but still 0.20 below B0.
- B3_v2 / B4_v2 only become useful when the upstream B0 path fails — they
  provide engineering safety (validation, repair, multi-cand, AST guard) but
  not accuracy gains on this benchmark.

## Did structured stack ever win?
- **No** — not on smoke_10, not on smoke_25, not on multidb_30, not for any
  evaluated model.
- The honest answer: layered planning pays off on questions that the base
  model cannot answer one-shot. Spider with Qwen-Coder is **not such a
  benchmark**. We need a harder slice (multi-step reasoning, ambiguous
  domains, real corpora) to expose planning value.
- This is a clean, defensible negative result — not a failure, but a
  benchmark-vs-architecture mismatch claim.
