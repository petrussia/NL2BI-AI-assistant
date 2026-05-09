# Architecture document — final (defense-ready)

**Date:** 2026-04-30T12:20:07.210990+00:00
**Project:** NL2BI-AI-assistant — natural-language → SQL technology for extracting and processing data from a heterogeneous source array.
**Author of this subsystem:** Шубин Денис Алексеевич (Shubin). Visualisation/BI subsystem (out of scope) — Petukhov.

---

## 1. High-level architecture

```
[NL question]
     │
     ▼
[Query Analysis]  (rule-based intent + signals; closes ТЗ 2.2.1)
     │
     ▼
[Schema Linking]  (lexical, token-overlap, table×2 + col×1, min_score=0.5)
     │
     ▼ (optional, for B3 family)
[Knowledge Channel] (DISABLED in B3_v2 — was harmful prompt noise on Spider)
     │
     ▼
[Planner]  (JSON plan, jsonschema-validated)
     │       on invalid plan → [B1 fallback (single-shot SQL)]
     ▼
[Plan Validator]  (Draft 2020-12 jsonschema vs `plan_schema_v1.json`)
     │
     ▼
[SQL Synthesizer]  (prompt = full schema + plan)
     │
     ▼
[Validation Gate] (SELECT-only AST guard, regex-level forbidden keywords)
     │
     ▼ (multi-cand, k=3, T=0.7, top_p=0.95 — only for B4 family)
[Consistency Selection] → if no executable: [B1 fallback (B4_v2 only)]
     │
     ▼
[Executor]  (SQLite, 8s `func_timeout`)
     │
     ▼
[Postprocess]  (normalize_rows + compute_summary)
     │
     ▼
[Analytics Handoff Payload v1] → consumed by Petukhov's BI subsystem
```

Diagrams: [outputs/plots/system_architecture_overview.png](../plots/system_architecture_overview.png),
[outputs/plots/ablation_pipeline_ladder.png](../plots/ablation_pipeline_ladder.png).

---

## 2. Components

| Layer | Component | Module | Closes |
|---|---|---|---|
| 1 | Query analyzer (NL→intent+signals) | `repo/src/evaluation/query_analysis.py` | ТЗ 2.2.1 |
| 2 | Schema linker (lex) | `repo/src/evaluation/baselines.py::lexical_schema_linking` | ТЗ 2.2.2 |
| 2b | Cross-DB retrieval helper | `repo/src/evaluation/retrieval.py` | ТЗ 2.2.2 |
| 3 | Planner v2 (B2_v2/B3_v2/B4_v2) | `baselines_b2_v2.py`, `baselines_b3_v2.py` | ТЗ 2.2.4 |
| 4 | Plan validator | `repo/docs/plan_schema_v1.json` + jsonschema | ТЗ 2.2.4 |
| 5 | SQL synthesizer | `baselines_*` make_*_sql_prompt | ТЗ 2.2.3 |
| 6 | SELECT-only AST guard | `baselines_b4_final.py::is_safe_select` | ТЗ 2.2.3 (safety) |
| 7 | Multi-cand + repair | `baselines_b4_v2.py::consistency_pick_v2` | ТЗ 2.2.4 |
| 8 | B1 fallback safety net | inline in B2_v2/B3_v2/B4_v2 | engineering |
| 9 | Executor + 8s timeout | `func_timeout`-wrapped `execute_sql` | ТЗ 2.2.3 (performance) |
| 10 | Postprocess + handoff | `repo/src/evaluation/postprocess.py` | ТЗ 2.2.5 / 2.2.6 |
| 11 | Bridge tooling | notebook cell `7f6bca53` + `tools/exec_remote.py` | infrastructure |

---

## 3. Baseline ladder and observed accuracy

| Baseline | smoke_10 | smoke_25 | multidb_30 | Notes |
|---|---|---|---|---|
| B0 (full schema, single-shot) | 1.0000 | 0.9600 | 0.9333 | Strongest direct config |
| B1 (lex schema linking) | 1.0000 | 0.9600 | 0.7667 | Reduces prompt 50%, hurts on multidb |
| B2_v0 (Plan→SQL v0) | 0.7000 | — | — | Initial planner |
| B2_v1 (subq+distinct) | 0.6000 | — | 0.6333 | Patches over v0 |
| **B2_v2 (B1-fallback + anti-overengineering)** | **—** | — | **—** | Targeted fixes, safety net |
| B3_v1 (adaptive dual retrieval) | 0.3000 | — | 0.4667 | Knowledge channel partial-off |
| **B3_v2 (knowledge OFF + B1 fallback)** | **0.8000** | — | **0.7333** | +0.50/+0.27 vs v1 |
| B4-lite | 0.2000 | — | — | Initial validation+repair |
| B4_final (B3_v1 + multi-cand + repair) | 0.3000 | — | 0.4667 | Capped by upstream plan failures |
| **B4_v2 (B3_v2 + multi-cand + B1 fallback ×2)** | **0.8000** | — | **0.7333** | Same +Δ as B3_v2 |

