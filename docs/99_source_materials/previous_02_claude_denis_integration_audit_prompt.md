# Промпт для Claude: аудит Text-to-SQL и контракта выхода

Ты работаешь как senior integration architect и backend/data engineer. Твоя задача — провести точный аудит текущей ветки experiments/denis и подготовить данные для объединения upstream Text-to-SQL модуля с downstream Text-to-Visualization модулем Петра.

Контекст проекта:
- Общая система должна работать как единый пайплайн: пользователь вводит естественно-языковой запрос на сайте → твой upstream-модуль определяет релевантный источник, таблицы и атрибуты, генерирует SQL, безопасно выполняет запрос, делает предварительную обработку/агрегацию → передаёт структурированный результат и metadata в модуль Петра → модуль Петра строит график/таблицу.
- Downstream-модуль Петра не должен генерировать SQL. Он ожидает готовую таблицу, исходный запрос и metadata по полям: имя, тип, роль, описание, единицы измерения, периодичность, допустимые агрегации, provenance и т.п.
- В отчёте по практике упоминались B0/B1/B2: B0 — full schema single-shot, B1 — lexical schema linking, B2 — minimal Plan→SQL с JSON Schema validation. Сейчас нужно проверить именно текущее состояние кода и артефактов.

Работай только в режиме аудита:
- Не изменяй продуктовый код.
- Не коммить изменения.
- Не запускай тяжёлые эксперименты без необходимости.
- Можно запускать короткие smoke-команды для проверки imports, entrypoint'ов, help-выводов и небольших примеров.
- Не выводи секреты, токены, ключи, приватные DB URL и персональные данные. Всё чувствительное редактируй как <REDACTED>.
- Если чего-то нет в коде, прямо пиши «не найдено», а не додумывай.

Сначала собери факты:
1. Определи текущую ветку, commit hash, корень репозитория, git status.
2. Найди основные директории, README, requirements/pyproject, notebooks, scripts, модули schema linking, planner, SQL synthesis, validation, execution, repair loop, evaluation.
3. Найди текущие entrypoint'ы:
   - как запустить B0;
   - как запустить B1;
   - как запустить B2;
   - как выполнить SQL;
   - как посчитать EX;
   - как получить predictions/metrics/logs.
4. Найди артефакты практики:
   - predictions JSONL;
   - metrics CSV;
   - run logs;
   - plan_schema.json;
   - baselines.py;
   - baselines_b2.py;
   - error taxonomy;
   - case diff reports.
5. Проверь реальные форматы входов и выходов: вопрос, schema, selected_tables, plan, SQL, execution result, rows, errors, metrics.

Главный результат — подготовь отчёт `integration_packet_denis.md` в следующей структуре.

# integration_packet_denis.md

## 1. Snapshot репозитория
Укажи:
- branch;
- commit hash;
- git status;
- root path;
- дата/время аудита;
- ключевые директории и файлы.

## 2. Карта текущей архитектуры Text-to-SQL
Опиши фактическую архитектуру по слоям:
- natural language query input;
- datasource/schema loading;
- schema linking;
- retrieval/RAG, если есть;
- planner;
- plan validation;
- SQL synthesis;
- SQL extraction/cleanup;
- static SQL validation;
- sandbox/read-only execution;
- repair loop, если есть;
- metrics/evaluation;
- artifacts/logging.

Для каждого слоя укажи:
- реализован / частично реализован / не найден;
- файлы и функции/классы;
- краткое назначение;
- зависимости.

## 3. Текущий входной контракт upstream-модуля
Опиши, что модуль реально принимает сейчас.

Нужно отдельно указать:
- формат пользовательского запроса;
- формат схемы БД;
- формат metadata схемы;
- поддерживаемый SQL dialect;
- как задаётся datasource/database;
- есть ли domain documentation / metric docs;
- какие настройки модели требуются;
- какие параметры безопасности/лимитов есть.

## 4. Текущий выходной контракт upstream-модуля
Опиши, что модуль реально возвращает сейчас:
- generated SQL;
- selected tables;
- selected columns;
- plan JSON;
- validation status;
- execution status;
- rows/result;
- errors;
- metrics;
- logs;
- reduction ratio;
- executable flag;
- assumptions.

Если выходы различаются между B0/B1/B2, покажи различия таблицей.

## 5. Что upstream уже может передать downstream-модулю Петра
Составь таблицу:

| Поле для визуализации | Уже есть в коде? | Где находится | Надёжность | Комментарий |
|---|---:|---|---|---|

Проверь поля:
- request_id;
- original user query;
- normalized query;
- SQL;
- SQL dialect;
- datasource id/name;
- selected tables;
- selected columns;
- result rows;
- result columns;
- SQL types;
- inferred JSON/pandas types;
- role: measure/dimension/time/id/text;
- descriptions;
- units;
- periodicity;
- allowed aggregations;
- default aggregation;
- filters;
- group_by;
- aggregations;
- order_by;
- limit;
- joins;
- grain;
- provenance for each output column;
- assumptions;
- warnings;
- confidence;
- execution latency;
- row_count;
- truncated flag.

## 6. Предлагаемый контракт `DataExtractionRequest`
Сформируй JSON Schema или Pydantic-like описание целевого входа от сайта/backend'а в upstream-модуль.

Обязательно включи:
```json
{
  "request_id": "string",
  "user_query": "string",
  "locale": "ru-RU",
  "timezone": "Europe/Moscow",
  "user_context": {
    "user_id": "string|null",
    "permissions": [],
    "organization_id": "string|null"
  },
  "data_source": {
    "id": "string",
    "dialect": "postgresql|sqlite|clickhouse|trino|unknown",
    "connection_ref": "string|null",
    "schema_version": "string|null"
  },
  "constraints": {
    "read_only": true,
    "timeout_ms": 8000,
    "row_limit": 1000,
    "max_joins": "integer|null",
    "allow_llm_repair": true
  },
  "presentation_hint": {
    "preferred_output": "chart|table|auto",
    "requested_fields": [],
    "requested_metrics": []
  }
}
```

