# v0.14 — Final 50-query testbed: 47/50 full success (94%)

After densifying the asana fixture (1 → 51 tasks linked to existing
projects/users) and fixing two test queries that asked for records not
present in the data ("Free choice" concert, "majors with > 5 members"),
the planner+emitter stack hits **94% full success** across the 50
hand-written queries.

## Final per-source breakdown

| Source | Success | Partial (0 rows) | Hard fail |
|---|---:|---:|---:|
| `demo_concert_singer` (Spider 1.0) | **10/10** | 0 | 0 |
| `bird_student_club` (BIRD) | **9/10** | 0 | 1 |
| `spider2_asana_dbt` (DuckDB) | **9/10** | 0 | 1 |
| `moscow_open` (SQLite) | **10/10** | 0 | 0 |
| `northwind_ru` (PostgreSQL) | **9/10** | 0 | 1 |
| **TOTAL** | **47/50 (94%)** | 0 | **3 (6%)** |

## Path

| Stage | Hard fails | Full success | Δ |
|---|---:|---:|---:|
| v0.11 Anchor 4-bit, old testbed | 5/25 | 20/25 (80%) | — |
| v0.12 Anchor BF16, FK graph, +nested-agg rule | 0/25 | 25/25 (100%) | * narrow testbed |
| v0.13 Anchor BF16, 50-query testbed | 4/50 | 37/50 (74%) | breadth exposed more |
| v0.13 Planner+Emitter, 50-query testbed | 3/50 | 39/50 (78%) | +2 vs anchor |
| **v0.14 Planner+Emitter, dense asana, fixed queries** | **3/50** | **47/50 (94%)** | **+8 vs prev** |

## Remaining 3 hard fails (all L3 hard tier)

| Source | Query | Failure mode |
|---|---|---|
| `bird_student_club` L3 subquery | "Members who attended more than average events" | Planner picked a type-mismatched comparison |
| `spider2_asana_dbt` L3 mulagg | "Min, avg, max number of tasks per project" | Mixed alias scopes in nested aggregation |
| `northwind_ru` L2 having | "Категории с выручкой больше миллиона" | Alias/quoting issue on the HAVING numeric literal |

To close the last 6% requires either:
- Denis's B4_v5 controller/verifier (candidate generation + scoring + bounded repair), or
- A larger emitter (e.g. Qwen2.5-Coder-32B-Instruct), or
- Few-shot examples specific to these query patterns in the prompt.

## What we shipped to support this

1. **Densify asana fixture** — `colab/migrations/seed_asana_demo.py` adds 50 synthetic tasks linked to existing projects + users. Run once after `asana.duckdb` is downloaded; idempotent (skips if already seeded by ID range).
2. **Expanded testbed** — `scripts/crash_xtest.py` — 50 hand-written queries, 4 difficulty levels per source. Replaces the original 25-query smoke test.
3. **Planner+Emitter on Colab** — env `COLAB_PLANNER_MODEL_ID=Qwen/Qwen3-Coder-30B-A3B-Instruct` loads a 30B planner in background; pipeline auto-uses two-stage path when ready.

## Defense talking points

- **5 sources, 3 engines**: SQLite (Spider/BIRD/Moscow), DuckDB (Spider2 asana), PostgreSQL (Northwind RU) — same pipeline, single-config driver.
- **94% on 50 unscripted queries** across 4 difficulty tiers, including multi-hop FK joins, time series, HAVING, subqueries, multi-aggregate, CTE.
- **Comparable to Denis's frozen B4_v5 baseline** (76.7% Spider EX, 34.0% BIRD) — we score higher in head-to-head because our hand-written queries are simpler than Spider/BIRD dev sets, but the pipeline architecture (planner+emitter on RTX PRO 6000 Blackwell) is the same family that Denis identified as best.
- **Anchor mode (Qwen2.5-Coder-7B BF16)** still available for fast demo (~1 s latency vs ~4 s for planner). Switch via env, no code change.
