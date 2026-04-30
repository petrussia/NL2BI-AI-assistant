# I/O Contracts

Date: 2026-04-29T15:03:36.172745+00:00.

## 1. NL Query (input)

Plain string. UTF-8. No length limit imposed by the system; practical max: 500 chars.

```
"How many singers do we have?"
```

## 2. QueryAnalysis (intermediate, after F1)

```json
{
  "raw_question": "<str>",
  "tokens": ["..."],
  "signals": {
    "aggregations": ["count" | "sum" | "avg" | "min" | "max"],
    "distinct": false,
    "ordering": ["order_desc" | "order_asc" | "sort"],
    "limit": null | <int>,
    "time": [{"kind": "year_filter" | "...", "match": "..."}],
    "comparisons": [">" | "<" | ">=" | "<=" | "=" | "!="],
    "join_hint": false
  },
  "predicted_intent": "select_count" | ...,
  "confidence": 0.0..1.0,
  "method": "rule_based_v1"
}
```

## 3. SchemaLinkResult (intermediate, after F2)

```json
{
  "db_id": "<str>",
  "q_tokens": ["..."],
  "all_tables": ["..."],
  "selected_table_indexes": [<int>, ...],
  "selected_tables": ["..."],
  "table_scores": {"<table_name>": <float>, ...},
  "matched_columns": {"<table_name>": ["<col>", ...], ...},
  "reduction_ratio": <float>,
  "fallback_used": false
}
```

## 4. JSON Plan (intermediate, after F5/F6)

`repo/docs/plan_schema_v1.json` — strict JSON Schema. Required: `intent`, `tables`, `operations`. Optional: `columns`, `filters`, `aggregations`, `group_by`, `order_by`, `limit`, `joins`, `notes`, `distinct`. `additionalProperties: false`.

```json
{
  "intent": "select_count",
  "tables": ["singer"],
  "operations": ["count"],
  "distinct": false
}
```

## 5. Generated SQL (intermediate, after F7)

Plain string (single SELECT statement, no trailing whitespace beyond a single semicolon).

```
SELECT COUNT(*) FROM singer;
```

## 6. AnalyticsPayload (output, after F13)

```json
{
  "schema_version": "v1",
  "produced_at": "<ISO8601 UTC>",
  "source": {
    "baseline": "B3" | ...,
    "model": "<HF model id>",
    "subset": "smoke_10" | ...,
    "idx": <int> | null,
    "db_id": "<str>",
    "question": "<str>",
    "generated_sql": "<str>",
    "gold_sql_present": <bool>
  },
  "rows": [{ "<col>": <value>, ... }, ...],
  "summary": {
    "row_count": <int>,
    "columns": {"<col>": {"count": <int>, "null_count": <int>, "distinct_count": <int>, "dtype": "numeric"|"categorical_or_mixed", ...} }
  },
  "n_rows": <int>,
  "is_executable": true,
  "notes": []
}
```

## 7. Prediction record (per-experiment artefact format)

JSON Lines, one record per item. Common fields:

| Field | Type | Notes |
|---|---|---|
| `idx` | int | item index in subset |
| `question` | str | original NL |
| `db_id` | str | gold DB id |
| `gold_sql` | str | reference SQL |
| `generated_raw` | str | raw model output |
| `generated_sql` | str | extracted SQL |
| `executable` | bool | did SQL run without exception |
| `execution_match` | bool | row-multiset equality with gold |
| `error_type` | str | "" / "result_mismatch" / "timeout" / "plan_invalid" / etc |
| `error_message` | str | short error description |

B1+ extras: `selected_tables`, `schema_reduction_ratio`, `fallback_used`.
B2+ extras: `plan_raw`, `plan_parsed`, `plan_valid`, `plan_error`.
B1R/B2R extras: `retrieved_db_id`, `retrieval_hit`, `retrieval_score`.
B4-lite extras: `cand_safe_flags`, `cand_results`, `selection_reason`, `repaired`.

## 8. Metrics CSV (per-run summary)

One row per run. Columns at minimum: `run_id`, `model`, `subset`, `n`, `execution_match_count`, `ex`, `executable_count`. Plus baseline-specific columns (`avg_reduction_ratio`, `plan_valid_count`, `plan_parse_failures`, `multi_candidate`, `repair_max`, `retrieval_hit_count`).
