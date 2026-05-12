# 08.07 — candidate_selector_v18.py

## Покрытие модуля

`repo/src/evaluation/candidate_selector_v18.py` (~364 LOC) — final gate перед output: оценивает каждого candidate через mini-pipeline (parse → AST closed-set → optional BQ dry_run), затем выбирает лучшего по priority score. Главные экспорты:

| Symbol | Purpose |
|---|---|
| `CandEval` | Per-candidate evaluation result dataclass |
| `parse_with_sqlglot_bq(sql)` | Parse helper (BQ dialect) |
| `_normalize_pack_names(pack)` | Build residency-check lookup tables from pack |
| `schema_valid_against_pack(sql, pack)` | AST closed-set residency check (BQ-style) |
| `dry_run_bq(sql)` | BQ dry_run wrapper |
| `evaluate_candidate(cand, pack, do_dry_run)` | Per-candidate evaluator |
| `select(candidates, pack, do_dry_run)` | Главный entry — оценить все candidate-ы + tie-break |

Inputs: `(candidates: list[dict], pack: dict, do_dry_run: bool)`. Outputs: `{evals, chosen_idx, chosen}` dict.

Hooked в pipeline: на **BQ lane** (где Family A/B/C все три producing candidates) — called после `emit_candidates`. На Snow lane runner-specific (`_phase27_snow_runner.py` использует упрощённый selector: только Family B exists). На SQLite — single-candidate, selector trivial.

## Code walkthrough

### Excerpt 1 — Module purpose + v18.1 patch comment (lines 1-22)

```python
"""candidate_selector_v18 — validator + minimal probe + selection policy.

Validator-first selection over a list of candidate SQLs.

v18.1 patch: replaced regex-based identifier residency with **AST-aware**
walking of the sqlglot parse tree. The earlier regex split on hyphens,
which falsely flagged `bigquery-public-data` as 3 separate "leaks"
(`bigquery`, `public`, `data`). The AST walker pulls Table.parts and
Column.parts directly from sqlglot, so hyphenated GCP project names,
nested struct paths, and wildcard date shards are handled correctly.

Wildcards: a candidate's table reference `<base>_<YYYYMMDD>` is treated
as residency-OK if the pack contains any sibling `<base>_<other_date>`
or a `<base>_*` family entry. This matches BigQuery's wildcard table
semantics.

Selection policy (in priority order):
  1. dry_run_ok (BQ live dry_run / explain) — first non-zero signal
  2. parse_ok (sqlglot in BQ dialect)
  3. schema_valid (identifiers exist in pack)
  4. preference for family A (deterministic) over B (LLM) when tied
"""
```

**Что критично**: docstring documents one of the **most important Phase 19 lessons** — regex-based residency check (Phase 18 v18.0) flagged `bigquery-public-data` as **3 separate leaks** (`bigquery`, `public`, `data`) because hyphen treated как separator. Phase 19 v18.1 fix — AST-aware walking pulls `Table.parts` directly from SQLGlot tree, preserving GCP project naming.

Также documented: **wildcard semantics** — `ga_sessions_20170201` is residency-OK if pack contains any `ga_sessions_*` or sibling `ga_sessions_<date>`. This matches BQ wildcard table semantics — without this, Family A's wildcard render would be rejected by AST validator.

### Excerpt 2 — Residency lookup construction (lines 55-120)

```python
def _normalize_pack_names(pack: dict) -> dict:
    """Return a structured residency dictionary derived from the pack.
    Returns {
      'projects':       set[str],   # db field
      'datasets':       set[str],   # schema field
      'project_dataset':set[str],   # 'project.dataset'
      'tables':         set[str],   # bare table names
      'wildcard_bases': set[str],   # date-shard families: 'ga_sessions'
      'columns_full':   set[str],   # full struct paths or column names
      'columns_root':   set[str],   # leaf top-level column or root of struct
      'columns_leaf':   set[str],   # last segment of nested path
    }
    """
    projects = set()
    datasets = set()
    project_dataset = set()
    tables = set()
    wildcard_bases = set()
    columns_full = set()
    columns_root = set()
    columns_leaf = set()

    for d in pack.get('databases', []):
        projects.add(d.get('name', ''))
        for s in d.get('schemas', []):
            datasets.add(s)
            project_dataset.add(f"{d.get('name','')}.{s}")

    for t in pack.get('tables', []):
        proj = t.get('db', '')
        dset = t.get('schema', '')
        tname = t.get('table', '')
        projects.add(proj)
        datasets.add(dset)
        project_dataset.add(f'{proj}.{dset}')
        tables.add(tname)
        # date-shard family
        m = _DATE_SHARD_RE.match(tname)
        if m:
            wildcard_bases.add(m.group('base'))
        # v22 STAGE A2: union BM25 top-K columns AND full all_columns side
        # channel for residency.
        bm25_cols = [c.get('name') or '' for c in t.get('columns', [])]
        all_cols = t.get('all_columns', []) or []
        for cn in list(bm25_cols) + list(all_cols):
            if not cn:
                continue
            columns_full.add(cn)
            if '.' in cn:
                parts = cn.split('.')
                columns_root.add(parts[0])
                columns_leaf.add(parts[-1])
            else:
                columns_root.add(cn)
                columns_leaf.add(cn)
    return {
        'projects': projects, 'datasets': datasets,
        'project_dataset': project_dataset, 'tables': tables,
        'wildcard_bases': wildcard_bases,
        'columns_full': columns_full, 'columns_root': columns_root,
        'columns_leaf': columns_leaf,
    }
```

