# Spider2-Lite-BQ v16 — analysis

_Generated: 2026-05-08_

## Headline

**chosen_schema_valid = 6/10 (60%)** — first time any non-DBT Spider2
lane cleared the user's 30% schema_valid gate. Constrained repair
helped 6 tasks. v12 was 1/10; v16 is 6/10.

## What worked

| signal | impact |
|---|---|
| Constrained substitution (top-1 catalog match) | 6 tasks moved from `schema_invalid` → `schema_valid` after deterministic identifier replacement |
| Multi-signal scoring (Levenshtein + token overlap + ngram + question-overlap) | suggestions made by validator are now actionable |
| Per-task try/except | no batch crashes |
| Wall time | 739s vs v12's 1232s — repair without extra LLM rounds is faster |

## What didn't move

`parse_ok = 0/10`. The 6 schema-valid candidates were sent to BQ
`dry_run` and 5 got `object_not_found`, 1 got runtime `syntax`.

The 5 `object_not_found` mean: validator says "this table+column
exist in catalog", live BigQuery says "I don't see that table". This
is **catalog/live divergence**:
- The Drive `resource/databases/bigquery/<DB>/<DATASET>/<table>.json`
  files were generated from sample-rows snapshots and may name tables
  that have since been deprecated, restricted, or never existed in
  the live `bigquery-public-data` project.
- Our SA may not have access to some of the named datasets.
- BQ regional / project-level visibility may differ from what the
  catalog metadata claims.

## Per-task pattern (from candidates.jsonl)

For BQ pilot10 (30 candidate slots = 10 tasks × 3 candidates):
- Total candidates: 30
- Reached `schema_valid=True`: 12 candidates (across 6 tasks)
- After live `dry_run`: 0 candidates passed
- The 5 `object_not_found` tell us WHICH catalog tables are stale —
  list available in `predictions.jsonl` for follow-up catalog refresh.

## Recommended next move

Refresh BQ catalog from live `INFORMATION_SCHEMA.TABLES` of each
target project at startup, instead of trusting the static JSON
dump. Estimated impact: parse_ok could move from 0/10 to 3-5/10 on
the same pilot — possibly clearing both gates and unlocking BQ FULL.

Code sketch:
```python
def refresh_bq_catalog_for_project(project, bq_client):
    sql = (f"SELECT table_catalog, table_schema, table_name "
           f"FROM `{project}.region-us.INFORMATION_SCHEMA.TABLES`")
    job = bq_client.query(sql, ...)
    return {row.table_name.upper() for row in job.result()}
```

This intersects with the existing v16 catalog and removes any table
that BQ doesn't actually expose. Flagged as a Phase 17 priority.

## Source breakdown

C0_direct=5, C1_retrieval=3, C2_cte=2 — model picks varied; selector
prefers schema-valid candidates with C3_repaired bias when applicable.
