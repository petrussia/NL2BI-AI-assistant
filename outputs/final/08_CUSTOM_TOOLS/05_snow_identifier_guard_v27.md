# 08.05 — snow_identifier_guard_v27.py

## Покрытие модуля

`repo/src/evaluation/snow_identifier_guard_v27.py` (~172 LOC) — **Phase 27 F1 dialect handler** для Snow lane. Walks SQL AST через SQLGlot, rejects identifier-leak SQL (`exp.Table.catalog ∉ {task_db}`), auto-fills missing catalog с `task_db`. Phase 28 добавил **F4c regex fallback** на SQLGlot ParseError.

Главные экспорты:

| Symbol | Purpose |
|---|---|
| `IdentifierLeakError(Exception)` | raised on foreign-catalog ref OR на сложных parse errors не-recoverable через regex |
| `_regex_catalog_leak_check(sql, allowed)` | F4c fallback — regex-based leak detection когда SQLGlot fails to parse |
| `guard_and_fix_snow_sql(sql, task_db, allowed_dbs=None)` | main entry — returns `(fixed_sql, info_dict)` или raises `IdentifierLeakError` |

Inputs: `(sql, task_db, allowed_dbs?)`. Outputs: `(fixed_sql, {'rewrote_n': int, 'leaked_catalogs': list, 'fallback'?: 'regex_only', 'parse_error'?: str})` или raises.

Hooked в pipeline: runner calls `guard.guard_and_fix_snow_sql(sql, task_db)` после selector chose candidate, перед `wrap_date_fn_on_nondate` и engine EXPLAIN.

## Code walkthrough

### Excerpt 1 — Main function header + early parse + F4c fallback (lines 36-58)

```python
def guard_and_fix_snow_sql(sql: str, task_db: str,
                           allowed_dbs: set | None = None) -> tuple:
    """Parse SQL as Snowflake dialect.
    - If any exp.Table has catalog NOT in allowed_dbs (default: {task_db}),
      raise IdentifierLeakError.
    - If exp.Table has no catalog, fill it from task_db.
    Returns (fixed_sql, {"rewrote_n": int, "leaked_catalogs": []}).
    """
    if not sql:
        raise IdentifierLeakError('empty_sql')

    import sqlglot
    from sqlglot import exp, errors as sg_errors

    allowed = {d.upper() for d in (allowed_dbs or {task_db})}
    try:
        ast = sqlglot.parse_one(sql, read='snowflake')
    except sg_errors.ParseError as e:
        # Phase 28 F4c: SQLGlot snowflake dialect has known gaps
        # (TABLE(LATERAL FLATTEN(...)), GENERATOR, some MERGE forms).
        # Don't fail-closed on a parser limitation — do a regex-only
        # catalog leak check and pass the SQL through unchanged.
        leaked = _regex_catalog_leak_check(sql, allowed)
        if leaked:
            raise IdentifierLeakError(
                f'catalog_leak:{sorted(set(leaked))} not in allow-list {sorted(allowed)}'
            )
        return sql, {'rewrote_n': 0, 'leaked_catalogs': [], 'fallback': 'regex_only',
                     'parse_error': f'{type(e).__name__}:{str(e)[:120]}'}
```

**Что критично**: lines 43-58 — **F4c fallback** (Phase 28). Previously (Phase 27), exception handler был `except Exception: raise IdentifierLeakError('parse_error_sqlglot:...')`. Это **fail-closed** — wholly valid Snow SQL отбрасывался если SQLGlot не может parse.

Empirical failure: sf_bq210 на pilot10c содержал `TABLE(LATERAL FLATTEN(INPUT => p.claims_localized))` — valid Snow construct, но SQLGlot snowflake parser fails. Pre-Phase-28 — task marked `parse_error_guard`. Post-Phase-28 F4c — falls back на regex check, passes если no foreign catalog found, далее reaches real Snow EXPLAIN.

**Phase 28 F4c код в action**:
- `except sg_errors.ParseError`: catch только ParseError (not generic Exception — narrow).
- `_regex_catalog_leak_check(sql, allowed)`: regex-based leak check.
- Если no leak: return SQL unchanged with `fallback='regex_only'` flag в info.
- Если leak detected: raise normally.

### Excerpt 2 — `_regex_catalog_leak_check` helper (lines 23-32)

```python
def _regex_catalog_leak_check(sql: str, allowed: set) -> list:
    """Find FROM/JOIN <ident>.<ident>.<ident> three-part references and
    return any first-segment catalog names that are not in `allowed`.
    Used as fallback when sqlglot parsing fails.
    """
    import re
    pattern = r'(?:FROM|JOIN)\s+"?([A-Za-z_][A-Za-z0-9_]*)"?\s*\.\s*"?[A-Za-z_][A-Za-z0-9_]*"?\s*\.'
    return [c for c in re.findall(pattern, sql, re.IGNORECASE)
            if c.upper() not in allowed]
```

