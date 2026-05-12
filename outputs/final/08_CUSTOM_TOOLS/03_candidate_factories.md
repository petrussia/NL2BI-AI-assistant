# 08.03 — candidate_factories (spider2_candidate_factory_v18 + sql_renderer_v18)

## Покрытие модулей

Две тесно связанные модули:

1. **`repo/src/evaluation/spider2_candidate_factory_v18.py`** (~106 LOC) — главная диспетчерская функция `emit_candidates(question, pack, plan, ...)` производит набор SQL-кандидатов от Family A/B/C.
2. **`repo/src/evaluation/sql_renderer_v18.py`** (~451 LOC) — реализация deterministic SQL renderer-ов: `render_bq`, `render_bq_with_joins`, `render_coder7b_direct_prompt`.

Главные экспорты factory модуля:

| Function | Family | Purpose |
|---|---|---|
| `family_A_deterministic(plan, pack, lane)` | A | Deterministic template render plan-JSON → BQ Standard SQL |
| `family_B_coder7b(question, pack, ek, _gen_fn)` | B | LLM emit (Coder-7B) с pack + question prompt |
| `family_C_join_aware(plan, pack, lane)` | C | JOIN-aware factory (BQ-only, Phase 22 STAGE A3) |
| `emit_candidates(question, pack, plan, ek, lane, _gen_fn)` | — | Orchestrator — calls all applicable families, returns list[candidate] |
| `_extract_sql(raw)` | — | Robust SQL extraction из free-form LLM output |

Inputs: `(question, pack, plan, external_knowledge, lane, _gen_fn)`. Outputs: list[dict] — каждый candidate as `{family, sql_raw, sql, meta}`.

Hooked в pipeline: runner calls `emit_candidates(...)` после plan validation; returned list передан `candidate_selector_v18.select(...)`.

## Code walkthrough

### Excerpt 1 — Family A deterministic (factory line 40-44)

```python
def family_A_deterministic(plan: dict, pack: dict, *, lane: str = 'bq') -> dict:
    from sql_renderer_v18 import render_bq
    sql = render_bq(plan, pack=pack) if lane == 'bq' else render_bq(plan, pack=pack)
    return {'family': 'A', 'sql_raw': sql, 'sql': sql,
              'meta': {'tables_used': plan.get('selected_tables', [])}}
```

**Что критично**: thin wrapper над `sql_renderer_v18.render_bq`. Note: lane is параметр, но **fall-back на render_bq** даже для не-BQ lane. Это — **Family A is BQ-only** в практике; на Snow lane runner не calls Family A, на SQLite — тоже. Trade-off: код мог бы explicitly raise для non-BQ lane, но silent BQ-fallback proven enough для current pipeline.

Critical look at `render_bq` (in `sql_renderer_v18.py`) — handles:
- Three-part name rendering (`project.dataset.table`),
- Nested column path support (`hits.product.productRevenue`),
- Wildcard table syntax (`events_* + _TABLE_SUFFIX BETWEEN`),
- UNNEST для array columns,
- BQ-specific date literals (`DATE '2023-12-15'`),
- GROUP BY / ORDER BY / LIMIT rendering из plan-JSON.

### Excerpt 2 — Family B Coder-7B emit (factory lines 57-73)

```python
def family_B_coder7b(question: str, pack: dict, external_knowledge: str = '',
                      *, _gen_fn=None) -> dict:
    """Family B uses Qwen2.5-Coder-7B-Instruct as a control direct emitter."""
    from sql_renderer_v18 import render_coder7b_direct_prompt
    prompt = render_coder7b_direct_prompt(question, pack, external_knowledge)
    if _gen_fn is None:
        _gen_fn = globals().get('_gen') or __builtins__.__dict__.get('_gen')
    if _gen_fn is None:
        raise NotImplementedError('No _gen function available for family B')
    raw = _gen_fn(prompt, max_new=900)
    return {'family': 'B', 'sql_raw': raw, 'sql': _extract_sql(raw),
              'meta': {'prompt_chars': len(prompt)}}
```

**Что критично**: Family B **doesn't depend on plan-JSON**. Получает `(question, pack, external_knowledge)` и produces SQL directly. Это **значит**: если planner failed (plan=None / validator exhausted), Family B all-the-same can run и produce candidate.

**`_gen_fn` injection pattern** — глобальная переменная `_gen` (deterministic decoding wrapper) injected на runner level. Это allows тот же factory used в разных runner-ах (Snow, BQ, Spider1/BIRD) с разными prompt templates.

### Excerpt 3 — Family C JOIN-aware (factory lines 47-54)

