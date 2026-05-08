# Spider2 Phase 14 (v11/v12) — scientific findings

_Generated: 2026-05-08 | branch experiments/denis_

> Three pilots aggregate: BQ v11 (n=10), Snow v11 (n=10, Phase 13),
> Snow v12 (n=10, Phase 14). All n=10 — pilot-level only; not benchmark
> claims. Only the Spider2-DBT FULL 68 (13.2% from Phase 11) is a
> publishable Spider2 number.

## F1 — Schema-grounding gate works on BOTH lanes

BQ v11 pilot10: 10/10 `object_not_found` (Phase 13 v10) → 10/10
`schema_invalid` (Phase 14 v11). Zero bytes billed on hopeless SQL.

Snow v11/v12 pilot10: 7/10 `object_not_found` (v10) → 0/10 (v11/v12);
catalog-validator catches all invented identifiers before SF
`EXPLAIN USING TEXT`.

**Implication.** The validator gate is correct, deterministic, and
saves real engine cost. Engineering signal is positive.

## F2 — Schema-grounding alone does not push schema_valid above ~10%

| pilot | schema_valid |
|---|---:|
| Snow v11 (rich render, 1-round repair) | 1/10 (10%) |
| Snow v12 (strict compact render, 3-round repair) | 0/10 (0%) |
| BQ v11 (rich render with backticks, 2-round repair) | 0/10 (0%) |

Even with deterministic Levenshtein nearest-match suggestions and
multiple repair rounds, the LLM cannot reliably produce identifiers
that exist in the catalog. This holds for both Snowflake (uppercase
unquoted) and BigQuery (`project.dataset.table` with dashes).

**Implication.** The model itself is the bottleneck. Coder-7B BF16
hallucinates identifiers at high rate even when shown allowed names.

## F3 — Stricter render did NOT help, slightly hurt

Snow v12 vs v11 (same 10 tasks):
- v11 chosen_schema_valid: 1/10
- v12 chosen_schema_valid: 0/10

The v12 compact render (top-K tables, top-N columns sorted, no
descriptions/samples, no marketing text) appears to have removed
context that v11's richer render occasionally used to land on a valid
identifier. Stricter ≠ better.

**Implication.** Future renders should keep description / sample-value
hints; the rule lines about "use ONLY listed identifiers" are already
necessary (and present in both v11 and v12) but not sufficient.

## F4 — Multi-round repair (3 rounds) did NOT lift any schema_invalid task

Snow v12 repair stats:
- repair_helpful_round_1: 0
- repair_helpful_round_2: 0
- repair_helpful_round_3: 0

Round 3 ("regenerate from scratch using ONLY allowed schema") is the
strongest possible repair short of constrained decoding, and it still
produced 0 schema-valid tasks. The model defaults to its hallucinated
identifier set even when the previous attempt's failure is in context.

**Implication.** Iterative natural-language repair has diminishing
returns. Constrained decoding restricted to catalog tokens or a
significantly stronger generator are the natural next experiments.

## F5 — BQ identifier hallucination is harder than Snow

BQ identifiers: `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_20210101`
Snow identifiers: `PATENTS.PUBLIC.PUBLICATIONS`

BQ catalog has dashes, lowercase project names, longer dataset names.
Coder-7B is more prone to BQ hallucinations: BQ v11 produced 0/10
schema_valid; Snow v11 produced 1/10.

**Implication.** When evaluating model-quality fixes (e.g. INT4 32B),
test on BOTH lanes — improvements on Snow may not translate to BQ.

## F6 — Async batch pattern fully resilient

All three Phase 13/14 pilots ran > 1000 s through Cloudflare
quick-tunnel without HTTP timeout. The pattern:
- one short `/exec` to start a Colab daemon thread;
- Drive `_DONE` / `_FAILED` markers;
- 30s polling, each poll < 1s.

No infrastructure change needed for FULL runs at this point.

## What's still NOT known

- Whether INT4 Coder-32B (`bitsandbytes` 4-bit on L4) clears the gate.
  Untested this session.
- Whether constrained decoding restricted to catalog tokens would
  push schema_valid > 50%. Significant code lift.
- Whether the per-task ground-truth column list (available in some
  Spider2 metadata) would lift schema_valid above 80%. That would be
  closer to "oracle retrieval" and should be marked as such.

## Validation plan

1. **INT4 Coder-32B sanity** — load via bitsandbytes 4-bit on L4
   (Colab), run Snow v12 pilot10. If schema_valid ≥ 30% → pursue 32B
   for Snow FULL.
2. **Hybrid retrieval** — when per-task gold column list exists in
   Spider2 metadata, inject that as the catalog subset. Compare
   schema_valid vs current pilots.
3. **Constrained decoding** — wrap generation with a token mask
   restricting identifier-position tokens to the catalog. Significant
   engineering, but a clean lever.
