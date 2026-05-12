# 5.2.1 Определения метрик

## Назначение

Этот файл — **canonical reference** для каждой метрики, которая когда-либо появлялась в Phase 1-28. Все остальные файлы dossier ссылаются к этому файлу вместо повторного определения. Включает: точное определение, как вычисляется, edge cases, при каких условиях применима, engine source, и **methodological caveat** про reliability bounds.

## Главная execution metric — `execute_ok` (EX)

**Definition** общая: SQL prediction выполняется на real engine и result **matches gold** in некотором bench-specific смысле.

Per-benchmark realization:

### Spider 1.0 / BIRD (SQLite engine)

```python
def execute_ok_sqlite(pred_sql, gold_sql, db_path):
    """Execute both SQL on SQLite, compare results as multiset of rows."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute(pred_sql)
        pred_rows = cur.fetchmany(1000)
    except Exception:
        return False
    cur.execute(gold_sql)
    gold_rows = cur.fetchmany(1000)
    
    # Multiset comparison — order-insensitive, count-sensitive
    return sorted(pred_rows) == sorted(gold_rows)
```

**Edge cases**:
- **NULL handling**: SQLite returns Python `None` for NULL. `sorted()` treats `None` comparable к other `None` but not к numeric — sort может raise. Spider 1.0 evaluation harness has explicit NULL-aware comparison.
- **Type coercion**: SQLite is dynamically typed — `'2023' == 2023` может pass или fail depending на column type. Bench evaluation handles this.
- **Column order**: matters in multiset comparison via tuple equality. Spider 1.0 evaluation **does** require matching column order.
- **Fetchmany(1000) cap**: prediction must return ≤1000 rows. Beyond — truncated. Rare on dev set.

**Spider 1.0 official harness**: includes Component Matching (CM) and Execution Accuracy (EX). We report only EX.

**BIRD specifics**:
- Larger DBs (up to 5GB) — same comparison logic but slower.
- Some BIRD tasks have **gold tolerance**: small numerical differences (rounding) accepted via `is_close` tolerance. Bench harness handles.

### Spider2-Lite / Spider2-Snow (BigQuery / Snowflake engines)

```python
def execute_ok_spider2(pred_sql, gold_sql, engine='bigquery'):
    """Execute both на real warehouse, multiset match с EXTRA COLUMNS ALLOWED."""
    if engine == 'bigquery':
        pred_df = bq_client.query(pred_sql).to_dataframe()
        gold_df = bq_client.query(gold_sql).to_dataframe()
    elif engine == 'snowflake':
        pred_df = snow_conn.cursor().execute(pred_sql).fetchall()
        gold_df = snow_conn.cursor().execute(gold_sql).fetchall()
    
    # Reduce pred к gold's columns (extra cols allowed)
    gold_cols = list(gold_df.columns)
    pred_reduced = pred_df[gold_cols]  # selects only gold columns from pred
    
    # Multiset row match
    return multiset_equal(pred_reduced, gold_df)
```

**Critical difference от Spider 1.0**: **extra columns allowed**. If gold returns `[name]` and prediction returns `[name, id]`, evaluation projects prediction к `[name]` and compares.

**Edge cases**:
- **Column type coercion**: BQ может implicit-cast numerics к strings — gold expects FLOAT64, prediction returns STRING — eval handles type coercion.
- **NULL representation**: BQ vs Snow vs SQLite differ on NULL printing. Eval harness normalizes.
- **Row count limit**: typically ≤10000 rows для evaluation (bench harness caps to avoid runaway queries).
- **ORDER BY consistency**: by default multiset match (no order); some tasks **explicitly require ORDER BY** — harness checks ORDER preserved.

**Note on our pipeline**: we use **`dry_run_ok`** (BQ) или **`explain_ok`** (Snow) как proxy для `execute_ok` during pipeline runs — actual execution doneFair post-pipeline via official evaluation harness. См. discussion на page bottom.

