# 3.2.7 Validators — JSON schema, AST closed-set, engine dry-run

## Главный тезис

В pipeline используется **трёхслойная защита** через independent validators:

1. **JSON Schema Validator** — checks structural compliance plan-JSON output planner-а (correct keys, types, mandatory fields). Catches: rare planner output malformations.
2. **AST Closed-Set Validator** — parses SQL portions plan-JSON через SQLGlot и checks что каждый identifier ∈ pack. Catches: dominant failure class — **identifier hallucination**.
3. **Engine Validator** — final check на реальном engine (BQ dry_run / Snow EXPLAIN / SQLite execute). Catches: dialect runtime errors (NUMBER cast, LATERAL FLATTEN parse, unknown functions, FK violations при exec).

Каждый layer **обязателен** — он catches different class failures, и pipeline relies на их **combination** для не-нулевого EX на Spider 2.0 family. Удаление любого layer (например, skip AST validator) приведёт к significant regression в EX.

## Layer 1: JSON Schema Validator

### Назначение

Парсит planner output как JSON и checks shape against expected schema. Реализация в `repo/src/evaluation/structured_plan_v18.py`.

### Validation logic

```python
def parse_plan(raw: str) -> PlanCandidate:
    # Try several extraction strategies:
    # 1. Direct JSON parse
    # 2. Extract from ```json ... ``` block
    # 3. Extract first {...} balanced block
    try: return PlanCandidate(**json.loads(raw))
    except: ... fallbacks
```

```python
@dataclass
class PlanCandidate:
    selected_database: str
    selected_schema: str
    selected_tables: list[str]
    selected_columns: list[str]
    metrics: list[dict] = []
    filters: list[dict] = []
    time_constraints: list[str] = []
    grouping: list[str] = []
    sorting: list[dict] = []
    limit: Optional[int] = None
    ambiguity_points: list[str] = []
    expected_shape: str = ''
```

JSON Schema validation использует **Pydantic-style dataclass** matching, не formal JSON Schema spec. Reasoning: planner output sufficiently constrained by template instructions, formal Schema overkill.

### What it catches

- Plan output with missing `selected_tables` field
- Plan output where `metrics` not a list (e.g., string)
- Plan output where `limit` is string instead of int/null
- Malformed JSON (unbalanced braces, trailing comma)

### What it does NOT catch

- Identifiers (table/column names) — not validated here (Layer 2)
- Semantic correctness — not validated here (Layer 3)

### Retry behavior

При `parse_plan` raises:

```python
def _retry_prompt(orig, reasons, last_plan):
    return f"""Your previous response was not valid:
- {reasons}

Please re-emit valid JSON matching the required schema.
{orig}"""
```

One retry. Если retry тоже fails → `plan_ok=False`, fallback в Family B direct emit без plan structure.

## Layer 2: AST Closed-Set Validator

### Назначение

**Самый critical layer**. Catches identifier hallucination — главная failure mode на Spider 2.0 family.

### Validation logic

Реализация — `_snow_schema_valid_ast` в `tools/remote_scripts/_phase27_snow_runner.py:150-218` (Snow-specific version; analogous logic для BQ in `spider2_candidate_factory_v18`).

```python
def _snow_schema_valid_ast(sql, pack, extra_allowed_cols=None):
    """AST validator: every identifier in SQL must be in pack.all_columns
    or task_db catalog cols (Phase 27 relaxation)."""
    # Build allow-set
    tables_allowed = {t['table'].upper() for t in pack['tables']}
    cols_allowed = set()
    for t in pack['tables']:
        for c in t.get('all_columns', []) + [c['name'] for c in t['columns']]:
            cols_allowed.add(c.upper())
    if extra_allowed_cols:
        cols_allowed.update(c.upper() for c in extra_allowed_cols)

    # SELECT-clause aliases — protected (Phase 28 fix)
    try: ast = sqlglot.parse_one(sql, read='snowflake')
    except: return (False, 'parse_failed:ParseError')
    
    select_aliases = set()
    for al in ast.find_all(E.Alias):
        a = al.alias_or_name
        if a: select_aliases.add(a.upper())
    cols_allowed |= select_aliases

    # Check each Column reference
    unknown_cols = []
    unknown_tables = []
    for col in ast.find_all(E.Column):
        cn = (col.name or '').upper()
        if cn not in cols_allowed:
            unknown_cols.append(col.name)
    for tab in ast.find_all(E.Table):
        tn = (tab.name or '').upper()
        if tn not in tables_allowed:
            unknown_tables.append(tab.name)
    
    if unknown_tables or unknown_cols:
        return (False, f"unknown_tables={unknown_tables}, unknown_cols={unknown_cols}")
    return (True, '')
```

