# Spider2-Snow v12 — root cause memo

_Generated: 2026-05-08_

## What the pilot tells us

`outputs/spider2_snow/runs/snow_v12_pilot10/`:
- n = 10 canonical Snow tasks
- chosen_schema_valid = **0 / 10 (0%)** — regressed from v11's 1/10
- All 10 ended with `schema_invalid` after 3-round repair
- repair_helpful_round_1 = 0, _2 = 0, _3 = 0

## What changed v11 → v12 (intent vs outcome)

| change | intent | outcome |
|---|---|---|
| Strict compact render (top-K tables, top-N cols sorted, no
descriptions/samples, no marketing text) | give the model a tighter,
unambiguous list to copy from | **regressed** chosen_schema_valid
1/10 → 0/10. Likely lost useful semantic context (descriptions,
samples) that occasionally helped the model pick the right column. |
| 3-round repair (r1 unknown-id, r2 syntax, r3 regenerate-from-scratch)
| more chances to converge | none of 3 rounds helped any task. The
model made fresh hallucinations on each retry rather than copying
from suggestions. |
| Alias-aware validator | reduce false positives when columns are
qualified by an alias | no measured impact (validator already produced
mostly true positives in v11). |
| Self-recovery on `/content/` wipe | prevent the catalog_missing
failure mode | prevented (v11 had a 31s catalog_missing run before
re-extract). |

## Concrete failure pattern

Even with the strict prompt rule "Use ONLY the identifiers (tables,
columns) EXACTLY as listed", the model produced things like:
- Column named after a description token rather than the column name
  (e.g. saw "user pseudo id" in the description text and emitted
  `user_pseudo_id` even though the listed column was `pseudo_user_id`).
- Plausible synonyms (`event_timestamp` instead of `event_time_micros`).
- Multi-segment identifiers built from substrings of listed names.

Levenshtein suggestions in the validation report flagged these but the
model kept its hallucination instead of accepting the suggestion.

## Root causes ranked

1. **Coder-7B identifier-hallucination strength**: dominant cause.
   Even with explicit "use ONLY listed" rule, model defaults to
   plausible-sounding identifiers from its pretraining distribution.
2. **Compact render dropped useful context**: small but measurable
   regression vs v11. Fixable: bring back column descriptions + sample
   values while keeping the top-K cap.
3. **Repair prompts framed naturally rather than mechanically**: the
   model treats the validation report as a hint, not a hard constraint.
   Constrained decoding is the natural fix.

## Concrete next steps for Snow specifically

1. **Snow v13** (rich render + 3-round repair): combine v11's richer
   render with v12's 3-round repair. Best of both.
2. **INT4 Coder-32B** on same 10. Predict: schema_valid jumps to
   3-5/10 if model size is the bottleneck.
3. **Catalog-token constrained decoding** in identifier positions:
   force the model to emit only catalog substrings. Significant code.
4. **Hybrid retrieval**: when per-task gold metadata exists in
   Spider2-Snow (it does for some tasks), inject that as the catalog
   filter. Mark results as "oracle retrieval" — not official EX.
