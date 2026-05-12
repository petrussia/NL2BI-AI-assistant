# 08.04 — Validators suite (structured_plan_v18 + AST + engine validators)

## Покрытие модулей

Три тесно связанные validator-а, разнесённые по нескольким файлам:

| Layer | File | Function | Stage |
|---|---|---|---|
| **L1 JSON Schema** | `repo/src/evaluation/structured_plan_v18.py` | `parse_plan(raw)` + `validate_plan(plan, pack)` | post-planner |
| **L2 AST closed-set** | inline `_snow_schema_valid_ast` в `tools/remote_scripts/_phase27_snow_runner.py`; BQ analog в `repo/src/evaluation/spider2_candidate_factory_v18.py` | per-candidate, после factories | post-emitter, pre-engine |
| **L3 Engine** | `_snow_explain` (Snow), `_bq_dry_run` (BQ), `sqlite3.cur.execute` (SQLite) | final SQL run | last |

Inputs per layer:
- L1: `raw: str` (planner output) → `(plan: PlanCandidate, validation: Validation)`.
- L2: `(sql: str, pack: dict, extra_allowed_cols?: set)` → `(ok: bool, error_msg: str)`.
- L3: `(sql: str, engine context)` → `(ok: bool, error_class: str, error_msg: str)`.

Hooked в pipeline: sequential через runner. L1 first (validates planner output), then per-candidate L2 (validates each emitted SQL), then L3 (engine confirms).

## Code walkthrough

### L1 — JSON Schema validator (`structured_plan_v18.py`)

```python
@dataclass
class PlanCandidate:
    selected_database: str
    selected_schema: str
    selected_tables: list[str]
    selected_columns: list[str]
    metrics: list[dict] = field(default_factory=list)
    filters: list[dict] = field(default_factory=list)
    time_constraints: list[str] = field(default_factory=list)
    grouping: list[str] = field(default_factory=list)
    sorting: list[dict] = field(default_factory=list)
    limit: Optional[int] = None
    ambiguity_points: list[str] = field(default_factory=list)
    expected_shape: str = ''


@dataclass
class Validation:
    ok: bool
    reasons: list = field(default_factory=list)


def parse_plan(raw: str) -> PlanCandidate:
    """Robust JSON extraction from planner output.
    Tries:
      1. Direct json.loads(raw)
      2. ```json ... ``` block extraction
      3. First balanced {...} block extraction
    Raises ValueError if no valid plan.
    """
    # 1. direct
    try: return PlanCandidate(**_clean(json.loads(raw)))
    except Exception: pass
    # 2. ```json ... ```
    m = re.search(r'```(?:json)?\s*\n?([\s\S]*?)```', raw, re.IGNORECASE)
    if m:
        try: return PlanCandidate(**_clean(json.loads(m.group(1))))
        except Exception: pass
    # 3. first balanced { ... }
    start = raw.find('{')
    if start >= 0:
        depth = 0
        for i in range(start, len(raw)):
            if raw[i] == '{': depth += 1
            elif raw[i] == '}':
                depth -= 1
                if depth == 0:
                    try: return PlanCandidate(**_clean(json.loads(raw[start:i+1])))
                    except: break
                    break
    raise ValueError('no valid JSON plan found')
```

**Что критично**: ladder of extraction strategies. Coder-30B-A3B sometimes wraps output in ` ```json ` block, sometimes outputs raw JSON, sometimes prepends "Here is the plan:" text. Robust extraction necessary.

`_clean(d)` — utility что normalizes field types (e.g., `limit` may come as string "10" → int).

### L1 — `validate_plan`

```python
def validate_plan(plan: PlanCandidate, pack: dict) -> Validation:
    """AST validator at plan level. Checks:
    1. selected_tables ⊆ pack.tables[*].table
    2. selected_columns + columns inside expressions ⊆ pack.tables[*].all_columns
    3. expressions parse via SQLGlot
    4. selected_database, selected_schema appear in pack.databases
    Returns Validation(ok, reasons) — reasons used for retry feedback.
    """
    reasons = []
    pack_tables = {t['table'] for t in pack['tables']}
    pack_cols = set()
    for t in pack['tables']:
        for c in t.get('all_columns', []):
            pack_cols.add(c)
        for c in t.get('columns', []):
            pack_cols.add(c['name'])
    
    # Check selected_tables
    for tbl in plan.selected_tables:
        bare = tbl.split('.')[-1] if '.' in tbl else tbl
        if bare not in pack_tables:
            reasons.append(f"unknown table: {tbl}")
    
    # Check selected_columns
    for col in plan.selected_columns:
        bare = col.split('.')[-1] if '.' in col else col
        if bare not in pack_cols:
            reasons.append(f"unknown column: {col}")
    
    # Parse metric/filter/sorting expressions via SQLGlot
    for m in plan.metrics:
        try: sqlglot.parse_one(m.get('expr', ''), read='bigquery')
        except: reasons.append(f"metric expr unparseable: {m['expr']}")
    for f in plan.filters:
        try: sqlglot.parse_one(f.get('expr', ''), read='bigquery')
        except: reasons.append(f"filter expr unparseable: {f['expr']}")
    
    return Validation(ok=(len(reasons) == 0), reasons=reasons)