```python
def family_C_join_aware(plan: dict, pack: dict, *, lane: str = 'bq') -> dict:
    """v22 STAGE A3 — deterministic multi-table JOIN rendering when the
    plan picks ≥2 tables and pack.join_hints lists a connecting hint."""
    from sql_renderer_v18 import render_bq_with_joins
    sql = render_bq_with_joins(plan, pack=pack)
    return {'family': 'C', 'sql_raw': sql, 'sql': sql,
              'meta': {'tables_used': plan.get('selected_tables', []),
                          'join_hints_in_pack': len(pack.get('join_hints') or [])}}
```

**Что критично**: Phase 22 STAGE A3 introduction. **`render_bq_with_joins`** (в `sql_renderer_v18.py`) реализует:
- Match plan.selected_tables → pack.join_hints для inference JOIN paths.
- BFS over join_hints edges чтобы spanning-tree connecting all tables.
- Render `INNER JOIN` clauses с derived ON conditions.
- Falls back на single-table render если no path found.

**Empirical issue** (Phase 22 audit): Family C **rarely chosen** by selector — generates false-positive JOINs (e.g., `created_at` shared by two tables ≠ proper FK). Output often fails AST validator. Family C → schema_invalid → selector deprioritizes.

### Excerpt 4 — Orchestrator `emit_candidates` (factory lines 76-106)

```python
def emit_candidates(question: str, pack: dict, plan: Optional[dict],
                       external_knowledge: str = '',
                       *, lane: str = 'bq', _gen_fn=None) -> list:
    cands = []
    if plan is not None:
        try:
            cands.append(family_A_deterministic(plan, pack, lane=lane))
        except Exception as e:
            cands.append({'family': 'A', 'sql': '', 'sql_raw': '',
                          'meta': {'error': f'{type(e).__name__}:{str(e)[:200]}'}})
        # v22 STAGE A3: emit Family C only when the plan picks multiple
        # tables AND a join hint exists.
        sel_tabs = plan.get('selected_tables') or []
        bare_tabs = {t.split('.')[-1] if '.' in t else t for t in sel_tabs}
        n_join_hints = len(pack.get('join_hints') or [])
        if len(bare_tabs) >= 2 and n_join_hints > 0:
            try:
                cands.append(family_C_join_aware(plan, pack, lane=lane))
            except Exception as e:
                cands.append({'family': 'C', 'sql': '', 'sql_raw': '',
                              'meta': {'error': f'{type(e).__name__}:{str(e)[:200]}'}})
    if _gen_fn is not None:
        try:
            cands.append(family_B_coder7b(question, pack, external_knowledge,
                                            _gen_fn=_gen_fn))
        except Exception as e:
            cands.append({'family': 'B', 'sql': '', 'sql_raw': '',
                          'meta': {'error': f'{type(e).__name__}:{str(e)[:200]}'}})
    return cands
```

**Что критично**: each factory wrapped в `try/except`. Если render throws — pipeline does NOT abort — failed candidate added with empty SQL + error meta. Selector далее skips empty SQL candidates.

**Family C gating** — line 93: `if len(bare_tabs) >= 2 and n_join_hints > 0`. **Не tries Family C** если только одна table в plan OR no join hints. Эконоment compute (Family C falls back trivial на single table — irrelevant candidate).

**Family B unconditional** if `_gen_fn` available — always tries. Это **universal fallback** — даже если plan=None, Family B emits на (question, pack) directly.

### Excerpt 5 — `_extract_sql` robust extraction (factory lines 21-37)

```python
def _extract_sql(raw: str) -> str:
    if not raw:
        return ''
    m = re.search(r'```sql\s*\n?([\s\S]*?)```', raw, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r'```\s*\n?([\s\S]*?)```', raw)
    if m:
        cand = m.group(1).strip()
        if any(kw in cand.upper() for kw in ('SELECT', 'WITH')):
            return cand
    upper = raw.upper()
    for tag in ('WITH ', 'SELECT '):
        idx = upper.find(tag)
        if idx >= 0:
            return raw[idx:].strip()
    return raw.strip()
```

**Что критично**: ladder of extraction strategies, from strict (sql-tagged code fence) to lenient (anywhere `SELECT`/`WITH` starts). LLM output может vary; this robust pattern catches typical formats:

1. `` ```sql\n SELECT … \n``` `` — preferred format, Qwen2.5-Coder reliably emits.
2. `` ``` SELECT … ``` `` — generic fence (rare).
3. Free-form text starting with `SELECT` or `WITH`.
4. Fallback: entire raw output stripped.

## Design decisions, видные в code

### D1. `try/except` per family wrap
Failure isolation. One family's exception не cripples whole task.

### D2. `_gen_fn` dependency injection
Не imports `_gen` directly — accepts as parameter. Enables testing с mock_gen, plus switching emitter model per-task если нужно.

### D3. Family C gating condition
Pure heuristic on plan tables count + pack join hints. Не actual run-time check that JOIN path discoverable.

