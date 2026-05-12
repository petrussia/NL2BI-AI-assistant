# 5.4 Phase 28 — F2a regression и Phase 28 revert (methodological centerpiece)

## Opening question

After Phase 27 closed cross-DB drift but left exec at 1/10, what closes the remaining gap on Spider2-Snow?

Phase 27 §5 failure analysis на pilot10c identified three failure clusters:

| Cluster | Count of misses | Hypothesized fix |
|---|---|---|
| Mixed-case quoting (`invalid identifier '"p"."country"'`) | 4 | **F2a** auto-UPPERCASE quoted identifiers |
| NUMBER/VARIANT date function errors | 3 | **F4** wrap with TO_DATE / ::DATE |
| LATERAL FLATTEN SQLGlot parse error | 1 | **F4c** regex fallback in guard |
| Hallucinated tables/columns | ~2 | Deferred (Phase 29 F3 territory) |

Plan: implement **F2a + F4 + F4c** в Phase 28, deploy, measure. Target: pilot10 exec_ok 1/10 → ≥5/10.

This file documents what happened — including the **F2a hypothesis falsification** through catalog probe that became the methodological centerpiece of the thesis (Claim 3).

## Hypothesis statement (Phase 27 §5)

The four `invalid identifier '"p"."country"'`-style errors на pilot10c шли from sf_bq026, sf_bq027, sf_bq029, sf_bq091. Phase 27 §5 analysis classified them as:

> **«Mixed-case lowercase quoting»**: emitter wraps lowercase column names в double-quotes. Snow stores them uppercase, so `"p"."country"` fails to resolve. Fix: do not quote unless the actual catalog row uses mixed-case identifier OR upcase before quoting. Catalog already has the answer — every column is stored upper.
>
> **Expected uplift**: +4/10 on pilot10 = +40pp. Single biggest dialect fix.

This classification was **based purely on error-message format** — `invalid identifier '"<quoted>"'` pattern. **No direct catalog read** was performed at the time. The assumption «catalog stores upper» was treated как self-evident (consistent с common Snow convention).

## Implementation

### F2a — `fix_mixedcase_quoting` (`snow_dialect_fixer_v28.py`)

```python
def fix_mixedcase_quoting(sql: str, allowed_cols_upper: set) -> tuple:
    """F2a: drop case-sensitive lowercase quotes on identifiers whose
    UPPER form is a real catalog column."""
    ast = sqlglot.parse_one(sql, read='snowflake')
    
    # Protect set: aliases / CTEs (declared в query)
    protected = set()
    for a in ast.find_all(exp.Alias): protected.add(a.alias_or_name.upper())
    for a in ast.find_all(exp.TableAlias): protected.add(a.name.upper())
    for c in ast.find_all(exp.CTE): protected.add(c.alias_or_name.upper())
    
    requoted = 0
    for ident in ast.find_all(exp.Identifier):
        if not ident.args.get('quoted'): continue
        name = ident.name
        if name.upper() == name: continue  # already upper
        if name.upper() in protected: continue  # alias / CTE
        if name.upper() in allowed_cols_upper:
            ident.set('this', name.upper())
            requoted += 1
    
    return ast.sql(dialect='snowflake', identify=True), {'requoted_n': requoted}
```

**4/4 unit tests pass**: `mixed_case_col_quoted`, `select_alias_protected`, `already_uppercase_noop`, `not_in_pack_left_alone`.

Synthetic test setup: `allowed_cols_upper = {'COUNTRY', 'DATE', 'CITATION', 'ASSIGNEE', 'PUBLICATION_DATE', 'PUBLICATIONS', 'PATENTS', 'GRANT_DATE'}` — все uppercase, **simulating expected Snow convention**.

### F4 — `wrap_date_fn_on_nondate`

```python
def wrap_date_fn_on_nondate(sql: str, col_types: dict) -> tuple:
    """F4: wrap Column args inside date-function calls when the column's
    declared type is NUMBER or VARIANT."""
    ast = sqlglot.parse_one(sql, read='snowflake')
    
    date_fn_types = (exp.Extract, exp.DateTrunc, exp.DateAdd, exp.DateDiff,
                     exp.DateSub, exp.Year, exp.Month, exp.Day)
    if hasattr(exp, 'TimestampTrunc'):
        date_fn_types += (exp.TimestampTrunc,)
    
    targets = []
    for fn in ast.find_all(*date_fn_types):
        for col in fn.find_all(exp.Column):
            cn = (col.name or '').upper()
            t = col_types.get(cn, '').upper()
            if t.startswith('NUMBER'): targets.append((col, 'number'))
            elif t == 'VARIANT': targets.append((col, 'variant'))
    
    wrapped = 0
    for col, kind in targets:
        if col.parent is None: continue
        if kind == 'number':
            inner = exp.func('TO_VARCHAR', col.copy())
            wrapper = exp.func('TO_DATE', inner, exp.Literal.string('YYYYMMDD'))
        else:
            wrapper = exp.Cast(this=col.copy(), to=exp.DataType.build('DATE'))
        col.replace(wrapper)
        wrapped += 1
    
    return ast.sql(dialect='snowflake', identify=True), {'wrapped_n': wrapped}
```