### Phase 27 relaxation: `extra_allowed_cols`

Изначально (Phase 22 STAGE A2) validator проверял только `pack.tables[*].all_columns`. На Snow lane после Phase 27 — расширили: union с **полным catalog cols set** task-а:

```python
task_db_all_cols = {
    (c.field_path or c.column) for c in cat_subset
    if (c.field_path or c.column)
}
sv_ok, sv_msg = _snow_schema_valid_ast(sql, pack, extra_allowed_cols=task_db_all_cols)
```

Это **Phase 27 correction 2** — релаксация валидатора. Reasoning: на Snow lane catalog большой (5K-50K columns в task subset), и BM25 не surface-ит все columns которые planner / emitter might validly reference. Релаксация позволяет SQL ссылаться на columns которые в task_db, но не в pack. Trade-off: increased schema_valid pass rate, но позволяет неprime columns в SQL. Acceptable trade — большинство таких columns на самом деле в task_db и engine validator final cleanup.

### Phase 28 protection of SELECT-clause aliases

Найдено в Phase 27 pilot10c diagnosis: SQL like:

```sql
SELECT FLOOR(date_part(YEAR, "publication_date") / 5) * 5 AS "five_year_period",
       COUNT(*) AS total_patent_count
FROM ...
ORDER BY "five_year_period"
```

`ORDER BY "five_year_period"` — references SELECT-clause alias. SQLGlot parses это as `Column(name='five_year_period')`. Plain `cols_allowed` check rejects (alias не в catalog), что **false-positive schema_invalid**.

Fix (Phase 27 closure, в `_snow_schema_valid_ast`):

```python
select_aliases = set()
for al in ast.find_all(E.Alias):
    a = al.alias_or_name
    if a: select_aliases.add(a.upper())
cols_allowed |= select_aliases
```

Все aliases declared в SELECT clause этого query — automatically allowed downstream. Это **architectural** fix, не case-handler-y patch.

### What catches

- **Column hallucination**: SQL ссылается на `country` где в pack только `country_code`. Validator returns `unknown_cols=['country']`.
- **Table hallucination**: SQL ссылается на `CITATIONS` где в pack нет такой table.
- **Cross-DB references** (на Snow): если SQL contains `OTHER_DB.SCHEMA.TABLE` где `OTHER_DB ≠ task_db` — F1 AST guard catches (separate from this validator, см. [09_dialect_handlers_f1_f4.md](./09_dialect_handlers_f1_f4.md)).

### What it does NOT catch

- **Type mismatches**: SQL like `WHERE numeric_col = 'string'` — passes AST validator, fails engine validator.
- **Logical errors**: aggregate без GROUP BY clause — engine catches.
- **Dialect-specific runtime**: `EXTRACT(YEAR FROM number_col)` — passes AST (column exists), fails Snow EXPLAIN (type mismatch).

## Layer 3: Engine Validator

### Назначение

Final check — отправляет SQL на real engine (или dry_run equivalent) и checks response.

### Per-engine implementations

**BigQuery dry_run** (`spider2_candidate_factory_v18._bq_dry_run`):

