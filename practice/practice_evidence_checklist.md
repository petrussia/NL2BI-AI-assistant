# Practice Evidence Checklist

Updated 2026-04-25T17:55:21.925124+00:00.

## Smoke10
- [x] B0 predictions / metrics / summary / runlog / error_cases / examples
- [x] B1 predictions (incl. selected_tables, schema_reduction_ratio) / metrics / summary / runlog / error_cases / examples / linking examples + audit
- [x] B2 predictions (incl. plan_raw, plan_parsed, plan_valid, plan_error, selected_tables, schema_reduction_ratio) / metrics (incl. plan_valid_count, plan_parse_failures) / summary / runlog / error_cases / examples / plan_examples
- [x] B0 vs B1 comparison CSV/MD/plot/case_diff
- [x] B0 vs B1 vs B2 three-way comparison CSV/MD/plot/case_diff

## Smoke25
- [x] B0 predictions / metrics / summary / runlog / error_cases / examples
- [x] B1 predictions / metrics / summary / runlog / error_cases / examples / linking examples + audit
- [x] B0 vs B1 comparison CSV/MD/plot/case_diff
- [x] aggregate progression smoke10→smoke25 CSV/MD/plot

## Cross-cutting
- [x] error_taxonomy_smoke25.md, b0_b1_failure_buckets.csv
- [x] practice_figure_index.md, practice_table_index.md
- [x] B2 design decision (`outputs/logs/b2_design_decision.md`)
- [x] B2 readiness, B2 implementation plan
- [x] B2 preflight (`outputs/logs/b2_preflight_drive.md`)

## Out of scope
- [ ] B2 on smoke25
- [ ] multi-DB subset evaluation
- [ ] B3/B4
- [ ] fine-tuning
- [ ] final practice and thesis writeups
