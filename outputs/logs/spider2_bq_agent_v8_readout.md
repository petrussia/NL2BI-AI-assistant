# Spider2-Lite BQ agent_v8 — readout

_Generated: 2026-05-05T21:23:52.617301+00:00_

## Headline numbers (A_bq lane only, n=205)

| Metric | v7 baseline | v8 agent | Delta |
|---|---:|---:|---:|
| parses | 196 (95.6%) | 120 (58.5%) | -76 (note: v7 used sqlglot OR exec; v8 uses BQ dry_run authoritative) |
| executable | 42 (20.5%) | 93 (45.4%) | **+24.9pp** |
| EX vs gold (compared 204) | 4/204 (1.96%) | 5/204 (2.45%) | **+0.49pp** |
| EX of total 205 | 4 (1.95%) | 5 (2.44%) | +0.49pp |
| Wilson 95% CI (v7) | [0.77, 4.93] | | |
| Wilson 95% CI (v8) | | [1.05, 5.61] | |

## Paired stats (McNemar on EX)

- n_paired with EM defined on both: **204**
- helpful (v8 right, v7 wrong): **2**
- harmful (v8 wrong, v7 right): **1**
- both right: 3, both wrong: 198
- McNemar p (continuity-corrected): **1.0000**
- verdict: **tied**

## Source breakdown (v8)

| source | n | parses | exec_ok | em | em_rate |
|---|---:|---:|---:|---:|---:|
| C2_cte_decomp | 80 | 26 | 16 | 2 | 2.50% |
| C1_retrieval_docs | 65 | 41 | 35 | 1 | 1.54% |
| C0_direct | 42 | 35 | 26 | 2 | 4.76% |
| C3_repaired | 18 | 18 | 16 | 0 | 0.00% |

## Error bucket comparison (v7 vs v8)

| bucket | v7_n | v7% | v8_n | v8% | delta_pp |
|---|---:|---:|---:|---:|---:|
| exec_ok_but_rows_mismatch | 38 | 18.5% | 88 | 42.9% | +24.4 |
| other_bad_request | 32 | 15.6% | 28 | 13.7% | -2.0 |
| unrecognized_column | 22 | 10.7% | 19 | 9.3% | -1.5 |
| other:InternalServerError | 11 | 5.4% | 18 | 8.8% | +3.4 |
| table_or_dataset_not_found | 28 | 13.7% | 15 | 7.3% | -6.3 |
| syntax_error | 28 | 13.7% | 14 | 6.8% | -6.8 |
| function_signature | 28 | 13.7% | 11 | 5.4% | -8.3 |
| EX_MATCH | 4 | 2.0% | 5 | 2.4% | +0.5 |
| permission_denied | 9 | 4.4% | 3 | 1.5% | -2.9 |
| aggregation_error | 5 | 2.4% | 2 | 1.0% | -1.5 |
| parse_failure | 0 | 0.0% | 2 | 1.0% | +1.0 |

## Repair impact
- repair_used: 103/205
- repair_success: 18

## Cost
- BQ bytes billed total (run+exec_match): 10.91 GB
- approximate cost @ $5/TB: $0.0533