**Что критично**: **8 separate sets**, each indexed by different identifier granularity. Residency check downstream queries different sets for different parts of qualified identifier:

- Column reference `hits.product.productRevenue` → splits to `[hits, product, productRevenue]` → check `columns_full` (full path), `columns_root` (root = `hits`), `columns_leaf` (leaf = `productRevenue`). Any match → residency OK.
- Bare column `family_id` → matches `columns_root` OR `columns_leaf` (both contain `family_id` since no `.` split).
- Wildcard table `ga_sessions_20170201` → splits via `_DATE_SHARD_RE`, matches `wildcard_bases` set если `ga_sessions` есть.

**Phase 22 STAGE A2 contribution** — lines 100-103 — union BM25-top-K columns AND `all_columns` side-channel. Without `all_columns`, residency check would have 10+ false-positive rejections per pilot10 task.

### Excerpt 3 — `evaluate_candidate` per-candidate runner (lines 323-345)

```python
def evaluate_candidate(cand: dict, pack: dict, *, do_dry_run: bool = True) -> CandEval:
    sql = cand.get('sql') or ''
    ev = CandEval(family=cand.get('family', '?'), sql=sql)
    if not sql:
        ev.error_class = 'empty_sql'
        return ev
    ast, perr = parse_with_sqlglot_bq(sql)
    ev.parse_ok = ast is not None
    if not ev.parse_ok:
        ev.error_class = 'parse_error'
        ev.error_msg = perr
    sok, serr = schema_valid_against_pack(sql, pack)
    ev.schema_valid = sok
    if not sok:
        ev.error_class = ev.error_class or 'schema_invalid'
        ev.error_msg = ev.error_msg or serr
    if do_dry_run and ev.parse_ok:
        dok, derr = dry_run_bq(sql)
        ev.dry_run_ok = dok
        if not dok:
            ev.error_class = ev.error_class or 'bq_dry_run_failed'
            ev.error_msg = ev.error_msg or derr
    return ev
```

**Что критично**:
- **Three checks** в order: parse → schema_valid → dry_run.
- **`error_class = ev.error_class or '...'`** pattern: first failure wins. Если parse failed, не overwrite с schema_invalid.
- **`do_dry_run` flag**: optional. На pilot runs можно set False для cost-controlled experimentation; на FULL runs всегда True.
- **`dry_run` only если `parse_ok`**: don't waste BQ API call на un-parseable SQL.

### Excerpt 4 — `select` priority logic (lines 348-364)

```python
def select(candidates: list, pack: dict, *, do_dry_run: bool = True) -> dict:
    evals = [evaluate_candidate(c, pack, do_dry_run=do_dry_run) for c in candidates]

    def score(ev: CandEval) -> tuple:
        return (
            int(ev.dry_run_ok),
            int(ev.parse_ok),
            int(ev.schema_valid),
            1 if ev.family == 'A' else 0,
        )

    chosen = max(range(len(evals)), key=lambda i: score(evals[i])) if evals else -1
    return {
        'evals': [ev.__dict__ for ev in evals],
        'chosen_idx': chosen,
        'chosen': evals[chosen].__dict__ if chosen >= 0 else None,
    }
```

**Что критично**: **lexicographic tuple comparison** — Python's `max` over tuples compares element-by-element. `(1, 1, 1, 1) > (1, 1, 1, 0) > (1, 1, 0, 0) > ...`. This gives **strict priority order**:

1. `dry_run_ok` — highest signal weight.
2. `parse_ok` — secondary.
3. `schema_valid` — tertiary.
4. Family A preference — tie-break only when first three equal.

Если candidates = `[A: (1,1,1,1), B: (1,1,1,0), C: (1,1,1,0)]` → A wins (Family A tie-break).

Если candidates = `[A: (1,0,0,1), B: (1,1,1,0)]` → B wins (parse_ok > Family A preference). This shows priority order **correctly weighs validation outcomes over family tie-break**.

## Design decisions, видные в code

