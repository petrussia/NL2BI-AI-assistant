# Prompt 04 — Codex / Peter: server CPU visualization service

Ты работаешь в `petrussia/NL2BI-AI-assistant` на ветке `integration/server-colab-nl2chart-mvp`.

## Цель

Сделать production-like CPU wrapper для Text-to-Visualization на server-runtime. Сервер без GPU, 8 GB RAM. Colab не используется для default visualization path.

## Контекст

Downstream-модуль Петра принимает готовую таблицу, текст запроса и metadata. Он не генерирует SQL. В текущих экспериментах есть B0/B1/B2/B3/B4/B5, но для server-runtime default разрешены только CPU-safe подходы: B0/B1/B2 или минимальный deterministic fallback.

## Жёсткие ограничения

1. Не импортировать `torch`, `transformers`, `bitsandbytes` в server runtime.
2. Не запускать LLM на сервере.
3. Не вызывать Colab на этом этапе.
4. Не генерировать SQL.
5. Работать с inline `result_table.rows`, без обязательного CSV path.
6. Всегда возвращать `VisualizationResponse` со status.
7. Не падать при неполных metadata.

## Реализовать

```text
services/visualization/cpu_visualization_service.py
services/visualization/rules.py
services/visualization/validation.py
services/visualization/render.py
```

### Input

`VisualizationRequest`:

- `request_id`;
- `user_query`;
- `result_table.columns`;
- `result_table.rows`;
- `field_metadata`;
- `query_context`;
- `presentation_preferences`.

### Output

`VisualizationResponse`:

- `request_id`;
- `status`;
- `selected_view`;
- `candidates`;
- `table_view`;
- `explanation`;
- `quality`;
- `performance`;
- `errors`;
- `warnings`.

## Logic

Implement or wrap B0/B1/B2:

1. Validate rows/columns.
2. Infer field roles if missing.
3. Detect intent from query:
   - trend/dynamics/time;
   - comparison/category;
   - top-N/list/table;
   - correlation;
   - distribution;
   - unknown.
4. Generate candidates:
   - line;
   - bar;
   - scatter;
   - table.
5. Apply hard constraints:
   - field exists;
   - x/y compatible;
   - aggregation legal;
   - time field for line preferred;
   - no chart if 0 rows.
6. Rank candidates.
7. Return selected view.
8. Store artifact if artifact service available.

## Fallback rules

| Case | Behavior |
|---|---|
| time + measure | line chart |
| dimension + measure | bar chart |
| two measures | scatter chart |
| top-N/order_by | table or bar |
| query asks table | table |
| query asks chart but data only has text | table + warning |
| 0 rows | failed or partial_success with `empty_result` |
| 1 row | table or single-value card |
| too many rows | truncate + warning |
| missing unit | continue + warning |
| missing role | infer + warning |
| missing allowed_aggregations | conservative defaults |
| invalid field reference | failed with validation error |

## Vega-Lite-like spec

Return spec like:

```json
{
  "mark": "line|bar|point",
  "encoding": {
    "x": {"field": "month", "type": "temporal"},
    "y": {"field": "revenue", "type": "quantitative", "aggregate": "sum"}
  },
  "data": {"values": []},
  "title": "..."
}
```

For large responses, `data.values` can be omitted if table artifact is stored separately, but MVP can inline small rows.

## Tests

Create/update:

```text
tests/unit/test_cpu_visualization_service.py
tests/unit/test_visualization_fallbacks.py
tests/integration/test_nl2chart_visualization_mock.py
```

Test cases:

1. time series -> line;
2. category comparison -> bar;
3. top-N -> table/bar;
4. empty rows -> safe response;
5. metadata incomplete -> warning + inferred roles;
6. all text fields -> table;
7. one row -> table/card;
8. invalid metadata field -> failed.

## Checks

```bash
pytest -q tests/unit/test_cpu_visualization_service.py tests/unit/test_visualization_fallbacks.py
curl -X POST http://127.0.0.1:8100/api/nl2chart \
  -H 'Content-Type: application/json' \
  -d '{"user_query":"Покажи выручку по месяцам","data_source_id":"demo_sales"}'
```

## Acceptance criteria

- Works on server without GPU.
- No LLM dependencies in default path.
- Visualization response is valid for time/category/top-N.
- Fallback warnings are explicit.
- Empty result does not crash.
- Server mock `/api/nl2chart` includes selected chart/table artifact.

## Итоговый отчёт

Output:

1. Changed files.
2. Which B0/B1/B2 logic was reused or reimplemented.
3. Test outputs.
4. Example `VisualizationResponse` for time/category/top-N.
5. Known limitations.
6. What to send to ChatGPT after this stage.
