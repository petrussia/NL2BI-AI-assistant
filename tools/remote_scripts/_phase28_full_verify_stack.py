"""Verify v28-revert-A stack on a Colab kernel.

Checks:
  1. Drive modules: schema_pack_builder_v18 + snow_identifier_guard_v27 + snow_dialect_fixer_v28
  2. /tmp/_phase27_snow_runner.py existence + key invariants:
     a. NO 'fix_mixedcase_quoting(' substring (F2a call site removed)
     b. YES 'wrap_date_fn_on_nondate(' substring (F4 call site kept)
     c. YES 'guard_and_fix_snow_sql(' substring (F1 guard kept)
     d. line ~250 prompt: 'Quote mixed-case identifiers' YES; 'UPPERCASE columns are unquoted' NO
  3. snow_identifier_guard_v27.py on Drive has '_regex_catalog_leak_check' (F4c)
  4. Model globals present: _TOK_EMIT, _MDL_EMIT, _PROF_EMIT, _TOK_PLAN, _MDL_PLAN, _PROF_PLAN
"""
import os, inspect
from pathlib import Path

g = inspect.currentframe().f_globals

EVAL = Path('/content/drive/MyDrive/diploma_plan_sql/repo/src/evaluation')
TMP_RUNNER = Path('/tmp/_phase27_snow_runner.py')

results = []

def check(name, cond, detail=''):
    results.append((cond, name, detail))
    print(f'  {"OK  " if cond else "FAIL"}  {name}{f" — {detail}" if detail else ""}')

print('=== Drive modules ===')
for fn in ['schema_pack_builder_v18.py', 'snow_identifier_guard_v27.py',
           'snow_dialect_fixer_v28.py']:
    p = EVAL / fn
    check(f'{fn} on Drive', p.exists(),
          f'size={p.stat().st_size}B' if p.exists() else 'MISSING')

# Guard has F4c regex fallback?
guard = (EVAL / 'snow_identifier_guard_v27.py').read_text(encoding='utf-8') if (EVAL / 'snow_identifier_guard_v27.py').exists() else ''
check('guard has _regex_catalog_leak_check (F4c)', '_regex_catalog_leak_check' in guard)
check('guard has sg_errors.ParseError except (F4c)', 'sg_errors.ParseError' in guard)

# Fixer has both functions
fixer = (EVAL / 'snow_dialect_fixer_v28.py').read_text(encoding='utf-8') if (EVAL / 'snow_dialect_fixer_v28.py').exists() else ''
check('fixer has fix_mixedcase_quoting def (kept for record)', 'def fix_mixedcase_quoting' in fixer)
check('fixer has wrap_date_fn_on_nondate def', 'def wrap_date_fn_on_nondate' in fixer)

print('\n=== /tmp runner ===')
check('/tmp runner exists', TMP_RUNNER.exists(),
      f'size={TMP_RUNNER.stat().st_size}B' if TMP_RUNNER.exists() else 'MISSING')

if TMP_RUNNER.exists():
    src = TMP_RUNNER.read_text(encoding='utf-8')
    check('NO fix_mixedcase_quoting call site (F2a reverted)',
          'fix_mixedcase_quoting(' not in src,
          f'count={src.count("fix_mixedcase_quoting(")}')
    check('YES wrap_date_fn_on_nondate call site (F4 kept)',
          'wrap_date_fn_on_nondate(' in src,
          f'count={src.count("wrap_date_fn_on_nondate(")}')
    check('YES guard_and_fix_snow_sql call site (F1 kept)',
          'guard_and_fix_snow_sql(' in src)
    check('prompt: Quote mixed-case identifiers (v27c kept)',
          'Quote mixed-case identifiers' in src)
    check('prompt: NO "UPPERCASE columns are unquoted" (reverted)',
          'UPPERCASE columns are unquoted' not in src)
    check('prompt: NUMBER/VARIANT cast rule (F4 support kept)',
          "TO_DATE(TO_VARCHAR(col), 'YYYYMMDD')" in src and '::DATE' in src)

print('\n=== model globals ===')
for k in ['_TOK_EMIT', '_MDL_EMIT', '_PROF_EMIT', '_TOK_PLAN', '_MDL_PLAN', '_PROF_PLAN']:
    check(f'{k} in globals', k in g,
          type(g[k]).__name__ if k in g else 'MISSING')

n_ok = sum(1 for ok, _, _ in results if ok)
n_fail = len(results) - n_ok
print(f'\n=== summary: {n_ok}/{len(results)} OK, {n_fail} FAIL ===')
if n_fail == 0:
    print('STACK_VERIFIED_OK')
else:
    print('STACK_VERIFICATION_FAILED')
    for ok, name, det in results:
        if not ok: print(f'  FAIL: {name} {det}')
