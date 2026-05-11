# Phase 28 F2a + F4 — Snow Dialect Fixes — STOP, hypothesis was wrong

**Date:** 2026-05-11
**Scope:** pilot10 Lite-Snow (same 10 instance_ids as pilot10c)
**Status:** **REGRESSION**. exec_ok dropped 1/10 → 0/10. Per brief acceptance ("exec_ok ≤ 2/10 → серьёзный stop, debug, фундаментально не работает"), Phase 28 stops here.
**Verdict:** Phase 27 §5's "mixed-case quoting" classification was **empirically wrong**. The Snow catalog for `PATENTS.PATENTS.PUBLICATIONS` stores 37/37 columns in **lowercase** (CREATEd with quoted lowercase identifiers). The `invalid identifier '"p"."country"'` failures in pilot10c were **hallucinated column names**, not case mismatch. F2a upper-casing those identifiers actively broke the one task that previously worked.

---

## 1. Mission recap

Per the Phase 28 brief, the three fixes targeted the failure mix from pilot10c:

| Failure pattern (Phase 27 §5) | Pilot10c count | Phase 28 fix |
|---|---|---|
| Mixed-case lowercase quoting | 4/10 | F2a — uppercase quoted identifiers if upper form is in catalog |
| Date fn on NUMBER / VARIANT | 3/10 | F4 — wrap with `TO_DATE(TO_VARCHAR(x),'YYYYMMDD')` or `x::DATE` |
| SQLGlot LATERAL FLATTEN parse error | 1/10 | F4c — guard fails-open via regex catalog leak check |
| Hallucinated table | 1/10 | (Phase 29 F3) |
| Pre-existing exec_ok (sf_bq211) | 1/10 | (untouched) |

Target: exec_ok 1/10 → ≥5/10. Stretch: ≥7/10. Stop-and-ask if ≤2/10.

---

## 2. What landed

### F4c — guard fails-open on `sqlglot.errors.ParseError`
[repo/src/evaluation/snow_identifier_guard_v27.py](../repo/src/evaluation/snow_identifier_guard_v27.py): the `except Exception` over `sqlglot.parse_one` was split into `except sg_errors.ParseError → _regex_catalog_leak_check(sql, allowed) → return sql unchanged` when clean. New helper `_regex_catalog_leak_check` matches `(?:FROM|JOIN)\s+ident\.ident\.` and flags first-segment catalogs outside the allow-list.
- **Unit tests:** 8/8 pass (6 originals + `lateral_flatten_fallback` + `lateral_flatten_with_leak`).
- **Pipeline outcome:** worked — sf_bq210 reached the dialect-fixer stage instead of being rejected at guard. (See §5 for the new ParseError that surfaced downstream.)

### F2a — mixed-case quoting auto-correct
[repo/src/evaluation/snow_dialect_fixer_v28.py](../repo/src/evaluation/snow_dialect_fixer_v28.py) `fix_mixedcase_quoting`: walks `exp.Identifier`, skips SELECT/Table/CTE aliases, and for any quoted lowercase identifier whose `.upper()` is in `allowed_cols_upper`, upper-cases the name in place. Re-emits with `identify=True`.
- **Unit tests:** 4/4 pass on synthetic data (mixed-case, alias-protected, already-upper no-op, not-in-pack no-op).
- **Pipeline outcome:** active harm. See §3.

