# 3.2.3 Schema linker v18 — BM25 над live catalog

## Главный тезис

Schema linker — **первый компонент** pipeline и **самый влияющий на performance** на Spider 2.0 family. Его задача — для каждой задачи найти top-K relevant `(table, column)` pairs из live INFORMATION_SCHEMA catalog. От качества этой выборки напрямую зависит, попадёт ли нужная таблица в pack — без неё все downstream стадии обречены на schema_invalid / column hallucination.

В работе используется **BM25** (rank_bm25-style ранжирование), реализованный в `repo/src/evaluation/schema_linking_v18.py` (~600 lines). Конкретно — own-implementation BM25 поверх **light synonym expansion** и **identifier-style tokenization** (camelCase + snake_case + numeric boundaries). **Embedding-free, GPU-free, fully deterministic.**

Главное архитектурное решение Phase 27 F1: **per-task partitioning by `TABLE_CATALOG`**. На Snow lane catalog содержит 587K columns across 152 databases; ranking над всей таблицей утекает hits из competitor databases в pack. Решение — для каждой задачи строим fresh BM25 index над subset catalog где `c.db.upper() == task_db.upper()` (типично 5K-50K columns). Это **architectural fix**, не hyperparameter — без него Snow lane был 0% executable до Phase 27.

## Источник входа: live INFORMATION_SCHEMA catalogs

| Lane | Catalog path | Размер | Sourcing |
|---|---|---|---|
| BigQuery | `outputs/cache/spider2_bq_live_catalog_v18.jsonl` | ~428K columns | batched `SELECT * FROM <project>.<dataset>.INFORMATION_SCHEMA.COLUMNS` |
| Snowflake | `outputs/cache/spider2_snow_live_catalog_v18.jsonl` | ~587K columns | batched `SELECT * FROM <database>.INFORMATION_SCHEMA.COLUMNS` |
| SQLite (Spider1/BIRD) | tables.json packaged | per-DB scale | не используется BM25, prompt direct schema text |
| DBT (Spider2-DBT) | DBT project files | per-project | агент читает existing `models/`, `schema.yml` напрямую |

Catalog harvesting сделан единократно в Phase 18 и не обновляется (snapshot at moment of harvest). Это создаёт некоторый риск **schema drift** на Snowflake / BigQuery, если warehouse owner добавляет / удаляет таблицы, но для академического evaluation acceptable.

Поля каждой записи — см. `CatalogColumn` dataclass (schema_linking_v18.py:144-158):

```python
@dataclass
class CatalogColumn:
    db: str        # BQ project / Snow database (TABLE_CATALOG)
    schema: str    # BQ dataset / Snow schema (TABLE_SCHEMA)
    table: str
    column: str
    data_type: str
    is_nullable: str
    description: str
    field_path: str  # для BQ nested fields (overrides column)
    alias: str       # Spider2 alias для BQ; '' для Snow
```

Особо важно: **`alias` пуст для всех Snow rows** (заполняется только для BQ Spider2 в processing pipeline). Phase 27 §1 диагностика обнаружила, что это делает `alias_filter` параметр linker-а no-op на Snow lane — отсюда необходимость per-task partition by `c.db` (TABLE_CATALOG, не alias).

## Алгоритм BM25

Реализация (schema_linking_v18.py:99-138) — own implementation Okapi BM25 с дефолтными параметрами:

| Параметр | Значение | Источник |
|---|---|---|
| `k1` | 1.5 | стандартный |
| `b` | 0.75 | стандартный |
| Tokenization | camelCase split + numeric boundary split + lowercase | own |
| Synonym expansion | light hand-tuned table (~30 entries) | own |

Каждая `CatalogColumn` rendered в "document" по template:

```
{db} {schema} {table} {column} {field_path} {data_type} {description}
```

(каждое поле tokenized отдельно, склеено в один list).

Query tokenization — то же + synonym expansion. Затем BM25 score per document; sorted descending.

Полный код BM25 в [08_CUSTOM_TOOLS/02_schema_linker_v18.md](../08_CUSTOM_TOOLS/02_schema_linker_v18.md).

## Tokenization details

