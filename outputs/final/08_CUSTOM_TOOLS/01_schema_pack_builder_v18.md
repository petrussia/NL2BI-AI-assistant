# 08.01 — schema_pack_builder_v18.py

## Покрытие модуля

`repo/src/evaluation/schema_pack_builder_v18.py` (~310 LOC) — превращает output schema linker-а в **compact JSON-friendly schema fragment**, передаваемый planner-у. Главные экспорты:

| Symbol | Purpose |
|---|---|
| `PackTable` / `PackColumn` | dataclasses representing pack rows |
| `build_pack(linker_out, *, lane, alias, max_tables, max_cols_per_table, all_catalog_cols)` | главный entry point |
| `pack_to_planner_prompt(pack, question, external_knowledge)` | renders pack в structured prompt для planner-а |

Inputs: `LinkerOutput` (от schema_linker), плюс параметры budget (max_tables, max_cols_per_table), lane name (для F1 catalog filter), alias (Spider2 task.db hint), и full catalog (для `all_columns` side-channel).

Outputs: pack dict + render string. Pack dict содержит fields `lane`, `alias`, `databases`, `tables[]` (с `columns[]` + `all_columns`), `wildcards`, `join_hints`, `token_budget_used`. См. schema в [04_ARCHITECTURE/04_pack_builder_v18.md](../04_ARCHITECTURE/04_pack_builder_v18.md).

Hooked в pipeline: runner calls `build_pack(...)` после `linker.query(...)`. Result передан `pack_to_planner_prompt(pack, Q, K)` для planner prompt; AST validator consumes `pack['tables'][*]['all_columns']` для residency check.

## Code walkthrough

### Excerpt 1 — F1 Snow catalog filter (lines 86-107)

```python
# Phase 27 STAGE F1: hard TABLE_CATALOG partitioning for Snow lanes.
# The Spider2-Snow / Lite-Snow catalog rows have `c.alias = ""`, so the
# alias_filter in the linker is a no-op and BM25 leaks hits across the
# entire 587K-column catalog. Defense-in-depth: also enforce here that
# the per-task pack only sees rows whose c.db (TABLE_CATALOG) matches
# the task's db_id. Gated on lane so BQ/SQLite paths are untouched.
_snow_lane_active = (lane in ('snow', 'lite_snow') and alias)
_task_db_upper = (alias or '').upper() if _snow_lane_active else None

# Group hits by (db, schema, table). Use the highest-scoring table set.
grouped: dict = defaultdict(list)
for h in linker_out.hits:
    c = h.record
    # F1 filter: drop hits from other catalogs for Snow lanes
    if _snow_lane_active and c.db.upper() != _task_db_upper:
        continue
    key = (c.db, c.schema, c.table)
    grouped[key].append(h)
```

**Почему критично**: это **defense-in-depth**. Даже если schema linker per-task partition (Phase 27 fix at runner level) leak-нул какие-то foreign-catalog hits (race condition, bug), pack builder отбрасывает их before they make it в planner prompt. Это **второй layer** Phase 27 F1.

`_snow_lane_active` flag — explicit gating. BQ and SQLite paths untouched. Принцип: lane-specific logic должен быть **gated explicitly**, не conditional через absence of values.

### Excerpt 2 — `all_columns` side-channel (lines 99-138)

```python
# v22 STAGE A2: index full catalog by (db, schema, table) for residency
full_table_cols: dict = defaultdict(set)
if all_catalog_cols is not None:
    for c in all_catalog_cols:
        # F1 filter on the side-channel too
        if _snow_lane_active and c.db.upper() != _task_db_upper:
            continue
        full_table_cols[(c.db, c.schema, c.table)].add(c.field_path or c.column)

# Score per table = sum of column hit scores
table_scores = sorted(
    [(k, sum(h.score for h in v)) for k, v in grouped.items()],
    key=lambda x: -x[1])[:max_tables]
chosen_tables = [k for k, _ in table_scores]

# Build PackTable per chosen table.
tables: list = []
seen_dbs: dict = defaultdict(set)
for (db, schema, table) in chosen_tables:
    hits = grouped[(db, schema, table)][:max_cols_per_table]
    cols = []
    for h in hits:
        c = h.record
        name = c.field_path or c.column
        cols.append(asdict(PackColumn(
            name=name,
            type=c.data_type,
            nullable=c.is_nullable,
            description=_short(c.description, max_desc_chars),
        )))
    tdict = asdict(PackTable(
        db=db, schema=schema, table=table,
        score=round(sum(h.score for h in hits), 2),
        columns=cols,
    ))
    # v22 STAGE A2: side-channel full column list for the validator
    if all_catalog_cols is not None:
        tdict['all_columns'] = sorted(full_table_cols.get((db, schema, table), set()))
    tables.append(tdict)
    seen_dbs[db].add(schema)
```