```python
from google.cloud import bigquery
client = bigquery.Client(project=PROJECT_FOR_DRYRUN)
config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
try:
    job = client.query(sql, job_config=config)
    return (True, 'ok', '')
except Exception as e:
    em = str(e)[:300]
    # Classification:
    if 'Unrecognized name' in em: return (False, 'invalid_identifier', em)
    if 'Syntax error' in em: return (False, 'syntax_error', em)
    ...
```

**Snowflake EXPLAIN** (`_phase27_snow_runner.py:_snow_explain`):

```python
def _snow_explain(sql, *, db=None, schema=None):
    if not sql: return (False, 'empty_sql', '')
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
        em = str(e)[:300]; emL = em.lower()
        if 'invalid identifier' in emL or 'does not exist' in emL:
            return (False, 'invalid_identifier', em)
        if 'syntax error' in emL:
            return (False, 'syntax_error', em)
        if 'incompatible' in emL or 'does not match' in emL:
            return (False, 'type_mismatch', em)
        return (False, type(e).__name__, em)
```

**SQLite execute** (для Spider1/BIRD/Lite-SQLite):

```python
def _sqlite_execute(sql, db_path):
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchmany(1000)
        conn.close()
        return (True, 'ok', '', rows)
    except Exception as e:
        return (False, type(e).__name__, str(e)[:300], None)
```

### Error classification

Per-engine errors map в canonical error classes для `error_taxonomy.csv`:

| Canonical class | Examples |
|---|---|
| `connect_fail` | Snow connect error (credentials missing — Phase 28 incident) |
| `parse_error` | SQLGlot fails to parse |
| `parse_error_guard` | F1 AST guard raises ParseError (Phase 27/28 specific) |
| `schema_invalid` | AST validator rejected (Layer 2 output) |
| `invalid_identifier` | Snow `000904` or BQ "Unrecognized name" |
| `syntax_error` | engine syntax error post-parse |
| `type_mismatch` | engine type mismatch |
| `ProgrammingError` | catch-all для unusual Snow/BQ exceptions |
| `catalog_leak` | F1 AST guard detected foreign catalog ref |
| `ok` | passes |

Counts persist в `progress.json:err_top` + `error_taxonomy.csv`.

## Trade-offs layered design

| Pro | Con |
|---|---|
| Каждый layer catches different class | 3 sequential checks → some latency |
| Engine layer — ground truth | Engine может быть slow / cost (BQ dry_run quota; Snow EXPLAIN warehouse credit minimal но non-zero) |
| AST layer prevents wasteful engine call для obvious hallucination | AST layer can false-positive (Phase 27 select_aliases issue) |
| Catalog-based AST validation prevents cross-DB drift (with extra_allowed_cols) | Catalog snapshot — может lag за live changes |

## Why all three needed

Phase 17-26 history:

| Phase | Layers active | Result on Spider2-Lite-BQ |
|---|---|---|
| Phase 17 | Engine only (joint emit, no validators) | ~0% executable (identifier hallucination dominates) |
| Phase 18 | + JSON Schema | small improvement (filters malformed JSON) |
| Phase 18 | + AST closed-set | **first non-zero EX (30% Lite-BQ pilot10)** |
| Phase 22 | + `all_columns` side-channel в AST | sv 50→54% (audit predicted +20pp, got +4pp) |
| Phase 27 | + extra_allowed_cols relaxation (Snow) | sv 12.6% → 80% on Snow pilot10c |
| Phase 27 | + SELECT-alias protection (Snow) | helped fix sf_bq029 case |

AST layer — **the** critical contribution. Без AST, identifier hallucination не catches до engine — wasted compute. С AST — caught upstream, retry possible, much higher final EX.

## Validator vs literature

Похожие подходы:

