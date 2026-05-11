# v0.13 — Planner+Emitter vs Anchor: expanded testbed comparison

50 hand-written queries (10 per source × 5 sources), four difficulty levels:
- **L1 simple**  — count, top-n, single-table filter, single GROUP BY
- **L2 medium** — 2-table JOIN, time series, HAVING
- **L3 hard**   — multi-hop JOIN, subquery/CTE, multi-aggregate

## Setup

| Stack | Architecture | VRAM | Median latency |
|---|---|---:|---:|
| **Anchor** | Qwen2.5-Coder-7B-Instruct BF16, single-shot | 15 GB | ~1.0 s |
| **Planner+Emitter** | Qwen3-Coder-30B-A3B-Instruct BF16 (planner) → Qwen2.5-Coder-7B-Instruct BF16 (emitter) | 74 GB | ~3.7 s |

Both on the same NVIDIA RTX PRO 6000 Blackwell (95 GB VRAM).

## Results

| Metric | Anchor | Planner+Emitter | Δ |
|---|---:|---:|---:|
| **Hard SQL failures** | 4/50 (8%) | **3/50 (6%)** | −1 |
| **Full success (rows ≥ 1)** | 37/50 (74%) | **39/50 (78%)** | +2 |
| **Valid SQL ratio (incl. partials)** | 46/50 (92%) | **47/50 (94%)** | +2 pp |

## Per-source breakdown

| Source | Anchor | Planner+Emitter |
|---|---|---|
| `demo_concert_singer` (Spider 1.0) | 9 success / 1 partial / 0 fail | 9 / 1 / 0 |
| `bird_student_club` (BIRD) | 8 / 1 / 1 | 8 / 1 / 1 |
| `spider2_asana_dbt` (DuckDB) | 3 / 6 / 1 | 3 / 6 / 1 |
| `moscow_open` (SQLite) | 9 / 1 / 0 | **10 / 0 / 0** |
| `northwind_ru` (PostgreSQL) | 8 / 0 / 2 | **9 / 0 / 1** |

## Where planner shines

Wins on:
- `moscow_open L3 mhop join` ("самые загруженные станции в Центральном округе") —
  anchor returned 0 rows, planner properly traced district→okrug FK
- `northwind_ru L3 mhop join` ("выручка по федеральным округам") —
  anchor missed the 3-hop FK path (заказы → клиенты → регионы → федеральный_округ),
  planner walked it correctly

## Where planner doesn't help

- **`spider2_asana_dbt`** — model isn't the bottleneck, the data is. The
  fixture has only 1 task in `task_data`; most aggregations correctly return
  0 rows (partial_success status). Both models hit the same data ceiling.
- **`bird_student_club` L3 subquery** — both stacks miss this; planner
  picked a slightly different decomposition that introduced a typed
  comparison error.
- **`northwind_ru` L2 having** — both stacks generate slightly wrong column
  references on this specific aggregation.

## Recommendation for diploma defense

- **Default to Anchor (Qwen2.5-Coder-7B BF16)** for demo speed — 1 s
  median latency vs 3.7 s. Already 92% valid SQL across 50 hand-written
  queries.
- **Switch to Planner+Emitter** for "complex multi-hop" demonstration
  questions, especially against Northwind RU and Moscow Open Data. The
  extra 2.7 s buys multi-hop FK traversal that the 7B alone misses.
- **Spider2 / asana** is a data-density problem, not a model problem.
  Either seed denser asana data or document this as a Spider2-Lite
  characteristic (Denis's logs flag the same — Spider2 needs evidence
  retrieval, not just bigger models).
