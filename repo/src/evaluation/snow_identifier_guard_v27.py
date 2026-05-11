"""Phase 27 STAGE F1 — SQLGlot AST guard for Snowflake candidate SQL.

Walks the AST and ensures every Table reference is either:
  (a) catalog ∈ allowed_dbs (default {task_db}), or
  (b) catalog absent — in which case auto-fill with task_db.

If any Table has a catalog OUTSIDE allowed_dbs → raise IdentifierLeakError.

Designed to plug into candidate_selector_v18.evaluate_candidate / select on
the Snow lane just before the Snow EXPLAIN call.

Return type: (fixed_sql, info_dict) on success; raises on leak.
info_dict = {'rewrote_n': int, 'leaked_catalogs': list[str]}
"""
from __future__ import annotations


class IdentifierLeakError(Exception):
    """Raised when candidate SQL references a Snow catalog outside the
    per-task allow-list."""


def _regex_catalog_leak_check(sql: str, allowed: set) -> list:
    """Find FROM/JOIN <ident>.<ident>.<ident> three-part references and
    return any first-segment catalog names that are not in `allowed`.
    Used as fallback when sqlglot parsing fails.
    """
    import re
    pattern = r'(?:FROM|JOIN)\s+"?([A-Za-z_][A-Za-z0-9_]*)"?\s*\.\s*"?[A-Za-z_][A-Za-z0-9_]*"?\s*\.'
    return [c for c in re.findall(pattern, sql, re.IGNORECASE)
            if c.upper() not in allowed]


def guard_and_fix_snow_sql(
    sql: str,
    task_db: str,
    allowed_dbs: set | None = None,
) -> tuple:
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
        # catalog leak check and pass the SQL through unchanged. EXPLAIN
        # is the real arbiter.
        leaked = _regex_catalog_leak_check(sql, allowed)
        if leaked:
            raise IdentifierLeakError(
                f'catalog_leak:{sorted(set(leaked))} not in allow-list {sorted(allowed)}'
            )
        return sql, {'rewrote_n': 0, 'leaked_catalogs': [], 'fallback': 'regex_only',
                     'parse_error': f'{type(e).__name__}:{str(e)[:120]}'}
    except Exception as e:
        # Non-parse exceptions are still surfaced as before
        raise IdentifierLeakError(f'parse_error_sqlglot:{type(e).__name__}:{str(e)[:200]}')

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


# ---- self-test (run with `python snow_identifier_guard_v27.py`) ----
if __name__ == '__main__':
    import sys
    cases = [
        # (label, sql, task_db, expect_ok, expect_rewrite, expect_leak)
        ('three_part_correct',
         'SELECT * FROM GITHUB_REPOS.GITHUB.COMMITS WHERE a=1',
         'GITHUB_REPOS', True, 0, []),
        ('two_part_fill',
         'SELECT * FROM GITHUB.COMMITS WHERE a=1',
         'GITHUB_REPOS', True, 1, []),
        ('one_part_fill',
         'SELECT * FROM COMMITS',
         'GITHUB_REPOS', True, 1, []),
        ('foreign_catalog_leak',
         'SELECT * FROM FINANCE__ECONOMICS.CYBERSYN.SEC_REPORTS',
         'GITHUB_REPOS', False, 0, ['FINANCE__ECONOMICS']),
        ('cte_and_join',
         'WITH a AS (SELECT * FROM GITHUB.COMMITS) '
         'SELECT * FROM a JOIN GITHUB.ISSUES b ON a.id = b.cid',
         'GITHUB_REPOS', True, 2, []),
        ('subquery_leak',
         'SELECT * FROM GITHUB_REPOS.GITHUB.COMMITS '
         'WHERE id IN (SELECT id FROM BAD_DB.SCHEMA.T)',
         'GITHUB_REPOS', False, 0, ['BAD_DB']),
        # Phase 28 F4c — sqlglot fails on TABLE(LATERAL FLATTEN(...));
        # regex fallback should pass it through (no foreign catalog).
        ('lateral_flatten_fallback',
         "SELECT COUNT(*) FROM PATENTS.PATENTS.PUBLICATIONS p "
         "WHERE p.entity_status = 'Granted' "
         "AND EXISTS (SELECT 1 FROM TABLE(LATERAL FLATTEN(INPUT => p.claims_localized)) cf "
         "WHERE LOWER(cf.value) LIKE '%claim%')",
         'PATENTS', True, 0, []),
        # F4c with a leak — regex catches it even though sqlglot may also parse.
        ('lateral_flatten_with_leak',
         "SELECT COUNT(*) FROM PATENTS.PATENTS.PUBLICATIONS p "
         "JOIN OTHER_DB.OTHER.T t ON p.id = t.id "
         "WHERE EXISTS (SELECT 1 FROM TABLE(LATERAL FLATTEN(INPUT => p.x)) cf)",
         'PATENTS', False, 0, ['OTHER_DB']),
    ]
    failures = 0
    for label, sql, db, ok, n_rewrite, leak in cases:
        try:
            fixed, info = guard_and_fix_snow_sql(sql, db)
            if not ok:
                print(f'FAIL  {label}: expected leak but got no error; fixed={fixed!r}')
                failures += 1; continue
            if info['rewrote_n'] != n_rewrite:
                print(f'FAIL  {label}: rewrote_n {info["rewrote_n"]} != expected {n_rewrite}')
                failures += 1; continue
            print(f'OK    {label}: rewrote_n={info["rewrote_n"]} fixed={fixed[:80]!r}')
        except IdentifierLeakError as e:
            if ok:
                print(f'FAIL  {label}: unexpected leak {e}')
                failures += 1; continue
            msg = str(e)
            if leak and not any(d in msg for d in leak):
                print(f'FAIL  {label}: expected leak {leak} not in error msg {msg}')
                failures += 1; continue
            print(f'OK    {label}: leak caught: {msg[:100]}')
    print(f'\n{"ALL TESTS PASS" if failures == 0 else f"{failures} FAILURES"}')
    sys.exit(0 if failures == 0 else 1)