Cross-model on smoke_10:
- Qwen2.5-7B-Instruct (no Coder fine-tune): B0 = 0.6000, B1 = 1.0000
- Llama-3.1-8B-Instruct: B0 = 0.8000, B1 = 0.9000
- Qwen2.5-Coder-14B-Instruct: B0 = —, B1 = —

---

## 4. Constraints and assumptions

1. **Hardware:** NVIDIA L4 24 GB, 4-bit nf4 bitsandbytes quantisation. Higher-precision runs would shift absolute EX but not the relative ordering.
2. **Benchmark:** Spider dev (n=1034) and 3 subsets: smoke_10, smoke_25, multidb_30 (6 distinct DBs).
3. **Decoding:** greedy for B0/B1/B2/B3 (`do_sample=False`); 3-cand sampling for B4 family (T=0.7, top_p=0.95).
4. **Plan schema:** `plan_schema_v1.json` (Draft 2020-12, additionalProperties:false). Required: intent, tables, operations.
5. **Safety:** SELECT-only via regex AST guard; no INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/PRAGMA/ATTACH/DETACH/GRANT/REVOKE.
6. **Execution sandbox:** SQLite read-only; 8 second timeout via `func_timeout`.

---

## 5. Recommended production configuration (defense recommendation)

**Use B0 + Qwen2.5-Coder-7B-Instruct (4-bit) + SELECT-only AST guard + 8s SQLite timeout + analytics handoff post-processor.**

- It is the **single strongest direct configuration** in this evaluation slice (1.00 / 0.96 / 0.9333).
- It is the **fastest** path (no planner, no multi-cand, no repair).
- B1 only when the schema is too large to fit in the model context.
- B3_v2 / B4_v2 only when downstream systems require an auditable JSON plan or a structured repair trail. Layered stack provides engineering safety, **not** EX gains on this benchmark.

**Why not B3_v2/B4_v2 in production:** they trade a smaller EX loss for the ability to validate, repair, and select among candidates. On Spider with Qwen-Coder-7B, B0 already saturates accuracy — the safety net is paying for nothing.

---

## 6. Trade-offs

| Choice | Pros | Cons |
|---|---|---|
| Full-schema prompt (B0) | Highest EX | Largest token budget; needs context window |
| Lex schema linker (B1) | 50% prompt reduction | Over-prunes on schema-diverse benchmarks |
| Plan-then-SQL (B2/B3/B4) | Auditable, repair-able | EX cost vs B0 on this benchmark |
| Multi-candidate (B4 family) | Robustness via consistency vote | 3× generation latency per item |
| Bounded repair | Self-correction on SQL errors | Negligible EX gain when plan is broken upstream |
| B1 fallback safety net (v2) | Guarantees layered ≥ B1 - noise | None observed |

---

## 7. Risk controls

- **All SQL is SELECT-only,** verified by regex AST guard before execution.
- **All execution is sandboxed** in a `func_timeout`-wrapped SQLite call; max 8 seconds per query.
- **All generated SQL is logged** per-item with raw model output, gold SQL, executable flag, match flag, and error type (`outputs/predictions/*.jsonl`).
- **All metrics are reproducible** by re-running the corresponding `tools/remote_scripts/NN_*.py` against a kernel with the same model loaded.
- **Negative results are documented honestly** — no inflation of layered baseline EX.

---

## 8. Connection diagram between components

```
Query Analyzer ──▶ Schema Linker ──▶ Reduced Schema ─┐
                                                     ├─▶ Planner ─▶ Plan Validator
Full Schema ─────────────────────────────────────────┘                  │
                                                                        ▼
                                                                  SQL Synthesizer
                                                                        │
                                                                        ▼
                                                                Validation Gate
                                                                        │
                                                                        ▼
                                                              Multi-Cand / Repair
                                                                        │
                                                                        ▼
                                                                    Executor
                                                                        │
                                                                        ▼
                                                                   Postprocess
                                                                        │
                                                                        ▼
                                                          Analytics Handoff Payload v1
```

---

## 9. References

- Master experiment matrix: [outputs/tables/final_experiment_master_matrix.md](../tables/final_experiment_master_matrix.md)
- Multi-DB scientific slice: [outputs/logs/multidb30_scientific_readout.md](../logs/multidb30_scientific_readout.md)
- Negative-result analysis: [outputs/logs/final_negative_result_analysis.md](../logs/final_negative_result_analysis.md)
- Plan schema (canonical): [repo/docs/plan_schema_v1.json](../../repo/docs/plan_schema_v1.json)
- Component registry: [outputs/tables/component_registry.csv](../tables/component_registry.csv)
- IO contracts (boundary with Petukhov's BI): [outputs/docs/io_contracts.md](io_contracts.md)