```

**Что критично**: simultaneously checks (a) identifier residency, (b) expression syntactic validity. `reasons` returned для downstream retry prompt construction.

### L2 — `_snow_schema_valid_ast` (Snow runner)

```python
def _snow_schema_valid_ast(sql, pack, extra_allowed_cols=None):
    """AST validator на финальном SQL. Closed-set check identifier residency."""
    # Build allow-set
    tables_allowed = {t['table'].upper() for t in pack['tables']}
    cols_allowed = set()
    for t in pack['tables']:
        for c in t.get('all_columns', []) + [c['name'] for c in t['columns']]:
            cols_allowed.add(c.upper())
    if extra_allowed_cols:
        cols_allowed.update(c.upper() for c in extra_allowed_cols)
    
    # Parse SQL
    try: ast = sqlglot.parse_one(sql, read='snowflake')
    except: return (False, 'parse_failed:ParseError')
    
    # SELECT-clause aliases — protected (Phase 28 fix)
    select_aliases = set()
    for al in ast.find_all(exp.Alias):
        a = al.alias_or_name
        if a: select_aliases.add(a.upper())
    cols_allowed |= select_aliases
    
    # Check each Column / Table reference
    unknown_cols = []
    unknown_tables = []
    for col in ast.find_all(exp.Column):
        cn = (col.name or '').upper()
        if cn and cn not in cols_allowed:
            unknown_cols.append(col.name)
    for tab in ast.find_all(exp.Table):
        tn = (tab.name or '').upper()
        if tn and tn not in tables_allowed:
            unknown_tables.append(tab.name)
    
    if unknown_tables or unknown_cols:
        return (False, f"unknown_tables={unknown_tables}, unknown_cols={unknown_cols}")
    return (True, '')
```

**Что критично**:

**`extra_allowed_cols`** — Phase 27 F1 correction 2. На Snow lane validator получает full task_db catalog set, не только pack subset. Расширяет allow-set. Phase 27 measurement: false-positive `schema_invalid` rate dropped с ~40% до minimal.

**SELECT alias protection** (Phase 27 finding): without lines collecting `exp.Alias`, SQL like `SELECT FLOOR(...) AS "five_year_period" ORDER BY "five_year_period"` rejects because `five_year_period` не в catalog cols. Fix — union alias set in cols_allowed.

### L3 — Snow EXPLAIN engine validator

```python
_SNOW_CONN = {}

def _snow_connect():
    """Cache connection per kernel — saves 5-10s per task."""
    if 'main' in _SNOW_CONN:
        try:
            _SNOW_CONN['main'].cursor().execute('SELECT 1').fetchone()
            return _SNOW_CONN['main']
        except Exception:
            del _SNOW_CONN['main']
    import snowflake.connector
    c = snowflake.connector.connect(
        account=os.environ['SNOWFLAKE_ACCOUNT'],
        user=os.environ['SNOWFLAKE_USER'],
        password=os.environ['SNOWFLAKE_PASSWORD'],
        role=os.environ.get('SNOWFLAKE_ROLE') or None,
        warehouse=os.environ.get('SNOWFLAKE_WAREHOUSE') or None,
    )
    _SNOW_CONN['main'] = c
    return c


def _snow_explain(sql, *, db=None, schema=None):
    if not sql:
        return (False, 'empty_sql', '')
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

**Что критично**:

- **Connection caching** (`_SNOW_CONN['main']`): per-kernel module-level dict. `select 1` test before reuse — handles connection drops.
- **`USE DATABASE`/`USE SCHEMA`** — optional context-setting. Snow runner passes `db=task_db` to ensure scope.
- **Error classification** at end: `invalid_identifier` / `syntax_error` / `type_mismatch` / catch-all. Used downstream в `error_taxonomy.csv`.

**Phase 28 incident**: на fresh kernel `SNOWFLAKE_*` env vars not set → `_snow_connect` raises `KeyError('SNOWFLAKE_ACCOUNT')` → all 64 post-restart tasks failed `connect_fail`. Mitigation script `_phase28_s1_fix_snowflake.py` + memory note (`colab_session_bringup.md` §2a).

## Design decisions, видные в code

### D1. Three independent layers, no shared state
JSON / AST / engine validators **don't depend на each other's state**. Each receives input, returns ok/err. Reduces coupling.

### D2. Retry feedback from `validate_plan(...).reasons`
L1 returns `Validation(ok, reasons)`. `reasons` is human-readable list — directly inject в retry prompt:

```python
def _retry_prompt(orig, reasons, last_plan):
    return f"""Your previous response was not valid:
- {'; '.join(reasons)}

Please re-emit valid JSON matching the required schema.
{orig}"""
```

