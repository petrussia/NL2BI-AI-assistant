# Phase 10 — Spider2-Lite BQ agent_v8

_Branch `experiments/denis`. A_bq lane only (205 items)._

## Headline

| Metric | v7 baseline (commit `0f70a5c`) | v8 agent | Delta |
|---|---:|---:|---:|
| executable (real BQ exec ok) | 42 / 205 = 20.49% | **93 / 205 = 45.37%** | **+24.88 pp** |
| EX vs gold (compared) | 4 / 204 = 1.96% | **5 / 204 = 2.45%** | +0.49 pp |
| Wilson 95% CI on EX | [0.77, 4.93]% | [1.05, 5.61]% | overlapping |
| McNemar paired (n=204) | helpful=2, harmful=1, p=1.0 | | **tied** |
| BQ bytes billed (run + exec_match) | ~7.1 GB ($0.04) | **~10.91 GB ($0.05)** | +3.8 GB |

The **structural** improvement is large and unambiguous: v8 produces SQL
that BigQuery accepts and runs **2.2× more often** than v7. The
**semantic** improvement (matching gold result rows) is small and
McNemar-tied: v8 wins +2, loses -1, net +1 on real EX.

**Verdict.** v8 closes the dialect / grounding gap that dominated v7's
failures. The remaining gap is reasoning over the question — many v8
queries now run to completion but compute the wrong aggregate, join
the wrong tables, or filter on the wrong predicate
(`exec_ok_but_rows_mismatch` jumped from 18.5% to 42.9%).

## What v8 is, in one paragraph

Eight modules, no production-path changes to v7. Per-task BQ schema
index walks `resource/databases/bigquery/<db>/<fq_dataset>/` to build a
deduplicated table catalog with column types, sample values, and
wildcard-family collapsing (`events_2021*` → one entry). Question-aware
retrieval picks top-k tables/columns/doc-chunks. Three candidate
prompts (C0_direct, C1_retrieval+docs, C2_cte_decomposition) emit BQ
Standard SQL governed by an explicit rules block (backticks,
`_TABLE_SUFFIX`, `DATE_DIFF`/not `DATEDIFF`, `UNNEST`, `SAFE_CAST`).
Each candidate is dry-run-verified by BigQuery itself (sqlglot's BQ
parser is unreliable). On no-pass, a bounded-repair LLM round runs
with the actual BadRequest message; success or failure adds a
`C3_repaired` candidate. A heuristic + answer-shape selector picks the
winner; an optional LLM-judge round breaks close calls.

## Step 0 audit findings (drive of v8 design)

The v7 audit ([outputs/logs/spider2_bq_v7_error_audit.md](logs/spider2_bq_v7_error_audit.md))
showed:

- **50% of items used wrong tables** (no overlap with gold tables).
- 13.7% syntax_error, 13.7% function_signature, 13.7% other_bad_request.
- 18.5% executable but rows mismatched gold.
- All 205 final picks were `C0_anchor` (zero candidate diversity).

v8 attacks these with: (a) better schema retrieval, (b) BQ-aware
prompt rules, (c) candidate diversity, (d) BQ-error-aware repair.

## Per-source breakdown on v8

| source | n_picked | parses | exec_ok | EX | EX rate |
|---|---:|---:|---:|---:|---:|
| C2_cte_decomp | 80 | 26 | 16 | 2 | 2.50% |
| C1_retrieval_docs | 65 | 41 | 35 | 1 | 1.54% |
| C0_direct | 42 | 35 | 26 | 2 | 4.76% |
| C3_repaired | 18 | 18 | 16 | 0 | 0.00% |

Repair was used on 103 / 205 items and produced parseable SQL on 18 of
them (17%). The repaired SQL never matched gold rows, but it kept
those items alive structurally — the heuristic selector picked the
repaired candidate over the broken originals.

## Error taxonomy delta (v7 → v8)

| bucket | v7 % | v8 % | delta_pp |
|---|---:|---:|---:|
| exec_ok_but_rows_mismatch | 18.5 | **42.9** | **+24.4** |
| function_signature | 13.7 | 5.4 | -8.3 |
| syntax_error | 13.7 | 6.8 | -6.8 |
| table_or_dataset_not_found | 13.7 | 7.3 | -6.3 |
| permission_denied | 4.4 | 1.5 | -2.9 |
| aggregation_error | 2.4 | 1.0 | -1.5 |
| unrecognized_column | 10.7 | 9.3 | -1.5 |
| other_bad_request | 15.6 | 13.7 | -2.0 |
| EX_MATCH | 2.0 | 2.4 | +0.5 |