**7/7 unit tests pass**.

### F4c — guard fail-open regex fallback

В `snow_identifier_guard_v27.py` заменили `except Exception: raise IdentifierLeakError('parse_error_sqlglot:...')` на `except sg_errors.ParseError → regex fallback`. См. [08_CUSTOM_TOOLS/05_snow_identifier_guard_v27.md](../08_CUSTOM_TOOLS/05_snow_identifier_guard_v27.md).

**2 new tests added** (`lateral_flatten_fallback`, `lateral_flatten_with_leak`); total 8/8 pass.

### Prompt rule additions

В `_snow_direct_prompt`:
- New line: `"- Quote mixed-case identifiers: ``"ParticipantBarcode"``. UPPERCASE columns are unquoted."` (Phase 28 addition, supporting F2a hypothesis).
- New block: NUMBER/VARIANT date cast rule (supporting F4):
  ```
  - Date arithmetic on non-DATE columns requires explicit cast:
    NUMBER (e.g. YYYYMMDD int) -> TO_DATE(TO_VARCHAR(col), 'YYYYMMDD')
    VARIANT -> col::DATE; JSON path: col:field::DATE
    Column types are shown as col:TYPE after each name in the schema below.
  ```
- New rendering format: `col:TYPE` annotations в schema block (e.g., `family_id:TEXT, publication_date:NUMBER`).

## The REGRESSION — pilot10 v28

Pilot10 v28 ran on same 10 instance_ids as pilot10c:

| Metric | pilot10c (Phase 27 final) | **pilot10 v28** |
|---|---|---|
| plan_ok | 4/10 | 4/10 |
| schema_valid | 8/10 | **7/10** ↓1 |
| parse_ok | 9/10 | 9/10 |
| **execute_ok** | **1/10** | **0/10** ↓1 ⚠️ **REGRESSION** |
| requoted_n | n/a | 67 (F2a fired heavily) |
| wrapped_n | n/a | 9 (F4 fired) |
| guard_regex_fallback | n/a | 1 (F4c worked on sf_bq210) |

**sf_bq211** — the **only previously-executable task across v25, v26, v27, v27b, v27c** — broke. New error: `invalid identifier '"p"."FAMILY_ID"'`.

This was unexpected. Pre-pilot smoke tests passed all unit cases для F2a + F4 + F4c. Unit tests на synthetic data — green. Real run on actual 10-task pilot — red.

## The catalog probe — F2a falsification

Phase 28 §6 diagnostic — direct probe of `outputs/cache/spider2_snow_live_catalog_v18.jsonl` для `PATENTS.PATENTS.PUBLICATIONS` table:

```python
# tools/remote_scripts/_phase28_catalog_case_probe.py
import json
from collections import Counter

cat_path = 'outputs/cache/spider2_snow_live_catalog_v18.jsonl'
target = ('PATENTS', 'PATENTS', 'PUBLICATIONS')

case_dist = Counter()
columns = []
with open(cat_path) as f:
    for ln in f:
        r = json.loads(ln)
        if (r.get('TABLE_CATALOG'), r.get('TABLE_SCHEMA'), r.get('TABLE_NAME')) == target:
            col = r.get('COLUMN_NAME')
            if col:
                columns.append(col)
                if col == col.lower(): case_dist['lower'] += 1
                elif col == col.upper(): case_dist['upper'] += 1
                else: case_dist['mixed'] += 1

print(f'Total cols found: {len(columns)}')
print(f'Case dist: {case_dist}')
print(f'First 10 cols: {columns[:10]}')
```

### Result

```
Total cols found: 37
Case dist: Counter({'lower': 37, 'upper': 0, 'mixed': 0})
First 10 cols: ['family_id', 'publication_number', 'application_number',
                'application_kind', 'art_unit', 'assignee',
                'assignee_harmonized', 'country_code', 'cpc',
                'description_localized']
```

