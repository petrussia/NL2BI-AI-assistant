# Baseline Registry

Frozen at: 2026-04-29T15:32:53.939276+00:00
Single source of truth for completed baseline runs. Append-only; new versions get a new row, never overwrite an existing one.

| Baseline | Ver | Subset | EX | Executable | Special fields | Status | Comment |
|---|---|---|---|---|---|---|---|
| B0 | v0 | smoke10 | 1.0 | 10 |  | completed | Single-shot full-schema NL->SQL prompt; reference baseline. |
| B1 | v0 | smoke10 | 1.0 | 10 | avg_reduction_ratio=0.475 | completed | Reduced schema via lexical schema linking (table x2, col x1, min_score=0.5). |
| B0 | v0 | smoke25 | 0.96 | 25 |  | completed | Single error idx 16 (wrong_aggregation), shared with B1. |
| B1 | v0 | smoke25 | 0.96 | 25 | avg_reduction_ratio=0.58 | completed | Identical EX to B0; same error idx 16. ~58% schema retained. |
| B2 | v0 | smoke10 | 0.7 | 9 | plan_valid_count=9,plan_parse_failures=0,avg_reduction_ratio=0.475 | completed (regressed) | Plan->SQL minimal pipeline. Regressed: 2 result_mismatch (idx 6,7 youngest-singer), 1 plan_invalid (idx 8 distinct+filter). |

## Conventions

- `baseline_name` is the family (B0, B1, B2, B1R, B2R...).
- `version` is `v0`, `v1`, ... within the family. Original B0/B1 do not need a version bump because the underlying prompt has not changed.
- `subset` matches the file in `data/spider/subsets/`.
- `special_fields` lists baseline-specific columns from the metrics CSV (avg_reduction_ratio, plan_valid_count, etc.).
- New runs MUST register a new row before being analysed.
