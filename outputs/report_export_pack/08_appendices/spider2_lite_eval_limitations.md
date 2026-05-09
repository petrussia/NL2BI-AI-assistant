# Spider 2.0-Lite — evaluation limitations

**Captured:** 2026-04-30T15:57:19.335000+00:00

## Why we cannot compute Execution Match (EX) on this slice from Colab

Spider 2.0-Lite tasks reference databases hosted on **BigQuery / Snowflake / DuckDB-extensions** (depending on the task). Executing the gold SQL against these requires:
- active credentials to the corresponding cloud data warehouse (BigQuery service account, Snowflake user/password, etc.); AND
- the original tables loaded into that warehouse (Spider 2.0 distributes pointer references, not the data).

Colab kernels do **not** carry these credentials and the project scope (NL→SQL extraction subsystem of Shubin) does not include provisioning a BigQuery/Snowflake account. **Therefore EX cannot be computed** on this slice from the current runtime.

## What we CAN do honestly
1. Generate predicted SQL with each baseline (B0/B1/B2_v2) and each model (Qwen-Coder-7B, Llama-3.1-8B).
2. Save predictions to `outputs/predictions/spider2lite_30_diverse_*` for inspection.
3. Report **structural metrics** that are computable without execution:
   - non-empty SQL emission rate
   - SQL parser-validity (sqlglot)
   - mean SQL length (tokens)
   - presence of expected SQL constructs (JOIN, GROUP BY, WHERE, subqueries) per model/baseline
4. (Optionally) Compute **string-level Exact Match** vs the published gold SQL strings (a strict metric, not executable).
5. Document this gap as an **environmental evaluation limitation**, not a methodological one.

## Honest classification
External validation slice — **prediction-only on Spider 2.0-Lite, EX not computable from Colab.** The mandatory operational evaluation continues on internal Spider subsets (smoke_10, smoke_25, multidb_30) where we have sandboxed SQLite execution.