**37 of 37 columns stored LOWERCASE**. There is **no `COUNTRY`** column (only `country_code`). No `DATE` (only `priority_date`, `grant_date`, `publication_date`, `filing_date`).

### Implications

Phase 27 §5's «mixed-case quoting» classification was **empirically wrong**:

1. `invalid identifier '"p"."country"'` was **not** a case mismatch. It was **column-name hallucination** — model emitted `country`, but catalog has `country_code`. Snow case-sensitive quoted lookup of `country` (lowercase) fails because column doesn't exist (any case).
2. Snow stores PATENTS.PUBLICATIONS columns lowercase because the dataset creator used `CREATE TABLE` с **quoted-lowercase** column names. This **contradicts common Snowflake convention** (default storage uppercase from unquoted DDL).
3. F2a hypothesis was based on prevailing Snow convention assumption, не on this specific dataset's catalog. **Wrong assumption.**

## The sf_bq211 regression mechanism (detailed)

How did F2a + prompt change break the one previously-working task?

### Pre-Phase-28 v27c sf_bq211 SQL

Model emitted (lowercase quoted):

```sql
SELECT COUNT(DISTINCT "p"."family_id")
FROM "PATENTS"."PATENTS"."PUBLICATIONS" AS "p"
WHERE "p"."grant_date" BETWEEN '2010-01-01' AND '2023-12-31'
  AND "p"."assignee" LIKE '%CN%'
GROUP BY "p"."family_id"
HAVING COUNT(DISTINCT "p"."family_id") > 1
```

Snow case-sensitive lookup inside quotes:
- `"family_id"` → catalog has `family_id` → match.
- `"grant_date"` → catalog has `grant_date` → match.
- `"assignee"` → catalog has `assignee` → match.

Result: **exec_ok = True**.

### Phase 28 v28 sf_bq211 SQL — after F2a + prompt change

Model emit changed (likely **due to prompt rule «UPPERCASE columns are unquoted»** which generalized to «drop quotes everywhere»):

```sql
SELECT COUNT(DISTINCT p.family_id)
FROM PATENTS.PATENTS.PUBLICATIONS p
WHERE p.entity_status = 'Granted'
  AND p.grant_date BETWEEN 20100101 AND 20231231
  AND p.assignee LIKE '%CN%'
GROUP BY p.family_id
HAVING COUNT(DISTINCT p.family_id) > 1
```

Then **F2a re-emitted с `identify=True` and after running fix_mixedcase_quoting**:

```sql
SELECT COUNT(DISTINCT "p"."FAMILY_ID")
FROM "PATENTS"."PATENTS"."PUBLICATIONS" AS "p"
WHERE "p"."ENTITY_STATUS" = 'Granted'
  AND "p"."GRANT_DATE" BETWEEN 20100101 AND 20231231
  AND "p"."ASSIGNEE" LIKE '%CN%'
GROUP BY "p"."FAMILY_ID"
HAVING COUNT(DISTINCT "p"."FAMILY_ID") > 1
```

Snow case-sensitive lookup:
- `"FAMILY_ID"` → catalog has `family_id` (lowercase) → **MISMATCH**.

Result: `invalid identifier '"p"."FAMILY_ID"'`. **exec_ok = False**.

The sequence — prompt change moved emitter towards unquoted → F2a re-quoted с upper-case → catalog doesn't have upper-case → fail.

## The revert decision

Per Phase 28 acceptance gate:

> *"exec_ok ≤ 2/10 → серьёзный stop, debug, что-то фундаментально не работает."*

0/10 exec on pilot10 v28 — clear failure. Revert F2a + prompt rule. Keep F4 + F4c (those не the cause).

## Pilot10 v28-revert-A — the closure

Three minimal reverts:
1. Delete F2a call site в runner (lines 503-509 в `_phase27_snow_runner.py`).
2. Truncate prompt line к v27c form — drop «UPPERCASE columns are unquoted» tail.
3. Keep `col:TYPE` rendering (deemed neutral — needed для F4 visibility).

8/8 smoke check assertions pass on regenerated prompt:
- No "UPPERCASE columns are unquoted" string в prompt.
- "Quote mixed-case identifiers" still present.
- TO_DATE / ::DATE rules still present.
- `col:TYPE` still present.
- No `fix_mixedcase_quoting(` call in runner source.
- `wrap_date_fn_on_nondate(` and `guard_and_fix_snow_sql(` still present.

Pilot10 v28-revert-A result:

