# B3 Retrieval Audit (smoke10)


PROXY DOCS — synthetic per-table descriptions derived from schema metadata. Not real enterprise documentation.

| idx | db_id | schema_selected | reduction | knowledge_top3 (table_idx, score) |
|---|---|---|---|---|
| 0 | `concert_singer` | ['stadium', 'singer', 'concert', 'singer_in_concert'] | 1.00 | [(0, 0), (1, 0), (2, 0)] |
| 1 | `concert_singer` | ['stadium', 'singer', 'concert', 'singer_in_concert'] | 1.00 | [(0, 0), (1, 0), (2, 0)] |
| 2 | `concert_singer` | ['singer'] | 0.25 | [(1, 1), (0, 0), (2, 0)] |
| 3 | `concert_singer` | ['singer', 'singer_in_concert'] | 0.50 | [(1, 1), (3, 1), (0, 0)] |
| 4 | `concert_singer` | ['singer'] | 0.25 | [(1, 1), (0, 0), (2, 0)] |
| 5 | `concert_singer` | ['singer'] | 0.25 | [(1, 1), (0, 0), (2, 0)] |
| 6 | `concert_singer` | ['stadium', 'singer', 'concert'] | 0.75 | [(1, 4), (2, 2), (0, 1)] |
| 7 | `concert_singer` | ['singer'] | 0.25 | [(1, 1), (0, 0), (2, 0)] |
| 8 | `concert_singer` | ['singer'] | 0.25 | [(1, 1), (0, 0), (2, 0)] |
| 9 | `concert_singer` | ['singer'] | 0.25 | [(1, 1), (0, 0), (2, 0)] |
