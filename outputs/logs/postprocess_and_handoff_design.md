# Postprocess and Handoff Design

Date: 2026-04-29T14:36:55.816591+00:00

## Purpose
Closes ТЗ items **2.2.5** (предварительная обработка и агрегация результатов) and
**2.2.6** (передача результатов в подсистему аналитического представления).

## Layer placement
Sits AFTER any baseline (B0..B4) executes its generated SQL. Takes the raw
SQLite row tuples and produces a structured analytics payload.

## API
- `normalize_rows(rows, column_names=None)` — coerce row-tuples to dicts; type-coerce numeric strings; preserve nulls.
- `compute_summary(rows)` — per-column descriptive summary (count / distinct / min / max / sum / mean for numeric, top values for categorical).
- `build_analytics_payload(...)` — assembles the canonical handoff JSON. Includes source metadata (baseline, model, subset, idx, db_id, question, generated_sql), normalized rows, and summary.
- `export_payload_json(payload, target_dir, basename)` and `export_payload_csv(...)` — persist the payload to disk in the analytics-friendly format.

## Handoff contract (`schema_version: v1`)

```json
{
  "schema_version": "v1",
  "produced_at": "<ISO8601 UTC>",
  "source": {
    "baseline": "B3",
    "model": "Qwen/Qwen2.5-Coder-7B-Instruct",
    "subset": "smoke_10",
    "idx": 0,
    "db_id": "concert_singer",
    "question": "How many singers do we have?",
    "generated_sql": "SELECT COUNT(*) FROM singer;",
    "gold_sql_present": true
  },
  "rows": [{ "c0": 6 }],
  "summary": {
    "row_count": 1,
    "columns": {"c0": {"count": 1, "null_count": 0, "distinct_count": 1, "dtype": "numeric", "min": 6, "max": 6, "sum": 6, "mean": 6.0}}
  },
  "n_rows": 1,
  "is_executable": true,
  "notes": []
}
```

## Why this contract
- Reporting subsystem (the partner project) accepts JSON; it can also ingest the parallel CSV mirror.
- `source.*` block makes every payload self-describing — no need to look up which baseline produced it.
- `summary` is computed once at handoff so the BI side does not have to re-aggregate trivial stats.
- `schema_version` lets the contract evolve without silent breakage.

## What this module deliberately does NOT do
- Authentication / authorization (left to the consuming subsystem).
- Schema-aware semantic enrichment (e.g., resolving FK references) — would require schema metadata at handoff; deferred.
- Streaming for large result sets (current impl materialises everything in memory; OK for benchmark sizes ≤ 1000 rows).
- Schema-version migration (only v1 exists now).