### F4 — date function cast wrapper
Same module, `wrap_date_fn_on_nondate`: walks `exp.Extract`, `exp.TimestampTrunc` (sqlglot's Snowflake-dialect representation of `DATE_TRUNC`), `exp.DateAdd/Diff/Sub`, `exp.Year/Month/Day`, finds `exp.Column` args whose declared type in `col_types` starts with `NUMBER` (→ `TO_DATE(TO_VARCHAR(x),'YYYYMMDD')`) or is `VARIANT` (→ `x::DATE`).
- **Unit tests:** 7/7 pass (extract NUMBER, date_trunc NUMBER, extract VARIANT, extract DATE no-op, qualified lower-case, qualified upper-case, F2a+F4 combined order).
- **Pipeline outcome:** wraps fired 9× across the 10 tasks (`wrapped_n=9`). No task became executable. See §4.

### Prompt + pack
- [_phase27_snow_runner.py](../tools/remote_scripts/_phase27_snow_runner.py): `_snow_direct_prompt` now renders each column as `name:TYPE` (stripping `NUMBER(38,0)`→`NUMBER`); adds rule lines for NUMBER and VARIANT date casts; the "Quote mixed-case identifiers" line was extended with "UPPERCASE columns are unquoted." (← this turned out to be wrong, see §6).
- Pack-builder: no change needed — `data_type` was already passing through from [schema_pack_builder_v18.py:125](../repo/src/evaluation/schema_pack_builder_v18.py#L125).

---

## 3. Pilot10 v28 result — regression

| run | plan_ok | schema_valid | parse_ok | **execute_ok** | requoted_n | wrapped_n | guard_regex_fallback |
|---|---|---|---|---|---|---|---|
| pilot10c (Phase 27) | 4/10 | 8/10 | 9/10 | **1/10** | (n/a) | (n/a) | (n/a) |
| **pilot10 v28** | 4/10 | **7/10** ↓1 | 9/10 | **0/10** ↓1 | 67 | 9 | 1 |

Direction: every count is at-or-below v27c. Most diagnostic: **the one task that had been executable since v25 (sf_bq211) is now broken**.

---

## 4. Per-task verdict and why F2a regressed

The 10 tasks classified against v27c outcomes:

| iid | v27c | v28 | F2a requoted | F4 wrapped | v28 error |
|---|---|---|---|---|---|
| sf_bq026 | sv✓ ex✗ | sv✓ ex✗ | 11 | 1 | `invalid identifier 'ASSIGNEE_HARMONIZED'` |
| sf_bq027 | sv✓ ex✗ | **sv✗** ex✗ | 4 | 0 | `invalid identifier 'DISCLOSURES_13'` |
| sf_bq029 | sv✓ ex✗ | sv✓ ex✗ | 5 | 0 | `invalid identifier 'PUBLICATION_DATE'` |
| sf_bq033 | sv✓ ex✗ | sv✓ ex✗ | 5 | 2 | `invalid identifier '"p".ABSTRACT_LOCALIZED'` |
| sf_bq091 | sv✓ ex✗ | sv✓ ex✗ | 5 | 2 | `invalid identifier '...'` |
| sf_bq099 | sv✓ ex✗ | sv✓ ex✗ | 14 | 1 | `invalid identifier '"p".ASSIGNEE_HARMONIZED'` |
| sf_bq209 | sv✗ ex✗ | sv✗ ex✗ | 11 | 1 | hallucinated table CITATIONS — unchanged |
| sf_bq210 | parse_guard | **sv✗ parse✗** | 0 | 0 | `ParseError: 'this' missing for exp.Lateral` (F4c pulled it past guard, then F2a parser tripped on `LATERAL JOIN LATERAL FLATTEN`) |
| **sf_bq211** | **sv✓ ex✓** | sv✓ **ex✗ ↓** | 6 | 0 | `invalid identifier '"p".FAMILY_ID'` |
| sf_bq213 | sv✓ ex✗ | sv✓ ex✗ | 6 | 2 | `invalid identifier '...'` |

### Why sf_bq211 regressed

Before: model emitted `"p"."family_id"` (lowercase, quoted). Snow does case-sensitive lookup inside quotes → finds catalog column `family_id` (which IS stored lowercase, see §6) → resolves.

In v28 the model emitted `p.family_id` (lowercase, **unquoted**). Snow folds unquoted identifiers to uppercase → looks for `FAMILY_ID` → catalog has `family_id` only → fails. F2a then re-emits with `identify=True`, producing `"p"."FAMILY_ID"` (quoted upper-case) which is even worse.

The reason the model dropped the quotes: the prompt added the line "UPPERCASE columns are unquoted" — intending to teach it to drop quotes around already-upper identifiers. Instead it generalized the rule to drop quotes around *everything*. This is the prompt change biting; the post-pass F2a then compounds the problem rather than fixing it.

---

## 5. F4c worked, but a different sqlglot gap surfaced

sf_bq210 in v27c: rejected at guard with `parse_error_sqlglot:ParseError` (the `TABLE(LATERAL FLATTEN(INPUT => ...))` form). F4c was meant to let it through.

In v28: F4c successfully passed it through the guard (`fallback='regex_only'`). Then the dialect-fixer module ran `sqlglot.parse_one` again for F2a and F4, and tripped on the same Lateral construct — but with a slightly different error (`Required keyword: 'this' missing for exp.Lateral`). F2a and F4 both correctly returned `skipped='parse_error'` and left the SQL alone. Then the runner's own `_snow_schema_valid_ast` (line 466 in the runner) tried to parse the SQL **again**, this time the ParseError surfaced as `sv_msg='parse_failed:ParseError'`, and the task was marked `parse_ok=False, schema_valid=False`.

So F4c moved sf_bq210's failure one stage downstream but didn't make it executable. To actually run this task end-to-end we'd need EITHER (a) the validator/parse_ok stages to also tolerate ParseError + fall through to EXPLAIN, OR (b) sqlglot upgrade with full LATERAL support. Both out of scope per the brief.

---

## 6. The fundamental error in Phase 27 §5 — catalog case discovery

Direct probe of [outputs/cache/spider2_snow_live_catalog_v18.jsonl](../outputs/cache/spider2_snow_live_catalog_v18.jsonl) for `PATENTS.PATENTS.PUBLICATIONS`:

```
total cols found: 37
case dist: lower=37  upper=0  mixed=0

specific col case check:
  'family_id':         exact=True  upper_in=False  lower_in=True
  'FAMILY_ID':         exact=False upper_in=False  lower_in=True
  'grant_date':        exact=True  upper_in=False  lower_in=True
  'GRANT_DATE':        exact=False upper_in=False  lower_in=True
  'assignee':          exact=True  upper_in=False  lower_in=True
  'date':              NOT IN CATALOG (the col is `priority_date` / `grant_date` / `publication_date` / `filing_date`)
  'country':           NOT IN CATALOG (the col is `country_code`)
  'kind_code':         exact=True  upper_in=False  lower_in=True
  'publication_date':  exact=True  upper_in=False  lower_in=True
  'fterm':             exact=True  upper_in=False  lower_in=True
```

**Every PUBLICATIONS column is stored lowercase. There is no `COUNTRY`, no `DATE`. The pilot10c `invalid identifier '"p"."country"'` and `'"p"."date"'` errors classified as "mixed-case quoting" in [REPORT_PHASE27_F1_SNOW_GROUNDING.md §5.1](REPORT_PHASE27_F1_SNOW_GROUNDING.md) were actually column-name hallucinations — `country` instead of `country_code`, `date` instead of one of the four date columns.**

I owe an apology to that earlier report's verdict. The 4-case category labelled "mixed-case quoting" with the predicted +40pp uplift was based on inspecting only the error message format, not on probing the catalog. The actual fix for those 4 cases is **better column-name grounding** (Phase 29 F3 self-refine on schema_invalid, or richer pack/prompt rendering that biases toward exact catalog names), not case rewriting.

F4 (date-fn cast wrapping) was on more solid ground — `publication_date` IS stored as NUMBER and DOES need a `TO_DATE(TO_VARCHAR(...), 'YYYYMMDD')` wrapper. The wraps fired correctly in 9 places (sf_bq026, sf_bq033, sf_bq091, sf_bq099, sf_bq209, sf_bq213). But the surrounding column refs in those queries still resolve to hallucinated names like `ASSIGNEE_HARMONIZED` and `ABSTRACT_LOCALIZED`, so EXPLAIN dies before the cast wrapper has anything to do.

---

## 7. Sample SQL — sf_bq211 before/after Phase 28

**Phase 27 v27c — executable**:
```sql
SELECT COUNT(DISTINCT "p"."family_id")
FROM "PATENTS"."PATENTS"."PUBLICATIONS" AS "p"
WHERE "p"."grant_date" BETWEEN '2010-01-01' AND '2023-12-31'
  AND "p"."assignee" LIKE '%CN%'
GROUP BY "p"."family_id"
HAVING COUNT(DISTINCT "p"."family_id") > 1
```

**Phase 28 v28 — broken**:
```sql
-- model emission (pre-guard, pre-fixer):
SELECT COUNT(DISTINCT p.family_id)
FROM PATENTS.PATENTS.PUBLICATIONS p
WHERE p.entity_status = 'Granted'
  AND p.grant_date BETWEEN 20100101 AND 20231231
  AND p.assignee LIKE '%CN%'
GROUP BY p.family_id
HAVING COUNT(DISTINCT p.family_id) > 1

-- after F2a + identify=True re-emit:
SELECT COUNT(DISTINCT "p"."FAMILY_ID")
FROM "PATENTS"."PATENTS"."PUBLICATIONS" AS "p"
WHERE "p"."ENTITY_STATUS" = 'Granted'
  AND "p"."GRANT_DATE" BETWEEN 20100101 AND 20231231
  AND "p"."ASSIGNEE" LIKE '%CN%'
GROUP BY "p"."FAMILY_ID"
HAVING COUNT(DISTINCT "p"."FAMILY_ID") > 1
```

Snow: `invalid identifier '"p".FAMILY_ID'` — because catalog has `family_id` lowercase.

The model also added a (probably correct) `entity_status = 'Granted'` filter that wasn't in v27c, but that's not what breaks the query.

---

## 8. What I'd recommend, strictly out-of-scope for Phase 28

1. **Revert F2a** entirely. Drop the `fix_mixedcase_quoting` call site in the runner (one-line change). Keep the module file for the record. The function is correctly implemented against its stated contract — the contract was just based on a wrong hypothesis.
2. **Revert the prompt's "UPPERCASE columns are unquoted" line**. It seeded the unquoted-emission regression visible across all 10 v28 tasks. Possibly also revert the `col:TYPE` rendering in the pack — needs an A/B check.
3. **Keep F4c**. It correctly stops fail-closing on LATERAL FLATTEN. The downstream parsers will still error on the same SQL until SQLGlot is upgraded or the validator is also taught to fall back.
4. **Keep F4**. Wraps are correct against the catalog. They don't help until the surrounding column-name grounding improves, but they are not load-bearing in either direction.
5. **Phase 29 should attack column-name hallucinations first** (the F3 self-refine that was deferred from this phase). The 4 cases labelled mixed-case in Phase 27 §5 are actually 4 column-name hallucinations and need the same treatment as sf_bq209's table-name hallucination. A single self-refine pass that feeds `invalid identifier 'X'` back to the planner with `"X is not in the schema; choose from <pack cols>"` would likely fix most of them.
6. **The lower-bound for Lite-Snow exec on this 10-task subset before any further work** is 1/10 (revert to v27c). The realistic ceiling on this subset, with F3 self-refine + correct case handling, is probably 5-6/10 — the same ceiling Phase 28 was aiming for, but reached via F3 rather than F2a.

---

## 9. Honest summary

- **What Phase 28 did:** correctly diagnosed F4c bug, correctly implemented F4 date-cast wrapper, correctly implemented F2a per spec, kept BQ/SQLite untouched, no FULL run launched.
- **What Phase 28 did NOT do:** lift exec_ok. It moved 1/10 → 0/10.
- **Why:** Phase 27's failure classification was wrong about `invalid identifier '"p"."country"'`. Those were column-name hallucinations, not case mismatch. F2a's contract is therefore not load-bearing for the actual Snow failure mix — and the surrounding prompt rewrite made the emitter drop quotes, which compounded with F2a's case-flip to break the one task that had been working.
- **Honest cost:** ~3h of debugging time, one regression run, zero exec gain. The diagnostic is genuinely valuable: we now know the catalog is lowercase-stored, which redirects Phase 29 to F3 self-refine and column-name grounding rather than dialect rewriting.

**Status:** STOPPED per brief acceptance gate (exec_ok ≤ 2/10 → серьёзный stop). No code reverted, no commits, no FULL launched. Awaiting instruction.

---

## Appendix: files touched in Phase 28

- [repo/src/evaluation/snow_identifier_guard_v27.py](../repo/src/evaluation/snow_identifier_guard_v27.py) — F4c regex fallback + 2 new self-tests
- [repo/src/evaluation/snow_dialect_fixer_v28.py](../repo/src/evaluation/snow_dialect_fixer_v28.py) — **new** module with F2a + F4 + 11 self-tests
- [tools/remote_scripts/_phase27_snow_runner.py](../tools/remote_scripts/_phase27_snow_runner.py) — wire fixer between guard and schema_valid; counters; prompt rule; `col:TYPE` rendering; `instance_ids_set` filter
- [tools/_send_phase28_step_by_step.py](../tools/_send_phase28_step_by_step.py) — local driver (cloudflare-tolerant chunked upload)
- [tools/remote_scripts/_phase28_*.py](../tools/remote_scripts/) — probes, diagnostics, and pull scripts

**Run dirs (kept on Drive, no cleanup):**
- `outputs/spider2_lite/runs/lite_snow_pilot10_v28/` — the regression run (0/10 exec)
- `outputs/spider2_snow/runs/snow_full_v25/` — S1 baseline sealed at 509/547 (`_STOPPED_PHASE28` marker; exec=0)
