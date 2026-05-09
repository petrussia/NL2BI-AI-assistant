# Spider2 v16 — root cause audit (across all historical pilots)

_Generated: 2026-05-08 | source: outputs/tables/spider2_identifier_failure_audit_v16.csv_

## Method

Parsed `predictions.jsonl` from every pilot run we have on disk
(15 pilot dirs, 117 task-attempts) and classified each failure by
inspecting `error_message` (UNKNOWN_TABLES / UNKNOWN_COLUMNS lists),
the chosen SQL itself, and structural patterns (4-part, GA4 nested,
wildcards). Categories:

| category | description |
|---|---|
| `is_true_hallucination` | invented identifier with no Levenshtein-close catalog match |
| `is_project_qualification_issue` | `bigquery-public-data.bigquery-public-data.X.Y` (project doubled) |
| `is_wildcard_issue` | `events_*` / `ga_sessions_*` table refs |
| `is_struct_array_issue` | GA4 `event_params.key`, GA360 `hits.product`, etc. |
| `is_alias_issue` | column qualifier matches a FROM/JOIN alias |
| `is_close_typo` | unknown ident within Levenshtein ≤ 2 of catalog |
| `is_catalog_render_missing` | identifier IS in catalog but NOT in selected_tables |

## Counts (n=117)

| class | count | share |
|---|---:|---:|
| **is_true_hallucination** | 112 | **95.7%** |
| is_project_qualification_issue | 14 | 12.0% |
| is_wildcard_issue | 11 | 9.4% |
| is_struct_array_issue | 6 | 5.1% |
| is_alias_issue | 2 | 1.7% |
| is_close_typo | 0 | 0.0% |
| is_catalog_render_missing | 0 | 0.0% |

(Categories are non-exclusive — many rows have hallucinations *plus*
a structural issue.)

## Recommendation distribution

| recommended_repair_type | count |
|---|---:|
| `none` (no clean recipe) | 98 |
| `wildcard_validator_fix` | 8 |
| `bq_nested_rewrite` | 6 |
| `4part_collapse_normalizer` | 5 |

## Headline finding

**112 / 117 = 95.7% of failures are true hallucinations.** The model
freely invents identifiers that aren't even within Levenshtein 2 of any
catalog entry. There is no deterministic repair path for these.

The 19 deterministically-recoverable cases (4 + 8 + 6 + 5 with
overlap) split into:
- **Wildcard tables**: BQ v12 already partially handles via prefix
  match. Hardening + better prompt examples can recover ~5 more.
- **BQ nested rewrites**: GA4/GA360 STRUCT/UNNEST patterns. New v16
  module will rewrite `event_params.key` → `EXISTS (SELECT 1 FROM
  UNNEST(event_params) ep WHERE ep.key = ...)`. Recovers ~6.
- **Project doubled**: BQ v12 normalizer already collapses these.
- **Aliases**: validator already handles.

## What v16 deterministic stack can lift

Optimistic upper bound: ~15% lift on schema_valid. Realistic: ~5-10%
because most "is_true_hallucination=True" rows ALSO have a structural
issue counted in another bucket; fixing the structural issue reveals
the underlying hallucination.

To clear the user's 30% gate we need EITHER:
1. A stronger generator (INT4 Coder-32B), OR
2. Constrained decoding (research lift), OR
3. Hybrid retrieval with gold metadata (oracle-like).

## What v16 deterministic stack does NOT do

It does NOT solve the dominant 95.7% problem. It removes specific
structural false-positives so the validator gives a clean signal.
Pilot10 numbers will likely move 0-1/10 → 1-2/10. Real progress, not
a gate-clear.

## Per-lane breakdown

| pilot | n | hallucination % | structural-issue % |
|---|---:|---:|---:|
| Snow v10/v11/v12/v13 | ~40 | ~95% | ~5% |
| BQ v10/v11/v12 | ~30 | ~95% | ~25% (BQ has more wildcard / project-doubled) |
| Lite-Mixed pilots | rest | ~95% | mixed |

BQ has more structural fixes available than Snow. v16 deterministic
work should help BQ slightly more than Snow.

## Files

- Raw audit table: `outputs/tables/spider2_identifier_failure_audit_v16.csv` (117 rows, 25 cols)
- This memo: `outputs/logs/spider2_v16_root_cause_audit.md`