### Spider2-DBT (DuckDB + DBT execution)

```python
def task_success_dbt(pred_project_dir, gold_target_tables, gold_duckdb_path):
    """Run dbt build на predicted project, compare output tables против gold."""
    # 1. Apply predicted file edits
    # 2. Run dbt build
    result = subprocess.run(['dbt', 'build', '--project-dir', pred_project_dir], ...)
    if result.returncode != 0:
        return False  # dbt build failed
    
    # 3. Compare each gold target table column-by-column
    for table_name in gold_target_tables:
        pred_df = duckdb.connect(pred_duckdb).execute(f'SELECT * FROM {table_name}').fetchdf()
        gold_df = duckdb.connect(gold_duckdb).execute(f'SELECT * FROM {table_name}').fetchdf()
        
        if not table_column_match(pred_df, gold_df):
            return False
    
    return True
```

**Stricter than EX**: not multiset row match — **table+column-level** match. Each expected output table должна present с matching columns + values.

**Edge cases**:
- **Materialization differences**: pred materialized 'view' vs gold 'table' — same output rows, but DBT considers structurally different. Eval should handle, но nuanced.
- **Multiple output tables**: всё-or-nothing semantics. If 3 expected tables, 2 match + 1 mismatch → task fail.
- **DBT compile vs run vs test**: full stack must pass. dbt parse + compile + run всё-or-nothing. dbt test optional (depends on task).

## Schema linker + planner metrics

### `parse_ok`

**Definition**: SQLGlot dialect-aware parsing successful.

```python
def parse_ok(sql, dialect='snowflake'):
    try:
        sqlglot.parse_one(sql, read=dialect)
        return True
    except sqlglot.errors.ParseError:
        return False
```

**Edge cases**:
- **SQLGlot dialect gaps**: SQLGlot's Snowflake parser cannot handle `TABLE(LATERAL FLATTEN(INPUT => col))` (sf_bq210 case). Phase 28 F4c regex fallback bypasses this for the guard.
- **Generated SQL with non-printable characters**: extremely rare, но may break parser.

### `schema_valid`

**Definition**: every column / table identifier referenced в SQL **exists** in pack.all_columns + pack.tables (allow-set).

**Phase 22 STAGE A2 baseline** (classical):

```python
def schema_valid_baseline(sql, pack):
    ast = sqlglot.parse_one(sql, dialect)
    cols_allowed = {c.upper() for t in pack['tables']
                                for c in t.get('all_columns', []) + [c['name'] for c in t['columns']]}
    tables_allowed = {t['table'].upper() for t in pack['tables']}
    
    for col in ast.find_all(exp.Column):
        if col.name.upper() not in cols_allowed:
            return False, f'unknown col: {col.name}'
    for tab in ast.find_all(exp.Table):
        if tab.name.upper() not in tables_allowed:
            return False, f'unknown table: {tab.name}'
    return True, ''
```

**Phase 27 F1 relaxation** (Snow only):

```python
def schema_valid_phase27(sql, pack, extra_allowed_cols):
    cols_allowed = baseline_cols_allowed | {c.upper() for c in extra_allowed_cols}
    # ...
    
    # Phase 27 SELECT-alias protection:
    select_aliases = {a.alias_or_name.upper() for a in ast.find_all(exp.Alias) if a.alias_or_name}
    cols_allowed |= select_aliases
    
    # Rest of validation...
```

`extra_allowed_cols = task_db_all_cols` — full catalog columns в task's DB. Released constraint to reduce false-positive schema_invalid on Snow lane (Phase 27 corrections 2+5).

**Edge cases**:
- **Aliased columns**: `SELECT t.col FROM t` — `col` parsed as `Column(table='t', name='col')`. Our check uses `col.name` (just `col`). Alias `t` not checked separately.
- **Schema-qualified identifiers**: `db.schema.table.col` — SQLGlot resolves к Table + Column nodes correctly.
- **CTE references**: CTE name appears as `exp.Table` в downstream usage. Phase 27 guard already handles CTE-aware skipping для catalog autofill; validator includes CTE names в tables_allowed (implicit via SQL self-reference).

