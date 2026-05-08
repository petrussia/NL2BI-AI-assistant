# Spider2-Lite-BQ v11 — root cause memo

_Generated: 2026-05-08_

## What the pilot tells us

`outputs/spider2_lite/runs/lite_bq_v11_pilot10/`:
- n = 10 BQ tasks
- chosen_schema_valid = **0 / 10 (0%)**
- parse_ok / execute_ok = 0 / 0 (no candidate reached BQ)
- All 10 tasks ended with `schema_invalid` after generation +
  2 repair rounds.

## What changed v10 → v11

| dimension | v10 | v11 |
|---|---|---|
| Generation | Coder-7B → SQL → BQ live execute | Coder-7B → SQL → **validator gate** → BQ execute IFF schema-valid |
| Errors | 10/10 `object_not_found` AT BIGQUERY | 10/10 `schema_invalid` AT VALIDATOR |
| BQ bytes billed | small (BQ rejected SQL after some processing) | 0 (no SQL reached BQ) |
| Identifier hallucination rate | Same as v11 (the model didn't change) | Same |

## Concrete failure pattern

The model emitted SQL with table identifiers like
`bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_20210101`
where the dataset name was correctly listed in the catalog but the
table name was a hallucination (e.g. `events_2021` or
`ga4_events`). For columns: very long event_param names like
`session_engaged.value.int_value` were mangled.

The validator surfaced these as `unknown_table` / `unknown_column`
with Levenshtein nearest-match suggestions. The model received those
suggestions in the repair prompt and...
- Repair round 1: model produced different but still wrong identifiers.
- Repair round 2: model regressed (in some cases reverted to round-1
  inventions).

## Why BQ is harder than Snow

- BQ catalog uses `project.dataset.table` with **dashes and lowercase**
  in `bigquery-public-data` projects. Coder-7B does worse on lowercase
  identifiers (its training corpus skews to uppercase SQL keywords).
- BQ datasets have many `events_YYYYMMDD` shard tables. The model
  predicts plausible-but-wrong dates.
- BQ wildcard table syntax (`events_*` + `_TABLE_SUFFIX`) was
  occasionally used correctly in v10 against the actual data, but
  the v11 validator rejected wildcard refs as "unknown" because we
  match exact table names. **This is a v11 false-positive class.**

## Root causes ranked

1. **Model-quality limit**: Coder-7B BF16 produces wrong identifiers
   even with explicit suggestions. Largest contributor.
2. **Wildcard-table validation gap**: v11 validator does not handle
   `events_*` BigQuery wildcard tables. False positive on otherwise
   correct SQL. Fixable in code.
3. **No catalog-token constrained decoding**: free-form generation
   permits arbitrary token sequences. Fixable but expensive.

## Concrete next steps for BQ specifically

1. Make validator wildcard-aware: any reference to `tablename_*`
   should match if any prefix-matching table exists in the catalog.
2. Add the per-task allowed `event_params` shape to the prompt
   when the dataset is GA4 — these are the highest hallucination rate.
3. Try INT4 Coder-32B on the same 10 BQ tasks; compare schema_valid.
4. Consider constrained decoding for identifier positions only.