- **CHESS** [Talaei et al., arXiv 2405.16755] — schema description generation + multi-agent validation. Uses LLM agents для validation, не deterministic AST. Trade-off: more flexible но добавляет LLM cost.
- **DAIL-SQL** [Gao et al., VLDB 2024] — нет explicit validator; relies on self-consistency voting.
- **ReFoRCE** [Deng et al., arXiv 2502.00675] — Self-Refinement (execution feedback loop). Closest to ours, но iterates над engine errors не AST errors. **Direction для Phase 29 F3 self-refine** (currently not implemented).
- **MCS-SQL** [Lee et al., COLING 2025] — multi-prompt + selection. Не validator per se, но достигает похожих effects через repeated sampling.

Наш AST validator — **deterministic, fast, type-precise**. CHESS/DAIL-SQL/ReFoRCE — LLM-or-engine-based, more expensive.

## Limitations

### L1. AST validator не catches type errors
SQL passes AST если все identifiers in pack. Type mismatches (numeric_col = 'string'), function arg type mismatches (EXTRACT on NUMBER) — passes AST, fails engine. Engine validator unavoidable.

### L2. Engine validator — cost / speed bottleneck
- BQ dry_run: ~1-3s per call, free.
- Snow EXPLAIN: ~0.5-2s per call, minimal warehouse credit.
- SQLite execute: ~0.1-1s, in-memory.

Сейчас sequential — каждая task ждёт engine response. Parallelization возможна (multiple concurrent calls), но не реализована — single-task processing makes orchestration простым.

### L3. `extra_allowed_cols` relaxation — opens schema_invalid hole
После Phase 27 relaxation, AST validator passes SQL referencing any column in task_db catalog (not just pack). Это означает что эмиттер может reference непрactical column, и AST не catches — engine catches. Trade-off была accepted, потому что без relaxation false-positive rate ~40% на Snow pilot10c (AST rejected valid SQL because column не в narrow BM25 hits).

### L4. Single retry per layer
JSON schema retry × 1, AST retry × 1. После двух retries → fallback в Family B без plan structure. Multi-round refinement (ReFoRCE-style) — Phase 29 territory.

### L5. Connection state — Phase 28 incident
Snow validator (`_snow_explain`) reads `SNOWFLAKE_*` env vars per `_snow_connect()`. На new kernel — если env не set, ALL tasks fail `connect_fail`. Phase 28 incident потратил 64 tasks впустую перед detection. Mitigation: `_phase28_s1_fix_snowflake.py` scripts + memory note (`colab_session_bringup.md` §2a — критическое первое действие после kernel restart).

## Cross-references

- Implementation: [08_CUSTOM_TOOLS/04_validators_suite.md](../08_CUSTOM_TOOLS/04_validators_suite.md)
- Engine specifics per lane: [10_execution_engines.md](./10_execution_engines.md)
- Planner-emitter contract (что валидатор проверяет): [05_planner_emitter_decomposition.md](./05_planner_emitter_decomposition.md)
- Phase 22 A2 `all_columns` introduction: [06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md)
- Phase 27 relaxation + SELECT alias fix: [06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md](../06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md)
- Phase 28 connect_fail incident: [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md) (handoff supervisor + Snowflake env fix)
- Failure analysis (where validators don't catch): [09_RESULTS_ANALYSIS/06_failure_analysis_remaining.md](../09_RESULTS_ANALYSIS/06_failure_analysis_remaining.md)

## Источники

| Утверждение | Источник |
|---|---|
| AST validator logic | `tools/remote_scripts/_phase27_snow_runner.py` lines 150-218 |
| Phase 22 A2 `all_columns` | memory `spider2_phase22_findings.md`; `outputs/REPORT_SPIDER2_V22.md` |
| Phase 27 relaxation evidence | `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` §2 corrections |
| SELECT-alias fix | `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` mentioned in pilot10c discussion |
| Engine validator per-engine code | `_snow_explain` в `tools/remote_scripts/_phase27_snow_runner.py:113-139`; `_bq_dry_run` в `repo/src/evaluation/spider2_candidate_factory_v18.py` |
| Phase 28 connect_fail incident | `colab_session_bringup.md` §2a; runtime conversation log |
| CHESS validator approach | research dossier §4 |
| ReFoRCE self-refinement | research dossier §4 |