### `chosen_schema_valid`

**Definition**: **selected candidate** (after `candidate_selector_v18.select`) passed AST validator.

Differs от `schema_valid` because multi-candidate pipeline (BQ lane) — Family A/B/C all evaluated, selector picks one. `chosen_schema_valid` measures the picked one specifically.

On Snow lane (only Family B), `chosen_schema_valid = schema_valid` trivially.

### `dry_run_ok` (BigQuery lane)

**Definition**: BQ `client.query(sql, job_config=QueryJobConfig(dry_run=True))` returns без exception.

```python
def dry_run_ok(sql):
    try:
        client = bigquery.Client()
        cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        client.query(sql, job_config=cfg)
        return True
    except Exception:
        return False
```

**Stronger than `parse_ok`** — checks **type compatibility, identifier resolution, function signature matching**. Equivalent к real query analysis без actual data scan.

**Cost**: free (BQ dry_run quota-only, no $ charge).

**Edge case**: BQ dry_run requires authenticated client + project context. If credentials missing, returns connect-fail, NOT actual validity check.

### `explain_ok` (Snowflake lane)

**Definition**: Snowflake `EXPLAIN USING TEXT <sql>` returns без exception.

```python
def explain_ok(sql):
    try:
        cur = snow_conn.cursor()
        cur.execute(f'EXPLAIN {sql}')
        cur.fetchall()
        return True
    except Exception:
        return False
```

**Equivalent of `dry_run_ok` для Snow**. Free (no warehouse credit per Snow docs).

**Edge case**: requires `USE DATABASE` + `USE SCHEMA` set first (or three-part identifier в SQL). Phase 27 F1 enforces three-part names, so context-setting optional but defensive.

### `plan_ok`

**Definition**: JSON Schema + AST validator pass on planner output (plan-JSON):

```python
def plan_ok(plan_json, pack):
    try:
        plan = parse_plan(plan_json)  # JSON Schema validation
        validation = validate_plan(plan, pack)  # AST closed-set validation
        return validation.ok
    except Exception:
        return False
```

**Per `_v18_plan`**: `max_attempts=2` retries on failure. `plan_ok` reports final state after retries.

## Phase 27-28 specific counters

### `guard_leaks` (Phase 27 F1)

**Definition**: count of candidates where `snow_identifier_guard_v27.guard_and_fix_snow_sql` raised `IdentifierLeakError(catalog_leak:...)`.

**Distinct от**:
- `guard_rewrites`: count of auto-fills (catalog missing → fills task_db).
- `guard_regex_fallback`: count of SQLGlot ParseError → regex fallback used.

**Empirical observation Phase 27/28**: `guard_leaks = 0` across all pilot10 runs after F1 catalog filter active. Means catalog drift **structurally impossible** at upstream (per-task BM25 partition) — guard never needs к fire.

### `requoted_n` (Phase 28 F2a — REVERTED)

**Definition**: count of `snow_dialect_fixer_v28.fix_mixedcase_quoting` requote applications.

**Status**: F2a reverted Phase 28 closure. **Stays 0** in post-revert runs (function exists but not called). Kept в metrics для historical record / future reference if F2a re-activated.

### `wrapped_n` (Phase 28 F4)

**Definition**: count of `snow_dialect_fixer_v28.wrap_date_fn_on_nondate` wrap applications.

**Each wrap** corresponds к one column inside a date function (`Extract`, `TimestampTrunc`, `DateAdd`, etc.) with declared NUMBER or VARIANT type.

**Empirical observation**: pilot10 v28-revert-A had `wrapped_n=9` across 10 tasks. Three of those wraps contributed к exec_ok lift (sf_bq026, sf_bq213; sf_bq029 used direct math).

### `pk_fk_injected` (Phase 27 correction 3)

