# Spider2 Phase 13 (v11) — production recommendation

_Generated: 2026-05-08 | branch experiments/denis_

## TL;DR

- **Publishable now**: Spider2-DBT FULL 68 = **9/68 = 13.2%** (Phase 11,
  commit `09abb5a`). Unchanged this session.
- **Not publishable**: Snow / Lite-BQ / Lite-SF / Lite-SQLite — gates
  failed in pilots, no FULL launches.

## Validated architectural moves (safe to keep)

1. **Schema-grounding pre-execution validator** (v11). Uses sqlglot AST
   + per-DB catalog + Levenshtein nearest-match. Correctly catches
   invented identifiers before engine. Reduced Snow `object_not_found`
   reaching engine from 7/10 to 0/10.
2. **Async batch pattern** for Colab pilots (`start_*_bg` + Drive
   `_DONE` marker + 30s polling). Eliminated Cloudflare 524 timeout
   entirely. Both pilots ran for >800s without HTTP failures.
3. **BQ retry-wrapper** (`bigquery_persistent_executor_v10`) — built
   in Phase 12; not exercised this session because the async pattern
   already prevents transport failures. Keep available as a safety net.
4. **Snowflake dialect normalizer** (v9) and **identifier 4-part
   collapse** (v10) — both maintained at 0 occurrences in v11; safe to
   keep enabled.

## What is NOT yet validated

- Whether v11's single-round schema-aware repair is enough for any
  meaningful gate-clear rate. Pilot says no (0 successful repairs out
  of 9 attempts).
- Whether INT4 Coder-32B is feasible on Colab L4. Need a separate
  experiment (load + 10-task sanity).
- Whether multi-round repair (`max_repair_rounds=3`) helps. Untested.

## What MUST NOT go into ВКР

- Any Spider2-Snow FULL number (no FULL run).
- Any Spider2-Lite FULL or per-lane production score (only pilots).
- The 1/10 `chosen_schema_valid` from Snow v11 framed as a benchmark
  result. It is a pipeline-correctness signal, not a quality signal.

## Recommended next operational steps (priority order)

1. **Backport Snow v11 schema-grounding to Lite-BQ** (~1–2 h code).
   Write `spider2_lite_bq_v11_colab_runner.py` with the same validator
   (different catalog source: `resource/databases/bigquery/`). Pilot
   10 BQ tasks. Goal: `chosen_schema_valid ≥ 30%`.
2. **Try INT4-quantized Coder-32B on Snow v11 pilot10**
   (~30–45 min including model load via bitsandbytes). Goal: see
   whether `chosen_schema_valid` jumps to 5+/10. If yes → model
   quality is the bottleneck; if no → schema retrieval is the bottleneck.
3. **Multi-round schema-aware repair** (`max_repair_rounds=3` on Snow
   v11 same 10 tasks; ~25 min wall). Cheap experiment.
4. **Snapshot the catalog to Drive** (~15 min). Eliminates the
   `/content/` re-extract dance. Adds ~5 MB to Drive.
5. **Push commits** (`a5cdbfe`, `09abb5a`, `44a4d23`, and the
   incoming Phase 13 commit) only on explicit user approval. Rotate
   the GCP SA test key before any external publish.
