# 3.2.4 Pack Builder v18 — компактный schema pack для closed-set planning

## Главный тезис

Pack Builder — **второй после schema linker** компонент, определяющий качество downstream planning. Его задача — взять top-K hits от schema linker и собрать из них **compact JSON-friendly schema fragment**, который:

1. **Помещается в prompt budget** планировщика (~32K tokens context, цель ~10-15K tokens для schema-блока, оставляя место для question + external knowledge + rules + JSON instructions),
2. **Содержит ровно то, что планнеру нужно** для построения plan-JSON: имена таблиц / колонок / типы / описания,
3. **Изолирует validator** от prompt: AST validator проверяет identifier residency против `pack.all_columns` — side-channel field, не показанный планировщику, но содержащий полный список column-имён каждой таблицы из catalog.

Pack — это **контракт между retrieval и planner**. Всё, что в pack — fair game для plan-JSON; всё что не в pack — должно быть rejected на AST-валидатор stage.

Файл реализации: `repo/src/evaluation/schema_pack_builder_v18.py` (~310 lines, last touched Phase 27 для F1 catalog filter + three-part rendering + Phase 28 prompt rule update).

## Структура pack-а

```json
{
  "lane": "snow" | "lite_snow" | "bq",
  "alias": "PATENTS",  // task.db для Snow lanes
  "databases": [
    {"name": "PATENTS", "schemas": ["PATENTS"], "score": 12.3}
  ],
  "tables": [
    {
      "db": "PATENTS",
      "schema": "PATENTS",
      "table": "PUBLICATIONS",
      "score": 18.4,
      "columns": [
        {"name": "family_id", "type": "TEXT", "nullable": "YES", "description": null},
        {"name": "publication_number", "type": "TEXT", "nullable": "YES", "description": null},
        // ... up to max_cols_per_table
      ],
      "all_columns": ["family_id", "publication_number", "application_number", ...]  // side-channel
    }
    // ... up to max_tables
  ],
  "wildcards": [
    {"fqn": "BQ.events_*", "base": "events", "sample_shard": "events_20231215", "note": "..."}
  ],
  "join_hints": [
    {"left_table": "PUBLICATIONS", "right_table": "DISCLOSURES_13",
     "on": "family_id", "reason": "shared_column_name_with_key_shape"}
  ],
  "token_budget_used": 4500
}
```

## Параметры по lanes

```python
# Spider1 / BIRD / Spider2-Lite-BQ defaults (Phase 17-26):
build_pack(linker_out, lane='bq', alias=None,
            max_tables=8, max_cols_per_table=22, max_desc_chars=120,
            all_catalog_cols=None)

# Spider2-Snow / Lite-Snow (Phase 27+):
build_pack(linker_out, lane='snow', alias=task_db,
            max_tables=10, max_cols_per_table=22, max_desc_chars=120,
            all_catalog_cols=cat_subset)  # required for all_columns side-channel
```

Параметр `all_catalog_cols` (Phase 22 STAGE A2 addition) — full list `CatalogColumn` per task — позволяет builder-у заполнить `all_columns` field каждой выбранной table-а полным списком колонок этой таблицы из catalog (не только top-K из BM25 hits). Это recipe для AST validator: «id columns из BM25 могут быть малочисленны, но мы знаем что full table содержит вот эти 35 колонок — validator проверяет residency против полного списка».

## Логика построения

### Step 1: F1 catalog filter (Phase 27, Snow only)

```python
_snow_lane_active = (lane in ('snow', 'lite_snow') and alias)
_task_db_upper = (alias or '').upper() if _snow_lane_active else None
# Drop hits from foreign catalogs
for h in linker_out.hits:
    c = h.record
    if _snow_lane_active and c.db.upper() != _task_db_upper:
        continue
    grouped[(c.db, c.schema, c.table)].append(h)
```

«Defense in depth»: даже если schema linker leak-нул hits из competitor DB, pack builder их отбрасывает. Это создаёт **second line of defense** после schema linker per-task partition.

### Step 2: Группировка hits по `(db, schema, table)` и top-N selection

Table-level score = сумма BM25 score-ов её column hits. Top-`max_tables` таблиц (по убыванию score) попадают в pack.

### Step 3: Column selection per table

В каждой выбранной таблице — top-`max_cols_per_table` column hits (по BM25 score). Это даёт **dense pack**: мало таблиц, но богатый column-list на каждую.

### Step 4: PK/FK heuristic injection (Phase 27 correction 3)

Делается отдельно в `_inject_pk_fk` (в runner-е, не в builder-е). См. [03_schema_linker_v18_bm25.md](./03_schema_linker_v18_bm25.md) для деталей.

### Step 5: `all_columns` side-channel (Phase 22 A2)

Для каждой выбранной таблицы — полный список column-имён из catalog, индексированный по `(db, schema, table)`. Используется AST validator-ом (residency check) для прохода SQL, ссылающегося на колонки которые BM25 не surface-ил но катало них точно содержит.

### Step 6: Wildcards (Phase 18)

