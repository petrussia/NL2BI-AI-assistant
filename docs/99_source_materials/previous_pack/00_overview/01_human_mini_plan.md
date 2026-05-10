# Мини-план для человека

## День 0: зафиксировать границы

- Создать ветку `integration/nl2chart-mvp` от `main` в `petrussia/NL2BI-AI-assistant`.
- Принять структуру монорепозитория из `02_architecture/target_repo_structure.md`.
- Договориться: MVP без Superset и без OpenAI API; все LLM — локальные/внутренние, если нужны.

## Шаг 1: перенести chat shell

Ответственный: shared / frontend.

- Скопировать из `SHUBINDENIS/superset_ai` только `frontend-next`, `api`, auth/chat persistence и health/frontend logs.
- Переименовать продукт из `Superset AI Assistant` в `NL2BI AI Assistant`.
- Удалить Superset routes/pages или временно скрыть их.
- Проверить `npm run build` и health backend.

## Шаг 2: очистить backend от OpenAI/Superset

Ответственный: shared / backend.

- Удалить обязательную проверку `OPENAI_API_KEY`.
- Заменить `SupersetAIAgent` на `Nl2biChatAgent` или `Nl2biOrchestrator`.
- Удалить MCP/Superset service dependencies.
- Оставить chat history, user/session settings, artifacts.

## Шаг 3: добавить общий контракт

Ответственный: shared.

- Добавить `packages/contracts`.
- Описать Pydantic models: `DataExtractionRequest/Response`, `VisualizationRequest/Response`, `Nl2ChartRequest/Response`, `ArtifactRef`, `ErrorItem`.
- Добавить shared error enum.
- Написать unit tests на validation.

## Шаг 4: сделать adapter

Ответственный: shared.

- `normalize_extraction_response(response) -> VisualizationRequest`.
- `AnalyticsPayload v1 -> DataExtractionResponse`.
- Type mapping, role inference, null handling, truncation, warnings.
- Contract tests на 5 fixtures.

## Шаг 5: завернуть Дениса

Ответственный: Denis.

- Вынести notebook/experiment logic в callable function.
- Сделать `extract(request: DataExtractionRequest) -> DataExtractionResponse`.
- Добавить `request_id`, `columns`, `row_count`, `truncated`, `errors`.
- Для MVP можно возвращать synthetic/mock fixture при отсутствии реальной БД, но API shape должен быть настоящим.

## Шаг 6: завернуть Петра

Ответственный: Peter.

- Сделать `visualize(request: VisualizationRequest) -> VisualizationResponse`.
- Для MVP использовать B1 constraint-ranker или B2 partial recommender как fast sync default.
- Добавить inline records adapter или временную materialization в CSV.
- Возвращать Vega-Lite/spec/table + optional PNG.

## Шаг 7: связать общий backend

Ответственный: shared.

- Реализовать `POST /api/nl2chart`.
- В chat `POST /api/chats/{session_id}/messages` вызвать `nl2chart` вместо OpenAI agent.
- Ответ положить в assistant message: краткий текст + artifacts.

## Шаг 8: frontend artifacts

Ответственный: frontend/shared.

- В chat bubble поддержать artifacts типов `table`, `chart_spec`, `image`, `error`, `warning`.
- Показывать empty result / metadata warning / truncated flag.
- Добавить кнопку «Скачать PNG/spec/table CSV».

## Шаг 9: тесты

Ответственный: все.

- Unit: contracts, adapter, role inference.
- Integration: `/extract`, `/visualize`, `/api/nl2chart` на fixtures.
- E2E: login → chat → ask query → chart artifact visible.
- Smoke: docker compose up + health/ready.

## Шаг 10: demo and freeze

Ответственный: shared.

- Подготовить 3 demo-запроса: time series, category comparison, top-N table.
- Зафиксировать known limitations.
- Обновить README и runbook.
