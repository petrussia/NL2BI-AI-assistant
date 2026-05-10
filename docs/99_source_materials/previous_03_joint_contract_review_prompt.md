# Дополнительный промпт: сверка контрактов двух веток

Ты работаешь как integration architect. У тебя есть два аудита:
- `integration_packet_denis.md` — upstream Text-to-SQL/DataExtraction;
- `integration_packet_peter.md` — downstream Text-to-Visualization.

Нужно сопоставить контракты и подготовить финальную таблицу совместимости. Не переписывай код. Не придумывай факты, которых нет в аудитах. Если информации не хватает — помечай как unknown.

Подготовь файл `joint_integration_contract_review.md`.

Структура результата:

# joint_integration_contract_review.md

## 1. Итоговая схема пайплайна
Опиши последовательность:
1. `POST /nl2chart` на общем backend'е;
2. вызов upstream `DataExtractionRequest`;
3. получение `DataExtractionResponse`;
4. нормализация таблицы и metadata;
5. вызов downstream `VisualizationRequest`;
6. получение `VisualizationResponse`;
7. возврат сайта пользователю.

Дай ASCII-схему:
User → Web UI → API Gateway → Text-to-SQL Service → Result/Metadata → Visualization Service → Chart/Table Artifact → Web UI.

## 2. Совместимость полей
Составь таблицу:

| Поле | Денис отдаёт? | Пётр требует? | Совместимо? | Действие |
|---|---:|---:|---:|---|

Проверь:
- request_id;
- user_query;
- locale;
- timezone;
- datasource id;
- dialect;
- SQL;
- plan;
- rows;
- columns;
- row_count;
- truncated;
- field name;
- display_name;
- sql_type;
- data_type;
- semantic_role;
- description;
- unit;
- periodicity;
- allowed_aggregations;
- default_aggregation;
- filters;
- group_by;
- aggregations;
- order_by;
- limit;
- provenance;
- errors;
- warnings;
- confidence;
- latency.

## 3. Минимальный контракт MVP
Сформируй минимальный JSON-контракт, который можно внедрить первым.

Должны быть только поля, без которых пайплайн не заработает:
- request_id;
- user_query;
- result_table.columns;
- result_table.rows или result_table.uri;
- field_metadata.name;
- field_metadata.data_type;
- field_metadata.semantic_role;
- query_context.sql;
- query_context.aggregations/group_by/filters по возможности.

Дай JSON Schema/Pydantic-like описание.

## 4. Расширенный контракт для хорошего качества
Сформируй расширенный контракт для улучшения качества:
- description;
- unit;
- periodicity;
- allowed aggregations;
- default aggregation;
- metric definition;
- grain;
- provenance;
- display formatting;
- cardinality;
- examples;
- confidence/warnings.

Укажи, как каждое поле влияет на выбор графика.

## 5. Adapter layer
Предложи слой адаптера между Денисом и Петром:
- `normalize_extraction_response(response) -> VisualizationRequest`;
- mapping SQL types to visualization data types;
- role inference;
- metadata enrichment;
- table truncation;
- null handling;
- error mapping;
- provenance mapping.

Дай псевдокод или Python-like структуру без полной реализации.

## 6. Общие статусы и ошибки
Согласуй enum статусов:
- success;
- partial_success;
- failed.

Согласуй error codes:
- schema_not_found;
- ambiguous_query;
- sql_generation_failed;
- sql_validation_failed;
- sql_execution_failed;
- timeout;
- empty_result;
- row_limit_exceeded;
- metadata_incomplete;
- visualization_failed;
- render_failed.

Для каждой ошибки укажи:
- кто генерирует;
- кто обрабатывает;
- что показывать пользователю на сайте.

## 7. API микросервисов
Предложи endpoint'ы:

Общий backend:
- `POST /api/nl2chart`;
- `GET /api/nl2chart/{request_id}`;
- `GET /api/artifacts/{artifact_id}`.

Text-to-SQL service:
- `POST /extract`;
- `GET /health`;
- `GET /ready`.

Visualization service:
- `POST /visualize`;
- `GET /visualize/{request_id}`;
- `GET /health`;
- `GET /ready`.

Для каждого endpoint укажи:
- request body;
- response body;
- sync/async;
- timeout;
- retry policy.

## 8. Интеграционные тесты
Составь 5 end-to-end тестов:
1. Time series → line chart.
2. Category comparison → bar chart.
3. Top-N query → table/bar chart.
4. Empty SQL result → safe user-facing error or empty table.
5. Metadata incomplete → fallback chart with warning.

Для каждого теста укажи:
- входной user_query;
- ожидаемые поля upstream response;
- ожидаемые поля downstream response;
- критерий успешности.

## 9. План доработок
Сделай roadmap:

### Этап 1 — MVP-интеграция
Что нужно сделать за минимальное число изменений.

### Этап 2 — Повышение качества
Что добавить для metadata, валидаторов и fallback.

### Этап 3 — Микросервис и сайт
Что нужно для production-like внедрения.

Для каждой задачи укажи owner: Denis, Peter, shared.

## 10. Главный вывод
В 10-15 строках сформулируй:
- какие данные обязательно выгружать со стороны Дениса;
- какие данные обязательно принимать со стороны Петра;
- где нужен adapter;
- какой формат обмена выбрать;
- какие риски самые критичные.
