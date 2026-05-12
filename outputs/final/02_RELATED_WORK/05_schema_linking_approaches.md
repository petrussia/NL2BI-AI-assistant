# 2.5 Schema linking approaches — deep dive

## Назначение

Schema linking — **core sub-problem** для NL2SQL: given a natural language question + schema (or full catalog), identify the **relevant subset** of tables/columns. На warehouse-scale (тысячи tables/DB на Spider2-Snow), schema linking is the **#1 contributor к failure** при non-Snow systems. This file surveys schema linking methodologies в literature и places наш BM25 + per-task partition approach.

## The schema linking problem

**Input**: natural language question $Q$ + schema $\mathcal{S}$ (tables + columns + types + descriptions + FKs).

**Output**: ranked subset $\mathcal{S}' \subset \mathcal{S}$ such что $|\mathcal{S}'| \ll |\mathcal{S}|$ и нужные таблицы/колонки для answering $Q$ — в $\mathcal{S}'$.

**Why critical**:
- LLM context limits: 587K Snow columns не помещаются ни в один context window.
- Pack budget: ~5-10K tokens schema text efficient для planner reasoning.
- Selection quality: if needed table not в $\mathcal{S}'$, downstream pipeline cannot recover (validator rejects, hallucination ensues).

## Approach 1: BM25 / TF-IDF baselines

**Idea**: classical IR — rank column documents (column name + table name + description + type) by token overlap с question.

### Pros

- **Deterministic**: same input → same output. Reproducible.
- **Fast**: BM25 query on indexed catalog — sub-second даже на 587K columns.
- **No GPU**: pure CPU. Cheap при scale.
- **No training data**: works without labeled examples.

### Cons

- **Misses semantic non-overlap**: question says "publications", column named `pubs` — no token match. Synonym expansion helps marginally.
- **Numeric tokens not split** by digit boundary: `events_20220715` single token, missed by query about "2022".

### What we use

**Our v18 schema linker** = own implementation Okapi BM25 (k1=1.5, b=0.75) с:
- Identifier-aware tokenization (camelCase + numeric boundary splits).
- ~30-entry synonym table (analytics domain).
- Per-task partition by `c.db.upper()` (Phase 27 F1).

Detailed: [04_ARCHITECTURE/03_schema_linker_v18_bm25.md](../04_ARCHITECTURE/03_schema_linker_v18_bm25.md).

## Approach 2: Dense retrieval (embeddings)

**Idea**: embed query + each schema entity (column/table) с sentence-transformer (BGE, E5, ColBERT, etc.); rank by cosine similarity.

### Pros

- **Catches paraphrase**: "publications" → `pubs` matches if embedding model trained на similar substitutions.
- **Quality usually higher recall at top-K** than BM25 alone для small K (e.g., K=10).

### Cons

- **GPU compute**: embedding model + ANN index. Storage: 587K columns × 768-dim float = ~3.5 GB just for embedding index.
- **Non-deterministic**: depends on embedding model version, seed.
- **Training-data dependency**: best embedding models fine-tuned for retrieval — sensitive to domain distribution.

### Empirical observation (research dossier)

> *modern LLMs at sufficient context length can sometimes outperform retrieval-based schema linking*

— [Maamari et al., arXiv 2408.07702, "The Death of Schema Linking?"]

Translation: at large context (32K+ tokens), giving model full schema directly **outperforms** explicit dense retrieval. **But**:
- 587K columns Snow catalog doesn't fit any context.
- 7B emitter (наш case) — not strong enough к sort из large irrelevant context.

Dense retrieval — incremental quality upgrade с **significant infrastructure cost**. Marginally beneficial для post-Phase-27 partitioned subsets (5K-50K columns).

### Used by

- **RASL** [Eben et al., Amazon Science, arXiv 2507.23104]: hybrid dense + sparse retrieval.
- Parts of **AutoLink** [arXiv 2511.17190]: dense retrieval as one component.

### Связь с нашей архитектурой

Not used. **Phase 27 per-task partitioning + BM25 200/40** sufficient for наш needs. Dense retrieval — Phase 30+ if BM25 plateaus.

## Approach 3: Hybrid retrieval

**Idea**: BM25 + dense retrieval merged + reranking.

