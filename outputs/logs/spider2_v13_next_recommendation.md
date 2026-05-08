# Spider2 Phase 15 → Phase 16 — recommendation

_Generated: 2026-05-08_

## What Phase 11–15 collectively established

1. **Engineering schema-grounding is correct and effective at the
   gate level.** Every schema-grounding error class (`wrong_dialect`,
   4-part identifier, double-project, struct-field false positive,
   wildcard table) has a clean fix in the validator/normalizer. After
   v12/v13:
   - `wrong_dialect`: 0/10 across all phases.
   - `object_not_found AT engine`: 0/10 on both lanes since v11.
   - `validator false positives`: 68 struct + 19 wildcard recovered
     on BQ v12.
2. **Engineering alone does NOT clear pilot gates.** Across **5 Snow
   pilots + 3 BQ pilots × 10 tasks each ≈ 80 task-attempts**, only
   2 chosen candidates were schema-valid (Snow v11 = 1, BQ v12 = 1).
   Coder-7B BF16 invents identifiers even with explicit
   nearest-match suggestions and 3-round repair.

## What's left to try (priority order)

### (1) Constrained identifier substitution — Phase 16, smallest lift
Per user spec ("если нет — следующий шаг не repair, а constrained
identifier selection"). Pure code, no LLM:
- After validator returns `schema_invalid`, take each unknown
  identifier and its top-1 nearest-match suggestion.
- Replace the unknown token in the SQL string with the suggested
  catalog identifier (or DB.SCHEMA.TABLE form for tables).
- Re-validate; if pass → live execute.
- Logs show `n_substitutions` and `which_unknown_ids_replaced`.

Expected impact: lifts schema_valid from 0-10% to maybe 30-50% on
"close" hallucinations (typos, plural/singular flips, value/_int
confusion). Doesn't help wholesale fabrications.

### (2) INT4 Coder-32B sanity
~30-45 min wall to load via bitsandbytes 4-bit on Colab L4. Run on
the same Snow v13 pilot10 (and BQ v12 pilot10). If schema_valid
jumps to 3+/10, model size is the bottleneck — FULL becomes reachable
on a stronger generator. If still 0-1/10, model size is not the
lever and constrained substitution becomes the only way forward.

### (3) Hybrid retrieval with gold metadata
Where Spider2 ships a per-task `column_names`-on-gold list, inject
that as the catalog filter (not just the natural-token retrieval).
This is closer to "oracle retrieval" — must be marked as such and
NOT reported as official EX. Useful as a UPPER BOUND check.

### (4) Constrained decoding (research lift)
Wrap generation with a token mask restricting identifier-position
tokens to catalog substrings. Significant engineering and only viable
if (1)–(3) don't clear the gate.

## Operating constraints carry-over

- No FULL claim on partial pilots.
- No FULL launch unless a pilot10 ≥ 30% AND pilot30 ≥ 50%.
- SQLite stub stays non-comparable.
- DBT FULL 68 (13.2%) is the only publishable Spider2 number.
- All commits stay local until explicit user push.
- GCP SA test key rotated before any external publish.

## What goes into ВКР right now

- Spider2-DBT FULL 68 = 13.2% (Phase 11).
- Spider2-Snow canonical 547 dataset acquisition + manifest (Phase 11).
- v9 dialect normalizer experiment (wrong_dialect 2/3 → 0/10).
- v11 schema-grounding validator (object_not_found AT engine 7/10 → 0/10
  on Snow; 10/10 → 0/10 on BQ).
- v12 BQ validator hardening (struct/wildcard/4-part fixes; +1 schema_valid).
- Honest pilot-vs-FULL discipline + gate policy (numbers in master
  matrices v9..v13 + scientific findings v9..v13).

## What is NOT publishable

- Any Snow / Lite-BQ / Lite-SF FULL number (none run; gates failed).
- Any "Spider2 average" score.
- The 1/10 hits on Snow v11 and BQ v12 framed as benchmark results —
  they are pipeline-correctness signals, not quality signals.
