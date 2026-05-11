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
    a Spider2-patent-dataset assumption. If the value-domain is wrong,
    EXPLAIN rejects and the candidate fails as before.
"""
from __future__ import annotations


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
        # parse-fail SQL is left alone; F4c guard fallback will let it
        # through to EXPLAIN unmodified
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


# ---- self-tests ----
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
         allowed, 'GRANT_DATE'),  # alias five_year_period must remain
        ('already_uppercase_noop',
         'SELECT "COUNTRY" FROM "PATENTS"."PATENTS"."PUBLICATIONS"',
         allowed, 'COUNTRY'),  # zero requote
        ('not_in_pack_left_alone',
         'SELECT "p"."unknown_col" FROM "PATENTS"."PATENTS"."PUBLICATIONS" AS "p"',
         allowed, 'unknown_col'),  # zero requote
    ]
    for label, sql, allowed_cols, must_appear in cases_f2a:
        fixed, info = fix_mixedcase_quoting(sql, allowed_cols)
        n = info.get('requoted_n', 0)
        ok = must_appear in fixed
        # alias case: must_appear is the col name; alias 'five_year_period' must still be quoted lowercase
        if label == 'select_alias_protected':
            ok = ok and '"five_year_period"' in fixed
        if label == 'already_uppercase_noop':
            ok = ok and n == 0
        if label == 'not_in_pack_left_alone':
            ok = '"unknown_col"' in fixed and n == 0
        status = 'OK   ' if ok else 'FAIL '
        print(f'{status} {label}: requoted_n={n} fixed={fixed[:120]!r}')
        if not ok: failures += 1

    # F4 tests
    print('\n=== F4 wrap_date_fn_on_nondate ===')
    col_types = {
        'PUBLICATION_DATE': 'NUMBER(38,0)',
        'GRANT_DATE': 'NUMBER(38,0)',
        'FTERM': 'VARIANT',
        'NORMAL_DATE': 'DATE',  # should NOT be wrapped
    }

    cases_f4 = [
        ('extract_on_number',
         'SELECT EXTRACT(YEAR FROM PUBLICATION_DATE) FROM T', 1, 'TO_DATE'),
        ('date_trunc_on_number',
         'SELECT DATE_TRUNC(\'MONTH\', GRANT_DATE) FROM T', 1, 'TO_DATE'),
        ('extract_on_variant',
         'SELECT EXTRACT(YEAR FROM FTERM) FROM T', 1, 'CAST'),
        ('extract_on_date_noop',
         'SELECT EXTRACT(YEAR FROM NORMAL_DATE) FROM T', 0, 'NORMAL_DATE'),
        # F4 uses col.name.upper() for the lookup, so it fires whether
        # the column is rendered lower- or upper-case. Pre-F2a callers
        # still get the wrap; F2a just makes the *catalog* lookup robust.
        ('extract_on_qualified_lowercase',
         'SELECT EXTRACT(YEAR FROM "p"."publication_date") FROM T AS "p"', 1, 'TO_DATE'),
        ('extract_on_qualified_uppercase',
         'SELECT EXTRACT(YEAR FROM "p"."PUBLICATION_DATE") FROM T AS "p"', 1, 'TO_DATE'),
    ]
    for label, sql, want_wrap, must_appear in cases_f4:
        fixed, info = wrap_date_fn_on_nondate(sql, col_types)
        n = info.get('wrapped_n', 0)
        ok = (n == want_wrap) and (must_appear in fixed)
        status = 'OK   ' if ok else 'FAIL '
        print(f'{status} {label}: wrapped_n={n} (want {want_wrap}) fixed={fixed[:120]!r}')
        if not ok: failures += 1

    # F2a + F4 combined order (the real pipeline)
    print('\n=== F2a + F4 combined order ===')
    sql = ('SELECT EXTRACT(YEAR FROM "p"."publication_date") FROM '
           '"PATENTS"."PATENTS"."PUBLICATIONS" AS "p"')
    s1, i1 = fix_mixedcase_quoting(sql, allowed | {'PUBLICATION_DATE'})
    s2, i2 = wrap_date_fn_on_nondate(s1, col_types)
    ok = ('TO_DATE' in s2 and 'PUBLICATION_DATE' in s2)
    print(f'{"OK   " if ok else "FAIL "} combined: F2a requoted={i1["requoted_n"]} '
          f'F4 wrapped={i2["wrapped_n"]}')
    print(f'      after F2a: {s1[:140]!r}')
    print(f'      after F4 : {s2[:160]!r}')
    if not ok: failures += 1

    print(f'\n{"ALL TESTS PASS" if failures == 0 else f"{failures} FAILURES"}')
    sys.exit(0 if failures == 0 else 1)
