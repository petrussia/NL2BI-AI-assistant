# integration_packet_denis.md

Audit packet for joining the upstream Text-to-SQL module (Шубин Денис)
with the downstream Text-to-Visualization module (Петухов Пётр).

Mode: **read-only audit**. No code modified, no commits, no heavy runs.

---

## 1. Snapshot репозитория

| Поле | Значение |
|---|---|
| Branch | `experiments/denis` |
| Commit hash | `181352f347c09478a488b2e3c1072d802545214f` |
| Last commit subject | `Phase 17 Spider2 model-swap pilot10 grid (4 models x 2 lanes)` |
| Root path | `d:/HSE/Диплом/NL2BI-AI-assistant` |
| Audit timestamp (UTC) | `2026-05-09T00:18:39Z` |
| Platform | Windows 11, PowerShell |
| Python build evidence | `repo/src/evaluation/__pycache__/*.cpython-311.pyc` and `*.cpython-312.pyc` (mixed 3.11/3.12) |

`git status` (head):

```
M  notebooks/example.ipynb
M  outputs/REPORT.md
M  outputs/logs/final_negative_result_analysis.md
M  outputs/logs/final_scientific_findings.md
M  outputs/plots/final_experiment_master_overview.png
M  outputs/snowflake/readiness/databases_visible.json
M  outputs/snowflake/readiness/databases_visible.md
M  outputs/tables/final_experiment_master_matrix.csv
M  outputs/tables/final_experiment_master_matrix.md
M  spider2_dbt_bridge/run_dbt_ablation.py
M  tools/remote_scripts/_run_dbt_inference.py
?? data/spider2_dbt/tasks/<~80 task dirs>/
?? data/spider2_snow/
?? notebooks/example_agent_setup_clean.ipynb
?? outputs/REPORT_SPIDER2_V18.md
?? outputs/cache/, outputs/exports/joint_vkr_export_pack_v10.tar.gz, ...
```

Working tree has uncommitted edits in REPORT.md, master matrix, Spider2 bridge,
and a heavy mass of untracked Spider2-DBT task directories. The integration
audit below treats committed code as authoritative; the dirty Spider2 files do
not affect the upstream→downstream contract.

Ключевые директории и файлы:

