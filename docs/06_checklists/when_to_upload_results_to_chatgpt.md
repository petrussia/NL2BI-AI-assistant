# Когда и что присылать ChatGPT для сверки

## После этапа 0/1: server bootstrap

Прислать:

```text
1. Codex report.
2. git status.
3. top-level tree.
4. /api/health JSON.
5. /api/runtime JSON.
6. Список зависимостей server runtime.
7. Подтверждение, что OpenAI/Superset/MCP отключены.
```

Цель моей проверки: убедиться, что серверная среда не смешалась с LLM/Colab и не требует GPU.

## После этапа 2: server mock pipeline

Прислать:

```text
1. Codex report.
2. pytest output.
3. /api/runtime JSON with EXTRACTION_MODE=mock.
4. /api/nl2chart JSON for:
   - time_series;
   - category_comparison;
   - top_n;
   - empty_result.
5. Artifact JSON/spec/table for at least one request.
```

Цель моей проверки: проверить contract shape, adapter, fallback visualization и user-safe errors.

## После этапа 3: Colab service

Прислать:

```text
1. Claude report.
2. Colab /health JSON.
3. Colab /extract JSON for at least one query.
4. GPU name and VRAM.
5. Model id and quantization.
6. SQL safety/timeout/row_limit evidence.
7. Errors, if model loading failed.
```

Цель моей проверки: проверить, что Colab возвращает именно DataExtractionResponse, а не произвольный notebook output.

## После этапа 4: server -> Colab smoke

Прислать:

```text
1. /api/runtime JSON with EXTRACTION_MODE=colab.
2. /api/nl2chart JSON in colab mode.
3. Server log lines for request_id.
4. Colab log lines for same request_id.
5. Artifact spec/table/image URI.
6. Full error/warning list.
7. Colab unavailable test result.
```

Цель моей проверки: сверить межсервисное взаимодействие и маппинг ошибок.

## После этапа 5: frontend chat artifacts

Прислать:

```text
1. Codex report.
2. Assistant message JSON with artifacts.
3. Screenshot or textual description of chat result.
4. npm build/test output.
5. UI behavior for warning/error/empty result.
```

Цель моей проверки: убедиться, что пользователь видит правильный BI-result, а не debug JSON.

## После финального этапа

Прислать:

```text
1. docs/final_integration_review_server_colab.md.
2. E2E pass/fail table.
3. Five /api/nl2chart JSON responses:
   - time series;
   - category comparison;
   - top-N;
   - empty result;
   - Colab unavailable.
4. Colab /health JSON.
5. Server /api/runtime JSON.
6. Remaining risks.
7. Что хотите включить в ВКР как финальную архитектуру.
```

Цель моей проверки: сделать финальную сверку и помочь сформулировать главу архитектуры/реализации/тестирования для ВКР.
