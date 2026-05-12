# 08.06 — snow_dialect_fixer_v28.py

## Покрытие модуля

`repo/src/evaluation/snow_dialect_fixer_v28.py` (~224 LOC) — **Phase 28 dialect post-processor** для Snow lane. Содержит **две** top-level функции:

| Function | Purpose | Status в pipeline |
|---|---|---|
| `fix_mixedcase_quoting(sql, allowed_cols_upper)` | F2a — uppercase quoted lowercase identifier-ов | **REVERTED — kept in source for record, NOT called в pipeline** |
| `wrap_date_fn_on_nondate(sql, col_types)` | F4 — wrap NUMBER/VARIANT column inside date-fn → cast to DATE | **Active (Phase 28 closure)** |

Inputs (F4): `(sql: str, col_types: dict[str.upper() → str])`. Output: `(fixed_sql, {'wrapped_n': int})`.

Hooked в pipeline: runner calls `fixer.wrap_date_fn_on_nondate(sql, col_types)` **после** `guard.guard_and_fix_snow_sql` (Phase 27 F1) и **перед** schema_valid + EXPLAIN.

## Context: F2a reverted methodological story

F2a was originally based на hypothesis «Snow catalog stores identifiers UPPERCASE → model emits lowercase quoted → mismatch». Phase 28 catalog probe direct showed: PUBLICATIONS table в Spider2-Snow PATENTS stores **37/37 columns в lowercase**. Hypothesis falsified. F2a auto-upper actively destroyed legitimately-correct lowercase refs (e.g., sf_bq211 `"p"."family_id"` → `"p"."FAMILY_ID"` → invalid_identifier).

