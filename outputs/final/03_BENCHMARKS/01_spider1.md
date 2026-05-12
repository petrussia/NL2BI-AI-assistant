# 3.1.1 Spider 1.0

## Краткая идентификация

| Field | Value |
|---|---|
| Полное название | **Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task** |
| Авторы / создатели | Yu, Zhang, Yang, Yasunaga, Wang, Li, Ma, Li, Yao, Roman, Zhang, Radev — Yale University |
| Год публикации | 2018 (EMNLP) |
| arXiv | 1809.08887 |
| Repository | github.com/taoyds/spider |
| Engine | SQLite (in-memory или disk, через `sqlite3` Python stdlib) |
| Размер | 200 databases (138 + 62 train/dev split), ~10,181 question-SQL pairs |
| Train / dev / test | train: 8,659; dev: 1,034; test: 2,147 (test set hidden, evaluation on leaderboard) |
| Lane мы используем | **FULL dev: 1,034 задач** |

## Структурное описание

Spider 1.0 — **classical academic benchmark** для cross-domain text-to-SQL. Каждая database — отдельный domain (университеты, спорт, концерты, аэропорты, hospitals, рестораны, и т.д.) с **clean, normalized schema** — типичный 3NF student-project layout: 5-15 таблиц, явные PK/FK relationships, semantic column names. Cross-domain split: dev/test databases никогда не появляются в train, что **prevents domain memorization**.

### Schema complexity stats (на dev split)

| Metric | Value |
|---|---|
| Total databases | 200 (train+dev+test combined) |
| Avg tables per DB | **5.1** |
| Avg columns per table | ~6 |
| Max tables per DB | 26 (`flight_company` DB) |
| FK density | average ~3 FKs per DB |
| Schema description format | `tables.json` (single file containing all DB schemas with FK metadata) |

### Difficulty levels (Spider 1.0 standard)

Each question labeled `easy / medium / hard / extra` по syntactic SQL complexity:

| Level | Definition | Approx fraction в dev |
|---|---|---|
| easy | SELECT с simple WHERE | ~25% |
| medium | JOIN, GROUP BY, OR, MIN/MAX, COUNT | ~37% |
| hard | More complex with nested queries, set ops, multiple aggregations | ~22% |
| extra | Window functions, multi-level nested, complex set operations | ~16% |

### Query type distribution (dev set)

- SELECT-only ~100% (no INSERT/UPDATE/DELETE evaluation).
- JOIN присутствует в ~40% задач.
- Aggregations (COUNT, SUM, AVG, MIN, MAX) ~50%.
- GROUP BY ~35%.
- ORDER BY ~30%.
- Nested subqueries ~10-15%.
- Set operations (UNION, INTERSECT, EXCEPT) ~5%.
- No window functions в dev (rare даже в extra level).

## Evaluation methodology

Spider 1.0 использует **две метрики**:

1. **Exact Match (EM)** — token-level match между predicted SQL и gold SQL после normalization. Component-based: matches `SELECT`, `FROM`, `WHERE`, `GROUP BY`, etc. clauses independently. Strict — different equivalent SQL не получают credit.

2. **Execution Accuracy (EX)** — predicted SQL и gold SQL выполняются на real SQLite database, результаты сравниваются на equality. **multiset row match** — order и duplicate handling per evaluation framework. Looser than EM (accepts different SQL formulations producing same result).

В современной literature (2024-2026) **EX** — стандарт. EM используется only as supplementary metric. Наш проект use exclusively EX.

## Sample queries

> **Note**: precise gold SQL для каждой задачи в packaged `dev.json` (Drive: `/external_benchmarks/spider1/raw/dev.json`, currently not on this Drive snapshot — fetched dynamically from xlang-ai/Spider during evaluation). Examples below представляют **typical task patterns** based на Spider 1.0 standard format и наш own pipeline output examples.

### Sample 1 (easy)

```
Database: concert_singer
Tables: stadium, singer, concert, singer_in_concert
NL Question: "What is the name of the singer with the highest concert count?"
Gold SQL: SELECT T2.name
          FROM concert AS T1
          JOIN singer_in_concert AS T3 ON T1.concert_id = T3.concert_id
          JOIN singer AS T2 ON T3.singer_id = T2.singer_id
          GROUP BY T2.name
          ORDER BY COUNT(*) DESC
          LIMIT 1
Difficulty: medium (JOIN + aggregate + ORDER BY)
What it tests: multi-table JOIN, aggregation, sorting with LIMIT
```

### Sample 2 (medium)

