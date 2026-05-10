# joint_integration_contract_review.md

> Integration architect review. Source-of-truth: [integration_packet_denis.md](integration_packet_denis.md) (upstream Text-to-SQL/DataExtraction) и [integration_packet_peter.md](integration_packet_peter.md) (downstream Text-to-Visualization). Факты, которых нет в этих двух пакетах, помечаются как `unknown`.

---

## 1. Итоговая схема пайплайна

Последовательность вызовов:

1. **`POST /api/nl2chart`** на общем backend'е сайта. Backend генерирует `request_id` (UUID), резолвит `user_id` / `permissions` / `data_source.id` / `dialect` / `locale` / `timezone`.
2. Backend конструирует **`DataExtractionRequest`** и зовёт upstream-сервис Дениса (`POST /extract` на Text-to-SQL service).
3. Upstream выполняет F1…F13 (query analysis → schema linking → planner → SQL synth → safe-select guard → executor → postprocess → AnalyticsPayload v2) и возвращает **`DataExtractionResponse`** (rows + field_metadata + plan + sql + errors).
4. **Adapter layer** на backend нормализует ответ: SQL types → visualization data types, role inference (если upstream не дал), table truncation, null handling, error mapping. Получается **`VisualizationRequest`**.
5. Backend зовёт downstream-сервис Петра (`POST /visualize` на Visualization service).
6. Downstream выполняет intent extraction → candidate generation (B0/B1/B2/B4/B5) → strict validation → ranking → optional render → возвращает **`VisualizationResponse`** (selected_view + candidates + table_view + explanation + rendered_artifacts).
7. Backend сохраняет артефакты, отдаёт сайту JSON + ссылки на `png_uri`/`svg_uri`/`html_uri`. Сайт показывает chart/table пользователю.

ASCII-схема:

```
+--------+      +--------+      +-------------+      +-------------------+      +-----------------+      +---------------------+      +----------------+      +--------+
|  User  | ---> | Web UI | ---> | API Gateway | ---> | Text-to-SQL Svc   | ---> | Result/Metadata | ---> | Visualization Svc   | ---> | Chart/Table    | ---> | Web UI |
| (NL Q) |      |        |      | (backend)   |      | (Denis: F1..F13)  |      | (Adapter layer) |      | (Peter: B0..B5)     |      | Artifact (PNG) |      |        |
+--------+      +--------+      +-------------+      +-------------------+      +-----------------+      +---------------------+      +----------------+      +--------+
                                       |                       |                          |                         |                          |
                                  request_id                DataExtraction          Visualization            Visualization              png_uri/svg_uri
                                  user_query                Request/Response        Request                   Response                  + Vega-Lite spec
```

Строго: upstream **не** знает про Vega-Lite; downstream **не** генерирует и **не** валидирует SQL. SQL пробрасывается только как provenance/debug.

---

## 2. Совместимость полей

Колонки: «Денис отдаёт?» — может ли upstream сейчас или после минимальных доработок выгрузить поле; «Пётр требует?» — нужно ли поле downstream'у; «Совместимо?» — совпадают ли семантика и формат напрямую.

