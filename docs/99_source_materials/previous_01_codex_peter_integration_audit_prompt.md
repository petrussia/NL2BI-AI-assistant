# Промпт для Codex: аудит Text-to-Visualization и контракта входа

Ты работаешь как senior integration architect и backend/data engineer. Твоя задача — не переписывать систему, а провести точный аудит текущей ветки experiments/peter и подготовить данные для последующего объединения с upstream-модулем Дениса.

Контекст проекта:
- Общая система должна работать как пайплайн: пользователь вводит естественно-языковой запрос на сайте → upstream-модуль Дениса выбирает источник/таблицы/атрибуты, генерирует SQL, безопасно выполняет запрос, возвращает структурированную таблицу и метаданные → downstream-модуль Петра выбирает табличное или графическое представление → сайт получает итоговый график/таблицу.
- Моя часть — post-query Text-to-Visualization: на входе уже есть готовая таблица, исходный пользовательский запрос и метаданные полей. SQL и качество извлечения данных не оцениваются в этом модуле.
- В отчёте по практике были подходы B0-B5: rule-based, constraint-ranker, partial recommender, local LLM, validator/reranker и Stage 8 LLM. Но сейчас нужно проверить именно текущее состояние кода и артефактов в репозитории, а не пересказывать отчёт.

Работай только в режиме аудита:
- Не изменяй продуктовый код.
- Не коммить изменения.
- Не запускай тяжёлые эксперименты, если это не нужно для минимальной проверки.
- Можно запускать короткие команды для проверки entrypoint'ов, тестов, импортов, help-выводов, smoke-примеров.
- Не выводи секреты, токены, ключи, приватные URL и персональные данные. Всё чувствительное редактируй как <REDACTED>.
- Если чего-то нет в коде, прямо пиши «не найдено», а не додумывай.

Сначала собери факты:
1. Определи текущую ветку, commit hash, корень репозитория, git status.
2. Найди основные директории, README, requirements/pyproject, notebooks, scripts, модули визуализации, валидаторы, ранжировщики, рендеринг, подготовку данных, evaluation.
3. Найди текущие entrypoint'ы:
   - как подготовить пример;
   - как запустить rule-based/constraint-ranker;
   - как запустить LLM-вариант, если он есть;
   - как получить Vega-Lite/JSON/spec;
   - как отрендерить PNG/SVG/HTML, если реализовано;
   - как посчитать метрики.
4. Найди артефакты экспериментов: jsonl/csv/png/logs/reports/run_id. Особенно проверь run_id из практики:
   - stage4_cpu_sample200;
   - stage5_partial_sample200;
   - stage6_qwen3_8b_fast_sample50;
   - stage7_b4_sample20_tokens384;
   - stage8_qwen3_14b_sample20;
   - stage8_mistral_small_32_24b_bnb4_sample20;
   - stage8_gemma3_12b_it_sample20;
   - stage8_gemma4_e2b_it_sample20.
5. Проверь, какие реальные форматы входа и выхода уже есть в коде: JSON, CSV, pandas DataFrame, path to CSV, Vega-Lite JSON, normalized spec, candidates, metrics, render artifacts.

Главный результат — подготовь отчёт `integration_packet_peter.md` в следующей структуре.

# integration_packet_peter.md

## 1. Snapshot репозитория
Укажи:
- branch;
- commit hash;
- git status;
- root path;
- дата/время аудита;
- какие директории и файлы являются ключевыми.

## 2. Карта текущей архитектуры Text-to-Visualization
Опиши фактическую архитектуру по слоям:
- input parsing;
- metadata parsing;
- intent extraction;
- candidate generation;
- constraints/validation;
- ranking;
- LLM generation, если есть;
- normalized spec;
- rendering/export;
- metrics/evaluation;
- artifacts/logging.

Для каждого слоя укажи:
- реализован / частично реализован / не найден;
- файлы и функции/классы;
- краткое назначение;
- зависимости от внешних библиотек.

## 3. Текущий входной контракт модуля
Опиши, что модуль реально принимает сейчас.

Нужно отдельно указать:
- формат таблицы: CSV path, inline rows, DataFrame, JSON records и т.п.;
- формат пользовательского запроса;
- формат metadata;
- обязательные поля metadata;
- опциональные поля metadata;
- какие поля реально используются алгоритмами;
- какие поля только декларируются, но не используются;
- какие поля нужны для лучшего качества, но пока отсутствуют.

Особенно проверь следующие metadata-поля:
- field name;
- source column name;
- data type / semantic type;
- role: measure, dimension, time, id, text;
- description;
- unit;
- periodicity;
- allowed aggregations;
- default aggregation;
- grain;
- nullable;
- value examples;
- cardinality;
- source table;
- provenance;
- metric definition;
- formatting hints.

## 4. Текущий выходной контракт модуля
Опиши, что модуль реально возвращает сейчас:
- raw visualization spec;
- normalized spec;
- Vega-Lite spec;
- table spec;
- candidates;
- scores;
- selected candidate;
- validation errors;
- render path;
- PNG/SVG/HTML/PDF support;
- manifest;
- latency;
- memory;
- error status.

Если выходы различаются между B0/B1/B2/B3/B4/B5, покажи различия таблицей.

## 5. Предлагаемый контракт `VisualizationRequest`
Сформируй JSON Schema или Pydantic-like описание целевого входа, который должен приходить от upstream-модуля Дениса.