Для каждого поля напиши:
- required/optional;
- тип;
- зачем нужно;
- как используется сейчас или как должно использоваться.

## 7. Предлагаемый контракт `DataExtractionResponse`
Сформируй JSON Schema или Pydantic-like описание целевого выхода, который должен передаваться модулю Петра.

Обязательно включи:
```json
{
  "request_id": "string",
  "status": "success|partial_success|failed",
  "user_query": "string",
  "normalized_query": "string|null",
  "data_source": {
    "id": "string",
    "name": "string|null",
    "dialect": "postgresql|sqlite|clickhouse|trino|unknown",
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
    "limit": "integer|null",
    "joins": [],
    "assumptions": []
  },
  "sql": {
    "query": "string|null",
    "dialect": "string",
    "validated": true,
    "read_only": true
  },
  "result_table": {
    "format": "records|csv_uri|arrow_uri",
    "columns": [],
    "rows": [],
    "uri": "string|null",
    "row_count": "integer",
    "truncated": "boolean"
  },
  "field_metadata": [],
  "execution": {
    "latency_ms": "integer|null",
    "row_limit": "integer|null",
    "timeout_ms": "integer|null",
    "executable": "boolean|null"
  },
  "quality": {
    "confidence": "number|null",
    "warnings": []
  },
  "errors": []
}
```

`field_metadata` должна быть массивом объектов:
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
    "derived": "boolean"
  }
}
```

Для каждого поля напиши:
- может ли оно быть заполнено уже сейчас;
- из какого источника его можно получить;
- точность/надёжность;
- что надо доработать.

## 8. Metadata inference: что можно вывести автоматически
Опиши правила, по которым upstream может автоматически заполнить metadata для Петра:

- SQL type → data_type;
- column name/date/time keywords → semantic_role=time;
- numeric type + aggregation → measure;
- string/category + low cardinality → dimension;
- id-like names → id;
- COUNT/SUM/AVG expressions → default_aggregation;
- date_trunc/group_by date → periodicity;
- aliases → display_name;
- schema comments/docs → description;
- metric docs → unit, definition, allowed aggregations;
- selected SQL expressions → provenance.

Для каждого правила укажи:
- пример;
- риск ошибки;
- нужна ли ручная документация/словарь метрик.

## 9. Безопасность и ограничения выполнения SQL
Опиши текущие и необходимые механизмы:
- SELECT-only;
- запрет DDL/DML;
- read-only connection;
- timeout;
- row limit;
- join limit;
- cost estimation, если есть;
- sandbox;
- защита от prompt injection через schema/docs;
- обработка ошибок SQL;
- repair loop;
- политика больших результатов.

Сформулируй рекомендуемый error enum:
- `schema_not_found`;
- `ambiguous_query`;
- `plan_invalid`;
- `sql_generation_failed`;
- `sql_validation_failed`;
- `sql_execution_failed`;
- `timeout`;
- `empty_result`;
- `row_limit_exceeded`;
- `permission_denied`;
- `metadata_incomplete`.

## 10. Метрики и экспериментальные результаты
Найди фактические метрики в артефактах и отчётах.

Для каждого baseline укажи:
- run_id / subset;
- sample size;
- database(s);
- model;
- prompt mode;
- EX;
- executable count;
- avg reduction ratio;
- plan valid count;
- plan parse failures;
- основные ошибки;
- ограничения эксперимента.

Не пересказывай без проверки. Если метрика не найдена в репозитории — напиши «не найдено в артефактах».

## 11. Интеграционные примеры
Сделай 3 минимальных примера `DataExtractionResponse`, которые downstream-модуль Петра сможет принять сразу:

1. Time series:
   - запрос пользователя про динамику;
   - SQL с группировкой по времени;
   - result_table с 3-5 строками;
   - field_metadata с periodicity и measure.

2. Category comparison:
   - запрос пользователя про сравнение категорий;
   - SQL с group by category;
   - result_table с 3-5 строками;
   - field_metadata с dimension и measure.

3. Table/top-N:
   - запрос пользователя про топ-N или список;
   - SQL с order by/limit;
   - result_table с 3-5 строками;
   - field_metadata для табличного вывода.

Используй реальные данные из тестовой БД, если это возможно быстро и безопасно. Если нет — используй синтетические данные, но явно пометь synthetic.

## 12. Что нужно от Петра/downstream
Сформулируй конкретные вопросы к модулю визуализации:
- какие поля metadata обязательны;
- какой формат таблицы предпочтителен: records/csv_uri/arrow_uri;
- какой лимит строк/колонок приемлем;
- нужна ли передача SQL;
- нужен ли plan;
- нужен ли provenance;
- какие output types поддерживаются;
- какие ошибки downstream умеет обрабатывать;
- как сайт будет получать PNG/SVG/HTML/Vega-Lite.

## 13. Риски интеграции
Составь таблицу:
- риск;
- причина;
- влияние;
- как обнаружить;
- как исправить;
- кому принадлежит: Denis/upstream, Peter/downstream, shared.

## 14. Executive summary
В 10-15 строках дай главный вывод:
- что upstream уже умеет отдавать;
- чего не хватает для качественной визуализации;
- какие поля обязательно добавить перед интеграцией;
- какой минимальный контракт можно принять для MVP;
- какие доработки нужны для production/microservice.