**Что критично**: regex captures `FROM <catalog>.<schema>.<table>` или `JOIN <catalog>.<schema>.<table>`. Optionally quoted с `"`. Returns list of catalog names NOT in allowed set.

**Design rationale**: simple lexical regex captures the **vast majority** of cross-DB drift cases. Real SQL containing `OTHER_DB.SCHEMA.T` в FROM/JOIN clause — easily detected. **Не detects**:
- Identifiers в WHERE subqueries (e.g., `WHERE id IN (SELECT … FROM OTHER_DB.…)`) — limitation we accept; falls back на full AST guard when SQLGlot parses OK. Если SQLGlot fails on subquery sql, our regex misses subquery leak.
- Catalog identified via session context (`USE DATABASE OTHER_DB; SELECT FROM t`) — but Snow runner explicitly does `USE DATABASE task_db` before EXPLAIN, so this scenario не occurs.

### Excerpt 3 — Normal path: parsed AST walk (lines 60-86)

```python
    if ast is None:
        raise IdentifierLeakError('parse_returned_none')

    # Collect CTE names first — Tables referencing a CTE should NOT have
    # a catalog filled (would break the CTE resolution).
    cte_names = set()
    for cte in ast.find_all(exp.CTE):
        nm = cte.alias_or_name
        if nm:
            cte_names.add(nm.upper())

    rewrote = 0
    leaked = []
    for t in ast.find_all(exp.Table):
        cat = t.args.get('catalog')
        if cat is not None:
            cat_name = cat.name if hasattr(cat, 'name') else str(cat)
            if cat_name.upper() not in allowed:
                leaked.append(cat_name)
        else:
            # Skip CTE references — they're aliases not real tables
            tname = t.name
            if tname and tname.upper() in cte_names:
                continue
            t.set('catalog', exp.to_identifier(task_db, quoted=False))
            rewrote += 1

    if leaked:
        raise IdentifierLeakError(
            f'catalog_leak:{sorted(set(leaked))} not in allow-list {sorted(allowed)}'
        )

    return ast.sql(dialect='snowflake', identify=True), {
        'rewrote_n': rewrote,
        'leaked_catalogs': [],
    }
```

**Что критично**:

**CTE awareness** (lines 64-69, 78-80): before walking exp.Table, collect CTE names from `find_all(exp.CTE)`. Then when processing `exp.Table` without catalog, **skip if name matches CTE name**. Without this, `WITH a AS (SELECT * FROM ...) SELECT * FROM a` would have its `FROM a` reference auto-filled to `PATENTS.a` — completely broken.

**Two-branch logic** per table:
- `cat is not None`: catalog explicitly given by emitter. Check membership in allowed. If not in — append to leaked list. **Don't raise immediately** — continue collecting all leaks for comprehensive error message.
- `cat is None`: no catalog. Skip if CTE reference; else auto-fill `task_db`.

**`exp.to_identifier(task_db, quoted=False)`** — produces unquoted identifier node. Important: unquoted, so when re-emitted с `identify=True`, becomes `"task_db"` (quoted uppercase by default Snow behavior). Snow treats `"PATENTS"` == `PATENTS` (case-insensitive resolution for canonical uppercase).

**`ast.sql(dialect='snowflake', identify=True)`** (line 84): re-emit с **all identifiers quoted**. Это design choice — even original unquoted refs come out quoted. Empirically — `"PUBLICATIONS"` works на Snow (PUBLICATIONS table stored uppercase) и `"family_id"` works (column stored lowercase, exact-case match). identifier=True ensures we always handle case correctly through quoting.

## Design decisions, видные в code

### D1. Narrow `except sg_errors.ParseError` (line 44)
Phase 28 F4c distinguishes ParseError из other exceptions. Если SQLGlot crashes for other reason (e.g., import error, mem error) — we want to surface that, not silently fall back.

### D2. Two-pass approach: collect leaks first, then raise (lines 72-83)
Don't raise on first leak — collect all → raise with **comprehensive list**. Better diagnostic: emitter outputs 3 wrong catalogs, error message lists все три. Easier debugging.

### D3. `not in allowed` uses `.upper()` (line 67)
Catalog names compared uppercase. Snow canonical form (unquoted identifiers folded to upper). Avoid case mismatch на comparison.

### D4. `quoted=False` for `to_identifier`
Don't force quoting style. SQLGlot's `identify=True` on `.sql()` adds quotes at emit. Двойная ответственность separated cleanly.

### D5. Self-test embedded в module (lines 88-140)
Module ends с `if __name__ == '__main__':` self-test block — 8 cases covering all branches. Runnable as `python snow_identifier_guard_v27.py`.

### D6. Module-level docstring (lines 1-14)
Explicit purpose statement, design rationale, return contract. Easy for downstream maintenance.

## Edge cases handled