Обязательно включи поля:
```json
{
  "request_id": "string",
  "user_query": "string",
  "locale": "ru-RU",
  "timezone": "Europe/Moscow",
  "data_source": {
    "id": "string",
    "name": "string",
    "dialect": "postgresql|sqlite|clickhouse|trino|unknown",
    "schema_version": "string|null"
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
  "query_context": {
    "sql": "string|null",
    "plan": "object|null",
    "filters": [],
    "group_by": [],
    "aggregations": [],
    "order_by": [],
    "limit": "integer|null",
    "assumptions": []
  },
  "presentation_preferences": {
    "preferred_output": "chart|table|auto",
    "preferred_chart_type": "string|null",
    "style_template": "string|null",
    "max_candidates": "integer",
    "render": "boolean"
  }
}
```

Для каждого поля напиши:
- required/optional;
- тип;
- зачем нужно визуализационному модулю;
- что делать, если поле отсутствует;
- критичность для качества: high/medium/low.

## 6. Предлагаемый контракт `VisualizationResponse`
Сформируй JSON Schema или Pydantic-like описание целевого выхода для сайта/общего backend'а.

Обязательно включи:
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
      "png_uri": "string|null",
      "svg_uri": "string|null",
      "html_uri": "string|null"
    }
  },
  "candidates": [],
  "table_view": {},
  "explanation": {
    "intent": "string|null",
    "used_fields": [],
    "used_aggregations": [],
    "reason": "string"
  },
  "quality": {
    "confidence": "number|null",
    "validation_passed": "boolean",
    "warnings": []
  },
  "performance": {
    "latency_ms": "integer|null",
    "model": "string|null",
    "mode": "fast|quality|fallback"
  },
  "errors": []
}
```

## 7. Какие данные критично выгружать со стороны Дениса
Сделай приоритетный список того, что upstream должен отдавать downstream-модулю.

Раздели на 4 группы:
1. Минимально необходимо для построения хоть какого-то графика.
2. Нужно для хорошего выбора типа графика.
3. Нужно для надёжности и предотвращения неправильных графиков.
4. Нужно для BI-качества и красивого отчёта.

Для каждого пункта укажи:
- пример;
- почему это влияет на качество;
- можно ли автоматически вывести из таблицы;
- что будет, если Денис это не передаст.

## 8. Fallback-логика при неполных metadata
Опиши, как downstream должен действовать, если:
- нет unit;
- нет periodicity;
- нет role;
- нет descriptions;
- нет allowed_aggregations;
- таблица слишком широкая;
- таблица слишком длинная;
- все поля текстовые;
- все поля числовые;
- запрос просит «график», но данные подходят только для таблицы;
- запрос просит «таблицу», но данные подходят для графика;
- SQL вернул 0 строк;
- SQL вернул 1 строку;
- значения содержат null/NaN.

## 9. Микросервисная готовность
Оцени, как текущий модуль можно обернуть в микросервис.

Нужно указать:
- рекомендуемые endpoint'ы;
- sync или async режим;
- где хранить render artifacts;
- ограничения по размеру таблицы;
- ожидаемая latency для fast/quality режимов;
- CPU/GPU требования;
- зависимости для рендеринга;
- какие части готовы, какие нужно реализовать.

Предложи API:
- `POST /visualize`;
- `GET /visualize/{request_id}`;
- `GET /artifacts/{artifact_id}`;
- `GET /health`;
- `GET /ready`.

## 10. Метрики и экспериментальные результаты
Найди фактические метрики в артефактах и отчётах.

Для каждого подхода укажи:
- run_id;
- sample size;
- validity;
- chart type accuracy;
- field F1;
- encoding accuracy;
- aggregation accuracy;
- exact match;
- oracle@3, если есть;
- latency;
- memory;
- failure rate;
- ограничения сравнения.

Не пересказывай без проверки. Если метрика не найдена в репозитории — напиши «не найдено в артефактах».

## 11. Интеграционные тест-кейсы
Сделай 3 минимальных JSON-примера `VisualizationRequest` в стиле ответа Дениса:

1. Time series:
   - временное поле;
   - числовая мера;
   - periodicity;
   - ожидаемый line chart.

2. Category comparison:
   - категориальное поле;
   - числовая мера;
   - aggregation sum/avg/count;
   - ожидаемый bar chart.

3. Table/top-N:
   - несколько колонок;
   - сортировка;
   - limit;
   - ожидаемая таблица или bar chart.

Для каждого примера дай ожидаемый `VisualizationResponse` в сокращённом виде.

## 12. Риски интеграции
Составь таблицу:
- риск;
- причина;
- влияние;
- как обнаружить;
- как исправить;
- кому принадлежит: Peter/downstream, Denis/upstream, shared.

## 13. Открытые вопросы к Денису
Сформулируй конкретные вопросы к upstream-модулю:
- какие metadata он может отдавать уже сейчас;
- может ли отдавать план;
- может ли отдавать provenance фильтров/агрегаций;
- как ограничивает строки;
- как передаёт большие таблицы;
- как сообщает ошибки SQL;
- какие типы источников поддерживает.

В конце дай краткий executive summary на 10-15 строк: какой контракт лучше всего принять для интеграции и какие поля upstream должен отдавать обязательно.
