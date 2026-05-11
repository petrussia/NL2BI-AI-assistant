"""Phase 28 revert smoke check — regenerate Snow prompt for 1 sample task,
verify five things:
  1. NO "UPPERCASE columns are unquoted" substring in prompt
  2. YES "Quote mixed-case identifiers" substring (v27c version kept)
  3. NO fix_mixedcase_quoting call in runner source
  4. YES wrap_date_fn_on_nondate call in runner source
  5. YES NUMBER -> TO_DATE and VARIANT -> ::DATE rules in prompt
"""
import sys, importlib
from pathlib import Path

EVAL = Path('/content/drive/MyDrive/diploma_plan_sql/repo/src/evaluation')
if str(EVAL) not in sys.path: sys.path.insert(0, str(EVAL))
for mod in ['schema_linking_v18', 'schema_pack_builder_v18', 'snow_dialect_fixer_v28']:
    if mod in sys.modules:
        importlib.reload(sys.modules[mod])
import schema_linking_v18 as sl
import schema_pack_builder_v18 as sb

# Pick PATENTS task — same DB as pilot10c subset
DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
cat = sl.load_catalog_jsonl(DRV / 'outputs/cache/spider2_snow_live_catalog_v18.jsonl', 'snow')

from collections import defaultdict
cat_by_db = defaultdict(list)
for c in cat:
    cat_by_db[c.db.upper()].append(c)

cat_subset = cat_by_db['PATENTS']
print(f'PATENTS catalog rows: {len(cat_subset)}')
linker = sl.SchemaLinker(cat_subset)
link = linker.query(
    'How many active patent assignees are there per region per year?',
    db_filter='PATENTS', top_columns=200, top_tables=40)
pack = sb.build_pack(link, lane='snow', alias='PATENTS',
                     max_tables=10, max_cols_per_table=22,
                     all_catalog_cols=cat_subset)

# Re-exec the runner to get _snow_direct_prompt
runner_src = open('/tmp/_phase27_snow_runner.py', encoding='utf-8').read()
local_ns = {}
exec(compile(runner_src, '<runner>', 'exec'), local_ns)
prompt_text = local_ns['_snow_direct_prompt']('test question', pack, ek='')

print('\n=== prompt length: {} chars ==='.format(len(prompt_text)))
print('\n--- Snow rules section ---')
# Find the rules block
rules_start = prompt_text.find('Snowflake rules:')
rules_end = prompt_text.find('Schema:')
if rules_start >= 0 and rules_end >= 0:
    print(prompt_text[rules_start:rules_end].strip())

print('\n=== grep checks ===')
checks = [
    (False, 'UPPERCASE columns are unquoted', 'should be absent (Phase 28 revert)'),
    (True,  'Quote mixed-case identifiers',  'v27c version kept'),
    (True,  "TO_DATE(TO_VARCHAR(col), 'YYYYMMDD')", 'F4 NUMBER rule kept'),
    (True,  '::DATE',                         'F4 VARIANT rule kept'),
    (True,  'col:TYPE',                       'col:TYPE annotation kept (revert-A)'),
]
all_pass = True
for expect_present, needle, label in checks:
    present = needle in prompt_text
    ok = present == expect_present
    flag = 'OK   ' if ok else 'FAIL '
    print(f'  {flag} {"present" if present else "absent ":>7}  | want {"present" if expect_present else "absent ":>7} | {needle!r} | {label}')
    if not ok: all_pass = False

print('\n=== runner source checks ===')
# Read the runner source as deployed
src = runner_src
src_checks = [
    (False, 'fix_mixedcase_quoting(', 'F2a call site should be removed'),
    (True,  'wrap_date_fn_on_nondate(', 'F4 call site should remain'),
    (True,  'guard_and_fix_snow_sql(', 'F1 guard call should remain'),
]
for expect_present, needle, label in src_checks:
    n = src.count(needle)
    present = n > 0
    ok = present == expect_present
    flag = 'OK   ' if ok else 'FAIL '
    print(f'  {flag} count={n:>2}  | want {"present" if expect_present else "absent ":>7} | {needle!r} | {label}')
    if not ok: all_pass = False

print(f'\n{"ALL SMOKE CHECKS PASS" if all_pass else "SMOKE CHECK FAILED"}')