Identifier-style split — критическая часть. Без него `assignee_harmonized` не split-ится на `[assignee, harmonized]` и не matches с query word "assignee".

```python
def tokenize(s: str) -> list:
    s = _NON_WORD.sub(' ', s)  # strip punctuation
    parts = []
    for w in s.split():
        for sub in _CAMEL_RE.split(w):     # camelCase boundary
            for sub2 in _NUM_RE.split(sub):  # numeric boundary
                if sub2:
                    parts.append(sub2.lower())
    return parts
```

Регулярки:
- `_CAMEL_RE = re.compile(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')` — boundary between `a-Z` и `Z-Aa`
- `_NUM_RE = re.compile(r'(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])')` — boundary letter↔digit
- `_NON_WORD = re.compile(r'[^A-Za-z0-9]+')` — punctuation cleanup

Примеры:

| Input | Token output |
|---|---|
| `assignee_harmonized` | `['assignee', 'harmonized']` |
| `ParticipantBarcode` | `['participant', 'barcode']` |
| `cropHintsAnnotations` | `['crop', 'hints', 'annotations']` |
| `event_date_20220715` | `['event', 'date', '20220715']` (numeric boundary inside camelCase pattern не срабатывает) |
| `MD5(content)` | `['md5', 'content']` |

## Synonym expansion

Light hand-tuned table (~30 entries) — конкретно analytics / Spider2 domain (schema_linking_v18.py:60-88):

```python
_SYNONYMS = {
    'count': ['n', 'num', 'number', 'cnt', 'total'],
    'avg': ['average', 'mean'],
    'date': ['day', 'time', 'datetime', 'timestamp', 'dt'],
    'user': ['users', 'customer', 'customers', 'client', 'clients', 'account', 'visitor'],
    'product': ['products', 'item', 'items', 'sku', 'goods'],
    'order': ['orders', 'purchase', 'transaction'],
    'revenue': ['sales', 'income', 'earnings', 'gmv'],
    # ...
}
```

Этот словарь покрывает наиболее частотные NL question phrasings (e.g. "how many users" → matches column `n_visitors` через `user`→`visitors` expansion). Не является комплексным — но достаточен в практике для типичных Spider 2.0 query patterns.

## Per-task partitioning (Phase 27 F1)

Архитектурный fix Phase 27 F1, реализованный в `tools/remote_scripts/_phase27_snow_runner.py`:

```python
# Pre-load full catalog once
full_catalog = sl.load_catalog_jsonl(cat_path, 'snow')

# Partition by TABLE_CATALOG (uppercase)
cat_by_db = defaultdict(list)
for c in full_catalog:
    cat_by_db[c.db.upper()].append(c)

# Per task: fresh BM25 over subset
for task in tasks:
    task_db = task.get('db').upper()
    cat_subset = cat_by_db[task_db]   # ~5K-50K columns vs 587K total
    linker = sl.SchemaLinker(cat_subset)
    link = linker.query(question, db_filter=task_db, top_columns=200, top_tables=40)
```

Эффект — таблица из competitor database **физически невозможна** в результате. Это даёт **0 guard_leaks across all pilot10 runs Phase 27/28** — guard не нужен для catching cross-DB drift, потому что drift невозможен на upstream level.

См. подробно: [06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md](../06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md).

## Retrieval window scaling (Phase 27 F1 side finding)

Defaults в Phase 1-16 (откалиброванные под Spider1/BIRD ≤30 tables per DB):

| Параметр | Spider1/BIRD default | Snow Phase 27 default | Lite-BQ default |
|---|---|---|---|
| `top_columns` | 80 | 200 | 80 (не менялось) |
| `top_tables` | 20 | 40 | 20 |

Rationale: на Spider2-Snow PATENTS — одна database содержит сотни таблиц с тысячами колонок. BM25 at top-80 columns не surface-ит достаточно candidate columns из правильной таблицы — нужная join key (`family_id`, `application_number`) лежит на rank 90-150. Расширение window 2.5× закрывает gap.