F2a function **остаётся** в module для:
- Historical record (commit history shows it was tried),
- Documenting the methodological lesson (in this file's "Known limitations" + main thesis [04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md)),
- Possible future use if a Snow corpus is encountered with actual uppercase storage.

В pipeline (`tools/remote_scripts/_phase27_snow_runner.py` lines 496-516 post-revert) — call site **deleted**. Only `wrap_date_fn_on_nondate` called.

## Code walkthrough

### Excerpt 1 — Module docstring (lines 1-19)

```python
"""snow_dialect_fixer_v28 — Phase 28 F2a + F4 post-passes on candidate Snow SQL.

Runs after the F1 catalog guard (snow_identifier_guard_v27), before EXPLAIN.

Two passes, applied in order:

  fix_mixedcase_quoting(sql, allowed_cols_upper) -> (sql, info)
    Upper-cases the .name of any quoted Identifier whose lowercase form
    is not in the catalog but whose uppercase form is. Snow treats "COL"
    (uppercase quoted) and COL (unquoted) as the same identifier, so the
    rewrite fixes lowercase-quoted column refs while leaving aliases and
    mixed-case-by-design identifiers untouched.

  wrap_date_fn_on_nondate(sql, col_types) -> (sql, info)
    Finds Column nodes inside date-function calls (EXTRACT, DATE_TRUNC,
    DATE_PART, YEAR, MONTH, DAY, DATEADD, DATEDIFF) whose declared type
    is NUMBER or VARIANT and wraps them: NUMBER -> TO_DATE(TO_VARCHAR(x),
    'YYYYMMDD'); VARIANT -> x::DATE. Trade-off: the YYYYMMDD format is
    a Spider2-patent-dataset assumption.
"""
```

**Note**: docstring describes both functions assuming both в pipeline. **Post-Phase-28 revert** — only F4 active. Docstring оставлен для polished documentation of original Phase 28 attempt.

### Excerpt 2 — F2a function (lines 24-70, REVERTED but kept)

```python
def fix_mixedcase_quoting(sql: str, allowed_cols_upper: set) -> tuple:
    """F2a: drop case-sensitive lowercase quotes on identifiers whose
    UPPER form is a real catalog column.

    `allowed_cols_upper` should be the set of all catalog column names
    in this task's TABLE_CATALOG, uppercased.
    """
    if not sql:
        return sql, {'requoted_n': 0}

    import sqlglot
    from sqlglot import exp, errors as sg_errors

    try:
        ast = sqlglot.parse_one(sql, read='snowflake')
    except sg_errors.ParseError:
        return sql, {'requoted_n': 0, 'skipped': 'parse_error'}
    if ast is None:
        return sql, {'requoted_n': 0, 'skipped': 'parse_none'}

    # Build the "do not touch" set: SELECT-clause aliases + table aliases
    # + CTE names. These were declared in the query, not the catalog.
    protected = set()
    for a in ast.find_all(exp.Alias):
        nm = a.alias_or_name
        if nm: protected.add(nm.upper())
    for a in ast.find_all(exp.TableAlias):
        nm = a.name if hasattr(a, 'name') else None
        if nm: protected.add(nm.upper())
    for c in ast.find_all(exp.CTE):
        nm = c.alias_or_name
        if nm: protected.add(nm.upper())

    requoted = 0
    for ident in ast.find_all(exp.Identifier):
        if not ident.args.get('quoted'):
            continue
        name = ident.name
        if not name or name == name.upper():
            continue  # already uppercase or empty
        upper = name.upper()
        if upper in protected:
            continue  # alias or CTE — leave as written
        if upper in allowed_cols_upper:
            ident.set('this', upper)
            requoted += 1

    return ast.sql(dialect='snowflake', identify=True), {'requoted_n': requoted}
```

**Что не работало**: function **correctly implemented** против its contract — it upper-cases quoted lowercase identifiers whose `.upper()` is in `allowed_cols_upper`. The **contract was wrong**: catalog stores lowercase, не uppercase. So `allowed_cols_upper` built as `{c.upper() for c in catalog}` matched `family_id.upper() == 'FAMILY_ID'`, but actual catalog column is `family_id` literal. Setting identifier to `FAMILY_ID` → Snow doesn't find it.

**Protected set** (lines 47-55): SELECT alias / TableAlias / CTE name **always preserved**. Correct design — alias names should never get touched. Empirically верный — F2a tests passed на synthetic synthetic data because tests used `allowed_cols_upper = {'COUNTRY', 'FAMILY_ID'}` assuming catalog upper.

**Critical lesson** (см. main story в [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md)): **synthetic unit tests passed**, real data revealed contract mismatch. Code correctness ≠ semantic correctness.

### Excerpt 3 — F4 function setup + AST parsing (lines 73-101)

```python
def wrap_date_fn_on_nondate(sql: str, col_types: dict) -> tuple:
    """F4: wrap Column args inside date-function calls when the column's
    declared type is NUMBER or VARIANT.

    `col_types` maps UPPERCASE column name -> declared DATA_TYPE
    (e.g. 'NUMBER(38,0)', 'VARIANT', 'TIMESTAMP_NTZ', 'DATE').
    """
    if not sql:
        return sql, {'wrapped_n': 0}

    import sqlglot
    from sqlglot import exp, errors as sg_errors

    try:
        ast = sqlglot.parse_one(sql, read='snowflake')
    except sg_errors.ParseError:
        return sql, {'wrapped_n': 0, 'skipped': 'parse_error'}
    if ast is None:
        return sql, {'wrapped_n': 0, 'skipped': 'parse_none'}

    # Snowflake dialect: DATE_PART is parsed as exp.Extract; DATE_TRUNC
    # as exp.TimestampTrunc. Cover both.
    date_fn_types = (exp.Extract, exp.DateTrunc, exp.DateAdd, exp.DateDiff,
                     exp.DateSub, exp.Year, exp.Month, exp.Day)
    if hasattr(exp, 'TimestampTrunc'):
        date_fn_types = date_fn_types + (exp.TimestampTrunc,)
    if hasattr(exp, 'DatePart'):
        date_fn_types = date_fn_types + (exp.DatePart,)
```

**Что критично** (line 96-99): **conditional addition** of `TimestampTrunc` and `DatePart`. Different SQLGlot versions may or may not have these classes. `hasattr` check protects against AttributeError. Не fails если old SQLGlot installed (degrades gracefully — DATE_TRUNC won't be caught).

**Critical empirical finding (Phase 28 debugging)**: in Snowflake dialect SQLGlot parses `DATE_TRUNC('MONTH', col)` as **`exp.TimestampTrunc`**, NOT `exp.DateTrunc`. Я initially had `(exp.Extract, exp.DateTrunc, …)` → DATE_TRUNC missed. Diagnostic:

```python
ast = sqlglot.parse_one("SELECT DATE_TRUNC('MONTH', col) FROM T", read='snowflake')
print(repr(ast))
# Output revealed: TimestampTrunc(this=Column(...), unit=Var(...), input_type_preserved=True)
```

Lesson: **all dialect-aware AST manipulation requires extensive testing against actual SQLGlot output**, not just nominal docs.

### Excerpt 4 — F4 target collection + replacement (lines 102-128)

```python
    targets = []  # (col_node, action)
    for fn in ast.find_all(*date_fn_types):
        for col in fn.find_all(exp.Column):
            cn = (col.name or '').upper()
            if not cn:
                continue
            t = (col_types.get(cn) or '').upper()
            if not t:
                continue
            if t.startswith('NUMBER'):
                targets.append((col, 'number'))
            elif t == 'VARIANT':
                targets.append((col, 'variant'))

    wrapped = 0
    for col, kind in targets:
        if col.parent is None:
            continue
        if kind == 'number':
            inner_varchar = exp.func('TO_VARCHAR', col.copy())
            wrapper = exp.func('TO_DATE', inner_varchar, exp.Literal.string('YYYYMMDD'))
        else:  # variant
            wrapper = exp.Cast(this=col.copy(), to=exp.DataType.build('DATE'))
        col.replace(wrapper)
        wrapped += 1

    return ast.sql(dialect='snowflake', identify=True), {'wrapped_n': wrapped}
```

**Что критично**:

**Two-pass approach** — collect targets first (lines 102-115), then mutate (lines 117-128). Why: mutating AST while iterating `find_all` results может break iteration (или silently miss subsequent nodes). Collect targets-first pattern — safe общая practice.

**`col.copy()` (lines 121, 124)**: deep copy of Column node before wrap. Otherwise the same node would be referenced from old place AND wrapper — broken AST structure.

**Two wrap strategies**:
- **NUMBER**: `TO_DATE(TO_VARCHAR(col), 'YYYYMMDD')`. Format `'YYYYMMDD'` is **Spider2-patent-dataset assumption** — many patent columns store dates as `20231215` integer.
- **VARIANT**: `col::DATE` via `exp.Cast(this=col, to=DataType.build('DATE'))`. SQLGlot emits as `CAST(col AS DATE)`.

**`col.parent is None` check** (line 119): defensive against orphaned column reference. Может happen после CTE rewriting. Practically rare, но защита.

**`col_types.get(cn)`**: keyed by UPPERCASE column name. `col.name.upper()` for lookup. Это makes it lane-агностично — col_types prepared с upper keys, SQL emitter may emit lowercase or upper, matches both.

### Excerpt 5 — Embedded self-tests (lines 132-220)

```python
if __name__ == '__main__':
    import sys
    failures = 0

    # F2a tests
    print('=== F2a fix_mixedcase_quoting ===')
    allowed = {'COUNTRY', 'DATE', 'CITATION', 'ASSIGNEE', 'PUBLICATION_DATE',
                'PUBLICATIONS', 'PATENTS', 'GRANT_DATE'}

    cases_f2a = [
        ('mixed_case_col_quoted',
         'SELECT "p"."country" FROM "PATENTS"."PATENTS"."PUBLICATIONS" AS "p"',
         allowed, 'COUNTRY'),
        ('select_alias_protected',
         'SELECT FLOOR("p"."grant_date"/5)*5 AS "five_year_period" '
         'FROM "PATENTS"."PATENTS"."PUBLICATIONS" AS "p" '
         'ORDER BY "five_year_period"',
         allowed, 'GRANT_DATE'),
        ('already_uppercase_noop',
         'SELECT "COUNTRY" FROM "PATENTS"."PATENTS"."PUBLICATIONS"',
         allowed, 'COUNTRY'),
        ('not_in_pack_left_alone',
         'SELECT "p"."unknown_col" FROM "PATENTS"."PATENTS"."PUBLICATIONS" AS "p"',
         allowed, 'unknown_col'),
    ]
    # ... validation logic

    # F4 tests
    print('\n=== F4 wrap_date_fn_on_nondate ===')
    col_types = {
        'PUBLICATION_DATE': 'NUMBER(38,0)',
        'GRANT_DATE': 'NUMBER(38,0)',
        'FTERM': 'VARIANT',
        'NORMAL_DATE': 'DATE',
    }

    cases_f4 = [
        ('extract_on_number', ...),
        ('date_trunc_on_number', ...),
        ('extract_on_variant', ...),
        ('extract_on_date_noop', ...),
        ('extract_on_qualified_lowercase', ...),
        ('extract_on_qualified_uppercase', ...),
    ]
    # ... runs cases, reports failures
```

**11 total tests** (4 F2a + 6 F4 + 1 combined order). **All pass** при последнем run. Critical: F2a tests passed на synthetic catalog → **misleading green signal** that contract correct. Real catalog probe later revealed wrong contract.

## Design decisions, видные в code

### D1. `try/except` skip patterns on ParseError (lines 87-92, 39-42)
Both functions защищены: если SQLGlot can't parse, skip без crash. Returns `{'skipped': 'parse_error'}` flag for diagnostic. Downstream pipeline продолжает с un-modified SQL.

### D2. `hasattr(exp, 'TimestampTrunc')` (line 97)
Conditional class detection. SQLGlot version-stable behavior.

### D3. Collect targets, then mutate (two-pass)
Avoid concurrent modification.

### D4. `col.copy()` before wrap
Deep copy preserves AST integrity.

### D5. F4 keyed by `col.name.upper()` not full path
Means `"p"."publication_date"` (table-qualified) also matches `publication_date` in col_types. Robust к qualified vs bare column refs.

### D6. F2a kept in source despite revert
Documents the explored & rejected hypothesis. Removing it would erase methodological record.

## Edge cases handled

- **Empty SQL**: F2a + F4 both early-return.
- **SQLGlot ParseError**: graceful skip с `'skipped': 'parse_error'` flag.
- **`ast is None`**: graceful skip с `'skipped': 'parse_none'`.
- **Column without name** (synthetic AST corner): line 105 `if not cn: continue`.
- **Column with no parent** (orphan from prior edit): line 119 `if col.parent is None: continue`.
- **Type info absent for column**: line 109 `if not t: continue` — leave SQL alone.
- **`TimestampTrunc` missing in SQLGlot version**: line 97 conditional — DATE_TRUNC silently un-wrapped if class missing.

## Test coverage

**11 self-tests** embedded в module. Runnable as `python repo/src/evaluation/snow_dialect_fixer_v28.py`. **All pass** на latest commit `ad5493b`.

Coverage summary:
- F2a: mixed-case, alias-protected, already-upper noop, not-in-pack noop. **4/4 pass.**
- F4: NUMBER extract, NUMBER date_trunc, VARIANT extract, DATE no-op, qualified lowercase, qualified uppercase. **6/6 pass.**
- Combined order: F2a + F4 on same SQL. **1/1 pass.**

**Same critique as F2a**: tests confirm **code correctness against intended contract**, не verify **contract correctness against real catalog**. Phase 28 closure §6 catalog probe — the missing test.

## Known limitations

| # | Limitation | Impact | Mitigation |
|---|---|---|---|
| L1 | F2a contract empirically wrong (catalog stores lowercase) | F2a auto-upper destroys correct refs | **Reverted** — function kept but not called |
| L2 | F4 NUMBER→YYYYMMDD assumes patent-dataset convention | Other NUMBER-stored date formats (Unix timestamp, YYYYMM only) not handled | Phase 29 — F3 self-refine catches via engine error retry |
| L3 | F4 VARIANT→DATE assumption: VARIANT contains date | На VARIANT holding JSON object (e.g., `assignee` in PATENTS) — wrong wrap | sf_bq091 case: GET_PATH(CAST(assignee AS DATE), 'assignee_date') fails — Phase 29 F3 |
| L4 | F4 skips DATE_TRUNC on SQLGlot versions lacking TimestampTrunc | Silently degrades | Document SQLGlot version requirement |
| L5 | F4 doesn't recurse into nested function calls beyond `find_all` | OK для practice — date functions rarely deep-nest | None needed |
| L6 | No integration test catching wrong contract | Phase 28 F2a regression | Lesson: catalog probe required before deploying dialect heuristic |

## Evolution history

| Phase | Change |
|---|---|
| **Phase 28 (initial — REGRESSION)** | F2a + F4 both implemented and called from pipeline. pilot10 v28 result: exec 1/10 → 0/10. |
| **Phase 28 (catalog probe §6)** | Empirical falsification of F2a hypothesis. 37/37 PATENTS PUBLICATIONS columns lowercase. |
| **Phase 28 closure (revert-A)** | F2a call site removed from runner. F4 retained. pilot10 v28-revert-A result: exec 0/10 → **4/10**. |
| **Current state (commit `ad5493b`)** | Both functions в source. Only `wrap_date_fn_on_nondate` called. F2a kept as documented dead-code. |

Module — stable since Phase 28 closure. 224 LOC, 11/11 tests pass.

## Cross-references

- Architecture description: [04_ARCHITECTURE/09_dialect_handlers_f1_f4.md](../04_ARCHITECTURE/09_dialect_handlers_f1_f4.md) (full F1+F4+F4c+reverted-F2a context)
- Companion module: [05_snow_identifier_guard_v27.md](./05_snow_identifier_guard_v27.md)
- Phase 28 F2a story: [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md)
- Catalog probe methodology (Claim 3): [01_INTRODUCTION/04_thesis_contributions.md](../01_INTRODUCTION/04_thesis_contributions.md)
- Pack builder (col:TYPE rendering supports F4): [01_schema_pack_builder_v18.md](./01_schema_pack_builder_v18.md)
- Runner integration: [08_runner_orchestration.md](./08_runner_orchestration.md)

## Источники

| Утверждение | Источник |
|---|---|
| Module structure | `repo/src/evaluation/snow_dialect_fixer_v28.py` |
| 37/37 lowercase catalog finding | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §6 |
| Pilot10 exec 1/10 → 0/10 (F2a active) | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §3 |
| Pilot10 exec 0/10 → 4/10 (F2a reverted) | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §10 |
| sf_bq091 VARIANT over-cast | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §10 per-task table |
| TimestampTrunc empirical finding | conversation log during Phase 28 development |
| 11/11 self-tests pass | run output of `python repo/src/evaluation/snow_dialect_fixer_v28.py` |