### Pros

- Catches both lexical match (BM25) и paraphrase (dense).
- Marginally higher recall чем either alone.

### Cons

- Inherits both BM25 limitations (numeric, non-paraphrase synonyms) and dense overhead.

### Used by

- **RASL** [Amazon Science, arXiv 2507.23104].
- Numerous CHESS / DAIL-SQL variants использовали simpler hybrid.

### Связь с нашей архитектурой

Not used. Marginal lift over BM25 alone at our scale не оправдывает infrastructure cost.

## Approach 4: Iterative LLM-guided exploration

**Idea**: agent calls schema catalog **progressively**, expanding pack each turn based на partial reasoning.

### Pros

- **Adaptive**: agent decides what to explore based на partial answer.
- **Strong results на Spider 2.0**: highest reproducible numbers (52.28% Lite, 54.84% Snow с DeepSeek-R1).

### Cons

- **Multi-call cost**: 3-7 LLM calls per task just для retrieval (before SQL generation). Significant compute.
- **Reasoning model dependency**: works best с reasoning models (R1, o3). Coder-7B agents struggle с iterative decisions.
- **Non-determinism**: agent's exploration trajectory varies.

### Used by

- **AutoLink** [arXiv 2511.17190]: LLM-guided expansion 3-7 rounds, achieves **91.2% strict schema recall** Spider2-Lite.
- **ReFoRCE** Column Exploration component [Deng et al., arXiv 2502.00675]: iterative `INFORMATION_SCHEMA` probing.

### Связь с нашей архитектурой

Not used. Multi-call iterative exploration **out of budget** для open ≤30B sequential pipeline. Phase 29 F3 self-refine — minimal step в this direction (single feedback retry on engine error, not multi-round exploration).

If we relax ≤30B constraint or move к multi-GPU setup, **iterative LLM-guided exploration** = strong Phase 30+ candidate.

## Approach 5: JOIN-graph traversal

**Idea**: build schema graph c nodes = tables, edges = FK relationships (and/or name-heuristic edges). After BM25 seeds, **BFS expand** to include FK-reachable tables.

### Pros

- **Catches multi-hop joins** где BM25 alone misses intermediate join tables.
- **Deterministic**: graph traversal repeatable.
- **Low compute**: BFS over small graph.

### Cons

- **Requires real FK metadata**. Heuristic FK detection (name patterns) — noisy.
- **Limited к structural relationships**. Doesn't catch semantic non-FK joins.

### Used by

- **SchemaGraphSQL** [Liu et al., arXiv 2505.18363]: BFS over FK + name-heuristic edges after BM25 seeds. **+4-8 EX on BIRD with zero fine-tuning**.

### Связь с нашей архитектурой

**Not currently used** in production pipeline.

Currently наш `join_hints` heuristic в pack builder generates name-matching pairs (shared column names с `*_id` shape). Family C factory uses these — но **rarely chosen** by selector due к false-positive hints.

**Phase 30 plan**: implement SchemaGraphSQL-style FK BFS expansion. Requires real FK metadata extraction:
- BQ: `INFORMATION_SCHEMA.KEY_COLUMN_USAGE` — often empty on public datasets.
- Snow: similar via `ACCOUNT_USAGE.FOREIGN_KEYS`.
- Fallback: name-heuristic FK detection (similar к current join_hints).

**Expected lift +6-10 EX на Lite-BQ** based на SchemaGraphSQL evidence (research dossier §5 F2 fix).

## Approach 6: PK/FK forced injection

**Idea**: после BM25 picks columns, **force-append declared PK/FK + heuristic `*_id` columns** to ranked output.

### Why critical

PK/FK columns systematically **under-ranked** by BM25 because они имеют **low semantic similarity** с natural language question. Example: question "show patents from 2010-2020" — PK column `id` или `family_id` has zero token overlap с question terms (`patents`, `2010`, `2020`). BM25 ranks них в bottom hundreds. But для multi-table query, FK columns are **essential** as join keys.

### Used by

- **CHESS** [Talaei et al., arXiv 2405.16755]: explicit rule — after BM25, force-append declared PK/FK + heuristic `*_id` columns.

### Связь с нашей архитектурой