### D4. Empty candidates with error meta
Instead of raising or returning empty list, returns candidates with empty SQL. Это **diagnostic-friendly** — selector can audit `cands[*].meta` to attribute failures to factory vs other stages.

### D5. Lane parameter accepted but ignored для render
Line 42: `if lane == 'bq' else render_bq` — same call. Means `family_A_deterministic` is BQ-locked в practice. Cleaner code would raise для non-BQ; current state is **deliberate flexibility** для future extension (Snow Family A).

## Edge cases handled

- **`raw is None / ''`** in `_extract_sql`: returns empty string.
- **Multiple code fences** in raw output: first matching `sql`-tagged wins; if no sql-tagged, first generic with SELECT/WITH detection.
- **No code fence**: SELECT/WITH anchor search.
- **plan is None**: skip Family A and C; Family B still runs.
- **`_gen_fn is None`**: skip Family B silently.
- **pack.join_hints empty**: skip Family C.
- **plan.selected_tables empty**: skip Family C (`len(bare_tabs) >= 2` fails).

## Test coverage

**Нет unit tests на factory level**. Integration testing через runner runs — e.g., Phase 19 BQ pilot10 produced predictions.jsonl с `chosen_family` field per task → analyzed Family choice distribution.

`_extract_sql` — implicit testing через emit_candidates pipeline. Edge cases happened (Coder-7B sometimes emits unfenced SELECT, sometimes fence без `sql` tag) — ladder handles them.

**Technical debt**: no formal tests. Add as future work `tests/test_candidate_factory_v18.py`:
- `_extract_sql` ladder cases.
- `emit_candidates` with mock_gen function.
- Family C gating logic.

## Known limitations

| # | Limitation | Impact | Mitigation |
|---|---|---|---|
| L1 | Family A — BQ only | На Snow lane only Family B | Deferred Phase 30 (Snow Family A renderer) |
| L2 | Family C heuristic join hints | False-positive JOINs | Phase 30 — real FK metadata |
| L3 | No fine-tuned ranker | Pure priority order | Phase 31+ — CHASE-SQL-style trained selector |
| L4 | No tests | Refactoring risk | Add tests as future work |
| L5 | `_extract_sql` fallback "entire raw" | Raw output может содержать leading "Here is the SQL:" text → SQL parse fails downstream | Acceptable — engine validator catches |

## Evolution history

| Phase | Change |
|---|---|
| **v18 (Phase 18)** | Initial: Family A + Family B (named "two foundation families"). Comment mentions C/D «deferred to v18.1». |
| **v18.1 (Phase 19)** | Minor `_extract_sql` improvements; no Family C/D yet. |
| **Phase 22 STAGE A3** | **Family C added** (`family_C_join_aware`). Uses `render_bq_with_joins` from sql_renderer_v18. Gated on `len(tables) >= 2 and join_hints > 0`. |
| **Phase 24** | A4 (engine-compat rewrites) integrated via `bigquery_engine_compat_v24.py` (separate module). Applied to Family A output BEFORE dry_run. |
| **Phase 27** | No changes в factory module. F1 Snow grounding patched runner-level + pack-builder + AST guard — factories untouched. |
| **Phase 28** | No changes. F4 dialect-fixer applied **after** factory output, не inside factories. |

Module — stable since Phase 22 A3 introduction. Architecture **cleanly separates** factories from dialect handlers (F1/F4) — single-responsibility win.

## Cross-references

- Architecture description: [04_ARCHITECTURE/06_candidate_factories_family_abc.md](../04_ARCHITECTURE/06_candidate_factories_family_abc.md)
- Pack builder (input): [01_schema_pack_builder_v18.md](./01_schema_pack_builder_v18.md)
- Snow dialect handlers (apply after factory): [05_snow_identifier_guard_v27.md](./05_snow_identifier_guard_v27.md), [06_snow_dialect_fixer_v28.md](./06_snow_dialect_fixer_v28.md)
- Validator suite (consumes candidates): [04_validators_suite.md](./04_validators_suite.md)
- Selector (consumes candidates): [07_candidate_selector.md](./07_candidate_selector.md)
- Phase 22 A3 narrative: [06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md)
- Phase 24 engine-compat rewrites: [06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md)
- `sql_renderer_v18.py` details — referenced inline (separate file, 451 LOC).

## Источники

| Утверждение | Источник |
|---|---|
| Family A/B/C structure | `repo/src/evaluation/spider2_candidate_factory_v18.py` |
| `_extract_sql` ladder | lines 21-37 |
| Family C gating condition | lines 86-93 |
| Phase 22 A3 introduction | memory `spider2_phase22_findings.md` |
| Phase 24 A4 integration via `bigquery_engine_compat_v24.py` | memory `spider2_phase24_findings.md`; `outputs/REPORT_SPIDER2_PHASE24_LITE_BQ.md` |
