# 08.02 — schema_linking_v18.py

## Покрытие модуля

`repo/src/evaluation/schema_linking_v18.py` (~312 LOC) — **entry point** pipeline-а на Spider 2.0 lanes. Реализует BM25 retrieval columns поверх live `INFORMATION_SCHEMA` catalog. Главные экспорты:

| Symbol | Type | Purpose |
|---|---|---|
| `CatalogColumn` | `@dataclass` | unified row from BQ / Snow live catalogs |
| `load_catalog_jsonl(path, lane)` | function | parses harvested jsonl с lane-specific field-name normalization |
| `tokenize(s)` | function | camelCase + numeric boundary + lowercase split |
| `expand_with_synonyms(toks)` | function | light hand-tuned synonym expansion |
| `BM25` | `@dataclass` | own implementation Okapi BM25 (`k1=1.5, b=0.75`) |
| `SchemaLinker` | class | indexes columns, answers `query(question, ...)` |
| `LinkerOutput` | `@dataclass` | results: ranked hits + db/table scores |

Inputs: `(catalog_path, lane)` для init; `(question, alias_filter, db_filter, top_columns, top_tables)` для query.

Outputs: `LinkerOutput` с list `LinkerHit(record, score, breakdown)`, sorted by score desc; aggregated db_score / table_score.

Hooked в pipeline runner-ом (e.g., `tools/remote_scripts/_phase27_snow_runner.py` lines 336-406): runner делает **fresh SchemaLinker per task** на subset catalog (Phase 27 F1 partition).

## Code walkthrough

### Excerpt 1 — Identifier tokenization (lines 38-55)

```python
_CAMEL_RE = re.compile(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')
_NUM_RE = re.compile(r'(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])')
_NON_WORD = re.compile(r'[^A-Za-z0-9]+')

def tokenize(s: str) -> list:
    if not s:
        return []
    s = _NON_WORD.sub(' ', s)           # strip punctuation / underscore boundaries
    parts = []
    for w in s.split():
        # split camelCase, then numeric boundaries, then lower
        for sub in _CAMEL_RE.split(w):
            for sub2 in _NUM_RE.split(sub):
                if sub2:
                    parts.append(sub2.lower())
    return parts
```

**Почему критично**: без identifier-aware splitting BM25 не matches `assignee_harmonized` с query word "assignee". Это одна из главных **silent failure modes** в early phases: ranking казалось работает, но recall systematically misses underscore-separated columns. Tokenization fix Phase 18.

`_CAMEL_RE` ловит **два класса boundary**: `aB` (lowercase-to-uppercase, e.g., `cropHints`→`crop|Hints`) и `ABc` (multi-uppercase preceding regular, e.g., `MD5Hash`→`MD5|Hash`). `_NUM_RE` ловит letter↔digit boundary (e.g., `event20220715`→`event|20220715`, no further numeric split — это design choice, не bug).

### Excerpt 2 — Synonym expansion (lines 58-96)

```python
_SYNONYMS: dict = {
    'count': ['n', 'num', 'number', 'cnt', 'total'],
    'avg': ['average', 'mean'],
    'date': ['day', 'time', 'datetime', 'timestamp', 'dt'],
    'user': ['users', 'customer', 'customers', 'client', 'clients', 'account', 'visitor'],
    'product': ['products', 'item', 'items', 'sku', 'goods'],
    'order': ['orders', 'purchase', 'transaction'],
    'revenue': ['sales', 'income', 'earnings', 'gmv'],
    # ... ~30 entries total
}

def expand_with_synonyms(toks: list) -> list:
    out = list(toks)
    for t in toks:
        if t in _SYNONYMS:
            out.extend(_SYNONYMS[t])
    return out
```

**Почему критично**: query about "how many users" → не matches column `n_visitors` без synonym mapping `user→visitors`. Hand-tuned table — domain-specific (analytics, e-commerce, ad-tech). Не реализуется через learned embeddings — мы предпочли determined behavior recall (synonym tables can be audited and extended).

