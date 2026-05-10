# Test Strategy for NL2BI Integration

## 1. Test pyramid

```text
E2E smoke tests                    3-5 tests
Integration/API tests              10-20 tests
Contract/adapter tests             20-40 tests
Unit tests                         many small tests
Manual demo checklist              3 happy paths + 4 failure paths
```

## 2. Unit tests

### Contracts

Path: `packages/contracts/tests/`

| Test | Purpose |
|---|---|
| `test_nl2chart_request_minimal_valid` | Minimal user query validates |
| `test_data_extraction_response_requires_columns` | Extraction response must include explicit result columns |
| `test_visualization_request_metadata_names_match_columns` | Field metadata must refer to existing columns |
| `test_error_enum_values` | Shared error codes validate |
| `test_warning_shape` | Warnings are serializable and source-tagged |

### Adapter

Path: `packages/adapter/tests/`

| Test | Purpose |
|---|---|
| `test_type_mapping_numeric` | numeric SQL/pandas -> number |
| `test_type_mapping_datetime` | date/time -> date/datetime |
| `test_role_inference_time_series` | date + revenue -> time/measure |
| `test_role_inference_category_comparison` | string + numeric -> dimension/measure |
| `test_id_role_inference` | id-like names -> id |
| `test_allowed_aggregations_measure` | measure aggregation defaults |
| `test_already_aggregated_default_none` | prevent double aggregation |
| `test_empty_result_no_crash` | empty rows handled |
| `test_legacy_analytics_payload_v1_mapping` | maps current Denis artifact |

### Extraction service

Path: `services/extract/tests/`

| Test | Purpose |
|---|---|
| `test_extract_fixture_time_series` | Returns valid DataExtractionResponse |
| `test_select_only_guard_rejects_drop` | Rejects DDL/DML |
| `test_sql_timeout_maps_error` | Timeout maps to `timeout` |
| `test_row_limit_sets_truncated` | Row limit works |
| `test_empty_result_status` | Empty result safe response |
| `test_request_id_propagated` | Same request_id returned |

### Visualization service

Path: `services/visualize/tests/`

| Test | Purpose |
|---|---|
| `test_visualize_time_series_line` | Time series fixture -> line chart |
| `test_visualize_category_bar` | Category comparison -> bar chart |
| `test_visualize_topn_table_preferred` | Explicit table request -> table primary |
| `test_visualize_empty_result` | Empty result -> no chart crash |
| `test_visualize_missing_metadata_warning` | Missing roles -> warning + fallback |
| `test_render_failure_partial_success` | Spec returned if PNG render fails |
| `test_fast_path_latency_small_fixture` | Fast path under practical threshold |

## 3. Integration/API tests

Path: `tests/integration/`

### Gateway with mocked clients

| Test | Expected |
|---|---|
| `POST /api/nl2chart` with time-series fixture | `status=success`, chart artifact |
| extraction failure | `status=failed`, no visualization call |
| visualization failure | `partial_success`, table fallback |
| render failure | `partial_success`, spec artifact exists |
| artifact retrieval | `GET /api/artifacts/{id}` returns content |
| chat message endpoint | persists user and assistant messages with artifacts |

### Service-to-service tests

| Test | Expected |
|---|---|
| gateway -> extract -> adapter -> visualize with fixture | Success |
| `request_id` consistency | Same id in logs/responses |
| `metadata_incomplete` warning propagation | Warning visible in final response |
| `truncated=true` propagation | UI artifact warning generated |

## 4. E2E tests

Path: `tests/e2e/` or Playwright if added.

| Test | Steps | Success criteria |
|---|---|---|
| Happy path time series | login -> chat -> ask «Покажи динамику выручки по месяцам» | line chart/table artifact visible |
| Category comparison | ask «Сравни продажи по категориям» | bar chart artifact visible |
| Top-N table | ask «Покажи топ-5 клиентов таблицей» | table primary, sorted rows |
| Empty result | ask fixture query with no rows | empty state, no crash |
| Metadata incomplete | mock missing roles | warning visible, fallback artifact visible |

## 5. Manual smoke checklist

1. `docker compose -f docker-compose.mvp.yml up --build`.
2. Open `http://localhost:3001/login`.
3. Register/login user.
4. Open `/app/chat`.
5. Send time-series query.
6. Confirm assistant response contains:
   - user-friendly text;
   - chart/table artifact;
   - no raw stack trace;
   - no Superset links;
   - no OpenAI requirement.
7. Switch technical mode.
8. Confirm SQL/debug block is visible only in technical mode.
9. Download spec/table/PNG if present.
10. Check backend logs contain same `request_id` across stages.

## 6. Contract fixture matrix

| Fixture | Purpose | Expected selected view |
|---|---|---|
| `time_series_extraction_response.json` | Date/month + numeric measure | line chart |
| `category_comparison_extraction_response.json` | Dimension + measure | bar chart |
| `topn_extraction_response.json` | Top-N table preference | table primary, bar candidate optional |
| `empty_result_extraction_response.json` | SQL returns zero rows | empty table / safe error |
| `incomplete_metadata_extraction_response.json` | Missing roles/types | fallback + warning |

## 7. CI gates

Required before merge:

```bash
python -m pytest packages/contracts packages/adapter services/gateway services/extract services/visualize tests/integration
cd apps/web && npm ci && npm run build
python scripts/validate_openapi.py  # if script exists
bash scripts/check_no_superset_openai_runtime.sh
```

Forbidden runtime strings check:

```bash
! grep -R "ChatOpenAI\|MCPAgent\|mcp_use" services packages apps/web/src || exit 1
! grep -R "OPENAI_API_KEY" services packages apps/web/src docker-compose.mvp.yml || exit 1
! grep -R "superset-init\|mcp-http\|apachesuperset" docker-compose.mvp.yml || exit 1
```

Historical docs may contain these strings, but runtime code and MVP compose must not.
