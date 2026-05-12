# BIRD official metrics — blocker

**Generated:** 2026-04-30T22:33:40.604353+00:00

## Why blocked
BIRD official evaluator subprocess returned: `eval dir missing: /content/drive/MyDrive/diploma_plan_sql/external_benchmarks/bird_mini_dev/raw/minidev/evaluation`

## Workaround in place
Internal `evaluate_bird` already computes EX exactly per item via SQLite `func_timeout` execution against the official mini_dev_sqlite_gold.sql tables. **Our internally-computed BIRD EX numbers are the authoritative ones for the diploma**, and they are reported throughout the master matrix.

## R-VES / Soft F1
Not computed in this iteration (would require running additional BIRD evaluator scripts; deferred).