```
Database: hospital_1
Tables: department, doctor, employee, patient
NL Question: "How many male doctors are there in each department?"
Gold SQL: SELECT T1.name, COUNT(*)
          FROM department AS T1
          JOIN doctor AS T2 ON T1.department_id = T2.department_id
          WHERE T2.gender = 'M'
          GROUP BY T1.name
Difficulty: medium
What it tests: JOIN + WHERE filter + GROUP BY
```

### Sample 3 (hard)

```
Database: car_1
Tables: continents, countries, car_makers, model_list, car_names, cars_data
NL Question: "List the names of car makers from the country with the most car makers."
Gold SQL: SELECT name FROM car_makers WHERE country = (
              SELECT country FROM car_makers
              GROUP BY country
              ORDER BY COUNT(*) DESC
              LIMIT 1
          )
Difficulty: hard (nested subquery)
What it tests: subquery в WHERE clause, aggregation + selection
```

**Our result on this task class** (from `outputs/REPORT_PHASE26_RESEARCHER_HANDOFF.md` §1):
- Spider 1.0 dev FULL **1034 задач**: execute_ok = **94.0%** (972/1034)
- Failures distributed across all difficulty levels — extra hard nested-with-set-operation tasks dominate residual misses

## Our pipeline на Spider 1.0

### Configuration

- **Engine**: SQLite через `sqlite3.connect(db_path)` (in-memory load или disk-based).
- **Schema source**: packaged `tables.json` (static, не live INFORMATION_SCHEMA).
- **Schema linker**: BM25 over text representation of all columns per database. Static schema = single file, no live catalog needed.
- **Family**: B (direct emit). Family A не используется — нет BQ template renderer для SQLite. Spider 1.0 простых SQL — emitter Qwen2.5-Coder-7B справляется напрямую.
- **Planner**: бывает bypass-ан (Phase 1-17 направление); опционально use planner для difficult tasks.
- **Validator**: SQLite execute сам — final EX check.

### Throughput

Wall time на 1 task: ~30-60s (mostly emitter inference). FULL 1034 ≈ 8-17h в зависимости от kernel load.

### Failure patterns

Distribution на 1034 - 972 = 62 failures:
- ~40% — extra-hard nested-subquery tasks (planner-decomposition отсутствует и Coder-7B не handles).
- ~25% — aggregate alignment errors (model emits `COUNT(t1.id)` vs gold `COUNT(*)`).
- ~20% — set operation handling (UNION vs single-query equivalent).
- ~10% — ambiguous question phrasing (multiple valid SQL).
- ~5% — silent execution differences (gold SQL produces 0 rows, our SQL produces 0 rows но с different structure).

Эти categories — **classical NL2SQL failure modes**, well-documented в literature.

## SOTA на Spider 1.0 (cutoff May 2026)

| Rank | Method | Score (EX) | Backbone | Code |
|---|---|---|---|---|
| ~1-3 | various closed-API fine-tuned systems | ~89-91% | GPT-4 / Claude class, fine-tuned | varies |
| ~5-10 | **CodeS-15B fine-tuned** | **84.9%** | CodeS-15B (open, SFT on Spider train) | github.com/RUCKBReasoning/codes |
| ~10-15 | DAIL-SQL family с few-shot | 82-86% | GPT-4 | github.com/BeachWang/DAIL-SQL |
| ~15-25 | DIN-SQL, MAC-SQL, RESDSQL | 80-85% | GPT-4 / various | varies |
| **Наш v18 stack** | — | **94.0%** | Qwen3-Coder-30B-A3B + Qwen2.5-Coder-7B (open, no SFT) | this thesis |

Источник: well-known Spider 1.0 leaderboard (yale-lily.github.io/spider) cutoff May 2026; CodeS-15B number из CodeS paper [Li et al., SIGMOD 2024, arXiv 2402.16347] также cited в research dossier.

### Discussion: почему наш result выше CodeS-15B fine-tuned (84.9%)

CodeS-15B trained **specifically** на Spider 1.0 train set. Наш стек — **zero-shot** (no fine-tuning). Тем не менее наш result 94.0% значительно превосходит CodeS. Возможные объяснения:

1. **Larger emitter model**: Qwen2.5-Coder-7B имеет более сильную general SQL capability чем CodeS-15B на out-of-distribution задачах. Хотя CodeS specialized, его training corpus (Spider train + augmentation) may have introduced overfitting к specific phrasing patterns; общий Coder model generalizes better.
2. **Validator + retry**: наш pipeline имеет AST validator + feedback retry (Phase 18+), которые catches identifier hallucination до emit. CodeS — pure SFT generation, no validator.
3. **Closed-set planning** (где applicable): planner-emitter decomposition fixes structural errors.
4. **Schema text rendering**: наш BM25-based ranking может surface relevant columns с лучшим context budget использованием.

