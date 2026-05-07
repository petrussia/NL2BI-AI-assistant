# Spider2-Lite v8 — run `lite_v8_pilot_1plus1plus1`

_Generated: 2026-05-07T23:15:40+00:00 | dataset: `data/spider2_lite/raw/spider2-lite.jsonl`_

## Lane metrics (do NOT average across lanes — they are not comparable)

| lane | n | parse_ok | execute_ok | parse_rate | execute_rate | non_comparable |
|---|---:|---:|---:|---:|---:|:---:|
| `A_bq` | 1 | 0 | 0 | 0.0% | 0.0% | no |
| `A_sf` | 1 | 0 | 0 | 0.0% | 0.0% | no |
| `C_sqlite_stub` | 1 | 0 | 0 | 0.0% | 0.0% | YES |

## Notes
- `A_bq` lane uses official BQ live execute (capped 1 GB billed).
- `A_sf` lane uses official Snowflake live execute (PARTICIPANT/COMPUTE_WH_PARTICIPANT).
- `C_sqlite_stub` lane runs against Spider2 sample-rows SQLite databases. Results are NOT comparable to official EX — flagged `non_comparable=True`.