**Design decision** видимый в code: synonyms добавляются к query токенам, **не к document токенам**. Это значит, query "how many customers" → expanded to `[how, many, customers, customer, users, user, client, ...]`. Document может contain `customers` literally, и match works через `customers→customers` direct. Если document содержит `users` and query word `customer`, match via `customer→users`. Если document and query оба contain neither — no match (synonym table одна, не bidirectional).

### Excerpt 3 — BM25 scoring (lines 99-138)

```python
@dataclass
class BM25:
    k1: float = 1.5
    b: float = 0.75
    docs: list = field(default_factory=list)
    df: dict = field(default_factory=dict)
    avgdl: float = 0.0
    N: int = 0

    def fit(self, docs: list) -> None:
        self.docs = docs
        self.N = len(docs)
        self.avgdl = sum(len(d) for d in docs) / max(1, self.N)
        df = Counter()
        for d in docs:
            for t in set(d):
                df[t] += 1
        self.df = dict(df)

    def idf(self, t: str) -> float:
        n_t = self.df.get(t, 0)
        if n_t == 0:
            return 0.0
        return math.log((self.N - n_t + 0.5) / (n_t + 0.5) + 1.0)

    def score(self, q_toks: list, d_toks: list) -> float:
        if not q_toks or not d_toks:
            return 0.0
        dl = len(d_toks)
        c = Counter(d_toks)
        s = 0.0
        for t in q_toks:
            f = c.get(t, 0)
            if f == 0:
                continue
            idf = self.idf(t)
            s += idf * (f * (self.k1 + 1)) / (f + self.k1 * (1 - self.b + self.b * dl / max(1, self.avgdl)))
        return s
```

**Standard Okapi BM25 formula**. Параметры `k1=1.5, b=0.75` — librarian defaults для general retrieval. Не tuned под наш task — могут быть subtle improvements от calibration, но для thesis scope acceptable.

**Subtle implementation detail** (line 124): `max(1, self.avgdl)` в length normalization — защита от division by zero, если catalog пустой. Также `max(1, self.N)` в `avgdl` computation (line 113). Без этих защит — `ZeroDivisionError` на empty catalog (rare edge case, но happened during early development).

### Excerpt 4 — Document construction (lines 235-257)

```python
@staticmethod
def _make_doc(c: CatalogColumn) -> list:
    toks = []
    toks += tokenize(c.column)
    if c.field_path and c.field_path != c.column:
        toks += tokenize(c.field_path)
    toks += tokenize(c.table)
    toks += tokenize(c.schema)
    toks += tokenize(c.description)
    toks += tokenize(c.data_type)
    # Type signal: rough keyword for common types
    dt = (c.data_type or '').lower()
    if 'int' in dt or 'numeric' in dt or 'float' in dt or 'number' in dt:
        toks.append('numeric')
    if 'date' in dt or 'time' in dt or 'timestamp' in dt:
        toks.append('temporal')
    if 'string' in dt or 'text' in dt or 'varchar' in dt:
        toks.append('text')
    if 'array' in dt or 'repeated' in dt:
        toks.append('array')
    if 'struct' in dt or 'record' in dt:
        toks.append('struct')
    return toks
```

**Document = combined tokens** column + field_path + table + schema + description + data_type + abstract type tags. Это даёт scoring сigy:

- Question word matching column name: direct hit, max score.
- Question word matching table name: also strong signal.
- Question word matching description: medium signal (description often paraphrases column purpose).
- Query about "year" matches column with `data_type='DATE'` через abstract `temporal` tag — even если column name не contains "year". This is small but useful boost для date-related queries.

### Excerpt 5 — Query method (lines 259-288)