**Definition**: count of columns force-injected to pack via PK/FK heuristic naming (`id`, `<tbl_singular>_id`, `*_pk`, `*_fk`, `*_id`, `*_key`, `*_sk`).

**Per-task counter**, cap 4 per table.

## Phase 27 diagnostic taxonomy

These metrics are **diagnostic-only** (computed on snapshot, not per-task), used в Phase 27 §1 catalog drift analysis:

### `correct_only` / `wrong/unknown` / `no_catalog` / `mixed`

Classification of each task's three-part identifier usage:

| Category | Definition |
|---|---|
| `correct_only` | All FROM/JOIN refs use `task_db` catalog (correct first segment) |
| `wrong/unknown` | All FROM/JOIN refs use catalog NOT == `task_db` (foreign catalog OR not-in-valid-set) |
| `no_catalog` | All FROM/JOIN refs are bare TABLE or SCHEMA.TABLE (missing first segment) |
| `mixed` | Some correct + some wrong refs |

Phase 26 v26 Lite-Snow baseline measurement: **90.2% of tasks `wrong/unknown + no_catalog + mixed`**. Reduced to **0%** after Phase 27 F1.

## Aggregate metrics — counters в `progress.json`

Per `_phase27_snow_runner.py` writes `progress.json` каждый task с следующими aggregated counters:

```json
{
  "n_total": <int>,          // tasks processed
  "n_target": <int>,         // total tasks in batch (with resume filtering)
  "plan_ok": <int>,
  "schema_valid": <int>,
  "parse_ok": <int>,
  "execute_ok": <int>,
  "guard_leaks": <int>,
  "guard_rewrites": <int>,
  "guard_regex_fallback": <int>,
  "requoted_n": <int>,
  "wrapped_n": <int>,
  "err_top": [(category, count), ...],   // top error class taxonomy
  "wall_sec": <float>,
  "last_task": "<instance_id>"
}
```

`err_top` = error class breakdown (canonical from engine error → mapping like `invalid_identifier`, `syntax_error`, `type_mismatch`, etc.). См. [04_ARCHITECTURE/10_execution_engines.md](../04_ARCHITECTURE/10_execution_engines.md) для full taxonomy.

## Metric reliability bounds

### Annotation reliability (Spider 2.0)

Per Wang et al. [arXiv 2601.08778, *"Pervasive Annotation Errors Break Text-to-SQL Benchmarks and Leaderboards"*]: **62.8% mismatch rate** на Spider 2.0 audit of gold vs re-annotated gold.

**Implications для metric interpretation**:

1. **Absolute EX upper bound** в worst case ~38% (если 62.8% gold mismatched, max audited-correct measurement is ~37%).
2. **Practically**: most systems report ~25-65% EX на Spider 2.0 — well within "noise + signal" zone.
3. **Relative system rankings remain robust** (noise affects all systems equally).
4. **Improvements <5% EX hard к claim reliably** на Spider 2.0 due к этого noise floor.

### Recommendation для thesis defense

- **Report EX с caveat**: «Spider2 EX reported here uses official eval harness; annotation reliability ~62.8% mismatch [Wang et al., arXiv 2601.08778] caps measurement granularity.»
- **Manual audit 20-30 post-fix failures** before final reporting — common-sense check whether claimed improvement reflects real semantic match vs annotation noise.
- **Don't claim absolute SOTA** — claim **relative position в reproducibility tier** instead.

### Pipeline-internal metric reliability

`schema_valid`, `parse_ok`, `dry_run_ok`, `explain_ok` — **deterministic given SQL input**. No annotation dependency, no noise. Reliable for measuring scaffolding interventions.

`execute_ok` — depends on gold SQL annotation (potentially noisy on Spider 2.0). Use `parse_ok` / `dry_run_ok` / `explain_ok` for **intervention measurement**, `execute_ok` for **final reporting only** (с caveat).

### Methodology audit per benchmark — recommendations