**Direct ancestor нашей Phase 27 correction 3** (`_inject_pk_fk` function в `_phase27_snow_runner.py`). Heuristic patterns:
- `id`, `<table_singular>_id`, `*_pk`, `*_fk`, `*_id`, `*_key`, `*_sk`.

Cap 4 columns per table. **Mutates pack in place after BM25**.

Empirically: 1-3 injections per task on Snow PATENTS pilot10. Small but cumulative lift in schema_valid.

## Approach 7: Multi-DB partitioning

**Idea**: filter catalog к single DB **before** schema linking. Eliminates cross-DB drift.

### When applicable

- Multi-DB benchmarks (Spider 2.0 family: 152 unique DBs on Snow).
- Bench annotates ground-truth `task.db` (Spider 2.0 does).

### Used by

- **LinkAlign** [Wang et al., arXiv 2503.18596]: **iterative LLM-guided DB selection** for production scenarios without ground-truth annotation.
- **Naше Phase 27 F1**: deterministic `c.db.upper() == task.db.upper()` filter when ground-truth available.

### Связь с нашей архитектурой

**Phase 27 F1 — the most impactful intervention в нашей всей Spider 2.0 work**. Before partition (Phase 25 baseline): 0/547 Snow exec. After partition + retrieval scale + PK/FK injection: pilot10c 8/10 schema_valid, eventually 4/10 exec at pilot10 v28-revert-A.

Comparison с LinkAlign:
- **LinkAlign**: iterative LLM selection. Generalizes к production (no annotation). Cost: extra LLM calls per task.
- **Phase 27 F1**: deterministic filter using `task.db`. Faster, simpler. Only works if bench annotates.