**Почему критично**: Phase 22 A2 introduction. Без `all_columns` side-channel, AST validator проверяет SQL identifiers только против `pack.tables[*].columns[*].name` (top-K BM25 hits per table). Это **систематически false-positive rejects** SQL, которые legitimately reference columns в table но не в top-K. Например, `PUBLICATIONS` имеет 37 columns; BM25 surface 22. SQL referencing 23rd column failed schema_invalid pre-Phase-22. After Phase 22: `all_columns` contains all 37 names → SQL passes.

**Subtle design choice**: `all_columns` is `sorted(set())` — deterministic order для test reproducibility. F1 filter also applied to side-channel (line 104) — defensive (without filter, side-channel could "leak" foreign-DB column names into validator allow-set).

### Excerpt 3 — Wildcard detection (lines 152-169)

```python
# v18.1: detect date-shard families and surface them as wildcards.
# Spider2-Lite-BQ has many `ga_sessions_YYYYMMDD`, `events_YYYYMMDD`,
# `bikeshare_trips_YYYYMM` style shards. The pack should advertise
# the wildcard form so the planner can target it as a closed-set
# identifier rather than enumerate dates.
import re as _re
_SHARD = _re.compile(r'^(?P<base>.+?)_(?P<date>\d{6,8})$')
wildcards: list = []
seen_bases: set = set()
for t in tables:
    m = _SHARD.match(t['table'])
    if not m:
        continue
    key = (t['db'], t['schema'], m.group('base'))
    if key in seen_bases:
        continue
    seen_bases.add(key)
    wildcards.append({
        'fqn': f'{t["db"]}.{t["schema"]}.{m.group("base")}_*',
        'base': m.group('base'),
        'sample_shard': t['table'],
        'note': 'wildcard family — use _TABLE_SUFFIX for date filtering',
    })
```

**Почему критично**: Spider2-Lite-BQ includes `bigquery-public-data.google_analytics_sample.ga_sessions_*` family (typically date-sharded). Planner needs **wildcard form** as closed-set identifier — если он эмитит `ga_sessions_20170201` literally, query covers только один day; если он эмитит `ga_sessions_*` plus `_TABLE_SUFFIX BETWEEN`, query covers correct range.

**Design decision** — `r'^(?P<base>.+?)_(?P<date>\d{6,8})$'`: requires trailing 6-8 digit suffix. Matches `events_20220715`, `bikeshare_trips_202301`, but **misses** other shard patterns (`_uk_2022`, `_v2`). On Spider2-Snow rarely uses sharded tables, на BQ — frequent.

### Excerpt 4 — Join hints (lines 172-226)

```python
# v22 STAGE A2: derive join_hints from co-occurring column names + FK-like
# naming conventions across the chosen tables. This is heuristic but
# deterministic and provides Family C with seed join paths.
join_hints: list = []
if all_catalog_cols is not None and len(tables) >= 2:
    # Build full column sets per chosen table
    cols_by_table = {}
    for t in tables:
        key = (t['db'], t['schema'], t['table'])
        cols_by_table[t['table']] = full_table_cols.get(key, set())
    # Pairwise: shared exact-match column names (likely join keys)
    seen_pairs = set()
    table_list = list(cols_by_table.keys())
    for i, ta in enumerate(table_list):
        for tb in table_list[i+1:]:
            shared = cols_by_table[ta] & cols_by_table[tb]
            # Prefer columns that look like keys
            for col in sorted(shared):
                cn = col.split('.')[-1].lower()
                is_key = (cn.endswith('_id') or cn == 'id'
                            or cn.endswith('_key') or cn == 'key'
                            or cn.endswith('id') and len(cn) <= 12)
                if not is_key:
                    continue
                pair = (ta, tb, col)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                join_hints.append({
                    'left_table': ta, 'right_table': tb,
                    'on': col,
                    'reason': 'shared_column_name_with_key_shape',
                })
    # FK-like naming: column `<table>_id` in B referring to `id` in A
    for ta in table_list:
        cols_a = cols_by_table[ta]
        if 'id' not in {c.split('.')[-1].lower() for c in cols_a}:
            continue
        for tb in table_list:
            if tb == ta: continue
            target_fk = ta.lower().rstrip('s') + '_id'
            for col_b in cols_by_table[tb]:
                cb = col_b.split('.')[-1].lower()
                if cb == target_fk or cb == ta.lower() + 'id':
                    id_col = next((c for c in cols_a if c.split('.')[-1].lower() == 'id'), 'id')
                    pair = (ta, tb, f'{id_col}={col_b}')
                    if pair in seen_pairs: continue
                    seen_pairs.add(pair)
                    join_hints.append({
                        'left_table': ta, 'right_table': tb,
                        'on_left': id_col, 'on_right': col_b,
                        'reason': 'fk_like_naming',
                    })
    # Cap to keep prompt small
    join_hints = join_hints[:10]
```

