# 3.2.10 Execution Engines — BQ dry_run, Snow EXPLAIN, SQLite execute

## Главный тезис

Финальный validator каждого SQL — **проверка на реальном engine**. У нас три engine типа, каждый со своими particularities:

1. **BigQuery dry_run** (`google.cloud.bigquery`) — full SQL validation **без выполнения** (zero data scan, zero cost). Используется на Spider2-Lite-BQ.
2. **Snowflake EXPLAIN USING TEXT** — full SQL validation на named warehouse без actual query execution. **Не потребляет credit** (per Snowflake docs). Используется на Spider2-Snow и Lite-Snow.
3. **SQLite `cur.execute()` + `cur.fetchmany()`** — действительное выполнение на in-memory или file-based SQLite. Используется на Spider 1.0, BIRD, и Lite-SQLite lanes.

Для Spider2-DBT engine — **`dbt build` + table comparison** в DuckDB. Это full execution (нет dry_run analogue для DBT).

## BigQuery: dry_run

### Что делает

`dry_run=True` flag на `client.query()` posts SQL к BQ servers for **server-side parse + name resolution + cost estimation**, без actual scan. Returns:
- Validation status (success / failure)
- Output schema (column names + types)
- Bytes processed estimate
- Slot estimate

Если SQL invalid — exception raised с specific error message:

```python
config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
try:
    job = client.query(sql, job_config=config)
    return (True, 'ok', '')
except Exception as e:
    em = str(e)[:300]
    return (False, classify(em), em)
```

### Classification error messages

| BQ error contains | Maps to canonical |
|---|---|
| "Unrecognized name" | `invalid_identifier` |
| "Table not found" | `invalid_identifier` |
| "Syntax error" | `syntax_error` |
| "Type mismatch" / "Cannot cast" | `type_mismatch` |
| "Subquery returns more than one row" | `subquery_multi_row` |
| (other) | `BQClientError` / `Exception name` |

### Quirks

- **Free**: dry_run не tarifizируется, не считается quota.
- **Speed**: 1-3s per call. На large schemas / complex SQL — иногда 5-10s.
- **Auth**: requires service account (JSON file) с `bigquery.jobs.create` permission. Setup в notebook cell 03 (secrets).
- **No data**: dry_run не возвращает rows — только metadata. Для real evaluation EX (multiset row match) — нужно real `query(dry_run=False)`. Spider2-Lite-BQ evaluation gold matching выполняется отдельно (post-pipeline) с real query.

### Wildcard tables

BQ wildcards (`bigquery-public-data.google_analytics_sample.ga_sessions_*`) — dry_run handles full wildcard expansion и type unification. Это позволяет нам surface wildcard pattern в pack (см. [04_pack_builder_v18.md](./04_pack_builder_v18.md)) и trust BQ для validation correctness.

## Snowflake: EXPLAIN USING TEXT

### Что делает

`EXPLAIN USING TEXT <sql>` — Snowflake equivalent of dry_run. Validates SQL (parse + bind + plan) **без actual execution**.

```python
def _snow_explain(sql, *, db=None, schema=None):
    try:
        c = _snow_connect()
        cur = c.cursor()
        if db:
            try: cur.execute(f'USE DATABASE "{db}"')
            except: pass
        if schema:
            try: cur.execute(f'USE SCHEMA "{schema}"')
            except: pass
    except Exception as e:
        return (False, 'connect_fail', f'{type(e).__name__}: {str(e)[:300]}')
    try:
        cur.execute(f'EXPLAIN {sql}')
        cur.fetchall()
        return (True, 'ok', '')
    except Exception as e:
        em = str(e)[:300]
        emL = em.lower()
        if 'invalid identifier' in emL or 'does not exist' in emL:
            return (False, 'invalid_identifier', em)
        if 'syntax error' in emL:
            return (False, 'syntax_error', em)
        if 'incompatible' in emL or 'does not match' in emL:
            return (False, 'type_mismatch', em)
        return (False, type(e).__name__, em)
```

### Quirks

