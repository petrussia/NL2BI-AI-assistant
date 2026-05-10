# Executive Summary

## Цель

Собрать единую NL2BI-систему в `petrussia/NL2BI-AI-assistant/tree/main`, где пользователь вводит текстовый запрос в веб-чате, а получает таблицу, график и пояснение.

Целевой путь:

```text
User
  -> Web UI / Chat
  -> Common FastAPI Backend
  -> Text-to-SQL/DataExtraction service
  -> Adapter layer
  -> Text-to-Visualization service
  -> Artifact storage
  -> Web UI / Chat response
```

## Базовые решения

1. **Frontend и часть backend**: взять из `SHUBINDENIS/superset_ai`:
   - Next.js UI shell;
   - login/register;
   - chat sessions;
   - chat messages;
   - artifact rendering model;
   - FastAPI routers/dependencies style;
   - Next.js catch-all API proxy.

2. **Удалить из `superset_ai`**:
   - `superset/`;
   - Superset MCP runtime;
   - `/app/preview`, `/app/recommend`, `/app/share`, `/app/scan` в текущем Superset-смысле;
   - Superset-specific API routes: `/api/viz/*`, `/api/scan/*`;
   - `langchain-openai`, `openai`, `mcp-use`, Superset service dependencies;
   - обязательный `OPENAI_API_KEY` и `OPENAI_MODEL`.

3. **Добавить вместо этого**:
   - `POST /api/nl2chart` как главный endpoint;
   - `GET /api/nl2chart/{request_id}` для статуса;
   - `GET /api/artifacts/{artifact_id}` для PNG/SVG/HTML/spec/table;
   - `POST /extract` wrapper для Дениса;
   - `POST /visualize` wrapper для Петра;
   - `packages/contracts` и `packages/adapter`.

## MVP-режим

Для MVP не нужен OpenAI и не нужен Superset. MVP должен запускаться так:

1. Пользователь отправляет сообщение в чат.
2. Backend создаёт `request_id`.
3. Backend вызывает upstream Дениса или in-process wrapper.
4. Upstream возвращает SQL, rows, columns, row_count, source context.
5. Adapter строит `VisualizationRequest`.
6. Downstream Петра строит Vega-Lite-like spec и/или PNG.
7. Backend сохраняет артефакты и возвращает их в chat message artifacts.

## Ключевой контракт MVP

Минимально нужны:

- `request_id`;
- `user_query`;
- `result_table.columns`;
- `result_table.rows` или `result_table.uri`;
- `field_metadata[].name`;
- `field_metadata[].data_type`;
- `field_metadata[].semantic_role`;
- `query_context.sql`;
- `query_context.filters/group_by/aggregations` по возможности.

## Главные риски

| Риск | Почему критично | Решение |
|---|---|---|
| Нет `request_id` | Невозможно трассировать цепочку | Backend генерирует UUID и пробрасывает везде |
| Неполные metadata | Пётр неверно выберет тип графика | Adapter inference + warnings |
| Double aggregation | График будет аналитически неверным | Provenance/default_aggregation=`none` for already aggregated |
| Нет row-limit/truncated | Пользователь может увидеть неполный результат как полный | Executor/backend row limit + `truncated` |
| Несовпадение names между rows/columns/metadata | Downstream validation падает | Contract tests |
| LLM latency | Сайт будет таймаутиться | Fast sync path, LLM async quality mode |

## Рекомендуемый roadmap

1. **Неделя 1**: импортировать и очистить `superset_ai`, поднять chat shell и auth без Superset/OpenAI.
2. **Неделя 1–2**: добавить contracts + adapter + fixture tests.
3. **Неделя 2**: завернуть upstream Дениса в service-compatible function/API.
4. **Неделя 2**: завернуть downstream Петра в service-compatible function/API.
5. **Неделя 3**: реализовать `POST /api/nl2chart` и связать с чатом.
6. **Неделя 3**: e2e tests, docker compose MVP, demo fixtures.
7. **После MVP**: artifact storage, async quality mode, model serving, production hardening.