**Почему критично**: Phase 22 A2 — Family C factory uses these hints. Two heuristics:

1. **Shared column with key shape** (lines 184-203): если ta и tb имеют **identical column name** заканчивающийся на `_id`, `_key`, или короткий `id` — это вероятный join key. False-positive risk: `created_at` shared многими tables, но это и не `_id` shape, не попадает.

2. **FK-like naming** (lines 205-224): `<table_singular>_id` pattern. `PUBLICATIONS.id` + `DISCLOSURES.publication_id` → join hint. Это classic FK convention в normalized schemas.

**Cap 10** — для prompt budget. Без cap могло бы быть 50+ pairs для multi-table pack.

### Excerpt 5 — Snow dialect rules block (lines 263-279)

```python
# Phase 27 STAGE F1: hard Snowflake dialect rules + catalog allow-list
if _snow_lane and _task_db:
    lines.append('')
    lines.append('Snowflake SQL rules:')
    lines.append('- ALWAYS use three-part identifiers: DATABASE.SCHEMA.TABLE.')
    lines.append(f'- Available database for this query: {_task_db}.')
    lines.append('- Do NOT reference any other database. Tables from other databases will be rejected at validation.')
    lines.append('- Quote mixed-case identifiers: "ParticipantBarcode".')
    lines.append('- Use LATERAL FLATTEN(INPUT => col) for array unnest, NOT UNNEST.')
    lines.append('- Use IFF(c,a,b) or CASE WHEN. Use QUALIFY for window-row filtering.')
    lines.append('- JSON path: payload:user.name::STRING (colon, not arrow).')
```

**Почему критично**: Phase 27 F1 not just AST-level fix. Это **also prompt-level intervention**. Without explicit rules, Coder-7B / Qwen3-Coder emit BQ-style SQL even for Snow lane (`UNNEST` instead of `LATERAL FLATTEN`, `->` JSON path instead of `:` colon).

**Phase 28 history**: Phase 28 added line «UPPERCASE columns are unquoted» — **regression seed**. Phase 28 closure removed it. Current rules — v27c-equivalent on quoting.

## Design decisions visible in code

### D1. Defensive `or ''` patterns (line 64, 91, etc.)
`_short(c.description, max_desc_chars)`: returns `None` если `s is None`. Не `''` — это explicit choice — description как `null` сигнализирует **отсутствие** vs empty string. Downstream JSON serializer keeps None как `null`, distinguishable.

### D2. `defaultdict(list)` / `defaultdict(set)` patterns
Heavy use throughout. Idiomatic Python для grouping без if-not-in-checks.

### D3. F1 filter gated by `_snow_lane_active` (line 86)
Triple condition: lane is Snow-family AND alias is set. If alias missing, filter doesn't activate (safer default — don't drop rows when we don't know task_db).

### D4. `token_budget_used = len(json.dumps(pack)) // 4`
Rough chars→tokens estimate (line 236). Not exact (BPE tokenization is more efficient), но close enough для monitoring. Used only diagnostically.

### D5. Three-part rendering forced (Phase 27 F1)
```python
db_render = (_task_db if _snow_lane and _task_db else t["db"])
lines.append(f'  - `{db_render}.{t["schema"]}.{t["table"]}` columns=[{cols}]')
```
Override `t['db']` with `_task_db`. This is **important**: даже если в pack table row remained с `t['db'] = 'WRONG_DB'` (например, F1 filter не сработал), rendering forces correct catalog name. Triple defense.