- **Free**: Snowflake docs (`docs.snowflake.com/en/sql-reference/sql/explain`) — EXPLAIN **не потребляет warehouse credit**. Validated empirically в Phase 26 — running тысячи EXPLAINS не invoiced. **Critical для cost-controlled academic work.**
- **Speed**: typically 0.5-2s per call. Connect overhead ~5-10s (cached after first call via `_SNOW_CONN['main']` reuse).
- **Auth**: requires `account / user / password / role / warehouse` env vars. **Critical lesson Phase 28**: на fresh kernel эти env vars НЕ установлены автоматически notebook cells — нужно отдельно их load из `secrets/snowflake.json`. См. [`colab_session_bringup.md`](C:\Users\dlaze\.claude\projects\d--HSE--------NL2BI-AI-assistant\memory\colab_session_bringup.md) §2a.
- **USE DATABASE / USE SCHEMA**: pre-EXPLAIN мы устанавливаем context (`USE DATABASE "PATENTS"; USE SCHEMA "PATENTS";`). Если SQL не использует three-part names, fallback к set context. После Phase 27 F1, three-part names enforced, USE DATABASE/SCHEMA — лишь convenience.

### Connection caching

```python
_SNOW_CONN = {}  # module-level cache

def _snow_connect():
    if 'main' in _SNOW_CONN:
        try:
            _SNOW_CONN['main'].cursor().execute('SELECT 1').fetchone()
            return _SNOW_CONN['main']
        except Exception:
            del _SNOW_CONN['main']
    c = snowflake.connector.connect(...)
    _SNOW_CONN['main'] = c
    return c
```

Per-task overhead: ~0.05s (cached connection re-use). Без caching: ~5-10s per task. Critical optimization для FULL 547 runs (10× speedup).

## SQLite: cur.execute + fetchmany

### Что делает

For Spider 1.0 / BIRD / Spider2-Lite-SQLite — packaged SQLite databases distributed as `.sqlite` files. Just `sqlite3.connect(...)` + `cur.execute(sql)`:

```python
def _sqlite_execute(sql, db_path, fetch_limit=1000):
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchmany(fetch_limit)
        conn.close()
        return (True, 'ok', '', rows)
    except Exception as e:
        return (False, type(e).__name__, str(e)[:300], None)
```

### Quirks

- **In-memory или file**: Spider1/BIRD packages each DB как separate `.sqlite` file. Loading ~10-100ms per DB на first access.
- **Speed**: typically 50-500ms per query. Fast.
- **Real execution**: actually returns rows. Goes towards full EX evaluation (multiset row match against gold).
- **Resource limits**: typical Spider1 DB <100MB; can fully load in-memory if needed. BIRD DBs sometimes >1GB.
- **No dry_run analogue**: SQLite не имеет dry_run. We just execute, fetch limited rows, и check no exception.

## Spider2-DBT: dbt build + table compare

### Что делает

После agent makes file edits в DBT project, evaluation:

1. `dbt build --select <target_models>` — compiles + executes models в DuckDB.
2. Если `dbt build` fails (compile error / runtime error) → `task_success = False`.
3. Если success — compare output tables against golden DuckDB (table-and-column match):
   ```python
   for target_table in expected_outputs:
       actual_df = read_duckdb(actual_path, target_table)
       expected_df = read_duckdb(gold_path, target_table)
       if not df_match(actual_df, expected_df, col_set=True, sort=True):
           task_success = False
           break
   ```
4. Per-task wall time: typically 5-15 minutes (compile + execute + compare).

### Quirks

- **Heavy**: full DBT execution per task. Cannot parallelize easily (DBT state).
- **Multi-file context**: agent must edit `models/`, possibly `schema.yml`, possibly `dbt_project.yml`. Edit format critical.
- **DuckDB engine**: actually executes SQL queries — strong typing, real result rows.
- **All-or-nothing**: если single model в multi-model task fails, entire task fails. Partial credit not awarded.

## Sequential execution и timing

| Engine | Per-task wall time | Typical bottleneck |
|---|---|---|
| BigQuery dry_run | 1-3s | network roundtrip |
| Snowflake EXPLAIN | 0.5-2s (cached connect) | network + EXPLAIN compute |
| SQLite execute | 0.05-0.5s | local disk for large DBs |
| DBT build | 5-15 min | compile + DuckDB execution |

**Per-task total** (включая planner + emitter + validator overhead):
- Spider 1.0 / BIRD: ~30-60s/task
- Spider2-Lite-BQ: ~90-150s/task (dry_run + multi-candidate)
- Spider2-Snow: ~70-120s/task
- Spider2-DBT: 5-15 min/task

## Reliability concerns

