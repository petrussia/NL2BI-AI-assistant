# Error Taxonomy (smoke25)

Generated at: 2026-04-25T17:10:59.663564+00:00

Bucket counts by baseline:

| Bucket | B0 | B1 |
|---|---|---|
| `unchanged_correct` | 24 | 24 |
| `wrong_aggregation` | 1 | 1 |

## Bucket definitions

- **unchanged_correct** — execution_match=True, both rows agree (the happy path).
- **syntax_or_runtime_error** — SQL did not execute (SQLite OperationalError, ProgrammingError, etc.).
- **sqlite_timeout** — SQL executed but timed out (>8s).
- **wrong_join_or_table** — SQL executed, but FROM/JOIN tables differ from gold.
- **wrong_aggregation** — same tables, but COUNT/AVG/SUM/MIN/MAX/GROUP BY presence differs from gold.
- **wrong_filter_or_predicate** — same tables and aggregation, but WHERE/HAVING presence differs.
- **result_mismatch_subtle** — executable, same tables/agg/filters, but rows differ (column choice, alias, ordering when ambiguous, etc.).
- **unexpected** — execution_match=True but executable=False (should not happen).

## Per-cell errors (smoke25 union of B0 and B1)

| idx | db_id | B0 bucket | B1 bucket |
|---|---|---|---|
| 16 | concert_singer | `wrong_aggregation` | `wrong_aggregation` |