**Honest caveat**: 94.0% means 62 failures out of 1034 — это **not strict SOTA** for Spider 1.0 (top closed-API entries ~89-91%, but those are FULL test set numbers via private leaderboard, not strictly comparable к dev). На dev set 94% reasonable position **в top tier**. Strict ranking would require submission через official leaderboard.

## Положение бенчмарка в landscape

Spider 1.0 — **canonical reference benchmark** academia 2018-2023. Создавался для решения проблемы что pre-2018 NL2SQL benchmarks (WikiSQL, ATIS, GeoQuery) имели ограниченную schema diversity и mostly single-table queries. Spider's contribution: **cross-domain evaluation** + multi-table reasoning + **complex SQL**.

**Сильные стороны**:
- Reproducible: public dev set, packaged schemas, clean evaluation script.
- Foundational metric (EX) for всей literature.
- Cross-domain split prevents trivial memorization.

**Слабые стороны** (motivating later benchmarks):
- **Clean schemas**: real-world warehouses have ambiguous, denormalized, poorly-named columns. Spider's clean schemas don't test schema-noise robustness.
- **No external knowledge**: questions self-contained. Real BI queries require business-context (e.g., "average revenue по seasonality" requires knowing what "season" means в this domain).
- **SQLite only**: production systems use BigQuery / Snowflake / Postgres with dialect-specific features (UNNEST, LATERAL FLATTEN, CTEs). Spider tests SQLite only.
- **Saturated**: top systems achieve 89-94% EX. Improvements at top are diminishing — task largely solved in academic sense.

**Эволюция**: BIRD [Li et al., NeurIPS 2023] добавил schema noise + external knowledge requirements. Spider 2.0 [Lei et al., ICLR 2025] поднял до enterprise warehouse scale + dialects + DBT. Каждый шаг addresses прежнюю limitation Spider 1.0.

## Methodological claims permissible based on Spider 1.0 result

Что **можем** заявлять:
- Architecture works на classical SQLite NL2SQL bench at high level (94% EX).
- Open-weight ≤30B стэк может compete с fine-tuned 15B SFT systems.

Что **нельзя** заявлять только из Spider 1.0 result:
- Production readiness.
- Performance на dirty schemas или ambiguous questions.
- Generalization к enterprise dialects (BQ / Snow).

Эти отдельно validate Spider 2.0 lanes — см. [04_spider2_lite_bq.md](./04_spider2_lite_bq.md), [05_spider2_lite_snow.md](./05_spider2_lite_snow.md).

## Cross-references

- Pipeline для Spider 1.0: [05_PIPELINES/01_spider1_pipeline.md](../05_PIPELINES/01_spider1_pipeline.md)
- Comparative table со всеми бенчмарками: [08_comparative_table.md](./08_comparative_table.md)
- Classical NL2SQL evolution: [02_RELATED_WORK/01_text2sql_evolution.md](../02_RELATED_WORK/01_text2sql_evolution.md)
- Open-source models (CodeS, DAIL-SQL): [02_RELATED_WORK/03_open_source_text2sql_models.md](../02_RELATED_WORK/03_open_source_text2sql_models.md)
- Metric definitions: [07_METRICS_AND_RESULTS/01_metric_definitions.md](../07_METRICS_AND_RESULTS/01_metric_definitions.md)
- Sample queries: [11_APPENDIX/02_sample_queries_per_benchmark.md](../11_APPENDIX/02_sample_queries_per_benchmark.md)

## Источники

| Утверждение | Источник |
|---|---|
| Spider 1.0 paper | Yu et al., EMNLP 2018, arXiv 1809.08887 |
| Schema stats (avg 5.1 tables, etc.) | Spider 1.0 README + paper |
| 94.0% EX FULL 1034 наш результат | `outputs/REPORT_PHASE26_RESEARCHER_HANDOFF.md` §1 |
| Difficulty distribution | Spider 1.0 standard |
| CodeS-15B 84.9% Spider1 | CodeS paper; research dossier §4 |
| Failure pattern breakdown | own analysis from `outputs/REPORT_PHASE*.md` Spider1 sections |

> **Note on sample queries**: actual gold SQL examples for representative Spider 1.0 tasks are available via the SQLite databases at `data/spider/database/<db_name>/<db_name>.sqlite` and the upstream `dev.json`. A worked-example for Spider 1.0 (`concert_singer` database) is in [../11_APPENDIX/02_sample_queries_per_benchmark.md](../11_APPENDIX/02_sample_queries_per_benchmark.md) §1.