### Cloudflare tunnel rotation
Не engine issue, но affects orchestration. Bridge URL (Colab → laptop communication) rotates on tunnel restart. Detection via DNS failure / 502 / 530 errors. Mitigation: `sync_bridge_url_from_notebook.py` reads new URL from Colab notebook output cells.

### Snowflake connect_fail (Phase 28 incident)
Если `SNOWFLAKE_*` env vars не set → ALL tasks fail `connect_fail`. **64 wasted tasks** в Phase 28 incident before detection. Fix script: `_phase28_s1_fix_snowflake.py` + memory note (`colab_session_bringup.md` §2a).

### BigQuery quota
Free dry_run, но **service account** quota: `bigquery.jobs.create` rate-limited. Sustained ~10 calls/sec OK; bursts >50/sec — throttling. Sequential pipeline avoids.

### DBT environment fragility
DBT projects depend on specific DuckDB version + DBT plugin version. Phase 11 baseline used `dbt-duckdb==1.5.2`. Newer versions имели breaking changes. Pinned in `requirements.txt`.

## Per-engine error message таксономия

Каждый engine producer different error message wording. Чтобы consolidate, наш `error_taxonomy.csv` (см. [07_validators_json_ast_engine.md](./07_validators_json_ast_engine.md)) maps engine errors к unified categories.

| Canonical | BQ wording | Snow wording | SQLite wording |
|---|---|---|---|
| `invalid_identifier` | "Unrecognized name X" | "invalid identifier 'X'" / "Object X does not exist" | "no such column: X" / "no such table: X" |
| `syntax_error` | "Syntax error at..." | "SQL compilation error: syntax error..." | "near 'X': syntax error" |
| `type_mismatch` | "No matching signature for operator", "Cannot cast..." | "Function X does not support TYPE argument" | "datatype mismatch" |
| `connect_fail` | (rare — credentials) | `connect_fail` from `_snow_connect()` | (n/a — local file) |
| `parse_error` | (caught earlier by SQLGlot) | (caught earlier) | (caught earlier) |
| `ok` | dry_run success | EXPLAIN success | execute + fetchmany success |

Это позволяет cross-bench failure pattern analysis (см. [07_METRICS_AND_RESULTS/04_error_taxonomy_evolution.md](../07_METRICS_AND_RESULTS/04_error_taxonomy_evolution.md)).

## Why not just run real query

Could we skip dry_run / EXPLAIN и run actual query? Pros: same code path как real EX evaluation. Cons:

- **Cost (BQ)**: real query scans data, costs $$. На full benchmark — thousands $ $.
- **Cost (Snow)**: real query consumes warehouse credit. Per-task ~$0.001-$0.01 — adds up на FULL 547.
- **Time**: real query на large warehouse table — может занимать minutes. dry_run / EXPLAIN — seconds.
- **Rate limiting**: cloud warehouses rate-limit concurrent queries; dry_run / EXPLAIN — much higher quotas.

For pipeline validation, dry_run / EXPLAIN are **superior**. For final EX evaluation (multiset row match), we use Spider2 official evaluation harness which **does** run real queries (offline / via cached results when possible).

## Cross-references

- Engine validator code: [08_CUSTOM_TOOLS/04_validators_suite.md](../08_CUSTOM_TOOLS/04_validators_suite.md)
- Phase 28 connect_fail incident: [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md)
- Lane-specific pipeline details: [05_PIPELINES/](../05_PIPELINES/)
- Error taxonomy evolution: [07_METRICS_AND_RESULTS/04_error_taxonomy_evolution.md](../07_METRICS_AND_RESULTS/04_error_taxonomy_evolution.md)
- Bridge / tunnel resilience: [08_CUSTOM_TOOLS/09_resilience_patterns.md](../08_CUSTOM_TOOLS/09_resilience_patterns.md)

## Источники

| Утверждение | Источник |
|---|---|
| BQ dry_run free | Google Cloud docs |
| Snow EXPLAIN no credit | Snowflake docs (sql-reference/sql/explain) |
| `_snow_connect` caching | `tools/remote_scripts/_phase27_snow_runner.py:94-110` |
| Phase 28 connect_fail incident — 64 wasted tasks | runtime log; `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` (post-mortem) + `colab_session_bringup.md` §2a |
| Spider2-DBT eval — table+column match | xlang-ai/Spider2 evaluation harness |
| DBT engine = DuckDB | `outputs/REPORT_PHASE26_RESEARCHER_HANDOFF.md` |