### D3. AST validator `extra_allowed_cols` — lane-specific extension
Без relaxation на Snow false-positive rate ~40%. Это **explicit trade-off**: relaxed validator passes some SQL referencing legitimately-in-catalog но not-in-pack columns; engine catches if SQL semantically wrong.

### D4. Engine validator caches connection
On Snow `_snow_connect()` caches. On BQ `bigquery.Client` reused. Avoid 5-10s connect overhead per task.

### D5. Error class taxonomy at engine validator
Centralized canonical classes (`invalid_identifier`, `syntax_error`, `type_mismatch`, etc.) used downstream `error_taxonomy.csv`. Allows cross-lane failure pattern analysis.

## Edge cases handled

- **No `raw` from planner** (L1): `parse_plan('')` raises `ValueError('no valid JSON plan found')`.
- **Plan field types wrong** (L1 `_clean`): coerces `"limit": "10"` → `limit=10` etc.
- **SQL with unbalanced quotes** (L2 SQLGlot ParseError): returns `(False, 'parse_failed:ParseError')`.
- **Snow connection drop** (L3 `_snow_connect`): re-establishes via `del _SNOW_CONN['main']` + reconnect.
- **`SNOWFLAKE_*` env missing** (L3): `KeyError` → caught by `except Exception` → `connect_fail` class.
- **CTE / wildcard tables** (L2 на Snow): `unknown_tables` returns matched_name; downstream uses for diagnostic.

## Test coverage

| Layer | Tests |
|---|---|
| L1 `parse_plan` | Ad-hoc testing via runner integration. No formal unit tests. |
| L1 `validate_plan` | Same — ad-hoc. |
| L2 `_snow_schema_valid_ast` | Tested via pilot10 traces (each pilot10 run produces validator outcomes per task). No isolated unit tests. |
| L2 BQ analog | Same. |
| L3 `_snow_explain` | Used millions of times in pilot+FULL runs. Empirically robust. |
| L3 `_bq_dry_run` | Same. |
| Connection caching | Phase 26 measurement: cached connection eliminates ~5-10s/task overhead. |

**Technical debt**: no isolated unit tests на validator layers. Integration coverage есть, но refactoring risky.

## Known limitations

| # | Limitation | Impact | Mitigation |
|---|---|---|---|
| L1 | L2 validator skipped if SQLGlot fails to parse | `parse_failed:ParseError` → marked schema_invalid | Phase 28 F4c addresses similar issue в guard; could be extended here |
| L2 | L1 `validate_plan` SQLGlot parsing of metric/filter expr uses 'bigquery' dialect | На Snow lane some valid expressions reject | Lane-specific dialect selection — future improvement |
| L3 | L3 engine validator может lag (network) | Snow EXPLAIN ~0.5-2s per call; aggregate latency on FULL 547 ~9-15min just в EXPLAIN | Acceptable; alternative — batched EXPLAIN, не supported by Snow API |
| L4 | No retry на engine validator transient errors | Network blip → false-failure | Add retry в Phase 31+ |
| L5 | `extra_allowed_cols` relaxation opens FP-of-FN hole | Some valid-against-relaxed-pack SQL fails engine | Acceptable; engine validator final authority |

## Evolution history

| Phase | Change |
|---|---|
| **v18 (Phase 18)** | Initial implementation. JSON Schema + AST closed-set + engine dry_run/EXPLAIN. |
| **Phase 22 STAGE A2** | L2 validator augmented с `pack.all_columns` side-channel. Reduced false-positive schema_invalid. |
| **Phase 27 F1** | L2 `extra_allowed_cols` relaxation added (Snow only). SELECT-alias protection added. |
| **Phase 28** | No core L2 changes. Connection caching pre-existing. |

## Cross-references

- Architecture description: [04_ARCHITECTURE/07_validators_json_ast_engine.md](../04_ARCHITECTURE/07_validators_json_ast_engine.md)
- Planner-emitter decomposition (L1 consumer): [04_ARCHITECTURE/05_planner_emitter_decomposition.md](../04_ARCHITECTURE/05_planner_emitter_decomposition.md)
- Engine specifics (L3): [04_ARCHITECTURE/10_execution_engines.md](../04_ARCHITECTURE/10_execution_engines.md)
- Pack builder (L2 consumer of `all_columns`): [01_schema_pack_builder_v18.md](./01_schema_pack_builder_v18.md)
- Phase 22 A2 narrative: [06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md)
- Phase 27 F1 narrative: [06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md](../06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md)
- Phase 28 connect_fail incident: [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md)

## Источники

| Утверждение | Источник |
|---|---|
| `PlanCandidate`, `validate_plan` | `repo/src/evaluation/structured_plan_v18.py` |
| `_snow_schema_valid_ast` | `tools/remote_scripts/_phase27_snow_runner.py` lines 150-218 |
| `_snow_explain`, `_snow_connect` | `tools/remote_scripts/_phase27_snow_runner.py` lines 94-139 |
| Phase 27 F1 relaxation | `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` §2 corrections |
| Phase 28 connect_fail incident | `colab_session_bringup.md` §2a |