Pack budget (max_tables × max_cols_per_table) — **не меняется**: 10 × 22 = 220 columns final. Linker retrieves wider, builder cuts narrower. Это **separation of concerns**: linker recall vs pack precision/budget.

## Why BM25 а не dense retrieval

Альтернатива: embedding-based dense retrieval (BGE / E5 / ColBERT family) over same catalog.

| Аспект | BM25 (наш) | Dense retrieval |
|---|---|---|
| Compute | CPU-only, deterministic, sub-second per query | GPU embedding model + ANN index, ~50-200ms per query |
| Storage | catalog jsonl ~50-100 MB | + embedding index ~500MB-2GB |
| Quality at top-K=30 | adequate after per-task partition (Phase 27 evidence) | comparable; some lift на synonym-heavy queries |
| Reproducibility | full | depends on embedding model version, seed, ANN params |
| Cost in CI/CD | trivially low | significant |

**Точное observation**: согласно [Maamari et al., arXiv 2408.07702 "The Death of Schema Linking?"], "**modern LLMs at sufficient context length can sometimes outperform retrieval-based schema linking**" — это означает что если context fits, лучше дать всю schema модели напрямую. На Snow это не fits (587K columns ≠ context window). Поэтому BM25 необходим, а dense — incremental upgrade с диминишинг returns после per-task partition.

Decision: BM25 — **достаточно** для нашего use case. Dense retrieval deferred until baseline plateaus.

## PK/FK heuristic injection (Phase 27 correction 3)

BM25 имеет **systematic blind spot**: имена join key columns (типа `id`, `family_id`, `application_number`) имеют **low semantic similarity** с natural language question, поэтому ranked низко. Но они нужны для multi-table queries.

Решение (`tools/remote_scripts/_phase27_snow_runner.py:_inject_pk_fk`): после построения pack, **forcibly inject** до 4 columns per pack table, matching одну из heuristics:

```
'id', '<table_singular>_id', '*_pk', '*_fk', '*_id', '*_key', '*_sk'
```

Это **echoes CHESS** [Talaei et al., arXiv 2405.16755]: *"after BM25 picks columns, force-append declared PK/FK + heuristic *_id columns"*. Direct intellectual lineage — наш PK/FK injection реализует именно эту recipe.

Empirical effect: per-task `pk_fk_injected` counter в trace показывает 1-3 columns injected per task на Snow lane. Without injection, pilot10 v27c had schema_valid 7-8/10; with injection (Phase 27 correction 3 active), 8/10. Marginal но measurable.

## Limitations и known issues

### L1. Synonym table — domain-specific
~30 entries покрывают analytics domain (e-commerce, advertising, web events). Не покрывают finance (price/revenue только partially), healthcare, genomics. На Spider2-Snow задачи на TCGA / GENOMICS_CANNABIS / EBI_CHEMBL могут under-recall.

### L2. Numeric tokenization quirk
Numeric tokens (e.g., `20220715`) остаются как single token, не split до digits. Это означает, что query про "2022" не matches column `event_date_20220715`. На практике queries про specific date rarely попадают в schema linker context; обычно queries про "year 2022" matches via `year` или `date` synonyms.

### L3. Empty `alias` on Snow rows
Уже обсуждалось — Phase 27 F1 это compensates через `c.db.upper()` partitioning. Не блокирующее, но создавало illusion of working ranking pre-Phase-27.

### L4. No semantic similarity beyond tokens
"Patent applications filed по company X" не matches column `assignee` (semantically — applicants ≈ assignees) если synonym table не имеет entry. Dense retrieval мог бы help, но требует separate setup.

### L5. Per-task BM25 build cost
Per-task partition требует rebuild BM25 index для каждой задачи (~5-50K columns subset). Cost: ~50-300ms per task — acceptable, но не free. Mitigation для production: pre-build per-db BM25 indices и reuse. В нашем pipeline — на-лету.

## Альтернативные подходы из литературы

### LinkAlign [Wang et al., arXiv 2503.18596]
Iterative multi-DB schema linking. Core insight: *"how to select the correct database from a large schema pool in multi-database settings"*. **Описывает точно root cause Phase 26 Snow 0% baseline**. Достигает 33.09% Spider2-Lite с DeepSeek-R1. Наш Phase 27 F1 — упрощённая static version: instead of iterative DB selection, мы используем `task.db` метаданные как ground truth. Это работает для Spider 2.0 (annotated bench), не работает для production (нет task.db hint от пользователя).