### D1. AST-aware residency (Phase 19 v18.1 fix)
Initial v18.0 used regex; failed на `bigquery-public-data`. Phase 19 patched. Documented в module docstring — historical record.

### D2. Wildcard handling via `_DATE_SHARD_RE`
Date-shard regex `^(?P<base>.+?)_(?P<date>\d{6,8})$` matches `ga_sessions_20170201` → base `ga_sessions`. Pack stores `ga_sessions_*` form в wildcards (см. [01_schema_pack_builder_v18.md](./01_schema_pack_builder_v18.md)) → residency match through `wildcard_bases` set.

### D3. Phase 22 STAGE A2 — union BM25 + all_columns
`columns_full / root / leaf` includes BOTH top-K BM25 hits AND full all_columns side-channel. Reduces false-positive rejections.

### D4. Priority tuple lexicographic compare
Pythonic implementation tie-break — без explicit nested if/else.

### D5. `do_dry_run` flag для cost control
On pilot10 runs, can set False to skip BQ API calls. На FULL — True default.

## Edge cases handled

- **Empty SQL**: `error_class = 'empty_sql'`, all checks skipped.
- **SQLGlot parse failure**: `parse_ok = False`, schema_valid still attempted (regex-based fallback might catch).
- **No candidates** в input list: `chosen = -1`, returned `chosen=None`.
- **GCP hyphenated project**: AST-aware walking handles.
- **Wildcards**: `_DATE_SHARD_RE` based match через `wildcard_bases`.
- **Struct paths**: Phase 22 A2 column union — `columns_full / root / leaf` all checked.
- **All candidates fail**: highest-scoring (least bad) returned for diagnostic — selector не raises.

## Test coverage

**Нет formal unit tests**. Integration coverage:
- Phase 19 BQ pilot10 → traces show `chosen_family` distribution (validates Family A tie-break).
- Phase 22 audit → confirmed `all_columns` union reduces false-positive rate.
- Phase 24 → A4 engine-compat rewrites validated via selector outcomes.

**Tech debt**: add `tests/test_candidate_selector_v18.py` с cases:
- Priority order на various candidate combinations.
- Wildcard residency matching.
- Hyphenated project residency.
- struct path residency.

## Known limitations

| # | Limitation | Impact | Mitigation |
|---|---|---|---|
| L1 | BQ-dialect SQLGlot parse used (line 49) | На Snow lane SQL parse via 'snowflake' dialect — но selector uses 'bigquery'. Phase 27+ Snow runner has own selector logic | Snow runner bypasses this module |
| L2 | No trained ranker | Simple priority order; CHASE-SQL [arXiv 2410.01943] trained 7B selector gives +3-5 EX | Phase 31+ |
| L3 | No tests | Refactoring risk | Add as future work |
| L4 | Family C bias underrepresented | Family C tie-break preference always 0 — only A vs B | Could add Family-C-preferred flag |

## Evolution history

| Phase | Change |
|---|---|
| **v18 (Phase 18)** | Initial: regex-based residency. |
| **v18.1 (Phase 19)** | AST-aware residency replaces regex. Fixes `bigquery-public-data` false-leak. |
| **Phase 22 STAGE A2** | `all_columns` union в residency check. Reduces false-positive schema_invalid. |
| **Phase 24** | A4 engine-compat rewrites integration (separate module) — selector evaluates rewritten SQL. |
| **Phase 27-28** | Snow runner uses **own selector logic** (simplified, no Family A на Snow). This module — BQ-only. |

## Cross-references

- Architecture description: [04_ARCHITECTURE/08_candidate_selector.md](../04_ARCHITECTURE/08_candidate_selector.md)
- Candidate factories (input): [03_candidate_factories.md](./03_candidate_factories.md)
- Validators (downstream): [04_validators_suite.md](./04_validators_suite.md)
- Pack builder (residency source): [01_schema_pack_builder_v18.md](./01_schema_pack_builder_v18.md)
- Phase 19 v18.1 narrative: [06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md)
- Phase 22 A2 narrative: same file
- CHASE-SQL trained selector alternative: [02_RELATED_WORK/02_sota_systems_2024_2026.md](../02_RELATED_WORK/02_sota_systems_2024_2026.md)

## Источники

| Утверждение | Источник |
|---|---|
| Module structure | `repo/src/evaluation/candidate_selector_v18.py` |
| v18.1 AST-aware patch | lines 1-22 docstring |
| `_normalize_pack_names` 8 sets | lines 55-120 |
| Phase 22 A2 column union | lines 100-103 |
| Priority lexicographic tuple compare | lines 351-357 |
| Selection trace на pilot10 traces | `outputs/spider2_lite/runs/lite_*` runs |
| Phase 27/28 Snow uses own selector | `tools/remote_scripts/_phase27_snow_runner.py` (does not call candidate_selector_v18.select) |
