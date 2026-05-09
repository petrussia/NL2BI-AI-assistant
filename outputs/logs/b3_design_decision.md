# B3 Design Decision

Date: 2026-04-29T14:33:22.366176+00:00

## Scope
B3 = B2_v1 + dual retrieval. Adds two information sources to the prompt:
1. Schema (lexical schema linker — same as B1; reduced relevant tables).
2. Knowledge (synthetic per-table proxy documentation derived from schema metadata).

## Knowledge proxy
The thesis target is enterprise-data-from-heterogeneous-sources, which expects
real domain documentation. Spider has no such documentation. We construct a proxy:
for each table, we emit a short text describing the entity (table name pretty-print),
its columns with PK/FK flags and types from `tables.json`. This is **honestly
labeled as proxy** in `b3_retrieval_audit.md` and in code comments.

For real enterprise data, this proxy would be replaced with curated docs,
glossaries, ontology snippets, etc.

## Retrieval
Both channels use lexical overlap (table name × 2, column name × 1, knowledge
doc tokens × 1). Top-k tables and top-k knowledge snippets are combined.
No embeddings; consistent with the B1 baseline weight scheme.

## Why no embeddings yet
- Embeddings add a heavy dependency (sentence-transformers / FAISS).
- Spider's small per-DB schema (avg ~5 tables) makes lexical retrieval
  competitive within a single DB.
- Cross-DB embedding retrieval is the next-iteration upgrade.

## Out of B3 scope
- Repair / retry on SQL execution failure (B4).
- Multi-candidate generation + selection (B4).
- Cross-DB retrieval (B1R/B2R, separate baselines).
- Real grammar-constrained decoding (planned for B4 if time permits — currently approximated).

## Acceptance for B3 smoke10
- B3 plan_valid_count ≥ 9/10 (do not regress relative to B2_v1).
- B3 EX ≥ B2_v1 EX (0.8) on smoke10.
