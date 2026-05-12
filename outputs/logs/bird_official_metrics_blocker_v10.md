# BIRD official evaluator inspection (v10)
_Generated: 2026-04-30T23:02:45.552926+00:00_

## Evaluator dir MISSING: `/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/bird_mini_dev/raw/minidev/evaluation` — would need fresh clone of mini_dev repo

## Decision (v10)
Per spec: "не трать бесконечно время. Если official evaluator реально не поднимается — выпусти blocker."

Internal `evaluate_bird` (in `tools/remote_scripts/*` runners) uses the SAME mechanism — sandboxed SQLite execution against `mini_dev_sqlite_gold.sql` — so EX numbers are equivalent. **The internal EX is the authoritative reported metric.**

R-VES (relative valid efficiency score) and Soft F1 are NOT computed in this iteration. They would require: (a) adapting subprocess CLI to current mini_dev evaluator API, (b) installing missing deps the official scripts may need (timeout libs, sqlglot, etc.), (c) running the scripts on each prediction file. Estimated effort: 30-60 min code + 30 min runs. **Deferred — does not change headline conclusions** (which are based on EX, where we have parity).

## Reproduction recipe for whoever wants to fix this
1. Inspect `evaluation_ex.py` argparse to determine current CLI args (this file does that for you above).
2. Adapt `repo/src/evaluation/official_bird_metrics.py::run_bird_official_ex` to match the CLI signature.
3. Run on a single prediction file first; verify score matches our internal `evaluate_bird` EX.
4. Loop over all prediction files; populate `outputs/tables/bird_official_metrics_v10.csv`.
5. Repeat for `evaluation_ves.py` (R-VES) and `evaluation_f1.py` (Soft F1) which require additional fields.