```python
def query(self, question: str, *, alias_filter: Optional[str] = None,
          top_columns: int = 80, top_tables: int = 25,
          db_filter: Optional[str] = None) -> LinkerOutput:
    q_toks = expand_with_synonyms(tokenize(question))
    # Score every column
    scored = []
    db_score = defaultdict(float)
    table_score = defaultdict(float)
    for i, c in enumerate(self.columns):
        if alias_filter and c.alias and c.alias != alias_filter:
            continue
        if db_filter and c.db != db_filter:
            continue
        s = self.bm25.score(q_toks, self._docs[i])
        if s <= 0:
            continue
        scored.append(LinkerHit(record=c, score=s, breakdown={'bm25': s}))
        db_key = f"{c.db}.{c.schema}"
        tab_key = f"{c.db}.{c.schema}.{c.table}"
        db_score[db_key] += s
        table_score[tab_key] += s
    scored.sort(key=lambda h: h.score, reverse=True)
    scored = scored[:top_columns]
    return LinkerOutput(
        hits=scored,
        db_score=dict(db_score),
        table_score=dict(table_score),
        n_columns_indexed=len(self.columns),
        n_tables_indexed=len({(c.db, c.schema, c.table) for c in self.columns}),
    )
```

**Two filters** (`alias_filter`, `db_filter`) — для Spider2-Lite-BQ + Spider2-Snow lane-specific behavior. **Phase 27 F1 insight**: `alias_filter` is no-op на Snow lane because `c.alias == ''` for all Snow rows (см. lines 188-198 в catalog loader). Phase 27 решение — использовать `db_filter` (которое filters by `c.db`, i.e., `TABLE_CATALOG`) и **per-task partitioning at runner level** (rebuilding linker per task on cat_subset). Это **не fix to query method** — `db_filter` уже был там, but не использовался в Snow path до Phase 27.

`s <= 0` filter — drops zero-score documents (no token overlap). Это saves memory at downstream sort.

`db_score` / `table_score` aggregations — для downstream pack builder, который выбирает top-N tables и нужны table-level rankings.

## Design decisions, видные в code

### D1. Lane-aware catalog loader (lines 161-199)
BQ live JSONL uses lowercase field names (`project`, `dataset`, `table_schema`, etc.), Snow live JSONL uses UPPER (`TABLE_CATALOG`, `TABLE_SCHEMA`, etc.). Loader has explicit two-branch logic. Это design choice **не из библиотеки**, а из observation что Snow `INFORMATION_SCHEMA.COLUMNS` results come back в uppercase keys.

### D2. `kind` field skipping (line 173)
```python
if r.get('kind') == 'error': continue
if r.get('kind') == 'table': continue
```
Catalog harvesting иногда записывает error rows (e.g., если access denied на specific schema) и table-level rows (separate metadata). Loader skips both — only column rows used для linker.

### D3. No CLS / SEP tokens
Pure BM25 — no transformer-style boundary tokens. Это intentional: BM25 — bag-of-words, не sequence model. Mixing approaches creates noise. Keep concerns separated.

### D4. `expand_with_synonyms` not applied to documents
Already discussed. Query-side expansion only. **Asymmetric** by design — synonyms list is one-way mapping.

## Edge cases handled

- **Empty catalog**: `max(1, …)` guards в BM25 `fit` and `score`.
- **Empty question**: `if not q_toks or not d_toks: return 0.0` в `score`.
- **Catalog rows missing fields**: `.get('field', '') or ''` consistently used in loader (lines 177-198).
- **`field_path == column`**: line 239 skip duplicate tokenization of field_path if it равен column. BQ flat columns have `field_path == column`; nested have `field_path = "parent.child"` different from `column = "parent"`.
- **Numeric tokenization** для year-encoded columns: regex `_NUM_RE` splits letter↔digit boundary, но не digit-digit. So `20220715` остаётся single token. Trade-off: queries про specific year don't match year-encoded columns by digit substring, but queries don't usually phrase that way (typically "year 2022" matches via synonyms).

