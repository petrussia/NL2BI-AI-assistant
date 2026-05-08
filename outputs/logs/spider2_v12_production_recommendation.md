# Spider2 Phase 14 (v12) — production recommendation

_Generated: 2026-05-08 | branch experiments/denis_

## TL;DR

- **Publishable**: Spider2-DBT FULL 68 = **9/68 = 13.2%** (Phase 11
  commit `09abb5a`). Unchanged this phase.
- **Not publishable**: any Snow / Lite-BQ / Lite-SF score (pilots-only,
  gates failed).
- Phase 14 lands the **schema-grounding gate on both lanes** (BQ +
  Snow). Engine never sees hallucinated identifiers anymore. But
  Coder-7B still hallucinates them at high rate, so the gate keeps
  blocking everything.

## Validated architectural moves (safe to keep enabled)

1. **Schema-grounding pre-execution validator** on both BQ (v11) and
   Snow (v11/v12). Uses sqlglot AST + per-DB catalog +
   Levenshtein nearest-match. Blocks hallucinated identifiers with
   zero engine-side cost.
2. **Async batch pattern** for Colab pilots. Eliminated Cloudflare
   100s edge timeout entirely. All Phase 13+14 pilots ran > 1000 s
   without HTTP failures.
3. **Snowflake dialect normalizer** (v9), **identifier 4-part collapse**
   (v10), **alias-aware column resolver** (v12) — all stable at zero
   contributions to error count in Phase 14 (because the validator
   blocks earlier).
4. **Self-recovery for `/content/` wipe** in Snow v12 runner — auto
   re-extracts the Drive tarball if the canonical extract is missing.

## NOT validated by Phase 14 numbers

- **Stricter compact render alone is worse than rich render** (v12 vs
  v11). Future renders should keep description + sample hints.
- **Multi-round natural-language repair (3 rounds)** does not improve
  schema_valid at this model size. Iterative repair plateaued.

## What MUST NOT go into ВКР

- Any Spider2-Snow / Lite-BQ / Lite-SF FULL number (no FULL run).
- The single 1/10 Snow v11 schema_valid framed as a benchmark result.
- Any "Spider2 average" — three benchmarks stay separate.

## Recommended next operational steps

1. **INT4 Coder-32B** on Snow v12 pilot10 (~30-45 min including model
   load via `bitsandbytes` 4-bit on Colab L4). If `chosen_schema_valid
   ≥ 30%`, model size IS the lever; FULL becomes reachable on a
   stronger generator. If still 0-1/10, consider constrained decoding
   or a different approach entirely.
2. **Per-DB catalog snapshot to Drive** for Snow + BQ both, eliminates
   the `/content/` re-extract dance and makes the grounding pipeline
   reproducible across Colab restarts. Cost: ~10 min code, ~5 MB Drive.
3. **Hybrid retrieval** — if Spider2 per-task metadata includes a gold
   column list for any subset, inject that as the catalog filter.
   Mark results clearly as "oracle retrieval" — not equivalent to
   official EX.
4. **Push commits** (`a5cdbfe`, `09abb5a`, `44a4d23`, `2b95742`, and
   the incoming Phase 14 commit) only on explicit user approval.
   Rotate the GCP SA test key before any external publish.