Detect date-shard families типа `events_YYYYMMDD`, `ga_sessions_YYYYMMDD` в имеющихся table-ах. Регулярка: `r'^(?P<base>.+?)_(?P<date>\d{6,8})$'`. Surface wildcard-form base в pack — planner может выбрать `events_*` вместо отдельных date-таблиц, и downstream рендеринг подставляет `_TABLE_SUFFIX BETWEEN` (BQ-specific).

### Step 7: Join hints (Phase 22 A2)

Heuristic JOIN-key inference между выбранными таблицами:

```python
# (a) Shared column names where the column "looks like" a key
shared = cols_A & cols_B
for col in shared:
    is_key = endswith('_id') or endswith('_key') or endswith('id') and len <= 12
    if is_key: join_hints.append((A, B, col, 'shared_column_name_with_key_shape'))

# (b) FK-like naming: table A has `id`, table B has `<a_singular>_id`
for table_A:
    if 'id' in cols_A:
        for table_B != A:
            for col_B in cols_B:
                if col_B == f'{A_singular}_id' or col_B == f'{A_lower}id':
                    join_hints.append((A, B, 'id=col_B', 'fk_like_naming'))
```

Cap at 10 hints. Семантически близко к **CHESS** [Talaei et al., 2405.16755] (PK/FK injection) и **SchemaGraphSQL** [arXiv 2505.18363] (FK BFS), но без real FK metadata — pure naming heuristic.

### Step 8: Token budget compute

```python
pack['token_budget_used'] = len(json.dumps(pack)) // 4   # rough chars→tokens
```

Используется только для metrics / diagnostic — не для cutting pack.

## Prompt rendering (Phase 27 + 28 dialect rules)

Pack rendered в planner prompt через `pack_to_planner_prompt(pack, question, external_knowledge='')`. Key changes Phase 27/28:

### Three-part name rendering (Phase 27 F1, Snow)

```python
_task_db = (pack.get('alias') or '').upper() if _snow_lane else None

for t in pack['tables']:
    db_render = (_task_db if _snow_lane and _task_db else t["db"])
    lines.append(f'  - `{db_render}.{t["schema"]}.{t["table"]}` columns=[{cols}]')
```

Forces task_db as catalog prefix — planner видит three-part names с правильным первым сегментом.

### Snow dialect rules block (Phase 27 + 28, после revert)

```
Snowflake SQL rules:
- ALWAYS use three-part identifiers: DATABASE.SCHEMA.TABLE.
- Available database for this query: PATENTS.
- Do NOT reference any other database. Tables from other databases will be rejected at validation.
- Quote mixed-case identifiers: "ParticipantBarcode".
- Use LATERAL FLATTEN(INPUT => col) for array unnest, NOT UNNEST.
- Use IFF(c,a,b) or CASE WHEN. Use QUALIFY for window-row filtering.
- JSON path: payload:user.name::STRING (colon, not arrow).
```

Phase 28 originally добавил «UPPERCASE columns are unquoted» — это было **regression seed** (см. [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md)). После revert эта строка удалена; current rules — v27c-equivalent с дополнительным F4 date-cast блоком.

### col:TYPE rendering (Phase 28, kept after revert-A)

```python
col_strs = []
for c in t.get('columns', [])[:22]:
    nm = c.get('name', '')
    ty = (c.get('type') or '').split('(')[0]   # strip NUMBER(38,0) -> NUMBER
    col_strs.append(f'{nm}:{ty}' if ty else nm)
cols = ', '.join(col_strs)
```

Per-column type annotation `col:TYPE` инлайн в schema block. Это даёт планировщику immediate signal что `publication_date:NUMBER` — это NUMBER, не DATE → требует cast. F4 date-cast rule в prompt block ссылается на этот rendering: "Column types are shown as col:TYPE after each name in the schema below."

### F4 date-cast rule (Phase 28, kept)

```
- Date arithmetic on non-DATE columns requires explicit cast:
  NUMBER (e.g. YYYYMMDD int) -> TO_DATE(TO_VARCHAR(col), 'YYYYMMDD')
  VARIANT -> col::DATE; JSON path: col:field::DATE
  Column types are shown as col:TYPE after each name in the schema below.
```

Это **soft hint** планировщику — если он успешно применит cast самостоятельно, post-processor (snow_dialect_fixer F4) не должен оборачивать column снова (catch via "already wrapped" check). Empirically, Coder-7B emitter не всегда следует rule — post-processor — safety net.

## Token budget calculation

Typical Spider2-Snow pack size на pilot10:

| Component | Approx tokens |
|---|---|
| Schema block (10 tables × 22 cols, with col:TYPE) | ~3500-4500 |
| Wildcards | ~50-200 |
| Join hints (up to 10) | ~300-500 |
| External knowledge (если есть) | 0-2000 |
| Snow rules block | ~250 |
| Question text | ~50-200 |
| Planner JSON instructions | ~400 |
| **Total prompt** | **~5000-8000 tokens** |