| Поле | Денис отдаёт? | Пётр требует? | Совместимо? | Действие |
|---|---|---|---|---|
| `request_id` | ❌ нет (нет HTTP API, есть только `(subset, idx)`) — denis §3, §5 | ✅ required — peter §5 | ❌ | Backend генерирует UUID; пробросить через все слои |
| `user_query` | ✅ есть как `payload.source.question` — denis §4.2 | ✅ required (`user_query`) — peter §5 | ⚠️ rename | Adapter: `question` → `user_query` |
| `locale` | ❌ нет (англ-only, не используется) — denis §3 | ⚠️ optional, default `ru-RU` — peter §5 | ⚠️ | Backend задаёт default; upstream может игнорировать |
| `timezone` | ❌ нет — denis §3 | ⚠️ optional, default `Europe/Moscow` — peter §5 | ⚠️ | Backend задаёт default |
| `datasource id` | ✅ `payload.source.db_id` (Spider-style) — denis §5 | ✅ `data_source.id` required — peter §5 | ✅ | Прямой mapping |
| `dialect` | ⚠️ partial: hardcoded `sqlite`, в plan_v5 есть, но **не сериализуется** в payload — denis §5 | ⚠️ optional `data_source.dialect`, default `unknown` — peter §5 | ⚠️ | Upstream должен явно класть в payload; enum согласовать (см. §6) |
| `SQL` | ✅ `payload.source.generated_sql` — denis §4.2 | ⚠️ optional `query_context.sql` (provenance only, downstream не оценивает) — peter §5, §13.4 | ✅ | Прямой mapping |
| `plan` | ✅ B2+ в predictions `plan_parsed`, **НЕ в payload** сейчас — denis §4.3, §5 | ⚠️ optional `query_context.plan` — peter §5 | ⚠️ | Upstream должен пробросить `plan_parsed` в payload; v1↔v5 mapper нужен |
| `rows` | ✅ `payload.rows` (нормализованные dict) — denis §4.2 | ✅ `result_table.rows` (records) | условно `csv_uri`/`arrow_uri` для больших — peter §5 | ⚠️ | Прямой mapping для inline; URI-форматы пока не реализованы у Дениса |
| `columns` | ⚠️ implicit — ключи `rows[0]` или `payload.summary.columns` — denis §5 | ✅ `result_table.columns` required (explicit list) — peter §5 | ⚠️ | Adapter: derive `columns = list(rows[0].keys())` если upstream не дал |
| `row_count` | ✅ `payload.summary.row_count` и `payload.n_rows` — denis §5 | ✅ `result_table.row_count` required — peter §5 | ✅ | Прямой mapping |
| `truncated` | ❌ нет (нет row-limit на executor'е) — denis §5, §9 | ⚠️ optional, default `false` — peter §5 | ❌ | Ввести row-limit на executor + flag (denis §9, §13) |
| `field name` | ✅ ключи в `rows[0]` — denis §5 | ✅ `field_metadata.name` required — peter §5 | ✅ | Прямой mapping; alias из плана если есть |
| `display_name` | ❌ нет, можно alias из плана v5 (`measures[].alias`) — denis §8 | ⚠️ optional (нет в Pydantic peter, но используется в title/i18n) — peter §3 | ❌ | Ввести; либо derive Title-Case из `name`, либо тянуть из плана |
| `sql_type` | ❌ sqlite cursor не отдаёт типы; нужен `PRAGMA table_info` — denis §5, §8 | ❌ не требует напрямую (использует `dtype`) — peter §3 | n/a | Optional; полезно для adapter mapping |
| `data_type` | ⚠️ partial: `summary.columns[*].dtype` ∈ {`numeric`, `categorical_or_mixed`} — бинарно, без int/float/date — denis §5 | ✅ важно (`field_metadata.dtype`) — peter §5 | ⚠️ | Adapter: расширить mapping (см. §5); подтянуть `PRAGMA table_info` для точных типов |
| `semantic_role` | ❌ не выводится — denis §5; правила inference в denis §8 | ✅ важно (`field_metadata.role` ∈ measure/dimension/time/id/text/unknown) — peter §5 | ⚠️ | Upstream запускает inference (denis §8) ИЛИ adapter inferит (см. §5) |
| `description` | ❌ нет (Spider не имеет column comments) — denis §5, §8 | ⚠️ optional, влияет на field linking & LLM prompt — peter §3 | ❌ | Источник: external metric dictionary / information_schema; пока `null` |
| `unit` | ❌ нет (требуется metric dictionary) — denis §5 | ⚠️ optional; влияет на axis labels / formatting — peter §5 | ❌ | Пока `null`; warning `missing_unit` |
| `periodicity` | ⚠️ partial: plan_v5 `dimensions[].time_grain` — denis §5, §8 | ⚠️ optional, влияет на line vs bar — peter §5 | ⚠️ | Пробросить из plan; adapter может поднять regex'ом по SQL |
| `allowed_aggregations` | ⚠️ partial: plan_v5 `measures[].agg` — но это _фактический_ выбор, не _множество_ — denis §5 | ⚠️ optional, hard validation у downstream — peter §5 | ⚠️ | Conservative defaults в adapter (peter §8): measure→[sum,mean,min,max,count], dimension→[count] |
| `default_aggregation` | ⚠️ partial: derive из `plan_parsed.aggregations` — denis §5 | ✅ важно (избежать sum vs avg угадывания) — peter §5 | ⚠️ | Если план есть — брать оттуда; иначе — heuristic (peter §8) |
| `filters` | ✅ partial: plan v1 `filters`, plan v5 `filters[]` — denis §5 | ⚠️ optional `query_context.filters` — peter §5 | ⚠️ | v1↔v5 unifying mapper (denis §13) |
| `group_by` | ✅ partial: plan v1 `group_by`, plan v5 `dimensions[]` — denis §5 | ⚠️ optional `query_context.group_by` — peter §5 | ⚠️ | Тот же mapper |
| `aggregations` | ✅ partial: plan v1 `aggregations`, plan v5 `measures[]` — denis §5 | ⚠️ optional `query_context.aggregations` — peter §5 | ⚠️ | Тот же mapper; критично для `already_aggregated` (peter §12 — double aggregation) |
| `order_by` | ✅ partial: plan v1/v5 — denis §5 | ⚠️ optional `query_context.order_by` — peter §5 | ⚠️ | Тот же mapper |
| `limit` | ✅ partial: в плане; не дублируется в payload — denis §5 | ⚠️ optional `query_context.limit` — peter §5 | ⚠️ | Пробросить в payload отдельным полем |
| `provenance` | ❌ sql_compiler_v2 знает выражения, но не пробрасывает в payload — denis §5; planner_v5 measures[] имеет `expr`/`agg` | ⚠️ optional, важно для derived fields & double-agg detection — peter §5, §12 | ❌ | Ввести `field_metadata.provenance.{expression, aggregation, derived}` (denis §7) |
| `errors` | ✅ `error_type`+`error_message`, плюс `error_taxonomy_v2.py` (16 категорий) — denis §4.1, §9 | ✅ `errors[].{code,message,field,recoverable}` — peter §6 | ⚠️ enum mismatch | Mapper taxonomy_v2 → unified enum (см. §6) |
| `warnings` | ⚠️ `payload.notes` (всегда `[]`); derive из `fallback_used`, `plan_invalid`, `repair_used` — denis §5 | ⚠️ `quality.warnings: list[string]` — peter §6 | ⚠️ | Adapter формирует warning-list |
| `confidence` | ⚠️ `query_analysis.confidence` (rule-based) + `plan_v5.confidence` — никуда не пробрасывается — denis §5 | ⚠️ `quality.confidence: float\|null` — peter §6 | ⚠️ | Пробросить в payload; калибровка отсутствует у обоих (low quality) |
| `latency` | ❌ замеряется per-run, не per-item, в payload не пишется — denis §5 | ✅ `performance.latency_ms` — peter §6 | ❌ | Ввести таймер вокруг executor; backend суммирует upstream+downstream |

**Резюме:** прямо совместимы только `user_query`/`db_id`/`SQL`/`rows`/`row_count`/`field name`. Всё остальное — либо требует mapping (rename / unification / inference), либо отсутствует у Дениса и должно быть добавлено (`request_id`, `dialect` в payload, `truncated`, `data_type` точный, `semantic_role`, `provenance`, `latency`).

---

## 3. Минимальный контракт MVP

Цель — поднять пайплайн end-to-end с минимальным числом изменений с обеих сторон. Только поля, без которых сайт не сможет показать ни chart, ни table.

### 3.1 JSON Schema (compact)

```json
{
  "$id": "nl2chart.MinimalContract.v1",
  "type": "object",
  "required": ["request_id", "user_query", "result_table", "field_metadata"],
  "properties": {
    "request_id": {"type": "string", "format": "uuid"},
    "user_query": {"type": "string", "minLength": 1},
    "result_table": {
      "type": "object",
      "required": ["columns", "row_count"],
      "properties": {
        "columns": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "rows":    {"type": "array", "items": {"type": "object"}},
        "uri":     {"type": ["string", "null"]},
        "row_count": {"type": "integer", "minimum": 0}
      },
      "oneOf": [
        {"required": ["rows"]},
        {"required": ["uri"]}
      ]
    },
    "field_metadata": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "data_type", "semantic_role"],
        "properties": {
          "name":          {"type": "string"},
          "data_type":     {"enum": ["number","string","date","datetime","boolean","unknown"]},
          "semantic_role": {"enum": ["measure","dimension","time","id","text","unknown"]}
        }
      }
    },
    "query_context": {
      "type": "object",
      "properties": {
        "sql":          {"type": ["string","null"]},
        "aggregations": {"type": "array"},
        "group_by":     {"type": "array"},
        "filters":      {"type": "array"}
      }
    }
  }
}
```

### 3.2 Pydantic-like описание

```python
class MinimalDataExtractionResponse(BaseModel):
    request_id: str                         # UUID, required, корреляция логов
    user_query: str                         # NL вопрос пользователя
    result_table: ResultTableMin            # см. ниже
    field_metadata: list[FieldMetadataMin]  # >= len(columns)
    query_context: QueryContextMin = QueryContextMin()  # opt но highly recommended

class ResultTableMin(BaseModel):
    columns: list[str]                      # explicit, required
    rows: list[dict[str, Any]] | None       # inline records
    uri: str | None                         # csv_uri/arrow_uri, альтернатива rows
    row_count: int

class FieldMetadataMin(BaseModel):
    name: str                               # совпадает с одним из result_table.columns
    data_type: Literal["number","string","date","datetime","boolean","unknown"]
    semantic_role: Literal["measure","dimension","time","id","text","unknown"]

class QueryContextMin(BaseModel):
    sql: str | None = None                  # provenance/debug only
    aggregations: list[dict] = []           # для already_aggregated detection
    group_by: list[str] = []
    filters: list[dict] = []
```

**Что _обязательно_ обеспечивает MVP-пайплайн (на стороне Дениса):**

- explicit `request_id` (генерится backend'ом, пробрасывается через `DataExtractionRequest`);
- explicit `result_table.columns` (derive из `rows[0].keys()` если нужно);
- расширенный `data_type` (mapping из `summary.dtype` + `PRAGMA table_info` — denis §8);
- `semantic_role` через rule-based inference (denis §8);
- `query_context.{sql, aggregations, group_by, filters}` пробрасываются из `plan_parsed` в payload.

Без этих пяти Пётр не сможет даже выбрать тип графика (ср. denis §14, peter §13).

---

## 4. Расширенный контракт для хорошего качества

Поверх MVP добавляем поля, повышающие качество визуализации. Ниже — каждое поле с указанием, **как именно** оно влияет на выбор графика. Источники: denis §7, §8, peter §3, §5, §7, §8.

| Поле | Как влияет на выбор графика |
|---|---|
| `description` | Усиливает field linking (peter §3): полезно для disambiguation между похожими колонками; попадает в LLM prompt для B3/B4/B5; используется в title/explanation. Без него — labels останутся technical (peter §7.4). |
| `unit` | Подписывает оси и tooltip (`Revenue, RUB`); в combo с `semantic_type=money/percent` — выбирает formatter (peter §7.4). Если null → warning `missing_unit`. |
| `periodicity` (`day/week/month/quarter/year`) | Ключевое для **line chart vs bar chart** на временных рядах (peter §8): корректный grain → line; mismatch → fallback на bar или warning `missing_periodicity`. Источник у Дениса — `plan_v5.dimensions[].time_grain` (denis §8). |
| `allowed_aggregations` (list) | Hard validation у downstream'а (peter §3, §5): blocked invalid `sum(category)`. Если null → conservative defaults (measure → sum/mean/min/max/count; dimension/id/text → count) (peter §8). |
| `default_aggregation` | Резолвит ambiguous `sum vs mean vs count` (peter §5, §7.2). Без него — downstream угадывает и может выбрать бизнес-неверную агрегацию. |
| `metric_definition` (`ARPU = revenue / users`) | Корректный title и explanation для BI-полезности (peter §7.4). Не влияет на выбор chart_type, но влияет на trust пользователя. |
| `grain` (e.g. `client`, `month`) | Защита от **double aggregation** (peter §12): если upstream уже сделал `sum(amount) by client`, downstream не должен повторно `sum`. Сочетается с `query_context.aggregations` и `provenance.derived=true`. |
| `provenance.{expression, aggregation, derived}` | Тот же double-agg guard + понимание derived columns (peter §7.3). Источник у Дениса — sql_compiler_v2 / plan_v5 measures[] (denis §5, §8). Если `derived=true` → downstream помечает поле как `already_aggregated`. |
| `formatting_hints` (`{format: currency, currency: RUB}`) | Прямой ввод для Vega `axis.format` / tooltip (peter §3). Без них — default browser formatting, цифры без разделителей. |
| `cardinality` | Решает **bar vs table vs scatter** (peter §7.2, §8): низкая cardinality (<= ~50) → bar; высокая — table или top-N + bar. У Дениса можно derive из `summary.distinct_count` (denis §8). |
| `value_examples` (top-N values) | LLM context для B3/B4/B5 (peter §3) и field disambiguation. У Дениса доступно через `summary.columns[*].top` (denis §5). |
| `quality.confidence` | Сайт может показать badge "low confidence — verify"; downstream может выбрать `partial_success` (peter §6). У Дениса — `query_analysis.confidence` + `plan_v5.confidence` (denis §5), оба rule-based, не калиброваны. |
| `quality.warnings` (list[str]) | Объяснения сайту: `fallback_used`, `plan_invalid`, `aggregation_defaults_used`, `wide_table_pruned`, `missing_periodicity` (peter §8). Не блокируют рендер, но информируют пользователя. |

Минимум, который реально двигает качество выше MVP, — это **periodicity + allowed_aggregations + default_aggregation + cardinality + provenance**. Они снижают риск double aggregation, неверного chart type и misleading axes (peter §12).

---

## 5. Adapter layer

Слой между upstream-ответом Дениса и downstream-запросом Петра. Псевдокод; реализация — backend (общий ownership).

```python
def normalize_extraction_response(resp: DataExtractionResponse) -> VisualizationRequest:
    # 1) request_id, user_query — passthrough
    columns = resp.result_table.columns or list(resp.result_table.rows[0].keys())

    # 2) field_metadata enrichment: для каждой колонки доводим до VisualizationRequest shape
    fields = [
        enrich_field_metadata(
            col,
            denis_field=resp.field_metadata.get(col),  # может быть пустым
            sample_values=[r[col] for r in resp.result_table.rows[:50]],
            summary=resp.summary.columns.get(col),     # denis §4.2
            plan=resp.plan,
        )
        for col in columns
    ]

    # 3) table truncation: если row_count > limit и truncated_flag не задан
    rt = resp.result_table
    truncated = rt.truncated if rt.truncated is not None else (rt.row_count > LIMIT)

    # 4) query_context
    qc = QueryContext(
        sql=resp.sql.query if resp.sql else None,
        plan=resp.plan.raw if resp.plan else None,
        filters=normalize_filters(resp.plan),     # v1 vs v5 mapper
        group_by=normalize_group_by(resp.plan),
        aggregations=normalize_aggregations(resp.plan),
        order_by=normalize_order_by(resp.plan),
        limit=resp.plan.limit if resp.plan else None,
        assumptions=collect_assumptions(resp),    # fallback_used, repaired, etc.
    )

    # 5) errors mapping (см. §6)
    errors = [map_error(e) for e in resp.errors]

    return VisualizationRequest(
        request_id=resp.request_id,
        user_query=resp.user_query,
        locale=resp.locale or "ru-RU",
        timezone=resp.timezone or "Europe/Moscow",
        data_source=DataSource(
            id=resp.data_source.id,
            name=resp.data_source.name or resp.data_source.id,
            dialect=resp.data_source.dialect or "unknown",
            schema_version=resp.data_source.schema_version,
        ),
        result_table=ResultTable(
            format="records" if rt.rows else "csv_uri",
            columns=columns,
            rows=rt.rows or [],
            uri=rt.uri,
            row_count=rt.row_count,
            truncated=truncated,
        ),
        field_metadata=fields,
        query_context=qc,
        presentation_preferences=infer_presentation(resp),  # из user_query/plan
    )


def map_sql_type_to_data_type(sql_type: str) -> str:
    # denis §8 — детерминированный маппинг; источник sql_type — PRAGMA table_info / cursor.description
    s = (sql_type or "").upper()
    if any(t in s for t in ("INT", "BIGINT", "NUMERIC", "REAL", "FLOAT", "DOUBLE", "DECIMAL")):
        return "number"
    if any(t in s for t in ("VARCHAR", "TEXT", "CHAR")):
        return "string"
    if "TIMESTAMP" in s or "DATETIME" in s:
        return "datetime"
    if "DATE" in s:
        return "date"
    if "BOOL" in s:
        return "boolean"
    return "unknown"


def infer_semantic_role(name: str, data_type: str, summary: dict, plan: dict) -> str:
    # denis §8 правила
    nm = name.lower()
    distinct = (summary or {}).get("distinct_count")
    n = (summary or {}).get("count") or 0

    if re.match(r"(date|day|year|month|quarter|week|created_at|.+_date)$", nm):
        return "time"
    if re.match(r"(.*_)?id$", nm) and distinct is not None and distinct == n:
        return "id"
    if data_type == "number" and re.match(r"^(count|cnt|n_|num_|sum|total|avg|mean|min|max)_?", nm):
        return "measure"
    # план-aware: alias из measures[] → measure
    if plan and any(m.get("alias") == name for m in plan.get("measures", [])):
        return "measure"
    if data_type == "string" and distinct is not None and distinct <= 50 and n > 50:
        return "dimension"
    if data_type == "number":
        return "measure"
    if data_type == "string":
        return "text"
    return "unknown"


def enrich_field_metadata(name, denis_field, sample_values, summary, plan) -> FieldMetadataV2:
    sql_type = denis_field.sql_type if denis_field else None
    data_type = map_sql_type_to_data_type(sql_type) if sql_type else \
                _from_summary_dtype(summary.dtype if summary else None, sample_values)
    role = (denis_field.semantic_role if denis_field and denis_field.semantic_role else
            infer_semantic_role(name, data_type, summary, plan))

    # provenance из плана / sql_compiler_v2
    prov = lookup_provenance(name, plan)  # {expression, aggregation, derived}
    derived = bool(prov and prov.get("aggregation"))

    return FieldMetadataV2(
        name=name,
        source_column=denis_field.source_column if denis_field else name,
        dtype=data_type,
        role=role,
        description=denis_field.description if denis_field else None,
        unit=denis_field.unit if denis_field else None,
        periodicity=lookup_periodicity(name, plan),    # plan_v5.time_grain
        allowed_aggregations=denis_field.allowed_aggregations or
                             default_allowed_aggs(role),   # measure→[sum,mean,min,max,count]; dim→[count]
        default_aggregation=(denis_field.default_aggregation if denis_field else None) or
                            default_agg_for_role(role),
        nullable=(summary.null_count > 0) if summary else None,
        value_examples=sample_values[:5],
        cardinality=(summary.distinct_count if summary else None),
        source_table=denis_field.source_table if denis_field else None,
        provenance=prov,                               # already_aggregated detection
    )


def map_error(denis_err) -> ErrorBlock:
    # denis §9 → unified enum (см. §6)
    return ErrorBlock(
        code=ERROR_CODE_MAP[denis_err.error_type],
        message=denis_err.error_message,
        recoverable=denis_err.error_type not in {"PIPELINE_EXCEPTION","NO_EVAL_ENGINE"},
    )
```

**Ключевые обязанности adapter'а:**

- `normalize_extraction_response` — полный mapper Denis → Peter request shape;
- `map_sql_type_to_data_type` — SQL `INTEGER/NUMERIC/REAL/TEXT/DATE/TIMESTAMP/BOOL` → `number/string/date/datetime/boolean` (denis §8);
- `infer_semantic_role` — rule-based по правилам denis §8 (alias regex + distinct_count + plan_v5 measures);
- metadata enrichment — заполняет `description/unit/periodicity/allowed_aggregations/default_aggregation/cardinality/provenance` оттуда, откуда возможно (план / summary / sample), оставляя `null` если источника нет;
- table truncation — если у Дениса `truncated` отсутствует, derive из `row_count > LIMIT`; ставит `quality.warnings += ["truncated"]`;
- null handling — peter §8: если `null_count > 0` → `nullable=true`; если high null ratio → warning `null_values_present`;
- error mapping — denis taxonomy_v2 (16 категорий) → unified enum §6 + human message;
- provenance mapping — `plan_v5.measures[].{expr, agg, alias}` → `field_metadata.provenance.{expression, aggregation, derived=true}` для defended derived measures (denis §8).

---

## 6. Общие статусы и ошибки

### 6.1 Status enum

| Status | Условие | Источник у Дениса | Источник у Петра |
|---|---|---|---|
| `success` | SQL executed + chart/table built + render OK | `executable=true` AND `error_type==""` | `validation_passed=true` AND render OK |
| `partial_success` | один из шагов прошёл, другой деградировал | `executable=true` BUT `metadata_incomplete` или `fallback_used` | spec OK BUT render failed; ИЛИ chart unsafe → table fallback (peter §6, §8) |
| `failed` | пайплайн не отдал юзабельный ответ | `executable=false` без recovered repair | `status=failed` в T2VPrediction (peter §4) |

### 6.2 Error codes (унифицированный enum)

| Code | Кто генерирует | Кто обрабатывает | Источник у Дениса | Сообщение пользователю |
|---|---|---|---|---|
| `schema_not_found` | upstream (Denis) | backend → site | новый код для unknown `data_source.id` (denis §9) | "Не найден источник данных. Проверьте подключение." |
| `ambiguous_query` | upstream | backend → site | low `query_analysis.confidence` (denis §9) | "Запрос неоднозначен. Уточните, пожалуйста." |
| `sql_generation_failed` | upstream | backend → site | `parse_error`, пустой `generated_sql` (denis §9) | "Не удалось сформировать запрос к данным. Попробуйте переформулировать." |
| `sql_validation_failed` | upstream | backend → site | `unsafe_blocked` / regex причины из `is_safe_select` (denis §9) | "Запрос не прошёл проверку безопасности." |
| `sql_execution_failed` | upstream | backend → site | `OperationalError`, `OP_NO_SUCH_TABLE`, `OP_NO_SUCH_COLUMN`, `OP_AMBIGUOUS_COL`, `OP_SYNTAX`, `RUNTIME_TYPE` (denis §9, error_taxonomy_v2) | "Ошибка выполнения запроса к источнику." |
| `timeout` | upstream | backend → site | `RUNTIME_TIMEOUT` / `func_timeout` (denis §9) | "Запрос выполнялся слишком долго. Попробуйте сузить условия." |
| `empty_result` | upstream → downstream | downstream → backend → site | `EMPTY_RESULT` (executable=true, rows=[]) (denis §9) | "По вашему запросу данных не найдено." (peter §8 — empty table view, no chart) |
| `row_limit_exceeded` | upstream | backend → site | новый код; нужен row-limit на executor'е (denis §9, §13) | "Слишком много строк. Покажу первые N." (плюс `truncated=true`) |
| `metadata_incomplete` | upstream | downstream | новый код; payload построен, но `field_metadata[]` частично unknown (denis §9) | (внутренний; downstream деградирует к conservative defaults) (peter §8) |
| `visualization_failed` | downstream (Peter) | backend → site | n/a | "Не удалось построить визуализацию." (peter §4 `error`) |
| `render_failed` | downstream | backend → site | n/a | "График не отрендерился. Покажу JSON-спецификацию." (peter §6, status=`partial_success`) |

Mapping `error_taxonomy_v2.py` → unified enum (denis §9): `OP_NO_SUCH_TABLE`/`OP_NO_SUCH_COLUMN`/`OP_AMBIGUOUS_COL`/`OP_SYNTAX`/`RUNTIME_TYPE` → `sql_execution_failed`; `RUNTIME_TIMEOUT` → `timeout`; `PIPELINE_EXCEPTION`/`NO_EVAL_ENGINE` → `sql_generation_failed`. Adapter §5 содержит `ERROR_CODE_MAP`.

---

## 7. API микросервисов

### 7.1 Общий backend (`/api/...`)

| Endpoint | Method | Sync/Async | Timeout | Retry | Request body | Response body |
|---|---|---|---|---|---|---|
| `/api/nl2chart` | POST | sync для fast-mode (peter §9), async-job для quality-mode | sync 5–10s, async unlimited | retry 1× на upstream `timeout`/`sql_execution_failed` | `{request_id?, user_query, data_source: {id, dialect}, locale, timezone, mode: "fast"|"quality"}` | `{request_id, status, selected_view, candidates, table_view, explanation, quality, performance, errors}` (peter §6 shape) |
| `/api/nl2chart/{request_id}` | GET | sync (статус async job) | 2s | none | path: `request_id` | то же body, что и `/api/nl2chart`, либо `{status: "running"}` |
| `/api/artifacts/{artifact_id}` | GET | sync, stream | 10s | none | path: `artifact_id` | binary PNG/SVG/HTML (peter §9) |

### 7.2 Text-to-SQL service (Denis)

| Endpoint | Method | Sync/Async | Timeout | Retry | Request body | Response body |
|---|---|---|---|---|---|---|
| `/extract` | POST | sync | 8000ms (denis §9 хардкод) + buffer ~2s | client-side 1× (для transient `OperationalError`); внутренний repair-loop B4 (`allow_llm_repair` flag, denis §6) | `DataExtractionRequest` (denis §6: `request_id, user_query, locale, timezone, user_context, data_source: {id, dialect, connection_ref, schema_version}, constraints: {read_only, timeout_ms, row_limit, max_joins, allow_llm_repair}, presentation_hint`) | `DataExtractionResponse` (denis §7: `request_id, status, user_query, data_source, plan, sql, result_table, field_metadata, execution, quality, errors`) |
| `/health` | GET | sync | 1s | none | — | `{status: "ok"}` |
| `/ready` | GET | sync | 3s | none | — | `{ready: bool, model_loaded: bool, schema_loaded: bool}` |

### 7.3 Visualization service (Peter)

| Endpoint | Method | Sync/Async | Timeout | Retry | Request body | Response body |
|---|---|---|---|---|---|---|
| `/visualize` | POST | sync для fast (B0/B1/B2 — `~0.4–7ms` на experiment, peter §9, §10); async для quality (B3 ~20s, B4 ~67s, B5 ~6–69s, peter §9, §10) | sync 5s; async timeout зависит от mode | client-side 1× на `render_failed`; renderer fallback PNG→SVG→spec-only | `VisualizationRequest` (peter §5) | `VisualizationResponse` (peter §6) |
| `/visualize/{request_id}` | GET | sync (job status) | 2s | none | path: `request_id` | `VisualizationResponse` либо `{status: "running"}` (peter §9) |
| `/health` | GET | sync | 1s | none | — | `{status: "ok"}` |
| `/ready` | GET | sync | 3s | none | — | `{ready: bool, model_loaded: bool, renderer_ready: bool, artifact_storage_ready: bool}` (peter §9) |

Все эндпоинты — JSON (`Content-Type: application/json`), кроме `/api/artifacts/{...}` (binary). `request_id` пробрасывается во все слои для трассировки.

---

## 8. Интеграционные тесты

Пять end-to-end тестов поверх сквозного пайплайна `POST /api/nl2chart`. Источники сценариев: denis §11.1–11.3, peter §11.1–11.3, peter §8.

### Test 1 — Time series → line chart

| Часть | Значение |
|---|---|
| Input `user_query` | `"Покажи количество концертов по годам"` (или эквивалент peter §11.1: `"Покажи динамику выручки по месяцам линейным графиком"`) |
| Ожидаемые поля upstream response | `result_table.columns=["year","n_concerts"]`, `field_metadata=[{name:"year",data_type:"number",semantic_role:"time",periodicity:"year"},{name:"n_concerts",data_type:"number",semantic_role:"measure",default_aggregation:"sum",provenance.derived=true}]`, `query_context.aggregations=[{function:"COUNT",alias:"n_concerts"}]`, `query_context.group_by=["year"]`, `status=success` (denis §11.1) |
| Ожидаемые поля downstream response | `selected_view.type="chart"`, `selected_view.chart_type="line"`, encoding `x={field:"year",type:"temporal"}`, `y={field:"n_concerts",type:"quantitative"}`, `explanation.intent="trend"`, `quality.validation_passed=true`, `rendered_artifacts.png_uri≠null` (peter §11.1) |
| Критерий успешности | `chart_type="line"`, validation passed, png_uri !=null, no `double aggregation` warning (peter §12) |

### Test 2 — Category comparison → bar chart

| Часть | Значение |
|---|---|
| Input `user_query` | `"Сравни продажи по категориям товаров"` (peter §11.2) или `"Total stadium capacity by country"` (denis §11.2) |
| Ожидаемые поля upstream response | `result_table.columns=["category","sales_sum"]` (или `["country","total_capacity"]`), `field_metadata` с `category.semantic_role="dimension"` + `sales_sum.semantic_role="measure"` + `provenance.aggregation="sum"`, `query_context.group_by=["category"]`, `query_context.aggregations=[{field:"order_amount",function:"sum",alias:"sales_sum"}]` (denis §11.2, peter §11.2) |
| Ожидаемые поля downstream response | `selected_view.chart_type="bar"`, encoding `x={field:"category",type:"nominal",sort:"-y"}`, `y={field:"sales_sum",type:"quantitative"}`, `explanation.intent="comparison"`, `validation_passed=true` (peter §11.2) |
| Критерий успешности | bar chart выбран, dimension по X, measure по Y, нет double-aggregation, `cardinality(category) <= 50` обеспечивает читаемость (peter §8) |

### Test 3 — Top-N query → table/bar chart

| Часть | Значение |
|---|---|
| Input `user_query` | `"Покажи топ-5 клиентов по выручке таблицей"` (peter §11.3) или `"Show name, country, age for all singers ordered by age from the oldest to the youngest"` (denis §11.3) |
| Ожидаемые поля upstream response | `result_table.row_count<=5` (или sorted full), `query_context.order_by=[{field:"revenue",dir:"desc"}]`, `query_context.limit=5`, `field_metadata` с `client_name.semantic_role="dimension"`/`region.dimension`/`revenue.measure` (peter §11.3, denis §11.3) |
| Ожидаемые поля downstream response | `selected_view.type="table"` если `presentation_preferences.preferred_output="table"`, `table_view.columns/rows/order_by/limit` заполнены; ИЛИ alt candidate `chart_type="bar"` со score >= 0.7; `explanation.intent="table"|"top"` (peter §11.3) |
| Критерий успешности | preferred_output respected; если table — table_view заполнен; sort преимущественно по measure desc; `limit=5` пробрасывается |

### Test 4 — Empty SQL result → safe user-facing error / empty table

| Часть | Значение |
|---|---|
| Input `user_query` | NL запрос с фильтром, который заведомо даёт 0 строк (e.g. `"Концерты в 1900 году"`) |
| Ожидаемые поля upstream response | `result_table.rows=[]`, `result_table.row_count=0`, `status="success"` либо `partial_success`, `errors=[{code:"empty_result", recoverable:true}]` (denis §9) |
| Ожидаемые поля downstream response | `selected_view.type="table"` пустая, либо `status="partial_success"` с `selected_view=null`; `explanation.reason` содержит "по запросу данных не найдено"; `quality.warnings=["empty_result_table"]` (peter §8) |
| Критерий успешности | НЕТ chart'а с пустыми данными (peter §8 `single_row_result`/`empty_result`); пользователю показано человекочитаемое сообщение, не stack trace |

### Test 5 — Metadata incomplete → fallback chart with warning

| Часть | Значение |
|---|---|
| Input `user_query` | NL запрос на источник без metric dictionary / без description'ов (Spider DB) |
| Ожидаемые поля upstream response | `result_table.{columns,rows,row_count}` заполнены, `field_metadata[*].{description,unit,allowed_aggregations}=null`, `errors=[{code:"metadata_incomplete", recoverable:true}]`, `quality.warnings=["metadata_incomplete"]` (denis §9) |
| Ожидаемые поля downstream response | `status="partial_success"` либо `success`, `selected_view.chart_type` chosen via inference (peter §8 fallback), `quality.warnings ⊇ ["aggregation_defaults_used","missing_unit","role_inferred"]`, `validation_passed=true`, `selected_view.spec` валиден Vega-Lite (peter §8) |
| Критерий успешности | downstream НЕ ломается; chart строится conservative defaults (measure→sum, dim→count); сайт получает explicit warnings, чтобы показать badge "low confidence" |

---

## 9. План доработок

### Этап 1 — MVP-интеграция

Минимальное число изменений, чтобы запустить пайплайн end-to-end на одном source-of-truth (Spider/SQLite).

| # | Задача | Owner |
|---|---|---|
| 1.1 | Ввести `request_id` (UUID) и пробросить через все слои F1…F13 + payload | Denis |
| 1.2 | Расширить `AnalyticsPayload v1` → v2: добавить `result_table.{columns explicit}`, `data_source.dialect`, `field_metadata[].{name,data_type,semantic_role}` (3 обязательных), `errors[].{code,message}` | Denis |
| 1.3 | Mapping `summary.dtype` + `PRAGMA table_info` → `data_type ∈ {number,string,date,datetime,boolean,unknown}` (denis §8) | Denis |
| 1.4 | Rule-based `semantic_role` inference (denis §8) | Denis |
| 1.5 | Обернуть upstream Python-функции в FastAPI `POST /extract` + `/health` + `/ready` | Denis |
| 1.6 | Adapter layer `normalize_extraction_response` (см. §5) — explicit columns, errors mapping, default presentation_preferences | shared |
| 1.7 | Visualization service: обернуть существующие B0/B1/B2 predictors в `POST /visualize` (sync, fast-mode); маппер `T2VPrediction → VisualizationResponse` (peter §6 mapping table) | Peter |
| 1.8 | Backend: `POST /api/nl2chart` — sync orchestration upstream→adapter→downstream | shared |
| 1.9 | Контракт-тесты на 5 e2e сценариев из §8 (минимум — Test 1, Test 2, Test 4) | shared |

Готовность: пайплайн выдаёт chart на time-series + category-comparison + emp ty-result сценариях.

### Этап 2 — Повышение качества

Расширенный контракт + валидаторы + fallback.

| # | Задача | Owner |
|---|---|---|
| 2.1 | Пробросить `plan_parsed` (B2+) в payload как `query_context.{plan, filters, group_by, aggregations, order_by, limit}`; написать unifying mapper plan v1↔v5 (denis §13) | Denis |
| 2.2 | `field_metadata.{periodicity, allowed_aggregations, default_aggregation, cardinality, value_examples}` — derive из плана + summary (denis §5, §8) | Denis |
| 2.3 | `field_metadata.provenance.{expression, aggregation, derived}` через sql_compiler_v2 + plan_v5 measures[] (denis §8) | Denis |
| 2.4 | Row-limit на executor + `result_table.truncated` flag + `row_limit_exceeded` error code (denis §9, §13) | Denis |
| 2.5 | `execution.latency_ms` per-item timing (denis §13) | Denis |
| 2.6 | `quality.confidence` — пробросить `query_analysis.confidence` + `plan_v5.confidence` в payload | Denis |
| 2.7 | sqlglot AST guard как primary (regex как secondary) — закрыть нестандартный DDL bypass (denis §13) | Denis |
| 2.8 | Downstream fallback policy (peter §8): `chart_request_fell_back_to_table`, `wide_table_pruned`, `large_table_previewed`, `single_row_result`, `null_values_present`, `aggregation_defaults_used` | Peter |
| 2.9 | Hard validation: `allowed_aggregations`, `grain`, `provenance` → block double aggregation (peter §12) | Peter |
| 2.10 | Strict schema validation на VisualizationRequest (Pydantic enums; reject malformed) | Peter |
| 2.11 | Контракт-тесты на 5 e2e сценариев из §8 полностью (Test 3, Test 5 включая metadata-incomplete fallback) | shared |
| 2.12 | Versioning контракта: semver на DataExtractionRequest/Response и VisualizationRequest/Response; deprecation policy (denis §13) | shared |

### Этап 3 — Микросервис и сайт

Production-like внедрение.

| # | Задача | Owner |
|---|---|---|
| 3.1 | Quality-mode async pipeline для B3/B4/B5 с GPU, model registry (peter §9, §10) | Peter |
| 3.2 | Artifact storage (S3/MinIO/static) + signed URLs + TTL (peter §9, §12) | Peter |
| 3.3 | `/api/nl2chart/{request_id}` polling + `/api/artifacts/{artifact_id}` (peter §9) | shared |
| 3.4 | SVG/HTML rendering поверх PNG (peter §4, §9) | Peter |
| 3.5 | `csv_uri`/`arrow_uri` для больших таблиц (peter §9) + upload step в upstream | shared |
| 3.6 | Metric dictionary / information_schema reader для `description/unit/metric_definition/allowed_aggregations` (denis §8, peter §7.4) | shared |
| 3.7 | Восстановить Spider2-Lite (BQ/Snowflake creds) для multi-dialect claim (denis §13) | Denis |
| 3.8 | LLM dependency lockfile (peter §12 `LLM dependency drift`): зафиксировать `torch/transformers/bitsandbytes` в requirements / отдельный image | Peter |
| 3.9 | i18n: ru/en titles, locale-aware formatting (denis §13, peter §13.15) | shared |
| 3.10 | Privacy/redaction policy для PNG/spec/logs (peter §12) | shared |
| 3.11 | Observability: trace `request_id` E2E, latency SLO, error-rate dashboard | shared |
| 3.12 | Load/regression тесты: latency budget (sync 5s), Vega-Lite render success rate, double-aggregation rate=0 | shared |

---

## 10. Главный вывод

Денис обязательно должен выгружать: `request_id`, `user_query`, `data_source.{id,dialect}`, `result_table.{columns explicit, rows, row_count, truncated}` и `field_metadata[]` хотя бы с тремя полями `{name, data_type, semantic_role}`. Без этих пяти блоков downstream не выберет тип графика и не подпишет оси (denis §14, peter §13). Расширенно — `periodicity`, `allowed_aggregations`, `default_aggregation`, `cardinality`, `provenance` — без них качество визуализаций сильно деградирует (peter §7.2–7.3, §12).

Пётр обязательно должен принимать `VisualizationRequest` с готовой таблицей и metadata и НЕ должен оценивать SQL или генерировать его (peter §13.4); SQL — только provenance/debug. Downstream обязан корректно деградировать при `metadata_incomplete` (conservative defaults + warnings, peter §8) и не строить misleading chart на пустых/single-row результатах.

Adapter-слой нужен между upstream и downstream на стороне общего backend'а: SQL types → visualization data types, semantic role inference (правила denis §8), v1↔v5 plan mapping, error taxonomy → unified enum, table truncation, null handling, default presentation preferences. Без adapter'а каждый сервис будет тянуть legacy-форматы соседа.

Формат обмена: JSON по HTTP, sync для fast (B0/B1/B2 ~ms; CPU), async для quality (B3/B4/B5 — секунды-десятки секунд, peter §9, §10); большие таблицы — `csv_uri`/`arrow_uri`, не inline rows. Артефакты PNG/SVG/HTML — через signed URLs из artifact storage. `request_id` — UUID, корреляция через все слои.

Самые критичные риски: (1) **double aggregation** — upstream уже агрегировал, downstream агрегирует повторно (нужны `provenance.derived` + `query_context.aggregations`, peter §12); (2) **отсутствие row-limit** на executor'е → OOM + раздутый payload (denis §13); (3) **plan v1 vs v5 формат** — два параллельных формата, сломают mapper при смешивании (denis §13); (4) **prompt injection** через schema descriptions / docs если адаптируется information_schema без sanitization (denis §13); (5) **LLM dependency drift** в downstream'е — `torch/transformers/bitsandbytes` не зафиксированы (peter §12); (6) **отсутствие versioning** контракта — breaking changes сломают второй модуль (denis §13).
