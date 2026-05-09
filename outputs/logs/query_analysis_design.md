# Query Analysis Design (closes ТЗ 2.2.1)

Date: 2026-04-29T14:59:37.653420+00:00

## Purpose
Add an explicit NL-query analysis layer that runs before the planner / SQL
synthesizer in B2..B4 baselines. Maps a natural-language question into a
structured `QueryAnalysis` object listing intent + signals.

## Why
Without this layer the planner had to derive intent from raw text every time;
this caused some classes of B2_v0 / B3 errors (e.g., "songs of the youngest
singer" misinterpreted as "single row by sort order"). Rule-based pre-analysis
makes signals explicit AND can be inspected, audited, and ablated.

## API (`repo/src/evaluation/query_analysis.py`)
- `analyze(question) -> dict` — pure rule-based, returns QueryAnalysis with:
  `raw_question`, `tokens`, `signals`, `predicted_intent`, `confidence`, `method`.
- `enrich_with_llm(question, base_analysis, gen_fn)` — optional, asks the model
  to confirm/correct intent. Original rule-based result is preserved; LLM result
  is added as a parallel field. Caller controls when to use it.
- `to_prompt_prefix(analysis) -> str` — renders analysis as a prompt prefix to
  inject into B2/B3/B4 planner prompts.

## Detected signals
- `aggregations`: count, sum, avg, min, max
- `distinct`: bool (distinct/unique/different)
- `ordering`: order_desc / order_asc / sort
- `limit`: int or None (top N, first N, "the youngest/largest/...")
- `time`: list of {kind, match} for year/date/month/before/after
- `comparisons`: list of operators >, <, >=, <=, =, !=
- `join_hint`: bool (for each / per X / along with)

## Intent classes
`select_count`, `select_aggregate`, `select_filter`, `select_join`,
`select_groupby`, `select_orderby`, `select_distinct`, `select_other`.
Same enum as `plan_schema_v1.json` so downstream consistency is trivial.

## Confidence
Heuristic value in [0, 1] derived from how many signals agree with the
chosen intent. Used downstream to decide if LLM refinement is worth invoking.

## Out of scope (deferred)
- Fine-tuned intent classifier.
- Embedding-based intent retrieval.
- Multi-language support.
- Question paraphrase normalization.

## Used by
- B2 / B3 / B4 baselines (optional `to_prompt_prefix` injection in next-iteration
  variants `b2_v2`, `b3_v2`, `b4_v2` if needed).
- Documentation / IO contract: the QueryAnalysis object is one of the formal
  intermediate representations of the system (see `outputs/docs/io_contracts.md`).