## Edge cases handled

- **No `all_catalog_cols`**: `all_columns` side-channel skipped, validator uses only top-K BM25 hits per table. Backwards-compatible с Phase 17-21 runs.
- **Single-table pack**: join_hints loop guarded `len(tables) >= 2`. Empty hints list returned.
- **Snowflake `alias` empty**: F1 filter handles — line 86 condition `(lane in ('snow', 'lite_snow') and alias)`. If alias empty (which is what BQ Spider2 has) — Snow filter NOT activated, behavior matches BQ.
- **Table without columns in BM25 hits**: doesn't make it into `grouped` since no hits, не появляется в `chosen_tables`.

## Test coverage

**Sanity test exists in tools/remote_scripts/**: `tools/remote_scripts/_phase27_sanity_pack_build.py`. Verifies:
- `db_filter=PATENTS` → pack with `unique_dbs == {'PATENTS'}`.
- No `db_filter` + Phase 27 builder F1 filter → still `pack['tables']` clean.

```python
pack2 = sb.build_pack(link2, lane='snow', alias='PATENTS',
                       max_tables=8, max_cols_per_table=22, all_catalog_cols=catalog)
unique_dbs2 = {t['db'] for t in pack2['tables']}
assert unique_dbs2.issubset({'PATENTS'}), f'F1 DEFENSE FAILED'
```

Это **integration-level** test (запускает real catalog through real linker through real builder), не unit. Unit tests для builder isolated **отсутствуют** — technical debt.

## Known limitations

| # | Limitation | Impact | Mitigation |
|---|---|---|---|
| L1 | Hard cap 220 columns final | Wide tables (GA360 with 200+ struct columns) не fit полностью | Manual hints in question typically narrow scope |
| L2 | Description truncation char-128 | Long descriptions lose detail | Acceptable trade-off; rarely affects task success |
| L3 | Wildcard regex misses non-date patterns | `_uk_2022` style shards не detected | Rare on Spider2 family |
| L4 | Join hints — pure naming heuristic | False-positive hints (random `created_at` shared) | Family C filters at use-site |
| L5 | No unit tests | Refactoring risk | Sanity test covers integration |

## Evolution history

| Phase | Change |
|---|---|
| **v18 (Phase 18)** | Initial implementation. `build_pack`, `pack_to_planner_prompt`. Wildcards detection. |
| **v18.1 (Phase 19)** | 7 minor fixes: BQ project rendering, wildcard regex tightening, description truncation. |
| **Phase 22 STAGE A2** | `all_columns` side-channel + join_hints heuristic. Largest single change. |
| **Phase 27 F1** | F1 catalog filter (lines 86-106), three-part name rendering (lines 246-256), Snow dialect rules (lines 263-279). Hard partition by `c.db.upper()`. |
| **Phase 28** | `col:TYPE` rendering moved to runner's `_snow_direct_prompt` (line 220+); pack-builder stays unchanged для col rendering. F4 cast rule в Snow rules block (стандартное в latest рев). |

Most critical addition — Phase 27 F1 catalog filter. Module remained stable across Phase 19-21 (минор патчи), Phase 22 added A2 features, Phase 27 added F1, Phase 28 had no code changes here.

## Cross-references

- Architecture description: [04_ARCHITECTURE/04_pack_builder_v18.md](../04_ARCHITECTURE/04_pack_builder_v18.md)
- Schema linker (input source): [02_schema_linker_v18.md](./02_schema_linker_v18.md)
- AST validator (consumer of `all_columns`): [04_validators_suite.md](./04_validators_suite.md)
- Candidate factories (consumer of pack): [03_candidate_factories.md](./03_candidate_factories.md)
- Phase 22 A2 narrative: [06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md)
- Phase 27 F1 narrative: [06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md](../06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md)

## Источники

| Утверждение | Источник |
|---|---|
| F1 catalog filter | `repo/src/evaluation/schema_pack_builder_v18.py` lines 86-106 |
| `all_columns` side-channel | lines 99-136 |
| Wildcard regex | lines 152-169 |
| Join hints heuristic | lines 172-226 |
| Snow dialect rules в prompt | lines 263-279 |
| Phase 22 A2 introduction | memory `spider2_phase22_findings.md` |
| Phase 27 F1 lessons | `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` |
| Sanity test | `tools/remote_scripts/_phase27_sanity_pack_build.py` |