- **Empty SQL** (line 36-37): early-raise.
- **Parse returns None** (line 60-61): rare but possible (e.g., SQL = `";"`); raise explicit.
- **CTE references** (lines 64-69, 78-80): skip catalog autofill.
- **SQLGlot ParseError** (lines 43-58): F4c regex fallback.
- **Quoted identifiers**: regex handles `"X"` form в `_regex_catalog_leak_check`.
- **Multiple leaks** in one query (e.g., 2 different foreign catalogs): collected, single comprehensive error.

## Test coverage

**Embedded self-test** (lines 88-140) — **8 unit cases**:

| Test | Input snippet | Expected outcome |
|---|---|---|
| `three_part_correct` | `FROM GITHUB_REPOS.GITHUB.COMMITS WHERE a=1` | rewrote_n=0, no leak |
| `two_part_fill` | `FROM GITHUB.COMMITS` | rewrote_n=1 (autofill catalog) |
| `one_part_fill` | `FROM COMMITS` | rewrote_n=1 |
| `foreign_catalog_leak` | `FROM FINANCE__ECONOMICS.CYBERSYN.SEC_REPORTS` | raises (leaked: `FINANCE__ECONOMICS`) |
| `cte_and_join` | `WITH a AS (SELECT * FROM ...) SELECT * FROM a JOIN ...` | rewrote_n=2 (only real tables autofilled, CTE `a` skipped) |
| `subquery_leak` | `FROM PATENTS.PATENTS.PUBLICATIONS WHERE id IN (SELECT id FROM BAD_DB.SCHEMA.T)` | raises (subquery leak detected by AST walk) |
| **`lateral_flatten_fallback`** (Phase 28) | `... TABLE(LATERAL FLATTEN(INPUT => p.x))` | pass-through (regex clean) with `fallback='regex_only'` |
| **`lateral_flatten_with_leak`** (Phase 28) | + foreign catalog ref | raises (regex catches) |

**All 8 tests pass**. Test runnable as standalone:

```bash
python repo/src/evaluation/snow_identifier_guard_v27.py
# Outputs: OK <test_label>: rewrote_n=... fixed=...
# Final: ALL TESTS PASS
```

This is the **only module в codebase** с complete embedded test suite — testimony to its critical role в Phase 27 F1 stack.

## Known limitations

| # | Limitation | Impact | Mitigation |
|---|---|---|---|
| L1 | SQLGlot snowflake parser fails on LATERAL FLATTEN | F4c fallback regex used | F4c fallback adequate; long-term — upgrade SQLGlot |
| L2 | Regex fallback misses subquery leaks | Pre-Phase-28 fail-closed gave 100% rejection (which was wrong for valid SQL); now post-Phase-28 fail-open misses some subquery leaks (acceptable trade) | Phase 30: better SQLGlot version or LLM-based parser |
| L3 | Cannot detect catalog from session context | Rare — Snow runner sets `USE DATABASE task_db` explicitly | Trade-off acceptable for current use |
| L4 | Auto-fill always uses task_db, не selects best schema | If задача spans multiple schemas — emitter has to qualify with schema explicitly | Pack rendering shows 3-part names; emitter trained on that |

## Evolution history

| Phase | Change |
|---|---|
| **Phase 27 STAGE F1** | **Initial implementation**. CTE-aware walk, autofill catalog, raise on foreign catalog. 6 self-tests. |
| **Phase 28** | **F4c regex fallback** added. New `_regex_catalog_leak_check` helper. Replaces `except Exception → raise IdentifierLeakError('parse_error_sqlglot')` с `except sg_errors.ParseError → regex check → pass through if clean`. Added 2 self-tests (`lateral_flatten_fallback`, `lateral_flatten_with_leak`). |

Module — **stable since Phase 28 closure** (commit `ad5493b`). 172 LOC, 8/8 tests pass.

## Cross-references

- Architecture description: [04_ARCHITECTURE/09_dialect_handlers_f1_f4.md](../04_ARCHITECTURE/09_dialect_handlers_f1_f4.md)
- Snow dialect fixer (next stage в pipeline): [06_snow_dialect_fixer_v28.md](./06_snow_dialect_fixer_v28.md)
- Pack builder (provides allowed catalog): [01_schema_pack_builder_v18.md](./01_schema_pack_builder_v18.md)
- Phase 27 F1 narrative: [06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md](../06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md)
- Phase 28 F4c narrative: [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md)
- Validator suite (uses output): [04_validators_suite.md](./04_validators_suite.md)

## Источники

| Утверждение | Источник |
|---|---|
| Module structure | `repo/src/evaluation/snow_identifier_guard_v27.py` |
| F4c regex fallback added Phase 28 | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §2 |
| 8/8 self-tests pass | run output of `python repo/src/evaluation/snow_identifier_guard_v27.py` |
| Phase 27 F1 introduction | `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` §2(b) |
| sf_bq210 LATERAL FLATTEN — was rejected pre-Phase-28 | `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` §4 |
