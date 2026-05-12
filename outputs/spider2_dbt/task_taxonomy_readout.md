# Task taxonomy readout (Phase 0, pre-floor)

_n_total = 68_

## Primary bucket distribution

| bucket | count |
|---|---:|
| create_new_model | 61 |
| patch_existing_model | 7 |

## Secondary bucket presence

| secondary | count |
|---|---:|
| grain_aggregation | 28 |
| join_semantics | 21 |
| date_time_semantics | 21 |
| nested_json_list_struct | 2 |
| schema_yml_contract | 1 |

## Notes
- floor_marker / floor_score fields blank until V0 run completes;
- after V0 run, taxonomy is updated by `tools/update_taxonomy_from_floor.py`;
- mode_tag is `mode_b_offline_labeling` for every row — gold is used only for taxonomy/floor diagnostics, never for prompt building.
