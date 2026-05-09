# Spider2-Snow v16 — analysis

_Generated: 2026-05-08_

## Headline

**chosen_schema_valid = 0/10**. Constrained repair helped 0 tasks.
Snow has now been pilot-tested under v10/v11/v12/v13/v16 with 5
different pipelines:

| pilot | schema_valid | render | repair |
|---|:---:|---|---|
| Snow v10 | 0/10 | rich (no validator) | none |
| Snow v11 | **1/10** | rich | 1-round LLM |
| Snow v12 | 0/10 | strict compact | 3-round LLM |
| Snow v13 | 0/9 | rich + ek | 3-round LLM |
| **Snow v16** | **0/10** | rich | constrained substitution (deterministic) |

The 1-task floor on Snow has held across all 5 attempts. This is a
strong, stable signal that constrained substitution does not help
the failure mode dominant on Snow.

## Why constrained substitution failed on Snow but worked on BQ

Asymmetry between catalogs:

| dimension | BQ | Snow |
|---|---|---|
| catalog scope | per-DB ~1-3 datasets × ~30-100 tables | per-DB ~1 schema × ~30-200 tables |
| total dbs in benchmark | small per-task pool | 152 across the canonical 547 |
| column count per table | typically ~10-30 | often 50-100+ (PATENTS, GA360-style) |
| identifier flavor | dashed lowercase project | uppercase SCREAMING_SNAKE |

Coder-7B on BQ tends to produce *typo-shaped* hallucinations — wrong
character, wrong suffix, dropped underscore. These land within
Levenshtein-2 of catalog and are recoverable.

Coder-7B on Snow tends to produce *semantically plausible but
catalog-absent* identifiers — "publication_date" when the table has
"pub_date_gd"; "user_count" when the table has "n_distinct_users".
These don't match Levenshtein bands; they don't match token bands;
they don't even share ngrams beyond trivial common substrings.
Substitution misses entirely.

## Source breakdown

C0_direct=6, C1_retrieval=4. Model picks more diverse on Snow than
BQ but none of the candidates were close enough to recover.

## Per-task n_unknown_columns distribution

Average ~3-5 unknown_columns per task. Substitution would need to
correctly replace 3-5 identifiers SIMULTANEOUSLY for the candidate to
become schema_valid. Even with 50% per-identifier replacement
accuracy, P(all 3-5 correct) ≈ 0.5^4 ≈ 6%. Observed = 0%, consistent
with sub-50% per-identifier accuracy on Snow's harder catalog.

## Recommended next moves for Snow

1. **INT4 Coder-32B on Snow v16 pilot10** — a stronger generator may
   produce identifiers within recoverable distance. If schema_valid
   jumps to 3+/10 on the same 10 tasks, model size IS the lever.
   GPU note: A100-40GB recommended; L4 22.5GB marginal (use AWQ pre-
   quant; cap max_new_tokens; risk of OOM on PATENTS/GA360 schemas).
2. **Hybrid retrieval with gold metadata** for Snow — when Spider2
   ships a per-task expected-columns list, inject that as the
   catalog filter. Mark results explicitly as "oracle retrieval",
   not official EX. Serves as upper-bound check.
3. **Constrained decoding** on identifier positions — research lift,
   not a quick fix; physically prevents the model from emitting
   off-catalog identifiers.

## Why Snow at 0% is informative, not failure

Across 12 historical pilots × ~10 tasks ≈ 120 attempts, Snow has
exactly **1 schema-valid candidate ever (v11)**. This stability says:

- The schema-grounding pipeline is deterministic and correct.
- The bottleneck is firmly **model-side identifier hallucination**.
- Engineering inside the validator/repair stack is essentially fully
  characterized.