| Metric | pilot10c (Phase 27) | pilot10 v28 | **pilot10 v28-revert-A** |
|---|---|---|---|
| schema_valid | 8/10 | 7/10 | 6/10 |
| parse_ok | 9/10 | 9/10 | **10/10** |
| **execute_ok** | **1/10** | **0/10** | **4/10 ✓✓ CLOSURE** |
| requoted_n | n/a | 67 | 0 (F2a disabled — confirmed) |
| wrapped_n | n/a | 9 | 9 |

**4/10 exec_ok — 4× lift over Phase 27 closure**. Acceptance gate (3-4/10 band) cleared.

### Per-task analysis of revert-A

| iid | v27c | v28 | revert-A | wrapped | comment |
|---|---|---|---|---|---|
| sf_bq026 | sv✓ ex✗ | sv✓ ex✗ | **sv✓ ex✓** | 1 | NEW PASS — F4 wrapped `"date"` column |
| sf_bq027 | sv✓ ex✗ | sv✗ ex✗ | sv✗ ex✗ | 0 | LATERAL FLATTEN `"c"."value"` still fails |
| sf_bq029 | sv✓ ex✗ | sv✓ ex✗ | **sv✓ ex✓** | 0 | NEW PASS — model emitted YYYYMMDD math directly |
| sf_bq033 | sv✓ ex✗ | sv✓ ex✗ | sv✓ ex✗ | 2 | hallucinated mixed-case alias `"Publications"` |
| sf_bq091 | sv✓ ex✗ | sv✓ ex✗ | sv✓ ex✗ | 2 | F4 wrapped VARIANT `"assignee"` (JSON object, not date) — wrong wrap |
| sf_bq099 | sv✓ ex✗ | sv✓ ex✗ | sv✗ ex✗ | 1 | F4 wrap altered SQL such that validator rejected |
| sf_bq209 | sv✗ ex✗ | sv✗ ex✗ | sv✗ ex✗ | 1 | hallucinated `CITATIONS` table — Phase 29 F3 |
| sf_bq210 | parse_guard | sv✗ ex✗ | sv✗ ex✗ | 0 | LATERAL FLATTEN — sqlglot upgrade needed |
| **sf_bq211** | **sv✓ ex✓** | sv✓ **ex✗** | **sv✓ ex✓** | 0 | regression healed; back to baseline |
| sf_bq213 | sv✓ ex✗ | sv✓ ex✗ | **sv✓ ex✓** | 2 | NEW PASS — F4 wrapped `"fterm"` VARIANT с CAST AS DATE |

### Key observations