### AutoLink [arXiv 2511.17190, AAAI 2026]
Iterative schema exploration с LLM-guided expansion. Достигает 91.2% strict schema recall на Spider2-Lite, 54.84% EX на Spider2-Snow с DeepSeek-R1. **Direct inspiration** для нашего planned Phase 30 (JOIN-graph BFS expansion).

### SchemaGraphSQL [arXiv 2505.18363]
BFS over FK + name-heuristic edges after BM25 picks seeds. +4-8 EX на BIRD. **Recipe для нашего planned Phase 30 F2** — Family C activation на BQ через graph-aware seed expansion.

### CHESS [Talaei et al., arXiv 2405.16755]
PK/FK column injection — реализован в нашем Phase 27 correction 3 (см. выше).

### RASL [Amazon Science, arXiv 2507.23104]
Retrieval-Augmented Schema Linking для массивных DB. Hybrid dense + sparse. Не реализован у нас — BM25 alone достаточен после per-task partition (наш ablation).

Подробно — [02_RELATED_WORK/05_schema_linking_approaches.md](../02_RELATED_WORK/05_schema_linking_approaches.md).

## Метрики качества schema linking в нашей работе

| Метрика | Definition | Pilot10 v28-revert-A measurement |
|---|---|---|
| **strict_recall@K** | gold tables ⊆ top-K linker hits | not measured per-task (нет gold table annotation для всех Spider2-Snow задач) |
| **pack_unique_dbs** | сколько unique catalog в pack | trace field, всегда {task_db} = 1 после Phase 27 F1 |
| **pack_n_tables** | сколько таблиц в pack | 8-10 (capped by max_tables) |
| **pk_fk_injected** | PK/FK heuristic injections | 1-4 per task |
| **schema_valid (post-validator)** | AST validator pass | 60-80% post-F1 на Snow (см. [09_RESULTS_ANALYSIS/03_spider2_snow_analysis.md](../09_RESULTS_ANALYSIS/03_spider2_snow_analysis.md)) |

## Cross-references

- Implementation: [08_CUSTOM_TOOLS/02_schema_linker_v18.md](../08_CUSTOM_TOOLS/02_schema_linker_v18.md)
- Pack construction: [04_pack_builder_v18.md](./04_pack_builder_v18.md)
- Phase 27 F1 narrative: [06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md](../06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md)
- Comparison со SOTA schema linking: [02_RELATED_WORK/05_schema_linking_approaches.md](../02_RELATED_WORK/05_schema_linking_approaches.md)
- BQ vs Snow pipeline differences: [05_PIPELINES/03_spider2_lite_bq_pipeline.md](../05_PIPELINES/03_spider2_lite_bq_pipeline.md) + [04_spider2_snow_pipeline.md](../05_PIPELINES/04_spider2_snow_pipeline.md)
- Failure analysis (where schema linker fails): [09_RESULTS_ANALYSIS/06_failure_analysis_remaining.md](../09_RESULTS_ANALYSIS/06_failure_analysis_remaining.md)

## Источники

| Утверждение | Источник |
|---|---|
| BM25 implementation details | `repo/src/evaluation/schema_linking_v18.py` lines 99-200 |
| Phase 27 F1 per-task partition | `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` §2(c) |
| 587K columns Snow / 428K BQ | `outputs/REPORT_PHASE26_RESEARCHER_HANDOFF.md` §2 |
| Maamari «Death of Schema Linking?» — BM25 sufficient at top-K=30 | arXiv 2408.07702; research dossier §4 |
| LinkAlign 33.09% Spider2-Lite | research dossier §4 |
| AutoLink 54.84% Spider2-Snow | research dossier §4 |
| CHESS PK/FK injection recipe | arXiv 2405.16755; research dossier §4 |
| Phase 27 retrieval window 80→200, 20→40 | `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` §2(c) + §6 |