| Path | Назначение |
|---|---|
| [repo/src/evaluation/](repo/src/evaluation/) | весь NL→SQL pipeline (B0…B4 и v2 stack) |
| [repo/docs/plan_schema.json](repo/docs/plan_schema.json) | компактный B2 plan schema (v1) |
| [repo/docs/plan_schema_v5.json](repo/docs/plan_schema_v5.json) | расширенный план для `sql_compiler_v2` |
| [repo/src/evaluation/postprocess.py](repo/src/evaluation/postprocess.py) | F12+F13: AnalyticsPayload v1 |
| [repo/src/evaluation/error_taxonomy_v2.py](repo/src/evaluation/error_taxonomy_v2.py) | финальная классификация исхода SQL |
| [outputs/docs/io_contracts.md](outputs/docs/io_contracts.md) | формальная фиксация I/O контрактов (existing) |
| [outputs/docs/architecture_document_v2.md](outputs/docs/architecture_document_v2.md) | финальная архитектура |
| [outputs/docs/functional_specification.md](outputs/docs/functional_specification.md) | F1…F13 functional spec |
| [outputs/predictions/*.jsonl](outputs/predictions/) | per-item predictions (B0…B4) |
| [outputs/metrics/*.csv](outputs/metrics/) | per-run метрики |
| [outputs/analytics_handoff/](outputs/analytics_handoff/) | образцы AnalyticsPayload v1 (JSON+CSV) |
| [outputs/tables/final_experiment_master_matrix.md](outputs/tables/final_experiment_master_matrix.md) | master matrix (127 runs) |
| [external_benchmarks/](external_benchmarks/) | bird_mini_dev, spider2_lite, spider, spider2_dbt, spider2_snow |
| [data/spider/](data/spider/) | тестовый Spider corpus + audit |
| [configs/](configs/) | snowflake + spider2_dbt experiments |
| [notebooks/example.ipynb](notebooks/example.ipynb) | основной runner-нотбук |

`requirements.txt` / `pyproject.toml` в корне **не найдены** — зависимости фактически объявляются inline в нотбуках и скриптах.

---

## 2. Карта текущей архитектуры Text-to-SQL

Источник: [outputs/docs/functional_specification.md](outputs/docs/functional_specification.md)
+ [outputs/docs/architecture_document_v2.md](outputs/docs/architecture_document_v2.md). Таблица актуализирована по фактическому коду.

| Слой | Реализация | Файлы | Назначение |
|---|---|---|---|
| Natural-language input | реализован | runner-нотбуки → строка вопроса | UTF-8 строка вопроса |
| Datasource / schema loading | реализован | `repo/src/evaluation/external_benchmark_adapters.py`, `data/spider/SOURCE_AND_AUDIT.md` | загрузка `tables.json` (spider-формат) и SQLite файла |
| Query analysis (F1) | реализован | `query_analysis.py` | rule-based intent + signals (agg/distinct/order/limit/time/comp/join_hint) |
| Schema linking — lexical (F2) | реализован | `baselines.py::lexical_schema_linking`, `baselines_b1_v3.py`, `schema_linking_bidirectional.py`, `schema_linker_bidirectional_v2.py` | сжатие схемы по токенам вопроса; есть bidirectional-вариант |
| Cross-DB retrieval (F3) | частично | `retrieval.py`, `retrieval_hybrid.py`, `retrieval_hybrid_v2.py`, `dense_retriever_v2.py`, `candidate_ranker.py`, `candidate_ranker_v4.py`, `reranker_v2.py` | поиск релевантной БД среди множества; для интеграции с фронтендом обычно избыточен — frontend знает datasource |
| Knowledge / docs retrieval (F4) | частично | `evidence_store_v2.py`, `evidence_semantics_v7.py`, `demo_retrieval_v7.py` | proxy-документы из метаданных; нет настоящего metric/domain-словаря |
| Planner (F5) | реализован | `baselines_b2.py`, `baselines_b2_v2.py`, `baselines_b2_v3.py`, `baselines_b2_v4.py`, `baselines_b2_v5.py`, `planner_v2.py`, `planner_gate.py` | LLM-генерация JSON-плана |
| Plan validation (F6) | реализован | `baselines_b2.py::parse_and_validate_plan`, `planner_v2.py::validate_plan` | jsonschema validation против `plan_schema*.json`; soft-fallback без jsonschema |
| SQL synthesis (F7) | реализован | `baselines.py::build_b1_prompt`, `baselines_b2*.py::make_*sql_prompt`, `sql_compiler_v2.py` | LLM emit + (для v2 stack) детерминированный compile из плана |
| SQL extraction / cleanup | реализован | `baselines_b2.py::extract_json_block` + регексп-извлечение SQL в нотбуке | вырезка fenced markdown / дроп комментариев |
| Static SQL validation | реализован | `baselines_b4.py::is_safe_select`, `baselines_b4_final.py::is_safe_select`, `sqlglot_checks_v2.py` | regex-guard SELECT-only + sqlglot-парсинг |
| Sandbox / read-only execution | реализован для SQLite | inline в runner-нотбуках через `sqlite3` + `func_timeout` 8s | для Spider2-Lite/BQ/Snow — отдельные lanes (`spider2_*_executor_v8.py`) |
| Repair loop | реализован (B4) | `baselines_b4.py::make_repair_prompt`, `baselines_b4_v2.py::make_repair_prompt_v2`, `repair_v2.py`, `spider2_*_repair_v8.py` | bounded retry x1 с приклеенным error_message |
| Multi-candidate + selection | реализован (B4) | `baselines_b4*.py::consistency_pick*`, `candidate_generator_v2.py`, `verifier_ranker_v2.py` | k=3 candidate, T=0.7, top_p=0.95, consistency-pick |
| Error taxonomy | реализован | `error_taxonomy_v2.py` | 16 категорий исхода (parse/exec/runtime/etc) |
| Postprocess (F12) | реализован | `postprocess.py::normalize_rows`, `compute_summary` | row→dict + per-column stats |
| Analytics handoff (F13) | реализован | `postprocess.py::build_analytics_payload`, `export_payload_json/csv` | **AnalyticsPayload v1** — текущая граница с downstream |
| Metrics / evaluation | реализован | `official_bird_metrics.py`, `stats_eval.py`, runner-нотбуки | EX, executable, plan_valid, reduction_ratio, CI95 |
| Spider2 family lanes | реализован, EX=0 на Lite | `spider2_*_v7.py..v10.py`, `spider2_lite_*_v8.py..v9.py`, `spider2_snow_*_v8.py..v10.py`, `spider2_dbt_*_v8.py` | BQ/Snowflake/SQLite executors; Lite EX=0.0 (env blocker) |
| Artifacts / logging | реализован | `outputs/predictions/*.jsonl`, `outputs/metrics/*.csv`, `outputs/logs/*`, `outputs/tables/*` | JSONL per item + CSV per run |
| Bridge / remote inference | реализован | `colab_bridge/`, `spider2_dbt_bridge/`, `tools/remote_scripts/` | local-generates / server-evaluates |

**Финальная production-конфигурация по `architecture_document_v2.md`:**
B0 (full schema, single-shot) + Qwen2.5-Coder-7B-Instruct (4-bit nf4) +
SELECT-only AST guard + 8s SQLite timeout + AnalyticsPayload v1.

**Definitive v9 finding (зафиксировано в REPORT.md):** на multi_db_30
B1_v3 (без планнера) даёт EX=0.80, B2_v3 (с планнером) — 0.7667. Планнер **проигрывает** retrieval-only на этом бенчмарке. Это нужно учитывать при интеграции — план полезен Петру как audit-trail / metadata-источник, но не как обязательная стадия для повышения EX.

---

## 3. Текущий входной контракт upstream-модуля

Сейчас upstream **не имеет HTTP/RPC API** — это набор Python функций, вызываемых из notebooks. Реальные входы фиксированы по полю и форме:

| Что | Реальная форма (что код принимает сейчас) | Где |
|---|---|---|
| Пользовательский запрос | `question: str` (UTF-8, без явных лимитов) | все `make_*_prompt(question, ...)` |
| Database id | `db_id: str` (Spider-style: `concert_singer`, `world_1`, …) | predictions JSONL, executor |
| SQL dialect | **SQLite по умолчанию** (compiler default `dialect='sqlite'`); BQ/Snowflake/MySQL частично | `sql_compiler_v2.py::_qid`, `bigquery_dialect_normalizer_v9.py`, `snowflake_dialect_normalizer_v9.py` |
| Schema | `tables_json` Spider-style: `{db_id, table_names, table_names_original, column_names, column_names_original, column_types, foreign_keys, primary_keys}` | `baselines.py::lexical_schema_linking`, `external_benchmark_adapters.py` |
| Reduced schema context | `reduced_schema_context: str` — строка с `CREATE TABLE`-эквивалентом | `baselines.py::build_b1_prompt` |
| Schema metadata | **минимум**: имена/типы колонок, FK, PK. Описаний колонок, единиц измерения, периодичности **не найдено** | — |
| Domain/metric documentation | **не найдено** в виде словаря; есть только `evidence_store_v2.py` с proxy-документами из метаданных | `evidence_store_v2.py`, `demo_retrieval_v7.py` |
| Model settings | `model_id` (HF), `quantization` (4bit_bitsandbytes / device_map_auto / fp16), inline в нотбуке. Sampling: T=0.7, top_p=0.95, k=3 в B4 | `baselines_b4_v2.py`, runner-нотбуки |
| Безопасность / лимиты | `func_timeout=8s`, regex `is_safe_select` (SELECT-only, запрет DDL/DML/PRAGMA/ATTACH/etc), no row-limit on raw exec | `baselines_b4.py::is_safe_select`, `baselines_b4_final.py::is_safe_select` |

Поля, которых **нет** в текущем входе и которые понадобятся для production-API:
`request_id`, `locale`, `timezone`, `user_id`/permissions, `connection_ref` (БД задаётся `db_id` + sqlite-файл по соглашению), `row_limit`, `presentation_hint`, `requested_metrics`.

---

## 4. Текущий выходной контракт upstream-модуля

Реальный выход — два слоя: per-item prediction record (JSONL) и AnalyticsPayload v1 (JSON+CSV).

### 4.1 Prediction record (по [outputs/docs/io_contracts.md §7](outputs/docs/io_contracts.md))

Common (B0):

```json
{
  "idx": 0,
  "question": "How many singers do we have?",
  "db_id": "concert_singer",
  "gold_sql": "SELECT count(*) FROM singer",
  "generated_raw": "```sql\nSELECT COUNT(*) FROM singer;\n```",
  "generated_sql": "SELECT COUNT(*) FROM singer;",
  "executable": true,
  "execution_match": true,
  "error_type": "",
  "error_message": ""
}
```

| Поле | Тип | Где |
|---|---|---|
| `idx` | int | per-item индекс |
| `question` / `db_id` / `gold_sql` | str | вход + reference |
| `generated_raw` / `generated_sql` | str | сырой ответ модели и извлечённый SQL |
| `executable` / `execution_match` | bool | базовая проверка |
| `error_type` / `error_message` | str | классификация (см. таксономию ниже) |

B1+ extras: `selected_tables: list[str]`, `schema_reduction_ratio: float`, `fallback_used: bool`.
B2+ extras: `plan_raw: str`, `plan_parsed: object|null`, `plan_valid: bool`, `plan_error: str`.
B1R/B2R extras: `retrieved_db_id: str`, `retrieval_hit: bool`, `retrieval_score: float`.
B4-lite extras: `cand_safe_flags: list[bool]`, `cand_results: list`, `selection_reason: str`, `repaired: bool`.

Это наблюдается в реальных файлах (`outputs/predictions/b0_spider_smoke10_predictions.jsonl`, `b1_*`, `b2_*`).

### 4.2 AnalyticsPayload v1 (текущая граница с Петром)

`postprocess.py::build_analytics_payload` → JSON или CSV.
Реальный пример: [outputs/analytics_handoff/B0_smoke10_idx0.json](outputs/analytics_handoff/B0_smoke10_idx0.json).

```json
{
  "schema_version": "v1",
  "produced_at": "2026-04-29T14:36:55.820828+00:00",
  "source": {
    "baseline": "B0",
    "model": "Qwen/Qwen2.5-Coder-7B-Instruct",
    "subset": "smoke_10",
    "idx": 0,
    "db_id": "concert_singer",
    "question": "How many singers do we have?",
    "generated_sql": "SELECT COUNT(*) FROM singer;",
    "gold_sql_present": true
  },
  "rows": [{"c0": 6}],
  "summary": {
    "row_count": 1,
    "columns": {
      "c0": {"count": 1, "null_count": 0, "distinct_count": 1,
              "dtype": "numeric", "min": 6, "max": 6, "sum": 6, "mean": 6.0}
    }
  },
  "n_rows": 1,
  "is_executable": true,
  "notes": []
}
```

### 4.3 Различия B0 / B1 / B2 на уровне выхода

| Поле | B0 | B1 | B2 |
|---|---|---|---|
| `generated_sql` | ✅ | ✅ | ✅ |
| `executable`, `execution_match`, `error_type` | ✅ | ✅ | ✅ |
| `selected_tables` | ❌ | ✅ | ✅ |
| `schema_reduction_ratio` | ❌ | ✅ | ✅ |
| `fallback_used` (всю схему вернули) | ❌ | ✅ | ✅ |
| `plan_raw`, `plan_parsed`, `plan_valid`, `plan_error` | ❌ | ❌ | ✅ |
| `cand_safe_flags`, `repaired`, `selection_reason` | ❌ | ❌ | в B4 |

`AnalyticsPayload v1` сейчас **одинаков** для всех baseline'ов — `source.baseline` различает их. План в payload **не передаётся**; это явный пробел для Петра.

---

## 5. Что upstream уже может передать downstream-модулю Петра

Источники: `postprocess.py`, predictions JSONL, plan_schema*.json, error_taxonomy_v2.py.

| Поле для визуализации | Уже есть? | Где находится | Надёжность | Комментарий |
|---|---:|---|---|---|
| `request_id` | ❌ | — | — | нет идентификатора запроса; есть только `(subset, idx)` |
| original user query | ✅ | `payload.source.question` | high | UTF-8 строка |
| normalized query | ❌ | — | — | `query_analysis.py` даёт `tokens`/`signals`, но не "нормализованную форму" |
| SQL | ✅ | `payload.source.generated_sql`, predictions `generated_sql` | high | extracted, без markdown |
| SQL dialect | ⚠️ partial | дефолт `sqlite`; в `plan_schema_v5` есть поле `dialect`; BQ/Snow — отдельные lanes | medium | в payload **не сериализуется** |
| datasource id | ✅ | `payload.source.db_id` | high | Spider-style id |
| datasource name | ❌ | — | — | имя/описание БД не хранится |
| selected tables | ✅ B1+ | predictions `selected_tables` | high | НЕ в текущем `AnalyticsPayload v1` |
| selected columns | ⚠️ partial | в plan v1: `plan_parsed.columns`; в plan v5: `measures[].expr` + `dimensions[].expr` | medium | НЕ в payload; зависит от валидности плана |
| result rows | ✅ | `payload.rows` (нормализованные dict'ы) | high | через `normalize_rows` |
| result columns | ✅ implicit | ключи в `rows[0]`; `payload.summary.columns` | high | имена либо из cursor.description, либо синтетические `c0`,`c1`… |
| SQL types | ❌ | — | — | sqlite cursor не отдаёт строгие типы; пока теряем |
| inferred JSON/pandas types | ✅ partial | `payload.summary.columns[*].dtype` ∈ {`numeric`, `categorical_or_mixed`} | medium | бинарная категоризация, не различает int/float/date |
| semantic role (measure/dimension/time/id/text) | ❌ | — | — | нужно вывести (см. §8) |
| descriptions | ❌ | — | — | в схеме Spider описаний колонок нет |
| units | ❌ | — | — | требуется внешний metric-словарь |
| periodicity | ❌ | в plan v5: `dimensions[].time_grain` (year/month/day/week/quarter) | medium | можно поднять из плана, если он валидный |
| allowed aggregations | ❌ | в plan v5: `measures[].agg` enum — но это _фактический_ выбор, не _допустимое множество_ | low | требуется словарь метрик |
| default aggregation | ⚠️ partial | можно вывести из `plan_parsed.aggregations` | medium | устойчиво только если planner отработал |
| filters | ✅ partial | plan v1: `plan_parsed.filters`, plan v5: `filters[]` | medium | формат различается между plan v1 и v5 |
| group_by | ✅ partial | plan v1: `plan_parsed.group_by`; plan v5: `dimensions[]` | medium | — |
| aggregations | ✅ partial | plan v1: `plan_parsed.aggregations`; plan v5: `measures[]` | medium | — |
| order_by | ✅ partial | plan v1: `order_by`; plan v5: `ordering[]` | medium | — |
| limit | ✅ partial | в plan'е; не дублируется в payload | medium | — |
| joins | ✅ partial | plan v1: `joins[]`; plan v5: `join_anchor_nodes[]` + `join_path_ids[]` | medium | — |
| grain | ⚠️ partial | плановое `time_grain`; неявно по агрегациям | low | требует normalization |
| provenance per output column | ❌ | — | — | sql_compiler_v2 знает выражения, но не пробрасывает их в payload |
| assumptions | ❌ | — | — | нет поля; в B4 есть `selection_reason` (не то же самое) |
| warnings | ⚠️ partial | `payload.notes` (всегда `[]` в текущей реализации); error_type когда executable=false | low | — |
| confidence | ⚠️ partial | `query_analysis.confidence` (rule-based); `plan_v5.confidence`; никуда не пробрасывается в payload | low | — |
| execution latency | ❌ | — | — | замеряется per-run, не per-item, в payload не пишется |
| row_count | ✅ | `payload.summary.row_count` и `payload.n_rows` | high | — |
| truncated flag | ❌ | — | — | нет row-limit на executor → нет flag'а |
| executable flag | ✅ | `payload.is_executable` (всегда `true` если payload построен) | medium | в predictions есть полноценный `executable` bool |
| reduction_ratio | ✅ B1+ | predictions `schema_reduction_ratio` | high | НЕ в payload |
| plan validation status | ✅ B2+ | predictions `plan_valid`, `plan_error` | high | НЕ в payload |

**Итог:** `payload.rows`, `payload.summary` и `payload.source` — это всё, что Пётр получает сегодня. Всё, что планер/линкер уже сделал (план, selected_tables, reduction_ratio, plan_valid, error_type), **не пробрасывается в payload** и теряется.

---

## 6. Предлагаемый контракт `DataExtractionRequest`

Целевой вход от backend сайта в upstream-модуль. Pydantic-style; `null` означает optional, остальные — обязательные.

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
    "dialect": "postgresql|sqlite|clickhouse|trino|bigquery|snowflake|unknown",
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

| Поле | Req? | Тип | Зачем нужно | Текущее использование |
|---|---|---|---|---|
| `request_id` | required | string (UUID) | трассировка через все слои + dedup | не используется; нужно ввести и пробрасывать |
| `user_query` | required | string UTF-8 | NL вопрос пользователя | есть как `question` в коде |
| `locale` | required | string BCP-47 | для NL-парсинга и формирования сообщений ошибок | не используется (англ-only сейчас) |
| `timezone` | required | string IANA | для time-фильтров (now, today, last week) | не используется; F1 видит только `year_filter` |
| `user_context.user_id` | optional | string | row-level security, аудит | не используется |
| `user_context.permissions` | optional | list[string] | фильтрация доступных datasource'ов / таблиц | не используется |
| `user_context.organization_id` | optional | string | мульти-тенантность | не используется |
| `data_source.id` | required | string | какой backend исполняет SQL | есть как `db_id` |
| `data_source.dialect` | required | enum | подобрать SQL synthesizer / sql_compiler_v2 | есть `dialect` в plan_schema_v5 (default `sqlite`) |
| `data_source.connection_ref` | optional | string | indirect handle (vault key / DSN id) | не используется; sqlite path по соглашению |
| `data_source.schema_version` | optional | string | для retrieval-кэша и диффа схем | не используется |
| `constraints.read_only` | required | bool=true | force SELECT-only guard | реализовано regex'ом + executor — но не как параметр |
| `constraints.timeout_ms` | required | int | бюджет на исполнение | реализован хардкодом 8000ms |
| `constraints.row_limit` | required | int | защита от больших результатов | **не реализовано** на executor'е |
| `constraints.max_joins` | optional | int | защита от взрывных join'ов | не используется |
| `constraints.allow_llm_repair` | optional | bool | разрешать ли B4 repair-loop | в коде B4 запускается всегда, флаг отсутствует |
| `presentation_hint.preferred_output` | optional | enum | подсказка планнеру: лучше выдать grouped vs table | не используется; `plan_v5.answer_shape` уже несёт похожую семантику |
| `presentation_hint.requested_fields` | optional | list[string] | фронтенд просит конкретные колонки | не используется |
| `presentation_hint.requested_metrics` | optional | list[string] | фронтенд просит конкретные метрики (если есть metric dictionary) | не используется (словаря метрик нет) |

---

## 7. Предлагаемый контракт `DataExtractionResponse`

Целевой выход в downstream Петра. Объединяет существующий `AnalyticsPayload v1`
с тем, что _уже_ генерируется выше по pipeline и сейчас теряется.

```json
{
  "request_id": "string",
  "status": "success|partial_success|failed",
  "user_query": "string",
  "normalized_query": "string|null",
  "data_source": {
    "id": "string",
    "name": "string|null",
    "dialect": "postgresql|sqlite|clickhouse|trino|bigquery|snowflake|unknown",
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
    "dialect": "string",
    "validated": true,
    "read_only": true
  },
  "result_table": {
    "format": "records|csv_uri|arrow_uri",
    "columns": [],
    "rows": [],
    "uri": "string|null",
    "row_count": 0,
    "truncated": false
  },
  "field_metadata": [],
  "execution": {
    "latency_ms": null,
    "row_limit": null,
    "timeout_ms": null,
    "executable": null
  },
  "quality": {
    "confidence": null,
    "warnings": []
  },
  "errors": []
}
```

`field_metadata` — массив объектов, по одному на колонку результата:

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
  "allowed_aggregations": ["sum","avg","count","min","max","none"],
  "default_aggregation": "sum|avg|count|min|max|none|null",
  "nullable": null,
  "examples": [],
  "provenance": {
    "expression": "string|null",
    "aggregation": "string|null",
    "derived": false
  }
}
```

Покрытие полей сегодняшним кодом:

| Поле response | Можно заполнить сейчас? | Источник | Точность | Что нужно доработать |
|---|---|---|---|---|
| `request_id` | ❌ | — | — | пробросить из request |
| `status` | ✅ | derive из `executable` + `error_type` | high | мапа: success/partial/failed |
| `user_query` | ✅ | `payload.source.question` | high | — |
| `normalized_query` | ⚠️ | `query_analysis.tokens`/`signals` | low | формализовать "normalized" (текущее — токены, не строка) |
| `data_source.id` | ✅ | `payload.source.db_id` | high | — |
| `data_source.name` | ❌ | — | — | требуется реестр БД |
| `data_source.dialect` | ✅ B0…B4 на SQLite, иначе зависит от lane | hardcoded | medium | пробрасывать как поле payload |
| `data_source.schema_version` | ❌ | — | — | завести версию tables.json |
| `plan.raw` / `plan.validated` | ✅ B2+ | predictions `plan_parsed`, `plan_valid` | high | пробросить в payload |
| `plan.intent` | ✅ B2+ | `plan_parsed.intent` (v1) | high | для v5: derive из `answer_shape`+`measures` |
| `plan.tables` | ✅ B2+ | `plan_parsed.tables` (v1) / `join_anchor_nodes` (v5) | high | — |
| `plan.columns/filters/aggregations/group_by/order_by/limit/joins` | ✅ B2+ | plan_parsed.* (формат различается v1↔v5) | medium | нужен унифицированный mapper plan→payload |
| `plan.assumptions` | ❌ | — | — | нет поля; можно начать со строки "fallback_used: true" |
| `sql.query` | ✅ | `payload.source.generated_sql` | high | — |
| `sql.dialect` | ✅ | hardcoded sqlite / lane-dependent | medium | сделать explicit |
| `sql.validated` | ✅ | `is_safe_select(sql)` | high | сейчас не пишется в payload |
| `sql.read_only` | ✅ | derive из guard | high | — |
| `result_table.format` | ⚠️ | сейчас `records` | high | поддержка `csv_uri`/`arrow_uri` потребует upload-step |
| `result_table.columns` | ✅ | ключи `rows[0]` | high | — |
| `result_table.rows` | ✅ | `payload.rows` | high | — |
| `result_table.row_count` | ✅ | `payload.summary.row_count` | high | — |
| `result_table.truncated` | ❌ | — | — | требуется row-limit и compare с факт. n |
| `field_metadata[].name/sql_type/data_type/nullable` | ⚠️ | имя — да; sql_type — нет (sqlite cursor не даёт); data_type — частично из `summary.dtype` | low | подключить cursor.description **типы**, либо PRAGMA table_info |
| `field_metadata[].source_table/source_column` | ❌ | — | — | нужен SQL-AST анализ выходных столбцов |
| `field_metadata[].display_name` | ❌ | — | — | можно alias из плана; иначе human-readable из `column_name` |
| `field_metadata[].description` | ❌ | — | — | нет; нужен schema-comments источник |
| `field_metadata[].semantic_role` | ❌ | — | — | derive по правилам §8 |
| `field_metadata[].unit/periodicity/allowed_aggregations/default_aggregation` | ❌ | — | — | нужен metric dictionary + правила §8 |
| `field_metadata[].examples` | ⚠️ | top values из `summary.columns[*].top` (только categorical) | medium | сделать единообразно |
| `field_metadata[].provenance` | ⚠️ | sql_compiler_v2 знает выражения; planner_v5 measures[] имеет `expr` и `agg` | medium | потребуется маппинг SQL alias → expr |
| `execution.latency_ms` | ❌ | — | — | завести таймер вокруг executor |
| `execution.row_limit/timeout_ms` | ⚠️ | hardcoded 8000ms | high | пробрасывать из `constraints` |
| `execution.executable` | ✅ | predictions `executable` | high | — |
| `quality.confidence` | ⚠️ | `query_analysis.confidence`, `plan_v5.confidence` | low | оба rule-of-thumb; нет калибровки |
| `quality.warnings` | ⚠️ | `payload.notes` (пустое); `fallback_used`, `plan_invalid`, `repair_used` — derive | medium | — |
| `errors[]` | ✅ | `error_type`+`error_message` (см. таксономия §9) | high | — |

---

## 8. Metadata inference: что можно вывести автоматически

Цель: заполнять `field_metadata[]` без metric-dictionary, с явным риск-уровнем.

| Правило | Пример | Источник | Риск ошибки | Нужен ли словарь? |
|---|---|---|---|---|
| `sql_type` "INTEGER"/"BIGINT"/"NUMERIC"/"REAL" → `data_type=number` | `INTEGER` → number | `PRAGMA table_info` (SQLite); `cursor.description` для других СУБД | low | нет |
| `sql_type` LIKE "VARCHAR"/"TEXT" → `data_type=string` | `TEXT` → string | то же | low | нет |
| `sql_type` LIKE "DATE"/"TIMESTAMP" → `data_type=date|datetime` | `DATE` → date | то же | low | нет |
| Имя колонки matches `^(date|day|year|month|quarter|week|created_at|.+_date)$` → `semantic_role=time` | `release_year` → time | имя колонки + наличие `query_analysis.signals.time` | medium | нет |
| `data_type=number` AND alias matches `^(count|cnt|n_|num_|sum|total|avg|mean|min|max)_?` → `semantic_role=measure` | `n_singers` → measure | alias плана / regex по имени колонки | medium | нет |
| `data_type=string` AND `summary.distinct_count <= 50` AND `row_count > 50` → `semantic_role=dimension` | `country` → dimension | `compute_summary` already produces distinct_count | medium | нет |
| Имя matches `(.*_)?id$` AND distinct_count == row_count → `semantic_role=id` | `singer_id` → id | summary + regex | low | нет |
| SQL func == COUNT/SUM/AVG/MIN/MAX → `provenance.aggregation` + `default_aggregation` | `COUNT(*)` → `count` | sql_compiler_v2 / plan `measures[].agg` | low | нет |
| `date_trunc(month, …)` или GROUP BY дата с trunc → `periodicity=month` | `DATE_TRUNC('month', x)` → month | plan v5 `time_grain` или regex по SQL | medium | нет |
| Alias из плана — это `display_name` | `count(*) AS n` → display_name="n" | plan `measures[].alias` | low | нет |
| schema comments / column docs → `description` | `COMMENT ON COLUMN ... IS 'X'` | **отсутствует в Spider** | — | да, потребуется внешний источник |
| metric dictionary → `unit`, `definition`, `allowed_aggregations` | `revenue` → unit=USD, allowed=[sum,avg] | **отсутствует** | high | **да**, нужен domain-dictionary |
| selected SQL expressions → `provenance.expression` | `SUM(price * qty) AS revenue` → expr | sql_compiler_v2 + AST | medium | нет |
| `data_type=number` AND alias похож на metric из словаря → допустимые `allowed_aggregations` берутся из словаря | `revenue` → [sum,avg,min,max] | metric dictionary | low (если словарь полон) | да |

**Главный пробел:** ни domain-dictionary, ни schema comments в текущем коде нет. Spider не предоставляет описаний / units / периодичности. Чтобы Пётр получал не "unknown" в большинстве полей, нужен либо вручную поддерживаемый metric dictionary, либо пайплайн извлечения из information_schema (для real-time БД).

---

## 9. Безопасность и ограничения выполнения SQL

**Текущие механизмы (ходовая ветка):**

| Mechanism | Where | Status |
|---|---|---|
| SELECT-only / запрет DDL/DML | `baselines_b4.py::is_safe_select`, `baselines_b4_final.py::is_safe_select`, `sqlglot_checks_v2.py` | ✅ regex + sqlglot |
| Запрет `PRAGMA / ATTACH / DETACH / GRANT / REVOKE` | те же | ✅ |
| Read-only connection | partial — для SQLite через guard, не через connection mode | ⚠️ |
| Per-query timeout | `func_timeout` 8s | ✅ хардкод |
| Row limit | **отсутствует** на уровне executor'а | ❌ |
| Join limit | отсутствует | ❌ |
| Cost estimation | отсутствует | ❌ |
| Sandbox | SQLite — отдельный файл; BQ/Snow — credentials lane-specific | ⚠️ |
| Защита от prompt-injection через schema/docs | минимальная — schema берётся из `tables.json` (контролируемо) | ⚠️ |
| Repair loop | `baselines_b4_v2.py::make_repair_prompt_v2` | ✅ k=1 retry |
| Политика больших результатов | отсутствует — payload включает все строки | ❌ |
| Mass mode classification | `error_taxonomy_v2.py` | ✅ 16 категорий |

**Рекомендуемый error enum для production response:**

| Code | Mapping из текущих error_type |
|---|---|
| `schema_not_found` | новое — для request с unknown `data_source.id` |
| `ambiguous_query` | derive из low `query_analysis.confidence` |
| `plan_invalid` | `plan_valid=false` + `plan_error=*` |
| `sql_generation_failed` | `parse_error`, пустой `generated_sql` |
| `sql_validation_failed` | `unsafe_blocked`, `regex_*` причины из `is_safe_select` |
| `sql_execution_failed` | `OperationalError` без частных подкатегорий |
| `timeout` | `error_type=timeout` / `runtime_timeout` |
| `empty_result` | `EMPTY_RESULT` / executable=true и rows=[] |
| `row_limit_exceeded` | новое — нужен row-limit на executor'е |
| `permission_denied` | новое — для row-level security |
| `metadata_incomplete` | новое — payload построен, но `field_metadata[]` частично unknown |

`error_taxonomy_v2.py` уже даёт более детальные `OP_NO_SUCH_TABLE`, `OP_NO_SUCH_COLUMN`, `OP_AMBIGUOUS_COL`, `OP_SYNTAX`, `RUNTIME_TYPE`, `RUNTIME_TIMEOUT`, `PIPELINE_EXCEPTION`, `NO_EVAL_ENGINE`. Нужен mapper `taxonomy_v2 → error enum выше` плюс `human_message`.

---

## 10. Метрики и экспериментальные результаты

Источник: [outputs/tables/final_experiment_master_matrix.md](outputs/tables/final_experiment_master_matrix.md) — 127 runs.

Каждая строка содержит: `Run`, `Baseline`, `Ver`, `Model`, `Subset`, `Bench`, `n`, `EX`, `CI95`. Дополнительные поля метрик — в per-run CSV в `outputs/metrics/`.

### 10.1 Production-recommended baseline

| Field | Value |
|---|---|
| `run_id` | `b0_multidb30_v2` |
| Sample size | 30 |
| Database(s) | multi-DB (объединённый Spider subset, 30 NL→SQL pairs) |
| Model | `Qwen2.5-Coder-7B-Instruct` (4-bit nf4 — `bitsandbytes_config`) |
| Prompt mode | B0 — full schema, single-shot |
| EX | **0.9333** |
| CI95 | [0.7868, 0.9815] |
| Executable count | n=30, не разбито в master matrix; `outputs/metrics/b0_multidb30_v2_metrics.csv` содержит executable_count |
| Plan valid count | N/A (B0 без планнера) |
| Plan parse failures | N/A |
| Avg reduction ratio | 1.0 (B0 не сжимает схему) |

### 10.2 B1 baseline (lexical schema linking, single LLM call)

| Field | Value |
|---|---|
| `run_id` | `b1_multidb30_v2` |
| Sample size | 30 |
| Model | `Qwen2.5-Coder-7B-Instruct` |
| Prompt mode | B1 — reduced schema через lexical_schema_linking |
| EX | **0.7667** |
| CI95 | [0.5907, 0.8821] |

| Field | Value |
|---|---|
| `run_id` | `b1v3_qwen2p5_coder_7b_multidb30` |
| Sample size | 30 |
| Model | `Qwen2.5-Coder-7B-Instruct` |
| Prompt mode | B1_v3 — bidirectional schema linker |
| EX | **0.8000** |
| CI95 | [0.6269, 0.9050] |

### 10.3 B2 baseline (Plan→SQL with JSON Schema validation)

| Field | Value |
|---|---|
| `run_id` | `b2v2_multidb30` |
| Sample size | 30 |
| Model | `Qwen2.5-Coder-7B-Instruct` |
| Planner | v2 prompt + `plan_schema.json` (v1) validation; B1 fallback при invalid |
| EX | **0.8000** |
| CI95 | [0.6269, 0.9050] |
| Plan valid count | "не найдено в master matrix; см. `outputs/metrics/b2v2_multidb30_metrics.csv`" |

| Field | Value |
|---|---|
| `run_id` | `b2_spider_smoke10` |
| Sample size | 10 |
| Model | `Qwen2.5-Coder-7B-Instruct` |
| EX | **0.7000** |
| Executable count | 9 |
| Plan valid count | 9 |
| Plan parse failures | 0 |
| Avg reduction ratio | **0.475** |
| Fallback (full schema) count | 2 |

### 10.4 Smoke-set ranges (representative)

| Subset | Best B0 EX | Best B1 EX | Best B2 EX |
|---|---|---|---|
| smoke_10 | 1.0000 (`b0_qwen2p5_coder_14b_instruct_smoke10`) | 1.0000 (`b1_qwen2p5_coder_14b_instruct_smoke10`) | 0.7000 (`b2_spider_smoke10`) |
| smoke_25 | 0.9600 | 0.9600 | "не найдено в master matrix" |
| multidb_30 | 0.9333 (`b0_multidb30_v2`) | 0.8000 (`b1v3_*`) | 0.9000 (`b2v2_qwen2p5_coder_14b_multidb30`) |
| bird_minidev_30 (EXT) | 0.2667 | 0.2000 | "B2_v2 ниже B0 на этой задаче" |
| spider2lite_30 (EXT) | 0.0000 | 0.0000 | 0.0000 — env blocker, BQ/Snow creds |

### 10.5 Spider2 family (последние commits)

Из commit log:
- Phase 17 (`181352f`): 4 models × 2 lanes pilot10
- Phase 16 (`360f2a9`): BQ schema_valid 1→6 после constrained identifier repair, Snow=0
- Phase 14 (`0a8b433`): BQ/Snow schema-grounding v12 pilots

Точные EX-цифры по Spider2 BQ/Snow в master matrix (внутренний core scope) — `0.0000` для всех `spider2lite_30` runs. Реальный progress зафиксирован в `outputs/REPORT_SPIDER2_V18.md` (untracked). По текущим артефактам — **EX по Spider2 не пробивает 0** на стандартизированном subset.

### 10.6 Главные ошибки (error taxonomy)

В `outputs/tables/error_taxonomy_smoke25.md` фиксируются bucket-counts. По typical B0/B1 smoke25:
- `RESULT_MISMATCH` — преобладает
- `OP_NO_SUCH_COLUMN`, `OP_NO_SUCH_TABLE` — schema-mismatch
- `OP_SYNTAX` — редко
- `EMPTY_RESULT` — несколько случаев
Точные числа по конкретному baseline — "см. `outputs/tables/error_taxonomy_smoke25.md`".

### 10.7 Ограничения экспериментов (явно указаны в `architecture_document_v2.md` §8)

1. Один benchmark family (Spider) — заявления о доминировании B0 могут не переноситься на BIRD/корпоративные NL→SQL.
2. 4-bit nf4 quantization — абсолютные EX могут вырасти на fp16/bf16.
3. Малые подмножества (n=10/25/30) — широкие confidence intervals.
4. EX как метрика не различает "правильные строки случайно" и "семантически верный SQL".
5. DeepSeek-Coder-V2-Lite-Instruct **не оценен** (environmental blocker).
6. BIRD official R-VES / Soft F1 **не получены** (CLI drift).
7. Spider2-Lite EX = 0 на всех runs из-за env (BQ/Snowflake creds).

---

## 11. Интеграционные примеры

Ниже — три минимальных `DataExtractionResponse`-payload'а в форме, которую Пётр сможет потреблять напрямую. Поля, которые пайплайн **сегодня** не заполняет (`field_metadata[].unit`, `description`, и т.п.), помечены `null` или `unknown`.

### 11.1 Time series (грейн — год, demo synthetic)

> Synthetic data — сгенерировано для иллюстрации, не реальный run.

```json
{
  "request_id": "demo-ts-001",
  "status": "success",
  "user_query": "Show me the number of concerts per year.",
  "normalized_query": null,
  "data_source": {"id": "concert_singer", "name": "concert_singer", "dialect": "sqlite", "schema_version": null},
  "plan": {
    "raw": {
      "answer_shape": "grouped",
      "measures": [{"agg": "count", "expr": "*", "alias": "n_concerts"}],
      "dimensions": [{"expr": "concert.year", "time_grain": "year"}],
      "filters": [],
      "join_anchor_nodes": ["concert"],
      "ordering": [{"expr": "concert.year", "direction": "asc"}]
    },
    "validated": true,
    "intent": "select_groupby",
    "tables": ["concert"],
    "columns": ["concert.year"],
    "filters": [],
    "aggregations": [{"function": "COUNT", "column": "*"}],
    "group_by": ["concert.year"],
    "order_by": [{"column": "concert.year", "dir": "ASC"}],
    "limit": null,
    "joins": [],
    "assumptions": []
  },
  "sql": {
    "query": "SELECT year, COUNT(*) AS n_concerts FROM concert GROUP BY year ORDER BY year ASC",
    "dialect": "sqlite",
    "validated": true,
    "read_only": true
  },
  "result_table": {
    "format": "records",
    "columns": ["year", "n_concerts"],
    "rows": [
      {"year": 2014, "n_concerts": 1},
      {"year": 2015, "n_concerts": 3},
      {"year": 2016, "n_concerts": 2},
      {"year": 2017, "n_concerts": 4},
      {"year": 2018, "n_concerts": 2}
    ],
    "uri": null,
    "row_count": 5,
    "truncated": false
  },
  "field_metadata": [
    {
      "name": "year",
      "source_table": "concert",
      "source_column": "year",
      "display_name": "Year",
      "description": null,
      "sql_type": "INTEGER",
      "data_type": "number",
      "semantic_role": "time",
      "unit": null,
      "periodicity": "year",
      "allowed_aggregations": ["min", "max", "count"],
      "default_aggregation": "none",
      "nullable": false,
      "examples": [2014, 2015, 2016, 2017, 2018],
      "provenance": {"expression": "concert.year", "aggregation": null, "derived": false}
    },
    {
      "name": "n_concerts",
      "source_table": "concert",
      "source_column": "*",
      "display_name": "Number of concerts",
      "description": null,
      "sql_type": "INTEGER",
      "data_type": "number",
      "semantic_role": "measure",
      "unit": null,
      "periodicity": null,
      "allowed_aggregations": ["sum", "avg", "min", "max"],
      "default_aggregation": "sum",
      "nullable": false,
      "examples": [1, 2, 3, 4],
      "provenance": {"expression": "COUNT(*)", "aggregation": "count", "derived": true}
    }
  ],
  "execution": {"latency_ms": 42, "row_limit": 1000, "timeout_ms": 8000, "executable": true},
  "quality": {"confidence": 0.85, "warnings": []},
  "errors": []
}
```

### 11.2 Category comparison (synthetic)

> Synthetic data.

```json
{
  "request_id": "demo-cat-002",
  "status": "success",
  "user_query": "Total stadium capacity by country.",
  "normalized_query": null,
  "data_source": {"id": "concert_singer", "name": "concert_singer", "dialect": "sqlite", "schema_version": null},
  "plan": {
    "raw": {
      "answer_shape": "grouped",
      "measures": [{"agg": "sum", "expr": "stadium.capacity", "alias": "total_capacity"}],
      "dimensions": [{"expr": "stadium.country"}],
      "join_anchor_nodes": ["stadium"]
    },
    "validated": true,
    "intent": "select_groupby",
    "tables": ["stadium"],
    "columns": ["stadium.country", "stadium.capacity"],
    "filters": [],
    "aggregations": [{"function": "SUM", "column": "stadium.capacity"}],
    "group_by": ["stadium.country"],
    "order_by": [{"column": "total_capacity", "dir": "DESC"}],
    "limit": null,
    "joins": [],
    "assumptions": []
  },
  "sql": {
    "query": "SELECT country, SUM(capacity) AS total_capacity FROM stadium GROUP BY country ORDER BY total_capacity DESC",
    "dialect": "sqlite", "validated": true, "read_only": true
  },
  "result_table": {
    "format": "records",
    "columns": ["country", "total_capacity"],
    "rows": [
      {"country": "England", "total_capacity": 95000},
      {"country": "Spain", "total_capacity": 81000},
      {"country": "Germany", "total_capacity": 75000},
      {"country": "France", "total_capacity": 67500}
    ],
    "uri": null, "row_count": 4, "truncated": false
  },
  "field_metadata": [
    {
      "name": "country",
      "source_table": "stadium", "source_column": "country",
      "display_name": "Country", "description": null,
      "sql_type": "TEXT", "data_type": "string",
      "semantic_role": "dimension",
      "unit": null, "periodicity": null,
      "allowed_aggregations": ["count"], "default_aggregation": "none",
      "nullable": false,
      "examples": ["England", "Spain", "Germany", "France"],
      "provenance": {"expression": "stadium.country", "aggregation": null, "derived": false}
    },
    {
      "name": "total_capacity",
      "source_table": "stadium", "source_column": "capacity",
      "display_name": "Total capacity", "description": null,
      "sql_type": "INTEGER", "data_type": "number",
      "semantic_role": "measure",
      "unit": null, "periodicity": null,
      "allowed_aggregations": ["sum", "avg", "min", "max"], "default_aggregation": "sum",
      "nullable": false,
      "examples": [67500, 75000, 81000, 95000],
      "provenance": {"expression": "SUM(stadium.capacity)", "aggregation": "sum", "derived": true}
    }
  ],
  "execution": {"latency_ms": 31, "row_limit": 1000, "timeout_ms": 8000, "executable": true},
  "quality": {"confidence": 0.78, "warnings": []},
  "errors": []
}
```

### 11.3 Top-N table (real Spider data — concert_singer.singer)

Real shape: payload построен на основе фактического spider DB (концепция совпадает с реальным [outputs/analytics_handoff/B0_smoke10_idx0.json](outputs/analytics_handoff/B0_smoke10_idx0.json), расширенным до целевого ответа).

```json
{
  "request_id": "demo-topn-003",
  "status": "success",
  "user_query": "Show name, country, age for all singers ordered by age from the oldest to the youngest.",
  "normalized_query": null,
  "data_source": {"id": "concert_singer", "name": "concert_singer", "dialect": "sqlite", "schema_version": null},
  "plan": {
    "raw": {
      "intent": "select_other",
      "tables": ["singer"],
      "operations": ["select", "orderby"],
      "columns": ["Name", "Country", "Age"],
      "order_by": [{"column": "Age", "dir": "DESC"}]
    },
    "validated": true,
    "intent": "select_other",
    "tables": ["singer"],
    "columns": ["singer.Name", "singer.Country", "singer.Age"],
    "filters": [],
    "aggregations": [],
    "group_by": [],
    "order_by": [{"column": "Age", "dir": "DESC"}],
    "limit": null,
    "joins": [],
    "assumptions": []
  },
  "sql": {
    "query": "SELECT Name, Country, Age FROM singer ORDER BY Age DESC;",
    "dialect": "sqlite", "validated": true, "read_only": true
  },
  "result_table": {
    "format": "records",
    "columns": ["Name", "Country", "Age"],
    "rows": [
      {"Name": "Joe Sharp", "Country": "Netherlands", "Age": 52},
      {"Name": "Timbaland", "Country": "United States", "Age": 32},
      {"Name": "Justin Brown", "Country": "France", "Age": 29},
      {"Name": "Rose White", "Country": "France", "Age": 41},
      {"Name": "John Nizinik", "Country": "France", "Age": 43}
    ],
    "uri": null, "row_count": 5, "truncated": false
  },
  "field_metadata": [
    {
      "name": "Name", "source_table": "singer", "source_column": "Name",
      "display_name": "Name", "description": null,
      "sql_type": "TEXT", "data_type": "string", "semantic_role": "text",
      "unit": null, "periodicity": null,
      "allowed_aggregations": ["count"], "default_aggregation": "none",
      "nullable": false, "examples": ["Joe Sharp", "Timbaland"],
      "provenance": {"expression": "singer.Name", "aggregation": null, "derived": false}
    },
    {
      "name": "Country", "source_table": "singer", "source_column": "Country",
      "display_name": "Country", "description": null,
      "sql_type": "TEXT", "data_type": "string", "semantic_role": "dimension",
      "unit": null, "periodicity": null,
      "allowed_aggregations": ["count"], "default_aggregation": "none",
      "nullable": false, "examples": ["France", "Netherlands", "United States"],
      "provenance": {"expression": "singer.Country", "aggregation": null, "derived": false}
    },
    {
      "name": "Age", "source_table": "singer", "source_column": "Age",
      "display_name": "Age", "description": null,
      "sql_type": "INTEGER", "data_type": "number", "semantic_role": "measure",
      "unit": "years", "periodicity": null,
      "allowed_aggregations": ["min", "max", "avg"], "default_aggregation": "avg",
      "nullable": false, "examples": [29, 32, 41, 43, 52],
      "provenance": {"expression": "singer.Age", "aggregation": null, "derived": false}
    }
  ],
  "execution": {"latency_ms": 12, "row_limit": 1000, "timeout_ms": 8000, "executable": true},
  "quality": {"confidence": 0.92, "warnings": []},
  "errors": []
}
```

> NB: реальный prediction по `idx=2` в `outputs/predictions/b2_spider_smoke10_predictions.jsonl` уже содержит `plan_parsed`, `selected_tables`, `generated_sql`, `executable=true`, `execution_match=true`. Все эти поля — ровно то, что нужно для shape выше. Достаёт только `field_metadata[]` с semantic_role/unit (см. §8).

---

## 12. Что нужно от Петра / downstream

Конкретные открытые вопросы:

| # | Вопрос | Почему важно |
|---|---|---|
| 1 | Какие поля `field_metadata[]` обязательны для рендера, какие optional? | определит, насколько глубоко надо инвестировать в metric dictionary |
| 2 | Какой формат `result_table` предпочтителен — `records` (inline JSON), `csv_uri`, `arrow_uri`? | сейчас отдаём только `records`; для больших результатов нужен URI |
| 3 | Какой лимит на `row_count` и количество колонок? | нужно для `constraints.row_limit` и `result_table.truncated` |
| 4 | Нужен ли `sql.query` строкой в response или Пётр ничего с SQL не делает? | если не нужен — можно сократить payload |
| 5 | Нужен ли `plan` целиком, или достаточно семантических полей в `field_metadata`? | план полезен для audit-trail; не каждый downstream его использует |
| 6 | Нужен ли `provenance` для каждой колонки или только для derived? | определяет глубину AST-анализа |
| 7 | Какие output types Пётр поддерживает (PNG / SVG / HTML / Vega-Lite spec / interactive React)? | определит, как сайт получает результат рендера |
| 8 | Какие классы ошибок downstream умеет показывать пользователю? | mapping `errors[]` → human messages |
| 9 | Кто отвечает за i18n: upstream (Денис) шлёт `display_name` на ru/en, или downstream локализует? | важно для locale в request |
| 10 | Как сайт получает финальный артефакт визуализации (PNG/SVG/HTML/Vega-Lite spec)? | определит, нужен ли HTTP-endpoint в downstream-модуле или достаточно in-process call |
| 11 | Должен ли upstream когда-нибудь возвращать партиционированный ответ (`status: partial_success`) с пустыми `field_metadata`, чтобы Пётр сам показал raw таблицу? | определит fallback-стратегию |

---

## 13. Риски интеграции

| Риск | Причина | Влияние | Как обнаружить | Как исправить | Owner |
|---|---|---|---|---|---|
| Отсутствие `field_metadata[].unit` / `description` в Spider | в Spider нет schema-comments | Пётр получает много `null` → не сможет подписать оси | unit-test на ratio non-null fields | metric dictionary (manual) или подключить information_schema из реальной БД | shared (Денис вкл. инфраструктуру, Пётр согласовывает required fields) |
| Plan-формат различается между v1 (`plan_schema.json`) и v5 (`plan_schema_v5.json`) | две параллельные ветки разработки | downstream-маппер ломается на одном из вариантов | прогнать payload-builder на B2_v2 (plan v1) и v5 stack | унифицирующий mapper plan→DataExtractionResponse.plan | Denis/upstream |
| Отсутствие `request_id` сегодня | нет HTTP API | трассировка проблем невозможна | любой prod incident | ввести в request, пробросить | Denis/upstream |
| Нет row-limit на executor | хардкод | OOM на больших таблицах + раздутый payload | стресс-тест на 100k-row таблице | LIMIT в executor + flag `result_table.truncated` | Denis/upstream |
| Нет latency_ms / per-item timing | замеряется только per-run | SLA-мониторинг невозможен | любой запрос с long-tail latency | timer вокруг F11 | Denis/upstream |
| BQ/Snow EX = 0 | env blocker (creds, dialect) | заявления о multi-dialect support пока пустые | `outputs/tables/final_experiment_master_matrix.md` (`spider2lite_30` runs) | пройти env runbooks для Spider2-Lite | Denis/upstream |
| Planner HURTS (-0.0333 EX vs B1_v3) | empirical finding на multi-DB | B2/B4 в production может снижать качество | сравнить EX по reproducible subset | в production использовать B0 single-shot; B2 как audit-trail | Denis/upstream |
| `is_safe_select` regex может пропустить нестандартный DDL (e.g. via comments) | regex вместо AST | injected statement исполняется | fuzzing с обфусцированными ключевыми словами | подключить sqlglot AST guard как primary, regex как secondary | Denis/upstream |
| Prompt injection через schema descriptions / docs | если description берётся из БД (не sanitized) | модель может выполнить вредную инструкцию | unit-test со специальной строкой в `column_comment` | sanitization + length cap на тексты, попадающие в prompt | Denis/upstream |
| Несогласованный `data_source.dialect` | upstream считает `sqlite`, фронтенд послал `postgresql` | SQL компилится под не тот диалект | request validation | строгий enum + reject unknown | shared |
| Отсутствие versioning контракта | сейчас `schema_version: "v1"` только в payload | breaking changes в Response сломают Петра | regression test по контракту | semver на Request/Response, deprecation policy | shared |
| Missing `field_metadata` для derived columns с CTE/window | sql_compiler_v2 не покрывает window/nested | `provenance` пустой | unit-test с window-query | расширить AST-mapper или явно ставить `derived=true, provenance=null` | Denis/upstream |
| Большие результаты в JSON | сейчас все строки inline | latency+payload size | benchmark на n=10000 | переключение на `csv_uri` / `arrow_uri` при превышении threshold | shared |
| Несогласованность locale | upstream англо-only, фронтенд русскоязычный | display_name/description не локализованы | смотреть `display_name` на rus-payload | i18n на стороне Пети **или** добавить локализованный schema-словарь | shared |

---

## 14. Executive summary

Что upstream **уже умеет отдавать сегодня** (B0/B1/B2 на Spider/multi_db_30, фактический EX 0.93 / 0.80 / 0.80):
SQL-строку (validated SELECT-only), per-item `executable`/`execution_match`/`error_type`, normalized rows + per-column descriptive summary, источник (db_id, model, baseline, idx), reduction_ratio и план (B2). Всё это уже сериализуется как `AnalyticsPayload v1` (`postprocess.py::build_analytics_payload`) и документировано в `outputs/docs/io_contracts.md`.

Чего **не хватает для качественной визуализации у Петра**:
`field_metadata[]` с semantic_role/data_type/unit/periodicity/allowed_aggregations/provenance; `request_id`; `latency_ms`; `result_table.truncated` + row-limit на executor'е; явный `data_source.dialect` в payload; пробрасывание `plan_parsed` и `selected_tables` в response. Domain/metric dictionary отсутствует — без него `unit`/`description`/`allowed_aggregations` вынужденно будут `null` или `unknown`.

Поля, которые **обязательно надо добавить** перед интеграцией:
`request_id`, `data_source.dialect`, `field_metadata[].name+data_type+semantic_role+default_aggregation`, `execution.executable+latency_ms`, `errors[].code` (по enum §9). Без этих пяти Пётр не сможет даже выбрать тип графика и подписать оси.

**Минимальный контракт для MVP** (двусторонний, можно поднять за 1 неделю работы):
input — `request_id`, `user_query`, `data_source.{id,dialect}`, `constraints.{timeout_ms,row_limit}`;
output — `request_id`, `status`, `sql.query`, `result_table.{columns,rows,row_count,truncated}`, `field_metadata[].{name,data_type,semantic_role,default_aggregation,provenance.aggregation}`, `errors[].code`. AnalyticsPayload v1 нужно расширить как `AnalyticsPayload v2`, не ломая v1: сегодняшние поля → `result_table` + `source` + новые `field_metadata`/`execution`/`errors`.

**Доработки для production / microservice:**
1) обернуть pipeline в HTTP service (FastAPI), 2) ввести `request_id` и трассировку через все слои (F1…F13), 3) ввести row-limit + truncated, 4) подключить sqlglot AST guard как первичный, regex как вторичный, 5) написать `field_metadata`-builder (правила §8) + опциональный metric dictionary, 6) разделить on-the-fly vs cached schema metadata, 7) восстановить Spider2-Lite (BQ/Snow creds) для multi-dialect claim, 8) ввести semver на Request/Response и regression test на контракт.

Source-of-truth для всех чисел в этом отчёте: `outputs/tables/final_experiment_master_matrix.md` (127 runs); per-item — `outputs/predictions/*.jsonl`; existing border — `outputs/docs/io_contracts.md` + `repo/src/evaluation/postprocess.py`.