For bench evaluation (where `task.db` available), **deterministic wins** на cost/quality trade-off. For production deployment (where user query doesn't include explicit DB), **LinkAlign-style** needed.

## Approach 8: "Death of schema linking?" — context-only

**Citation**: Maamari et al., arXiv 2408.07702.

### Idea

Argue что **reasoning-class LLMs at sufficient context length** can handle large irrelevant schema directly, **without explicit schema linking**. Schema linking может быть obsolete для top-tier models.

### Evidence

- GPT-4-class models с 128K context can process entire BIRD-class schema directly.
- BM25 sufficient at top-K=30 — beyond that, dense retrieval marginal.

### Связь с нашей архитектурой

**Mixed applicability к our context**:
- Naш 7B emitter — **not a reasoning model**. Cannot handle large irrelevant context well.
- Snow 587K columns — **not fit** any context window regardless of model class.
- **Schema linking remains critical** для open ≤30B stack.

Maamari finding **does** validate: BM25 sufficient at top-K=30 (not need significant dense retrieval improvement). Phase 27's choice of 200/40 retrieval window — somewhat above top-K=30 but reflects warehouse-scale context (200 columns × 22 cols/table = 9 tables × 22 cols = ~200-column budget pack).

## Сводная таблица

| Approach | Pro | Con | Used by | Our usage |
|---|---|---|---|---|
| BM25 / TF-IDF | Deterministic, fast, no GPU | Misses paraphrase | classical, RAT-SQL, CHESS, DAIL | ✓ **primary** в v18 schema_linker |
| Dense retrieval | Better paraphrase recall | GPU + index, non-determ | RASL, parts AutoLink | not used |
| Hybrid sparse+dense | Combines BM25 + dense | Inherits both costs | RASL, CHESS variants | not used |
| Iterative LLM-guided | Adaptive, strong на Spider2 | Multi-call cost, reasoning model | AutoLink, ReFoRCE Column Exploration | not used (deferred Phase 30+) |
| JOIN-graph BFS | Catches multi-hop joins | Needs real FK metadata | SchemaGraphSQL | **Phase 30 plan** (currently heuristic join_hints only) |
| PK/FK forced injection | Catches join keys BM25 misses | Heuristic noise | CHESS | ✓ **Phase 27 correction 3** |
| Multi-DB partitioning | Eliminates cross-DB drift | Requires task.db annotation OR iterative selection | LinkAlign, **наш Phase 27 F1** | ✓ **primary fix для Snow** |
| Context-only (no linker) | Saves complexity | Needs reasoning model + huge context | proposed by Maamari for o3-class | not viable для open ≤30B |

## Где наш schema linker сидит в landscape

**Approach**: BM25 + identifier-aware tokenization + synonym expansion + per-task partition + PK/FK heuristic injection.

**Position**:
- **Below state-of-the-art** AutoLink (iterative LLM-guided, 91.2% schema recall Spider2-Lite).
- **Above pure BM25 baseline** через 3 added components (partition + PK/FK injection + retrieval scaling).
- **Comparable** с CHESS schema linking variant (BM25 + PK/FK injection).

**Strength**:
- Deterministic, reproducible, fast.
- Compatible с open ≤30B stack (no reasoning model dependency).
- After Phase 27 corrections (200/40 retrieval, PK/FK injection), достаточен для 8/10 pilot10c schema_valid.

**Weakness**:
- No semantic similarity beyond tokens (limited synonyms).
- No iterative refinement.
- Heuristic FK detection — noisy (Family C false-positive joins).

**Phase 29-30 improvement plan**:
- Phase 30 F2: real FK metadata + JOIN-graph BFS (SchemaGraphSQL recipe). Expected +6-10 EX Lite-BQ.
- Phase 30+ optional: dense retrieval добавление для post-partition refinement. Expected marginal.
- Phase 30+ optional: AutoLink-style iterative exploration. Expected +5-15 EX но multi-call cost.

## Где наш подход fundamentally limited

### Limit 1: No paraphrase semantic match
"Active customers" → column `is_active` matches via synonym table. "Loyal users" → column `repeat_purchaser` — **no match** в synonym table. Dense retrieval would catch this. Not currently supported.

### Limit 2: Reactive vs proactive retrieval
Our BM25 — **single pass** ranking. AutoLink-style iterative agent can **proactively** request specific tables when reasoning suggests them. Our schema linker has no reasoning component.

### Limit 3: Heuristic FK detection
Real FK metadata often missing на public datasets. Naше name-heuristic FK detection generates false positives. SchemaGraphSQL needs real metadata pipeline (Phase 30 territory).

### Limit 4: No question-decomposition retrieval
Сложные queries с multiple aggregations / sub-questions могут benefit from retrieving for each sub-question separately (DTS-SQL / MAC-SQL pattern). Naше retrieval — single pass на full question.

## Cross-references

- Implementation: [08_CUSTOM_TOOLS/02_schema_linker_v18.md](../08_CUSTOM_TOOLS/02_schema_linker_v18.md)
- Architecture detail: [04_ARCHITECTURE/03_schema_linker_v18_bm25.md](../04_ARCHITECTURE/03_schema_linker_v18_bm25.md)
- Pack builder (consumer): [04_ARCHITECTURE/04_pack_builder_v18.md](../04_ARCHITECTURE/04_pack_builder_v18.md)
- Phase 27 F1 narrative: [06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md](../06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md)
- AutoLink / LinkAlign / SchemaGraphSQL details: [02_sota_systems_2024_2026.md](./02_sota_systems_2024_2026.md)
- Text-to-SQL evolution: [01_text2sql_evolution.md](./01_text2sql_evolution.md)
- Future work: [09_RESULTS_ANALYSIS/06_failure_analysis_remaining.md](../09_RESULTS_ANALYSIS/06_failure_analysis_remaining.md)

## Источники

| Утверждение | Источник |
|---|---|
| BM25 implementation | own `repo/src/evaluation/schema_linking_v18.py` |
| RASL hybrid retrieval | Eben et al., arXiv 2507.23104 |
| AutoLink iterative + 91.2% recall | arXiv 2511.17190 (AAAI 2026); research dossier §4 |
| ReFoRCE Column Exploration | Deng et al., arXiv 2502.00675; research dossier §4 |
| SchemaGraphSQL +4-8 EX | Liu et al., arXiv 2505.18363; research dossier §4 |
| CHESS PK/FK injection | Talaei et al., arXiv 2405.16755; research dossier §4 |
| LinkAlign multi-DB | Wang et al., arXiv 2503.18596; research dossier §4 |
| Maamari "Death of schema linking?" | arXiv 2408.07702 |
| Phase 27 F1 per-task partition | `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` |
| Phase 27 PK/FK injection | `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` §2 corrections |
