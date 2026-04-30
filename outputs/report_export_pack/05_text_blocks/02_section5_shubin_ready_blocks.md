# Раздел 5 — Программная реализация и интеграция (Шубин)

## 5.1. Реализованные модули

В `repo/src/evaluation/` реализованы 14 модулей подсистемы извлечения:

- `baselines.py` — базовый B0 (full schema) + лексический schema linker (B1).
- `baselines_b2.py`, `baselines_b2_v1.py`, `baselines_b2_v2.py` — три версии планового конвейера; финальная v2 добавляет anti-overengineering инструкцию, distinct cue и superlative subquery cue.
- `baselines_b3.py`, `baselines_b3_v1.py`, `baselines_b3_v2.py` — три версии dual-retrieval-конвейера; финальная v2 отключает knowledge proxy и подключает B1-fallback.
- `baselines_b4.py`, `baselines_b4_final.py`, `baselines_b4_v2.py` — три версии validation+repair-конвейера с multi-candidate (k=3) и SELECT-only AST guard.
- `postprocess.py` — нормализация строк результата + построение AnalyticsPayload v1.
- `query_analysis.py` — rule-based анализ намерения и сигналов NL-запроса.
- `retrieval.py` — кросс-БД lex-retrieval helper.
- `external_benchmark_adapters.py` — адаптеры для BIRD-Mini-Dev (полное EX-исполнение) и Spider 2.0-Lite (структурные метрики).

Плановые схемы хранятся в `repo/docs/plan_schema.json` и `repo/docs/plan_schema_v1.json`.

## 5.2. Входы и выходы

**Вход подсистемы (production-режим):** NL-запрос (русский или английский) + `db_id` (имя БД, как в `tables.json` Spider).

**Выход подсистемы:** JSON+CSV `AnalyticsPayload v1` со схемой:

```json
{
  "metadata": {
    "query": "<NL question>",
    "db_id": "<source DB>",
    "intent": "<select_count|select_aggregate|...>",
    "generated_sql": "<final SQL>",
    "execution_time_seconds": <float>,
    "timestamp_utc": "<ISO 8601>"
  },
  "rows": [<normalized result rows>],
  "summary": {
    "row_count": <int>,
    "distinct_values": {...},
    "min_max": {...}
  }
}
```

CSV-вариант — табличная развёртка `rows` с заголовками из `metadata.columns`. Контракт фиксирован в `outputs/docs/io_contracts.md`.

## 5.3. Безопасность исполнения SQL

Реализована трёхуровневая защита:

1. **AST-guard (`is_safe_select`).** Regex-проверка запрещает любые из ключевых слов `INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|PRAGMA|ATTACH|DETACH|GRANT|REVOKE`. SQL должен начинаться с `SELECT` (или `WITH ... SELECT`).
2. **Sandboxed execution.** Запросы выполняются в SQLite read-only через `func_timeout` с жёстким лимитом 8 секунд. Превышение → `error_type='timeout'`, пустой результат.
3. **Per-item logging.** Каждая выработка SQL сохраняется с raw model output, gold SQL, флагами executable/match и типом ошибки. Постфактум-аудит возможен.

## 5.4. Контракт интеграции с подсистемой Петухова

После исполнения SQL и постобработки модуль `postprocess.py::build_analytics_payload` эмитирует `AnalyticsPayload v1` в формате JSON+CSV. В production-конфигурации payload попадает на message bus / API endpoint подсистемы аналитического представления. В рамках работы реализованы demo-payloads в `outputs/analytics_handoff/`. Контракт версионирован (v1) — любые расширения требуют согласования и параллельной поддержки старой версии.
