# Spider2 Phase 13 (v11) — scientific findings

_Generated: 2026-05-08 | branch experiments/denis_

> All findings are pilot-level (n=10 each); they are hypotheses, not
> benchmark claims. The only Spider2 benchmark with a publishable score
> remains DBT FULL 68 from Phase 11 (task_success = 9/68 = 13.2%).

## F1 — Schema-grounding gate moves the failure mode upstream

Snow v10 pilot10: 7/10 errors = `object_not_found` from Snowflake
(model invented columns; engine rejected them).

Snow v11 pilot10: 9/10 errors = `schema_invalid` from our pre-execution
sqlglot+catalog validator; 0/10 `object_not_found` reaching the engine.
1/10 candidate cleared validation but failed SF `EXPLAIN USING TEXT`
with `syntax` (Snowflake-specific construct).

**Implication.** The strict validator works as designed — invented
identifiers no longer reach Snowflake. This is good for cost (no
credit burn on hopeless SQL) and good for diagnostics (clean signal:
"model hallucinates" vs "model emits broken syntax").

## F2 — Schema-grounding alone lifts schema_valid 0 → 1 (10%) on n=10

This is the only positive numerical delta this session: v10's
`chosen_schema_valid = 0/10` → v11's `chosen_schema_valid = 1/10`. The
single repair round did not pull any of the 9 invalid cases over the
gate; schema-aware repair WITH explicit nearest-match suggestions was
not enough on its own.

**Implication.** The validator + repair structure is correct but
under-powered against a 7B model that confidently emits non-existent
identifiers. We need either (a) a stronger generator, or (b) more
deterministic SQL synthesis pinned to the catalog (e.g. a post-hoc
column-substitution pass that snaps each unknown column to its
nearest-match in a selected table).

## F3 — Lite-BQ has the same root cause as Snow

Lite-BQ v10 pilot10: 10/10 errors = `object_not_found` from BigQuery
(model invents BQ table/column names). 0 retries from the v10
retry-wrapper fired (no transport failures), so the wrapper is not
relevant to this run — what failed is purely SQL semantics.

**Implication.** The Snow v11 schema-grounding approach should be
backported to BQ verbatim. Same sqlglot AST → catalog → nearest-match
repair pattern. The BQ catalog already exists on Drive
(`resource/databases/bigquery/<DB>/<DATASET>/<table>.json`).

## F4 — The async batch pattern eliminated Cloudflare 524 entirely

Both pilots ran for >800s through the Cloudflare quick-tunnel without
a single HTTP timeout. The pattern: kick off a daemon thread on Colab
via one short `/exec`, then poll `_DONE` markers on Drive every 30s.
Each poll is a sub-second `/exec`.

**Implication.** Long pilots are now reliable. The earlier "BQ HTTP
500 wave" (Phase 12 v9) was a per-task transport pattern, not a
fundamental Colab problem.

## F5 — Volatile Colab `/content` is a runtime hazard

The first Snow v11 attempt this session got `catalog_missing 10/10` in
31 seconds because `/content/spider2_snow_extract/` was wiped between
sessions. Re-extract from the persistent Drive tarball took 15s and
fixed it.

**Implication.** Any catalog/schema/data on `/content/` must include
self-recovery: if missing, re-extract from a Drive copy. The Snow v11
runner does this manually in this session; future runners should bake
it in.

## What is and is not concluded

- **Concluded**: schema-grounding does what it claims (v10→v11 metrics).
  The validator gate is necessary and correct.
- **Concluded**: BQ and SF lanes share the same model-quality bottleneck.
- **Not concluded**: that v11 is the right level of investment vs
  switching to a stronger generator. Need INT4 Coder-32B sanity on the
  same 10 tasks to disambiguate.
- **Not concluded**: any FULL benchmark numbers (NONE were run).

## Validation plan

1. **INT4 Coder-32B sanity on Snow v11 pilot10**: same 10 tasks, see
   if `chosen_schema_valid` jumps to 5+. If yes → model is the lever.
2. **Backport schema-grounding to Lite-BQ**: write
   `spider2_lite_bq_schema_grounding_v11.py` mirroring Snow v11. Pilot
   10 BQ tasks. If `chosen_schema_valid ≥ 30%`, open BQ FULL gate.
3. **Multi-round schema-aware repair**: try `max_repair_rounds = 3` on
   the same Snow 10. Each round adds ~60–80s; if it converts even 3/10
   the gate becomes reachable.