| Bench | Audit type recommended | Effort | Where reported |
|---|---|---|---|
| Spider 1.0 | run official harness on our predictions | low | [09_RESULTS_ANALYSIS/01_classical_benchmarks_spider1_bird.md](../09_RESULTS_ANALYSIS/01_classical_benchmarks_spider1_bird.md) |
| BIRD | run official `evaluation.py` on our predictions | low | same file (critical — наш 87.9% claim above leaderboard) |
| Spider2-Lite-BQ | sample 20 successes + 20 failures, manual check | medium | post-FULL |
| Spider2-Snow | sample 20 successes + 20 failures, manual check | medium | post-FULL |
| Spider2-DBT | examine each of 9 successes + diagnose 59 failures | high | [09_RESULTS_ANALYSIS/04_spider2_dbt_analysis.md](../09_RESULTS_ANALYSIS/04_spider2_dbt_analysis.md) |

## Pipeline-internal vs official-harness EX

Our pipeline produces **predictions.jsonl с metadata** for each task. To get **official EX score**:

1. Strip `predictions.jsonl` к `{instance_id, sql}` format (drop our internal counters).
2. Run **bench's official evaluation script** против predictions:
   - Spider 1.0: `python evaluation.py --gold dev_gold.sql --pred predictions.txt`
   - BIRD: `python evaluation.py --predicted_sql_path ... --ground_truth_path ... --db_root_path ...`
   - Spider 2.0: official harness via `scripts/evaluate_lite.py` / `evaluate_snow.py`

3. Compare reported EX к our internal `n_exec / n_total`.

**Expected**:
- Spider 1.0 / BIRD: external EX should match within ±0.5pp (deterministic execution).
- Spider 2.0: external EX may differ ±2-5pp due к network round-trips, BQ dry_run vs real query, multiset matching nuances.

## Quick reference — what metric для what

| Question | Use metric |
|---|---|
| Did pipeline produce executable SQL? | `execute_ok` (final), `dry_run_ok` / `explain_ok` (pipeline) |
| Did emitter avoid hallucination? | `schema_valid` |
| Did SQL parse? | `parse_ok` |
| Did planner produce valid JSON plan? | `plan_ok` |
| Did F1 catalog filter work? | `guard_leaks` (should be 0), `pack_unique_dbs` |
| Did F4 wrap fire correctly? | `wrapped_n` |
| Was F4c needed? | `guard_regex_fallback` |
| Total task wall time? | `wall_sec` |
| Failure breakdown? | `err_top` |

## Cross-references

- Validators implementation: [08_CUSTOM_TOOLS/04_validators_suite.md](../08_CUSTOM_TOOLS/04_validators_suite.md)
- Engine specifics: [04_ARCHITECTURE/10_execution_engines.md](../04_ARCHITECTURE/10_execution_engines.md)
- Architecture validators layer: [04_ARCHITECTURE/07_validators_json_ast_engine.md](../04_ARCHITECTURE/07_validators_json_ast_engine.md)
- Phase 27 metric updates: [06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md](../06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md)
- Phase 28 metric updates: [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md)
- Annotation reliability discussion: [03_BENCHMARKS/03_spider2_overview.md](../03_BENCHMARKS/03_spider2_overview.md)
- Lessons learned (annotation reliability bounds): [06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md](../06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md)

## Источники

| Утверждение | Источник |
|---|---|
| EX definition Spider 1.0 / BIRD / Spider 2.0 | bench official harnesses + Spider2 paper (Lei et al., ICLR 2025) |
| Annotation reliability 62.8% | Wang et al., arXiv 2601.08778 |
| BQ dry_run mechanics | Google Cloud BQ docs |
| Snow EXPLAIN no credit | Snowflake docs (sql-reference/sql/explain) |
| Phase 27 metric extensions | `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` §2 |
| Phase 28 metric extensions | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §2 |
| F4c regex fallback | `snow_identifier_guard_v27._regex_catalog_leak_check` |
