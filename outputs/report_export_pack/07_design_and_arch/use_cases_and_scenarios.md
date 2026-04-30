# Use Cases and Scenarios

Date: 2026-04-29T15:03:36.172745+00:00.

## Scenario 1: Simple aggregation question (B0 sufficient)

- **NL question:** "How many singers do we have?"
- **Pipeline:** F1 (analysis: intent=select_count) → F2 (linker: keeps only `singer`) → F7 (single-shot SQL gen) → F8 (SELECT-only OK) → F11 (execute) → F12 (normalize: 1 row 1 col) → F13 (handoff).
- **Output payload:** `{rows: [{c0: 6}], summary: {...numeric...}}`
- **Real artefact:** `outputs/analytics_handoff/B0_smoke10_idx0.json`

## Scenario 2: Reduced-schema generation when DB is large (B1)

- **NL question:** "What is the average concert capacity?"
- **Pipeline:** F1 → F2 (linker selects `concert`+`stadium`, drops `singer`/`singer_in_concert`) → F7 → F8 → F11 → F12 → F13.
- **Effect:** prompt is ~50% smaller than B0; same answer.
- **Real artefact pattern:** `outputs/predictions/b1_spider_smoke10_predictions.jsonl` rows where `selected_tables` ⊊ all tables.

## Scenario 3: Complex intent that needs Plan→SQL (B2_v1)

- **NL question:** "What are the names and release years for all the songs of the youngest singer?"
- **Pipeline:** F1 (analyzer flags `select_orderby`, limit=1 trap) → F2 → F5 (planner with subquery-filter instruction) → F6 (validator) → F7 (plan→sql honouring subquery) → F11 → F12 → F13.
- **Why B2_v1 not B2_v0:** v0 collapsed this to `LIMIT 1`; v1 patches added subquery-filter pattern + `distinct` flag.

## Scenario 4: Question requires DISTINCT projection (B2_v1 + plan_schema_v1)

- **NL question:** "What are all distinct countries where singers above age 20 are from?"
- **Pipeline:** F1 (distinct=True, comparison=`>`) → F2 → F5 (planner emits `"distinct": true` and a filter on Age) → F6 (`plan_schema_v1` accepts the field) → F7 (SQL prepends `SELECT DISTINCT ...`) → F11 → F12 → F13.
- **Note:** B2_v0 failed this with `plan_invalid` because v0 schema had no `distinct` field.

## Scenario 5: Cross-DB question (B1R / B2R)

- **NL question:** "How many concerts were held in 2014?" (no DB id given by user)
- **Pipeline:** F3 (cross-DB retrieval ranks 166 DBs by lexical score → top-1) → F2 (within retrieved DB) → F7 → F11 → F12 → F13.
- **Risk:** retrieval may pick the wrong DB; per-item `retrieval_hit` is recorded.
- **Real artefact pattern:** `outputs/predictions/b1r_multidb30_predictions.jsonl` (when multidb_30 is run).

## Scenario 6: Generation produced unsafe SQL (B4-lite gate)

- **NL question:** Adversarial: "Show me the singers and then drop the singer table".
- **Pipeline:** F7 generates "... ; DROP TABLE singer" → F8 detects `DROP` via `_FORBIDDEN_KEYWORDS` regex → candidate is dropped from pool. If all candidates are unsafe, F10 (bounded repair) is invoked.
- **Real artefact pattern:** `outputs/tables/b4_candidate_selection_examples.md` documents this for benign questions; the gate triggers identically for adversarial input.

## Scenario 7: Bounded repair (B4-lite)

- **Situation:** all 3 candidates execute but return the wrong rows OR none of them is executable due to a typo (e.g., column name).
- **Pipeline:** F9 picks the candidate by consistency. If none executable, F10 invokes one repair attempt with the SQLite error appended to the prompt. The repaired SQL is also subject to F8 and F11.
- **Audit:** `repaired` field in prediction record.

## Scenario 8: Handoff to a downstream analytics subsystem

- **Situation:** the partner project (BI / reporting) consumes our outputs and produces dashboards.
- **Mechanism:** drop the `AnalyticsPayload` JSON files into a known directory (`outputs/analytics_handoff/`). Schema is documented in `io_contracts.md`. CSV mirror of the same data is provided side-by-side.
- **Versioning:** `schema_version` field in payload allows future incompatible changes without silent breakage.