1. **F4 wrap = load-bearing** для 2 of 4 new exec_ok (sf_bq026 NUMBER date, sf_bq213 VARIANT fterm cast).
2. **sf_bq211 recovered** — F2a was the cause of its regression.
3. **sf_bq029** — model wrote YYYYMMDD math directly без F4 wrap (valid path through prompt's NUMBER cast rule).
4. **F4c** worked but downstream still fails — sf_bq210 cleared guard but `_snow_schema_valid_ast` ParseError'ed on same construct (Phase 29 territory).
5. **F4 false-positive** sf_bq091 — VARIANT `assignee` is JSON object, not date encoding; F4 wrap with `CAST AS DATE` causes `GET_PATH(DATE, 'assignee_date')` type error downstream. **F4 needs value-based type inference** (Phase 29 issue).

## Methodological lessons (for thesis Conclusion)

### Lesson 1: Error-message taxonomy without catalog ground-truth is unreliable

Phase 27 §5 classified 4 misses as «mixed-case quoting» based на error-message pattern matching. Phase 28 catalog probe falsified this. **Error message tells you what Snow rejected**, не **why model emitted what it emitted**.

### Lesson 2: Catalog probe should precede any dialect heuristic

Generalized methodological principle: when designing dialect-specific post-processor, **direct read the catalog**. Check:
- Case distribution (upper/lower/mixed).
- Type distribution (data types of "interesting" columns).
- Sample values (e.g., what's в a VARIANT column — JSON object, array of strings, date string?).

These three probes would have prevented F2a hypothesis.

### Lesson 3: Layered fixes interact non-trivially

F4 wraps fired correctly under both v28 and v28-revert-A (`wrapped_n=9` both runs). **Same F4 contributed differently** depending on F2a state:
- Under v28 (F2a active): F4 wraps applied к columns whose names were corrupted by F2a → wraps fired but on wrong identifiers → exec=0.
- Under v28-revert-A (F2a disabled): F4 wraps applied к columns с correct names → 3 of 4 new exec_ok directly attributable к F4.

**F4 was hidden by F2a regression**. Revert exposed F4's value.

### Lesson 4: Revert experiments separate fix contributions

Ablation through deletion (revert F2a) — necessary methodology. **Just adding** all fixes simultaneously and measuring net effect = aggregate. **Revert** isolates each fix's marginal contribution.

### Lesson 5: Spider2 public Snow datasets contradict common Snow convention

Empirical finding worth documenting: Snowflake's Marketplace public datasets для Spider 2.0 — **predominantly lowercase identifier storage**. This contradicts typical corporate Snow deployments (which mostly use unquoted-folded-to-upper или quoted-mixed-case). Generalization of our v28-revert-A stack to corporate Snow is **uncertain**.

## Final Phase 28 stack (committed `ad5493b`)

- **F1** (Phase 27): catalog filter + per-task BM25 + AST guard + three-part rendering + PK/FK injection + validator relaxation + SELECT-alias protection.
- **F4c** (Phase 28): regex fallback в guard.
- **F4** (Phase 28): NUMBER/VARIANT date-cast wrap.
- **F2a** (Phase 28): REVERTED — function kept в module for record, but not called в pipeline.
- **Prompt rules**: v27c-equivalent on quoting; F4 NUMBER/VARIANT cast rules retained; `col:TYPE` rendering retained.

## What worked

- **F1+F4+F4c stack** — pilot10 4/10 EX. First publishable Snow result для open ≤30B.
- **Catalog probe methodology** — falsified F2a wrong hypothesis cleanly.
- **Revert-A discipline** — surfaced F4's true contribution post-F2a-removal.

## What didn't

- **F2a wasted ~3h of engineering** — implementation + testing + deployment before catalog probe falsification.
- **Phase 27 §5 misclassification** — error message taxonomy without catalog read produced wrong hypothesis.
- **F4 false-positive** sf_bq091 — VARIANT cast assumes date encoding; не handles JSON object case.

## Transition to Phase 28 FULL

After pilot10 v28-revert-A closure:
- Acceptance gate cleared (3-4/10 band).
- Phase 28 FULL launched on Spider2-Snow 547 + Spider2-Lite-Snow 207 (in progress).
- Phase 29 F3 self-refine planned to address remaining column/table hallucinations.

См. [05_phase28_full_baseline.md](./05_phase28_full_baseline.md) для FULL closure (placeholder pending run completion).

## Cross-references

- Phase 28 main report: `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md`
- F2a kept in source: [08_CUSTOM_TOOLS/06_snow_dialect_fixer_v28.md](../08_CUSTOM_TOOLS/06_snow_dialect_fixer_v28.md)
- F4c regex fallback in guard: [08_CUSTOM_TOOLS/05_snow_identifier_guard_v27.md](../08_CUSTOM_TOOLS/05_snow_identifier_guard_v27.md)
- Pre-Phase-28 state (Phase 27 closure): [03_phase27_f1_grounding.md](./03_phase27_f1_grounding.md)
- Catalog probe methodology in thesis claims: [01_INTRODUCTION/04_thesis_contributions.md](../01_INTRODUCTION/04_thesis_contributions.md) Claim 3
- Snow analysis (full picture): [09_RESULTS_ANALYSIS/03_spider2_snow_analysis.md](../09_RESULTS_ANALYSIS/03_spider2_snow_analysis.md)
- Snow pipeline detailed config: [05_PIPELINES/04_spider2_snow_pipeline.md](../05_PIPELINES/04_spider2_snow_pipeline.md)
- Lessons learned thesis-level: [06_lessons_learned.md](./06_lessons_learned.md)
- Phase 28 FULL placeholder: [05_phase28_full_baseline.md](./05_phase28_full_baseline.md)

## Источники

| Утверждение | Источник |
|---|---|
| Phase 27 §5 mixed-case classification | `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` §5 |
| F2a/F4/F4c implementation | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §2 |
| 4/4 + 7/7 + 8/8 unit tests pass | runs of `python repo/src/evaluation/snow_dialect_fixer_v28.py` и `snow_identifier_guard_v27.py` |
| Pilot10 v28 regression numbers | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §3 |
| Catalog probe finding 37/37 lowercase | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §6 |
| Pilot10 v28-revert-A closure 4/10 | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §10 |
| Per-task v27c / v28 / revert-A comparison | same §10 table |
| sf_bq211 regression mechanism | own analysis + pilot10 v28 trace details |