Это с запасом помещается в Qwen3-Coder-30B-A3B 32K context. На Spider2-Lite-BQ — может быть выше (max_tables=8 — но GA360-class схемы имеют wide tables ~50-80 cols each, описания значительнее).

## Сравнение pack-структуры с альтернативами

| Подход | Что в pack | Размер | Where used |
|---|---|---|---|
| **Наш pack v18** | Top-K tables + top-M cols + side-channel all_columns + join_hints + wildcards | ~5-8K tokens | этот проект |
| **CHESS Schema Description Generation** | Full table DDL + PK/FK + heuristic injection | larger (~10-20K tokens) | CHESS [arXiv 2405.16755] |
| **DAIL-SQL packaged schema** | Concatenated DDL + sample rows | Largest (~20K+ tokens) | DAIL-SQL [Gao et al., VLDB 2024] |
| **ReFoRCE Column Exploration** | Iterative `INFORMATION_SCHEMA` probing (no upfront pack) | dynamic | ReFoRCE [arXiv 2502.00675] |
| **Spider-Agent (filesystem)** | No pack — agent reads files on demand | dynamic, multi-turn | Spider-Agent baseline |
| **LinkAlign / AutoLink** | Multi-round retrieval + expansion (no upfront pack budget) | dynamic | [arXiv 2503.18596, 2511.17190] |

Наш подход — **upfront static pack** — proxies the simplicity / verification trade-off: static pack делает validator-feedback retry semantics простыми (если идентификатор не в pack — переплан с feedback), но **не может recover из situations where the right table isn't initially ranked**. Это «hallucinated table» failure mode (Phase 28 §10, sf_bq209).

Phase 30 F2 (planned, out of scope) — выйти за upfront pack через JOIN-graph BFS expansion: после initial pack, BFS по FK-edges чтобы добавить tables reachable from initial seeds. Это компромис между LinkAlign iterative и наш static.

## Известные limitations

### L1. Hard cap на column-set
22 columns × 10 tables = 220 columns в final pack. Большие schemas (GA360 — single table с 200+ struct'ed columns) могут not fit полностью. Coder-7B emitter sometimes hallucinates nested column path основываясь на name pattern.

### L2. No descriptions for Snow
Snow `COMMENT` field on INFORMATION_SCHEMA.COLUMNS rarely populated (~5% rows have descriptions, 95% null). Mostly relying на column name semantics. BQ catalogs significantly richer (descriptions on ~40% rows, особенно `bigquery-public-data` corpus).

### L3. Wildcard detection — only for date-shard patterns
Regex `_\d{6,8}$` catches `events_20220715`, `ga_sessions_20170201`. Doesn't catch other shard patterns (`_uk_2022`, `_v2`). Spider2-Snow rarely uses sharded tables (datasets curated normally) — limit not painful in practice.

### L4. Join hints — pure naming heuristic
No real FK metadata used. Generates false-positive hints (random columns with shared name like `created_at`). Family C factory имеет filter — picks only hints that fit planner's selected_tables. False positives don't bleed into Family A/B output.

### L5. Description truncation
`_short(s, max_desc_chars=120)` обрезает описания до 120 chars с trailing `…`. Long descriptions sometimes contain critical disambiguating info beyond char 120 (e.g., "Identifier of customer in the legacy system; do NOT use for current-system customer linkage" — second clause critical).

## Cross-references

- Implementation в [08_CUSTOM_TOOLS/01_schema_pack_builder_v18.md](../08_CUSTOM_TOOLS/01_schema_pack_builder_v18.md)
- AST validator (consumer всех pack fields включая `all_columns`): [07_validators_json_ast_engine.md](./07_validators_json_ast_engine.md)
- Phase 22 A2 (when `all_columns` появился): [06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md)
- Phase 27 F1 changes к prompt rendering: [06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md](../06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md)
- Phase 28 col:TYPE + revert-A: [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md)
- Schema linker (provides hits to builder): [03_schema_linker_v18_bm25.md](./03_schema_linker_v18_bm25.md)
- Dialect handlers F1+F4: [09_dialect_handlers_f1_f4.md](./09_dialect_handlers_f1_f4.md)

## Источники

| Утверждение | Источник |
|---|---|
| Pack structure JSON shape | `repo/src/evaluation/schema_pack_builder_v18.py` lines 30-31, 228-237 |
| F1 catalog filter (Phase 27) | `repo/src/evaluation/schema_pack_builder_v18.py` lines 86-106 |
| `all_columns` side-channel (Phase 22 A2) | `repo/src/evaluation/schema_pack_builder_v18.py` lines 99-136 |
| Wildcard regex (Phase 18) | `repo/src/evaluation/schema_pack_builder_v18.py` lines 152-169 |
| Join hints heuristic | `repo/src/evaluation/schema_pack_builder_v18.py` lines 172-225 |
| col:TYPE rendering (Phase 28) | `tools/remote_scripts/_phase27_snow_runner.py` lines 233-238 |
| F4 date-cast rule в prompt | `tools/remote_scripts/_phase27_snow_runner.py` lines 253-256 |
| Phase 28 revert "UPPERCASE columns are unquoted" | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §10 |
