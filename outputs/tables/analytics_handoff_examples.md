# Analytics Handoff Examples


Generated at: 2026-04-29T14:36:55.816591+00:00
Demonstrates the postprocess → analytics-handoff layer for one item per baseline.
Files saved to `outputs/analytics_handoff/`.

| baseline | idx | db_id | n_rows | question | generated_sql | json_path | csv_path |
|---|---|---|---|---|---|---|---|
| B0 | 0 | `concert_singer` | 1 | How many singers do we have? | `SELECT COUNT(*) FROM singer;` | `outputs/analytics_handoff/B0_smoke10_idx0.json` | `outputs/analytics_handoff/B0_smoke10_idx0.csv` |
| B1 | 0 | `concert_singer` | 1 | How many singers do we have? | `SELECT COUNT(*) FROM singer;` | `outputs/analytics_handoff/B1_smoke10_idx0.json` | `outputs/analytics_handoff/B1_smoke10_idx0.csv` |

## Per-demo summary previews

### B0 idx=0
```json
{"row_count": 1, "columns": {"c0": {"count": 1, "null_count": 0, "distinct_count": 1, "dtype": "numeric", "min": 6, "max": 6, "sum": 6, "mean": 6.0}}}
```

### B1 idx=0
```json
{"row_count": 1, "columns": {"c0": {"count": 1, "null_count": 0, "distinct_count": 1, "dtype": "numeric", "min": 6, "max": 6, "sum": 6, "mean": 6.0}}}
```