## Test coverage

Module имеет **тiny CLI smoke** (lines 293-312):

```bash
python -m repo.src.evaluation.schema_linking_v18 \
  --catalog outputs/cache/spider2_snow_live_catalog_v18.jsonl \
  --lane snow \
  --question "How many active patent assignees per region per year?" \
  --db PATENTS \
  --top 15
```

Outputs top-15 ranked hits с scores и db summary. Used during Phase 17-18 development для manual inspection BM25 quality.

**Что НЕ покрыто tests**:
- No formal unit tests для `tokenize` (camelCase boundaries, numeric boundaries).
- No tests для `expand_with_synonyms` (validate all entries reachable).
- No tests для `BM25.score` (e.g., reproduce textbook example values).

Это **technical debt** — модуль changed Phase 17→18→27 без regression tests. Phase 27 fix per-task partitioning was верно по логике, но без unit-level guarantees. Recommended future work: add `tests/test_schema_linking_v18.py` with at least:
- `tokenize` boundary case suite,
- `BM25` reproducibility on known small dataset,
- `query` integration test на 10-row synthetic catalog.

## Known limitations

| # | Limitation | Impact | Mitigation |
|---|---|---|---|
| L1 | Synonym table — analytics domain only | Healthcare / genomics queries undr-recall | Manual extension; or learned embeddings |
| L2 | No semantic similarity beyond tokens | "Applicants" не matches `assignee` | Dense retriever альтернатива (см. RASL) |
| L3 | Numeric tokens not split | `20220715` single token | Не блокирующее — queries about years rarely use literal date |
| L4 | `alias_filter` no-op on Snow | Cross-DB drift до Phase 27 | Phase 27 F1 per-task partition by `db_filter` + caller-level subset |
| L5 | No tests | Refactoring risk | Add tests as future work |
| L6 | Memory: индексирует full catalog в `self._docs` | На 587K columns Snow ~700 MB list memory | Per-task partition limits subset to ≤50K — manageable |

## Evolution history

| Version / Phase | Change |
|---|---|
| v18 (Phase 18) | Initial implementation: BM25 + tokenization + synonym table |
| (Phase 19-22) | Minor synonym additions, no algorithmic changes |
| (Phase 22 STAGE A2) | No changes в этом модуле — pack builder consumes; linker stable |
| (Phase 24) | No changes |
| (Phase 27) | **No code change в этом модуле**. Phase 27 fix at runner level (per-task `SchemaLinker(cat_subset)`). Это значит модуль остался semantically stable across major fix-уровень interventions — testimony to clean separation of concerns. |
| (Phase 28) | No changes |

Module — **stable** since Phase 18. Все subsequent fixes layered above через runner orchestration, не патчили internal BM25 logic.

## Cross-references

- Architecture description: [04_ARCHITECTURE/03_schema_linker_v18_bm25.md](../04_ARCHITECTURE/03_schema_linker_v18_bm25.md)
- Pack builder (consumer): [01_schema_pack_builder_v18.md](./01_schema_pack_builder_v18.md)
- Runner integration (per-task partition): [08_runner_orchestration.md](./08_runner_orchestration.md)
- Phase 27 F1 narrative: [06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md](../06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md)
- Schema-linking literature: [02_RELATED_WORK/05_schema_linking_approaches.md](../02_RELATED_WORK/05_schema_linking_approaches.md)

## Источники

| Утверждение | Источник |
|---|---|
| Module structure + exports | `repo/src/evaluation/schema_linking_v18.py` |
| Tokenization regex | lines 38-55 |
| BM25 algo | lines 99-138 |
| `_make_doc` token bag | lines 235-257 |
| Per-task partition at runner | `tools/remote_scripts/_phase27_snow_runner.py` lines 336-406 |
| Phase 17-18 phase findings | memory `spider2_phase17_findings.md`, `spider2_phase18_findings.md` |