The `exec_ok_but_rows_mismatch` bucket grew because the items it
absorbed used to fail BQ at parse / function / table levels in v7.
v8's grounding turns those into runnable but semantically wrong SQL.
This is the right kind of failure mode to be left with — the next
lever is question-understanding (intent matching, multi-step
decomposition, possibly oracle-tables analysis), not more grounding.

## Target check

| Target | Value | Status |
|---|---|---|
| EX > 1.96% | 2.45% | ✓ minimum cleared |
| exec_ok > 20.5% | **45.4%** | ✓ structurally crushed |
| all_known up | 22% → 44% (90/205) | ✓ |
| BadRequest/unknown drop | strong (-25 pp aggregate) | ✓ |
| EX > 10% | 2.45% | ✗ |
| EX > 20% | 2.45% | ✗ |

## Cost

11 GB BQ bytes billed total across run + exec_match recompute. At
$5/TB that is ≈ $0.05 — well within the test-key budget.

## Files

```
repo/src/evaluation/
  spider2_bq_schema_index_v8.py
  spider2_bq_retrieval_v8.py
  spider2_bq_prompting_v8.py
  spider2_bq_candidate_generator_v8.py
  spider2_bq_verifier_v8.py
  spider2_bq_repair_v8.py
  spider2_bq_selector_v8.py
  spider2_agent_v8.py

tools/remote_scripts/
  129_spider2_bq_v8_runner.py
  130_spider2_bq_v8_consolidation.py

outputs/predictions/
  spider2_bq_agent_v8_predictions.jsonl              (205 rows)
  spider2_bq_agent_v8_predictions_with_em.jsonl      (with EM column)
  spider2_bq_agent_v8_candidates.jsonl
outputs/traces/spider2_bq_agent_v8_traces.jsonl
outputs/tables/
  spider2_bq_v7_error_taxonomy.csv
  spider2_bq_v7_gold_sql_oracle_audit.csv
  spider2_bq_agent_v8_metrics.csv
  spider2_bq_agent_v8_error_taxonomy.csv
  spider2_bq_agent_v8_source_breakdown.csv
  spider2_bq_agent_v8_helpful_harmful_vs_v7.csv
  final_experiment_master_matrix_spider2_v8.csv
  paired_significance_phase_ten_v1.csv
outputs/logs/
  spider2_bq_v7_error_audit.md
  spider2_bq_agent_v8_readout.md
outputs/plots/spider2_bq_v8_overview.png
```

## What blocks further EX gains (next sprint candidates)

1. **Question understanding.** ~88 items now BQ-execute but emit the
   wrong rows. Closing this requires either: a stronger reasoning
   model on the same prompt, or a question-rewrite step (decompose →
   verify each sub-answer → assemble).
2. **Oracle-tables analysis.** Use gold SQL **offline** to compute
   "if the agent had been given the right tables, would the SQL have
   worked?" upper bound. That tells us which fraction of remaining
   gap is grounding vs reasoning.
3. **Result-row sanity checks.** Many failures share a shape mismatch
   (gold returns 1 row, v8 returns 1k rows). A simple shape check on
   the dry-run can flag obvious wrong-grain queries before they
   execute.
4. **Multi-step ReAct.** The current single-shot generator emits one
   query. Spider2 questions often need 2-3 steps (build a CTE, count,
   filter). The CTE candidate helps but only for queries that *look*
   like one — multi-step planning could lift more items.
5. **Self-consistency on close calls.** The judge fires only on close
   verifier scores; running 3-of-5 voting on items where executable
   candidates disagree is a known-cheap signal.

## What's NOT in this PR

- No production-path changes to B6_v7 / S1_v7 / B7d (Spider/BIRD
  controller). v8 is a Spider2-only addition that imports v7 modules
  but does not modify them.
- No A_sf (Snowflake) execution. The Snowflake setup folder
  ([snowflake_setup/](../snowflake_setup/)) prepares the env-var path
  + connection probe, but does not generate SQL until creds + agent
  port land in a future PR.
- No B_sqlite v8 yet (deferred per brief Step 7; the optional uplift
  on stub data is non-comparable and lower priority than improving
  the EX-comparable A_bq lane).
- No Spider2-DBT integration in the v8 codebase. The
  `spider2_dbt_bridge/` folder is a parallel coverage track for the
  68 DBT tasks; it lives in its own SSH-based pipeline and does not
  intersect with the BQ v8 lane.
