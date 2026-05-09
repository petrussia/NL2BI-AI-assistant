# NL2BI contracts — server + Colab MVP

This file summarizes the contracts that must be implemented as Pydantic models.

## 1. Common enums

```python
Status = Literal["success", "partial_success", "failed"]
ErrorSource = Literal["server", "colab", "extraction", "adapter", "visualization", "frontend", "unknown"]
```

## 2. ErrorItem

```json
{
  "code": "string",
  "message": "string",
  "source": "server|colab|extraction|adapter|visualization|frontend|unknown",
  "retryable": false,
  "details": {}
}
```

Recommended error codes:

- `colab_unavailable`
- `extraction_timeout`
- `invalid_extraction_response`
- `colab_service_error`
- `colab_request_error`
- `model_not_loaded`
- `schema_not_found`
- `ambiguous_query`
- `sql_generation_failed`
- `sql_validation_failed`
- `sql_execution_failed`
- `timeout`
- `empty_result`
- `row_limit_exceeded`
- `metadata_incomplete`
- `visualization_failed`
- `render_failed`

## 3. DataExtractionRequest

Server sends this to Colab in `EXTRACTION_MODE=colab`.

```json
{
  "request_id": "string",
  "user_query": "string",
  "locale": "ru-RU",
  "timezone": "Europe/Moscow",
  "data_source": {
    "id": "string",
    "dialect": "sqlite|postgresql|clickhouse|trino|unknown",
    "connection_ref": "string|null",
    "schema_version": "string|null"
  },
  "constraints": {
    "read_only": true,
    "timeout_ms": 8000,
    "row_limit": 1000,
    "allow_llm_repair": true
  },
  "presentation_hint": {
    "preferred_output": "auto|chart|table",
    "requested_fields": [],
    "requested_metrics": []
  }
}
```

## 4. DataExtractionResponse

Colab returns this to server.

```json
{
  "request_id": "string",
  "status": "success|partial_success|failed",
  "user_query": "string",
  "normalized_query": "string|null",
  "data_source": {
    "id": "string",
    "name": "string|null",
    "dialect": "sqlite|postgresql|clickhouse|trino|unknown",
    "schema_version": "string|null"
  },
  "plan": {
    "raw": {},
    "validated": true,
    "intent": "string|null",
    "tables": [],
    "columns": [],
    "filters": [],
    "aggregations": [],
    "group_by": [],
    "order_by": [],
    "limit": null,
    "joins": [],
    "assumptions": []
  },
  "sql": {
    "query": "string|null",
    "dialect": "sqlite|postgresql|clickhouse|trino|unknown",
    "validated": true,
    "read_only": true
  },
  "result_table": {
    "format": "records",
    "columns": [],
    "rows": [],
    "uri": null,
    "row_count": 0,
    "truncated": false
  },
  "field_metadata": [],
  "execution": {
    "latency_ms": null,
    "row_limit": 1000,
    "timeout_ms": 8000,
    "executable": true
  },
  "quality": {
    "confidence": null,
    "warnings": []
  },
  "errors": [],
  "warnings": []
}
```

## 5. FieldMetadata

```json
{
  "name": "string",
  "source_table": "string|null",
  "source_column": "string|null",
  "display_name": "string|null",
  "description": "string|null",
  "sql_type": "string|null",
  "data_type": "number|string|date|datetime|boolean|unknown",
  "semantic_role": "measure|dimension|time|id|text|unknown",
  "unit": "string|null",
  "periodicity": "day|week|month|quarter|year|null",
  "allowed_aggregations": ["sum", "avg", "count", "min", "max", "none"],
  "default_aggregation": "sum|avg|count|min|max|none|null",
  "nullable": "boolean|null",
  "examples": [],
  "provenance": {
    "expression": "string|null",
    "aggregation": "string|null",
    "derived": false
  }
}
```

## 6. VisualizationRequest

Server adapter creates this from `DataExtractionResponse`.

```json
{
  "request_id": "string",
  "user_query": "string",
  "locale": "ru-RU",
  "timezone": "Europe/Moscow",
  "data_source": {},
  "result_table": {
    "format": "records",
    "columns": [],
    "rows": [],
    "uri": null,
    "row_count": 0,
    "truncated": false
  },
  "field_metadata": [],
  "query_context": {
    "sql": "string|null",
    "plan": {},
    "filters": [],
    "group_by": [],
    "aggregations": [],
    "order_by": [],
    "limit": null,
    "assumptions": []
  },
  "presentation_preferences": {
    "preferred_output": "auto|chart|table",
    "preferred_chart_type": null,
    "style_template": null,
    "max_candidates": 3,
    "render": true
  }
}
```

## 7. VisualizationResponse

```json
{
  "request_id": "string",
  "status": "success|partial_success|failed",
  "selected_view": {
    "type": "chart|table",
    "chart_type": "bar|line|scatter|pie|area|table|unknown",
    "title": "string",
    "spec": {},
    "normalized_spec": {},
    "rendered_artifacts": {
      "png_uri": null,
      "svg_uri": null,
      "html_uri": null
    }
  },
  "candidates": [],
  "table_view": {},
  "explanation": {
    "intent": null,
    "used_fields": [],
    "used_aggregations": [],
    "reason": "string"
  },
  "quality": {
    "confidence": null,
    "validation_passed": true,
    "warnings": []
  },
  "performance": {
    "latency_ms": null,
    "model": "local_cpu_rules",
    "mode": "fast|fallback"
  },
  "errors": [],
  "warnings": []
}
```

## 8. Nl2ChartRequest

Frontend/server chat sends this to `/api/nl2chart`.

```json
{
  "user_query": "string",
  "data_source_id": "demo_sales",
  "locale": "ru-RU",
  "timezone": "Europe/Moscow",
  "presentation_preferences": {
    "preferred_output": "auto|chart|table"
  }
}
```

## 9. Nl2ChartResponse

```json
{
  "request_id": "string",
  "status": "success|partial_success|failed",
  "message": "string",
  "selected_view": {},
  "artifacts": [],
  "warnings": [],
  "errors": [],
  "debug": {}
}
```
