# Spider2 BQ agent_v7 — A_bq error audit (Step 0)

_Generated offline. n_total_a_bq=205._

## Headline numbers (parses=executor dry_run accepted)

- parses: 196/205 = 95.61%
- all_known (schema-validity): 45/205 = 21.95%
- executable (real BQ exec ok): 42/205 = 20.49%
- execution_match=True (vs gold rows): 4/204 compared, total 4/205 = 1.95%
- gold SQL present: 142/205 (69.3%) — only items with gold can be EX-evaluated

## Error bucket distribution

| bucket | n | pct |
|---|---:|---:|
| exec_ok_but_rows_mismatch | 38 | 18.5% |
| syntax_error | 28 | 13.7% |
| function_signature | 28 | 13.7% |
| other_bad_request | 28 | 13.7% |
| table_or_dataset_not_found | 28 | 13.7% |
| unrecognized_column | 25 | 12.2% |
| other:InternalServerError | 11 | 5.4% |
| permission_denied | 9 | 4.4% |
| aggregation_error | 5 | 2.4% |
| EX_MATCH | 4 | 2.0% |
| bytes_billed_exceeded | 1 | 0.5% |

## Structural feature vs exec_ok

| feature | pos_n | pos_exec | pos_em | neg_n | neg_exec | neg_em |
|---|---:|---:|---:|---:|---:|---:|
| has_join | 110 | 13 | 1 | 95 | 29 | 3 |
| has_groupby | 136 | 29 | 3 | 69 | 13 | 1 |
| has_subquery | 38 | 6 | 1 | 167 | 36 | 3 |

## Unknown-identifier breakdown

- items with unknown_tables: 105 (51.2%)
- items with unknown_columns: 119 (58.0%)

## Gold SQL oracle table-overlap summary

- gold subset of pred (predicted referenced ALL gold tables): 38/142 = 26.8%
- partial overlap: 33/142 = 23.2%
- no overlap: 71/142 = 50.0%

## Bucket × structural cross-tabs

### Per-bucket all_known + executable rates

| bucket | n | all_known | exec_ok | em |
|---|---:|---:|---:|---:|
| exec_ok_but_rows_mismatch | 38 | 16 | 38 | 0 |
| syntax_error | 28 | 0 | 0 | 0 |
| function_signature | 28 | 5 | 0 | 0 |
| other_bad_request | 28 | 9 | 0 | 0 |
| table_or_dataset_not_found | 28 | 1 | 0 | 0 |
| unrecognized_column | 25 | 2 | 0 | 0 |
| other:InternalServerError | 11 | 6 | 0 | 0 |
| permission_denied | 9 | 1 | 0 | 0 |
| aggregation_error | 5 | 3 | 0 | 0 |
| EX_MATCH | 4 | 2 | 4 | 4 |
| bytes_billed_exceeded | 1 | 0 | 0 | 0 |

## Top gold-referenced datasets

| dataset | n_items_using_it |
|---|---:|
| bigquery-public-data.google_analytics_sample | 12 |
| bigquery-public-data.stackoverflow | 10 |
| bigquery-public-data.ga4_obfuscated_sample_ecommerce | 9 |
| bigquery-public-data.census_bureau_acs | 9 |
| firebase-public-project.analytics_153293282 | 6 |
| bigquery-public-data.noaa_gsod | 5 |
| bigquery-public-data.geo_us_boundaries | 5 |
| hits.transaction | 3 |
| bigquery-public-data.cms_medicare | 3 |
| bigquery-public-data.new_york_taxi_trips | 3 |
| bigquery-public-data.san_francisco_bikeshare | 3 |
| bigquery-public-data.census_bureau_international | 3 |
| bigquery-public-data.world_bank_wdi | 3 |
| bigquery-public-data.chicago_taxi_trips | 3 |
| bigquery-public-data.the_met | 3 |
| bigquery-public-data.iowa_liquor_sales | 3 |
| bigquery-public-data.austin_bikeshare | 3 |
| bigquery-public-data.world_bank_intl_debt | 3 |
| bigquery-public-data.london_crime | 3 |
| event_params.value | 2 |

## Honest takeaways (no inference yet)

_This memo is the freeze for Step 0. Conclusions go in Step 1+ once schema-grounding is built._

1. Parse rate is high; the underlying problem is **wrong tables/columns/dataset names**, NOT broken syntax.
2. 50% of items where gold SQL exists have at least partial table overlap; pure dataset-discovery is the dominant gap.
3. unknown_tables/columns counters from sqlglot are unreliable for BQ — cross with the gold-table check.
4. The single source `C0_anchor` for all 205 means v7 had no candidate diversity; multi-candidate v8 has room to help.
