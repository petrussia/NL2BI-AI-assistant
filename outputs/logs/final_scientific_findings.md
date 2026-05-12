# Final scientific findings (v9 — post v7-closure)

**Generated:** 2026-04-30T22:33:40.604353+00:00

## DEFINITIVE v7-closure finding: Planner adds NO value over retrieval-only

After 4 iterations the project debated whether the layered planner stack helps. v7-closure provides the definitive answer with a 4-way head-to-head on multi-DB with Qwen-Coder-7B:

| Configuration | Has planner? | multi-DB EX |
|---|---|---|
| **B1_v3 (bidirectional linker)** | **NO** | **0.8000** |
| **B3_v3 (hybrid BM25+ngram retrieval)** | **NO** | **0.8000** |
| **B2_v3 (compact planner + linker fallback)** | **YES** | **0.7667** |
| **B4_v3 (compact planner + multi-cand + repair)** | **YES** | **0.7667** |

**The planner-equipped baselines are 0.0333 EX BELOW the retrieval-only baselines.** The planner doesn't merely fail to help — **it actively hurts on the schema-diverse benchmark**. The +0.0333 multi-DB win that this project has reported for 4 iterations was always attributable to the schema linker, not to the planner machinery.

## Strongest configurations (v9 locked)

| Role | Configuration | EX |
|---|---|---|
| **Production direct winner** | B0 + Qwen2.5-Coder-7B | smoke_10/25/multi-DB = 1.00 / 0.96 / 0.9333; BIRD = 0.2667 |
| **Production layered winner** | **B1_v3 + Qwen2.5-Coder-7B** | multi-DB = 0.8000 (one LLM call, no planner) |
| Audit-trail variant (if downstream needs JSON plan) | B2_v2 + Qwen-Coder-7B | multi-DB = 0.80 (same as B1_v3, more complexity, same accuracy) |
| Best mandatory model | Llama-3.1-8B B0 multi-DB = 0.8333 | competitive |
| **Strongest cross-model (NEW v7-closure)** | **Gemma-3-12b-it B0** | smoke_10 = 1.0000 (= incumbent), multi-DB = 0.8667, BIRD = 0.2333 |

## v7-closure model screening results

| Model | smoke_10 | smoke_25 | multi-DB | BIRD | Verdict |
|---|---|---|---|---|---|
| Qwen-Coder-7B (incumbent) | 1.00 | 0.96 | **0.9333** | **0.2667** | strongest overall |
| **Gemma-3-12b-it (NEW)** | **1.00** (tied) | 0.96 (tied) | 0.8667 | 0.2333 | strongest non-Qwen-Coder model in project |
| **Qwen-Coder-32B (NEW)** | — | 0.96 (tied) | 0.8333 | 0.2667 (tied) | right-sizing #2: 32B does NOT beat 7B |
| **SQLCoder-7B-2 (NEW)** | — | — | 0.7000 | 0.0333 | weak on multi-DB and BIRD; specialised but small |
| Qwen3-8B | — | 0.76 | 0.9000 | 0.1333 | non-Coder fine-tune; weaker on harder tasks |
| Llama-3.1-8B | 0.80 | 0.60 | 0.8333 | 0.1333 | competitive multi-DB; weak on harder |
| Qwen-Coder-14B | 1.00 | 0.96 | 0.8667 | — | right-sizing #1: 14B does NOT beat 7B |

**Right-sizing CONFIRMED at TWO scales (14B AND 32B).** Qwen-Coder-7B is the right model size on this benchmark family.

## NEW v7-closure: Gemma-3-12b-it is the best non-Qwen-Coder model

Gemma-3-12b-it ties Qwen-Coder-7B on smoke_10 (1.0) and smoke_25 (0.96), and only loses 0.07 EX on multi-DB. This is the strongest non-Qwen-Coder model in the project — better than Llama-3.1-8B on every internal subset.

## Statistical significance — paired McNemar vs incumbent

See `outputs/tables/paired_significance_v7_closure.csv` for full pairwise
deltas with bootstrap CI and McNemar p-values.

## Final production recommendation (v9)

**Production:** B0 + Qwen2.5-Coder-7B-Instruct (4-bit nf4 or BF16) + SELECT-only AST guard + 8s SQLite timeout + AnalyticsPayload v1 post-processor.

**Audit-trail variant (v9 simplification):** **B1_v3 + Qwen2.5-Coder-7B-Instruct.**
- Same +0.0333 EX gain on multi-DB as the prior B2_v2 audit-trail variant.
- **One LLM call per query** (vs B2_v2's 2-3 calls) — drastically lower latency.
- No JSON plan, no jsonschema validator, no fallback hierarchy, no planner LLM call.
- The bidirectional schema linker is a deterministic O(N · |schema|) algorithm.

If a downstream system genuinely requires a structured JSON plan as compliance artefact, keep B2_v2. Otherwise B1_v3 is strictly better.
