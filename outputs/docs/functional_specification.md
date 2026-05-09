# Functional Specification

Date: 2026-04-29T15:03:36.172745+00:00.

## What the system does

Turns a natural-language question targeted at a relational database into an executable SQLite SQL query, runs it against the database, and returns a structured analytics payload that downstream BI / reporting subsystems can consume.

## Functional blocks (with input → output contracts)

### F1. Query Analysis
- Input: NL question (string).
- Output: `QueryAnalysis` (dict) with `predicted_intent` ∈ {select_count, select_aggregate, select_filter, select_join, select_groupby, select_orderby, select_distinct, select_other}, `signals` (aggregations, distinct, ordering, limit, time, comparisons, join_hint), `tokens`, `confidence`.

### F2. Schema Retrieval
- Input: NL question, DB id (gold or retrieved), `tables_map`.
- Output: `SchemaLinkResult` (dict) with `selected_table_indexes`, `selected_tables`, `reduction_ratio`, `fallback_used`, `matched_columns`.

### F3. Cross-DB Retrieval (B1R / B2R / B3 with cross-DB enabled)
- Input: NL question, `tables_map` (all DBs).
- Output: ranked list of `(db_id, score, breakdown)`.

### F4. Knowledge Retrieval (B3+, proxy docs)
- Input: NL question, DB tables_obj.
- Output: top-k synthetic per-table docs (from schema metadata).

### F5. Planner
- Input: NL question, reduced schema context, optional knowledge snippets.
- Output: raw model output → JSON parse → `Plan` dict.

### F6. Plan Validator
- Input: Plan dict, `plan_schema.json` / `plan_schema_v1.json`.
- Output: `(plan_obj, plan_valid: bool, plan_error: str)`.

### F7. SQL Synthesizer (single-candidate)
- Input: NL question, Plan, reduced schema (+ optional knowledge).
- Output: raw model SQL text → regex extraction → SQL string.

### F8. Validation Gate (B4-lite)
- Input: SQL string.
- Output: `(safe: bool, reason: str)`. Rejects DDL/DML/PRAGMA/etc.

### F9. Multi-Candidate Generation & Selection (B4-lite)
- Input: prompt, num_return_sequences=K, temperature, top_p.
- Output: K candidates → safe-filter → execute each → consistency pick.

### F10. Bounded Repair (B4-lite)
- Input: failed SQL, error message, schema, plan.
- Output: re-generated SQL (1 retry, then give up).

### F11. SQL Executor
- Input: SQL, sqlite path, timeout=8s.
- Output: row tuples or exception.

### F12. Postprocess
- Input: row tuples, optional column names.
- Output: list of dicts with type-coerced values + per-column descriptive summary.

### F13. Analytics Handoff
- Input: postprocessed rows + summary + source metadata.
- Output: `AnalyticsPayload` (dict) following schema_version "v1"; serialized to JSON + CSV.

## Supported question classes

- Single-table SELECT with optional WHERE, GROUP BY, ORDER BY, LIMIT, DISTINCT.
- Multi-table joins (lexical link will pick relevant tables; planner emits join descriptions).
- Aggregations (COUNT, SUM, AVG, MIN, MAX).
- Subquery filters (added in v1: "find X whose property = MIN(...)" pattern).
- Time-bounded filters (year/date — analyzer detects, planner emits filter).

## Out of supported scope

- Update/insert/delete (intentionally blocked by validation gate).
- Multi-statement SQL (single SELECT only).
- Recursive CTEs (planner does not target this; can degrade gracefully).
- Domain-specific NL paraphrasing / multilingual queries.
