# Приложение Б.1 — Глоссарий терминов

Алфавитный (по русским заголовкам) словарь технических терминов, используемых в работе. Где термин — английский (большинство), он остаётся в исходной форме (без транслитерации), но с русским объяснением.

---

## A

### AST (Abstract Syntax Tree)
Дерево, получаемое парсингом SQL-выражения. В работе используется реализация из библиотеки **SQLGlot** ([10_REFERENCES/02_repos_and_codebases.md](../10_REFERENCES/02_repos_and_codebases.md)). AST позволяет programmatically проверять структуру SQL (validator AST), а также модифицировать её (post-processor F4 в Phase 28: оборачивание `Column` внутри `Extract` / `TimestampTrunc` в `TO_DATE(TO_VARCHAR(x), 'YYYYMMDD')`).

### AST guard
Конкретный модуль `repo/src/evaluation/snow_identifier_guard_v27.py`, Phase 27 F1. Walks SQL AST, проверяет каждую `exp.Table`: если её catalog (первый из трёх сегментов имени) — не в allow-list-е task-а, raise `IdentifierLeakError`. Если catalog отсутствует — auto-fills его task_db. CTE-aware (не трогает ссылки на CTE-имена). См. [08_CUSTOM_TOOLS/05_snow_identifier_guard_v27.md](../08_CUSTOM_TOOLS/05_snow_identifier_guard_v27.md).

---

## B

### BF16 (bfloat16)
16-битный numeric format с тем же exponent range, что у float32. Используется для inference Qwen3-Coder-30B-A3B (без потерь точности по сравнению с FP16 на длинных контекстах). Total memory footprint при BF16: ~60 GB для 30B model, ~14 GB для 7B emitter.

### BIRD (Big bench for laRge-scale Database grounded text-to-SQL evaluation)
NL2SQL бенчмарк с более крупными SQLite-схемами, чем Spider 1.0, и с external knowledge tags. ~12K задач train + 1534 FULL dev. См. [03_BENCHMARKS/02_bird.md](../03_BENCHMARKS/02_bird.md).

### BM25 (Best Matching 25)
Класс retrieval-функций, ранжирующих документы по term-frequency / inverse-document-frequency. В работе используется библиотека `rank_bm25` (Python) над текстовым представлением catalog row-а: `db.schema.table.column + description + type` каждый из record-ов в `INFORMATION_SCHEMA.COLUMNS`. См. [04_ARCHITECTURE/03_schema_linker_v18_bm25.md](../04_ARCHITECTURE/03_schema_linker_v18_bm25.md).

### BigQuery dry_run
Mechanism BigQuery API позволяющий проверить корректность SQL без execution — возвращает `valid: true/false`, schema выходных колонок, byte-cost estimate. Бесплатный. В работе — основной engine validator на Spider2-Lite-BQ lane. См. [04_ARCHITECTURE/10_execution_engines.md](../04_ARCHITECTURE/10_execution_engines.md).

---

## C

### Candidate factory
Компонент pipeline, генерирующий SQL-кандидат из (план + pack). В работе их три семейства:
- **Family A** — детерминированный рендер plan-JSON в BQ Standard SQL по rule-based template (BQ-only, Spider1/BIRD пути не используют).
- **Family B** — direct emit Coder-7B по plan-JSON + pack (универсальный для всех lanes).
- **Family C** — JOIN-aware factory (использует `pack.join_hints`), внедрённая в Phase 22; почти не выбирается selector-ом исторически.
См. [04_ARCHITECTURE/06_candidate_factories_family_abc.md](../04_ARCHITECTURE/06_candidate_factories_family_abc.md).

### Candidate selector
Компонент, выбирающий final SQL из набора кандидатов от factories. Priority order: `dry_run_ok` > `parse_ok` > `schema_valid` > Family A tie-break. См. [04_ARCHITECTURE/08_candidate_selector.md](../04_ARCHITECTURE/08_candidate_selector.md).

### Catalog
В контексте Snowflake: верхний уровень иерархии `catalog.schema.table.column`. На уровне Spider2-Snow это совпадает с «database» (e.g., `PATENTS`, `GA360`, `TCGA`). На BQ — это «project_id».

### Catalog probe
Методология (Phase 28 contribution), которая использует прямое чтение catalog JSONL и анализ полей (e.g., `column` field, `data_type`) для проверки гипотез о dialect failure mode. Применена в Phase 28 §6, опровергнув гипотезу «mixed-case quoting» эмпирическим показом что 37/37 PATENTS columns хранятся в lowercase.

### Catalog file
В работе — `outputs/cache/spider2_snow_live_catalog_v18.jsonl` (~587K columns для Snow) и `outputs/cache/spider2_bq_live_catalog_v18.jsonl` (~428K columns для BQ). Полученные через batched `INFORMATION_SCHEMA.COLUMNS` запросы в Phase 18.

### CTE (Common Table Expression)
`WITH name AS (...) SELECT ... FROM name`. На Spider2-Snow часто встречается. AST guard skip-ает Table-references-на-CTE-name (имена не должны получать catalog auto-fill — это сломало бы их resolution).

### closed-set planning
Парадигма (Phase 18): planner получает на вход pack из top-K таблиц+колонок и должен сформировать план только из этого набора. Validator проверяет, что каждый идентификатор в plan-JSON присутствует в pack. См. [04_ARCHITECTURE/05_planner_emitter_decomposition.md](../04_ARCHITECTURE/05_planner_emitter_decomposition.md).

### connect_fail
Категория error class в `error_taxonomy.csv`. Означает, что попытка установить соединение с warehouse engine (Snowflake / BigQuery) провалилась до того, как SQL отправили на EXPLAIN/dry_run. Типичная причина — отсутствующие credentials в `os.environ` (см. Phase 28 incident в `colab_session_bringup.md` 2a).

### Cross-DB drift
Failure mode (Phase 26), когда модель выдаёт three-part identifier с правильной схемой/таблицей но **неправильным первым сегментом (catalog)**, потому что schema linker leaked candidates from other databases. На Snow lane до Phase 27 affected 90.2% задач (диагностический probe Phase 27 §1).

---

## D

### DAIL-SQL
Один из ранних LLM-based NL2SQL подходов (DAIL-SQL, Gao et al., 2023). Использует question-similarity selection of few-shot examples. См. [02_RELATED_WORK/02_sota_systems_2024_2026.md](../02_RELATED_WORK/02_sota_systems_2024_2026.md).

### DBT (data build tool)
Framework для transformation-layer в data warehouse. Проект DBT — это директория с `models/`, `seeds/`, `tests/`, `dbt_project.yml`. `dbt build` выполняет все models в DAG-порядке. См. [04_ARCHITECTURE/10_execution_engines.md](../04_ARCHITECTURE/10_execution_engines.md), Spider2-DBT в [03_BENCHMARKS/07_spider2_dbt.md](../03_BENCHMARKS/07_spider2_dbt.md).

### Dialect handler
Модуль, инкапсулирующий dialect-specific логику. В работе:
- `_bq_dry_run` (BQ),
- `_snow_explain` (Snow),
- `snow_identifier_guard_v27.py` + `snow_dialect_fixer_v28.py` (Snow-only post-processing).

### dry_run_ok
Метрика: SQL прошёл BQ `client.query(sql, job_config=QueryJobConfig(dry_run=True)).result()` без exception. Эквивалент `execute_ok` для BQ lane (см. [07_METRICS_AND_RESULTS/01_metric_definitions.md](../07_METRICS_AND_RESULTS/01_metric_definitions.md)).

---

## E

### EM (Exact Match)
Метрика: token-level exact match между предсказанным SQL и эталонным. Старая Spider 1.0 метрика, во многом устаревшая (один и тот же результат может быть expressed via разные SQL).

### Emitter
Компонент pipeline, генерирующий final SQL из plan-JSON + pack. В работе — Qwen2.5-Coder-7B-Instruct, BF16, prompt-based (no fine-tuning). См. [04_ARCHITECTURE/02_models_qwen3_qwen2.5.md](../04_ARCHITECTURE/02_models_qwen3_qwen2.5.md).

### EX (Execution Accuracy)
Метрика: SQL выполнен на engine, результат multiset-match с эталоном. Стандарт для Spider 1.0 / BIRD / Spider2-Lite. Также — `execute_ok` в `predictions.jsonl` нашего pipeline.

### EXPLAIN (Snowflake)
`EXPLAIN USING TEXT <sql>` команда Snowflake — проверяет parse + type checking без actual execution. Бесплатна (не списывает warehouse credits). Используется как validator на Snow lane.

### External knowledge
Дополнительная domain-specific информация, прилагаемая к BIRD задаче (e.g., бизнес-определение конкретной метрики). В нашем pipeline передаётся в planner prompt как отдельный блок.

---

## F

### F1 / F2a / F4 / F4c
Кодовые названия Phase 27/28 интервенций на Snow lane:
- **F1** (Phase 27): catalog-level identifier grounding через per-task BM25 + three-part rendering + AST guard.
- **F2a** (Phase 28): auto-uppercase identifiers — REVERTED, basis was wrong empirical hypothesis.
- **F4** (Phase 28): wrap NUMBER/VARIANT column inside `Extract`/`TimestampTrunc` etc. with `TO_DATE(TO_VARCHAR(x), 'YYYYMMDD')` or `x::DATE`.
- **F4c** (Phase 28): fallback regex-only catalog leak check when SQLGlot fails to parse SQL (e.g., on `LATERAL FLATTEN`).
См. [04_ARCHITECTURE/09_dialect_handlers_f1_f4.md](../04_ARCHITECTURE/09_dialect_handlers_f1_f4.md).

### Family A/B/C → см. Candidate factory

### FK (Foreign Key)
Reference от колонки одной таблицы к primary key другой. В Spider2 catalog-ах FK metadata часто отсутствует или неполна → используется heuristic injection (Phase 27 correction 3): инжектируем `id`, `<table_singular>_id`, `*_pk`, `*_fk`, `*_key`, `*_sk` в pack.

### FQN (Fully Qualified Name)
Three-part identifier в Snow/BQ: `catalog.schema.table` или `project.dataset.table`. В Spider2 pipeline всегда требуется (Phase 27 F1 enforces).

### FUSE sync
Поведение Google Drive mount в Colab: writes в append-открытый файл накапливаются в локальном FUSE cache и не пушатся в cloud Drive до `file.close()`. В Phase 28 это создало illusion of regression на S2 (n=119 in-memory progress.json, но только 40 entries реально на cloud Drive). Закрыто через **periodic close+reopen каждые 10 tasks** (Phase 28 hardening, см. [08_CUSTOM_TOOLS/09_resilience_patterns.md](../08_CUSTOM_TOOLS/09_resilience_patterns.md)).

---

## G

### Gold SQL
Эталонный SQL запрос, against который сравнивается prediction для evaluation.

### Guard regex fallback
Phase 28 F4c контракт: при SQLGlot ParseError на SQL — вместо raise `IdentifierLeakError(parse_error_sqlglot)` сделать lightweight regex `(?:FROM|JOIN)\s+ident\.ident\.` проверку catalog leak, и если clean — pass SQL через guard unchanged.

---

## H

### Hallucination
Failure mode model-я: эмиссия идентификаторов / values / structures, которых нет в input context. В нашем pipeline:
- **column hallucination**: model выдает имя колонки не из pack (e.g., `country` вместо `country_code`),
- **table hallucination**: model выдает имя таблицы не из pack (e.g., `CITATIONS` где её нет).
Закрывается self-refine loop (Phase 29 territory).

### HSE (Higher School of Economics, Russia)
Университет, в котором защищается работа.

---

## I

### Identifier leak
В контексте Phase 27 — событие, когда candidate SQL содержит three-part identifier с catalog name не в task-specific allow-list-е. AST guard raises `IdentifierLeakError`. См. [04_ARCHITECTURE/09_dialect_handlers_f1_f4.md](../04_ARCHITECTURE/09_dialect_handlers_f1_f4.md).

### INFORMATION_SCHEMA
Стандартный набор views в SQL-92, доступный в большинстве warehouse-engines (BQ, Snowflake, Postgres, …), описывающий metadata схемы: `TABLES`, `COLUMNS`, `KEY_COLUMN_USAGE`, etc. В работе использован как **live catalog source** в Phase 18.

### invalid_identifier
Snowflake error category `000904`. Означает, что в SQL-выражении использован identifier (имя колонки или таблицы), которого нет в схеме. Главный класс post-F1 failures на Snow lane.

---

## J

### JSON план (plan-JSON)
Output planner-а — структурированный JSON с полями: `selected_database`, `selected_schema`, `selected_tables`, `selected_columns`, `metrics`, `filters`, `time_constraints`, `grouping`, `sorting`, `limit`, `ambiguity_points`, `expected_shape`. См. [04_ARCHITECTURE/05_planner_emitter_decomposition.md](../04_ARCHITECTURE/05_planner_emitter_decomposition.md) для полной спецификации.

### Join hints
Heuristic JOIN-key пары, выведенные из pack-а на основе shared column names и FK-naming patterns. Phase 22 contribution. Используется Family C factory.

---

## L

### LATERAL FLATTEN
Snowflake-специфический construct: `SELECT … FROM table, LATERAL FLATTEN(INPUT => col)` — разворачивает array/object column в строки. SQLGlot snowflake dialect parser имеет gap на этой конструкции (Phase 28 F4c addresses).

### Live catalog
В работе — снимок `INFORMATION_SCHEMA.COLUMNS` (и `KEY_COLUMN_USAGE` где доступно) для всех databases bench-а, сохранённый локально как JSONL. Используется schema linker-ом вместо packaged `schemas.json`. См. [04_ARCHITECTURE/03_schema_linker_v18_bm25.md](../04_ARCHITECTURE/03_schema_linker_v18_bm25.md).

---

## M

### MoE (Mixture of Experts)
Архитектурный pattern, в котором каждый forward pass routes input через subset «experts» (subnetworks). Qwen3-Coder-30B-A3B имеет 30B total parameters и ~3B active per token. Это даёт characteristics более крупной модели при ~3B inference compute. См. [04_ARCHITECTURE/02_models_qwen3_qwen2.5.md](../04_ARCHITECTURE/02_models_qwen3_qwen2.5.md).

### Multiset row match
Метрика comparing prediction execution result vs gold execution result. Игнорирует порядок строк, считает duplicates как separate rows (proper multiset). Standard для Spider 1.0 / BIRD / Spider2-Lite/Snow.

---

## N

### NL2SQL / NL2BI
Natural Language to SQL / Natural Language to Business Intelligence. См. [01_INTRODUCTION/01_problem_statement.md](../01_INTRODUCTION/01_problem_statement.md).

### NUMBER (Snowflake type)
Snowflake numeric type, типично `NUMBER(38,0)`. На PATENTS в Spider2-Snow многие date-like columns (e.g., `publication_date`, `grant_date`) хранятся как `NUMBER` в формате YYYYMMDD. EXTRACT/DATE_TRUNC на NUMBER требуют explicit cast (Phase 28 F4 закрывает).

---

## P

### Pack (schema pack)
Compact JSON-friendly fragment схемы, сформированный pack builder-ом из top-K hits от schema linker. Содержит `tables[].columns[]`, optionally `wildcards`, `join_hints`, `all_columns` side-channel для validator-а. Размер budget: max_tables × max_cols_per_table. См. [04_ARCHITECTURE/04_pack_builder_v18.md](../04_ARCHITECTURE/04_pack_builder_v18.md).

### parse_ok
Метрика: SQL парсится SQLGlot-ом в указанном dialect-е. Pre-stage before schema_valid / dry_run / EXPLAIN.

### Periodic flush
Phase 28 hardening: каждые N tasks (N=10) runner делает `pf.close() / tf.close()` + reopen в append, чтобы Drive FUSE синкнул накопленные writes в cloud. Закрывает регрессию, обнаруженную на S2 в Phase 28.

### PK (Primary Key)
Колонка(ы), однозначно идентифицирующая(ие) строку в таблице. На Spider2 catalog-ах PK metadata часто неполна — использован heuristic injection (см. FK выше).

### Planner
Компонент pipeline, генерирующий JSON-план из (вопрос, pack, external_knowledge). В работе — Qwen3-Coder-30B-A3B, BF16, prompt-based. См. [04_ARCHITECTURE/02_models_qwen3_qwen2.5.md](../04_ARCHITECTURE/02_models_qwen3_qwen2.5.md).

### Pipeline (для конкретного бенчмарка)
Конкретная конфигурация общей архитектуры под данный bench: какие dialect-handlers активны, какие factories выбраны, какие validators цепочка. См. [05_PIPELINES/](../05_PIPELINES/).

---

## R

### Resume scaffolding (resume-from-kernel-death)
Phase 28 hardening в runner-е: при старте читает existing `predictions.jsonl` в run dir, собирает set уже завершённых `instance_id`s, пропускает их в task loop, восстанавливает counter-ы (n_sv, n_parse, n_exec, n_plan) из существующих preds + traces. Открывает файлы в `'a'` mode вместо `'w'`. См. [08_CUSTOM_TOOLS/09_resilience_patterns.md](../08_CUSTOM_TOOLS/09_resilience_patterns.md).

### run_id
Unique string, идентифицирующий конкретный прогон. Используется как имя поддиректории под `outputs/spider2_*/runs/`. Resume scaffolding использует тот же `run_id` для подбора preds.

### Runner
Программа, оркеструющая весь pipeline для bench-а: load catalog, iterate tasks, call planner+emitter, validators, EXPLAIN, write predictions. Главный runner — `tools/remote_scripts/_phase27_snow_runner.py` (28970-29635B, Phase 27/28 hardened). См. [08_CUSTOM_TOOLS/08_runner_orchestration.md](../08_CUSTOM_TOOLS/08_runner_orchestration.md).

---

## S

### schema_invalid
Error class в `error_taxonomy.csv`: SQL прошёл parse_ok, но AST validator нашёл column/table которой нет в pack.all_columns или task_db catalog cols. Главная failure mode на Spider2 family до Phase 27.

### schema linker (schema linking)
Компонент retrieval top-K relevant (table, column) для данного вопроса. В работе — BM25 над live catalog. См. [04_ARCHITECTURE/03_schema_linker_v18_bm25.md](../04_ARCHITECTURE/03_schema_linker_v18_bm25.md).

### schema_valid
Метрика: SQL прошёл AST validator. Means: каждый column/table reference в SQL присутствует в pack.all_columns (или task_db catalog cols после Phase 27 relaxation).

### Self-refine
Pattern: после первой попытки запуска SQL получить engine error (e.g., `invalid identifier 'X'`), вернуть error в planner с инструкцией «X не в схеме, выбери из <pack cols>», и сгенерировать новую попытку. Phase 29 F3 territory (out of scope для current dossier).

### SOTA (State-of-the-Art)
Лучший known публичный результат на конкретном benchmark. См. [09_RESULTS_ANALYSIS/05_leaderboard_position.md](../09_RESULTS_ANALYSIS/05_leaderboard_position.md) для текущих чисел.

### Spider 1.0
NL2SQL benchmark (Yu et al., 2018), 200 university-style SQLite-баз. Около 8K dev + train задач. Долгое время — главный academic benchmark.

### Spider 2.0 family
Семейство NL2BI бенчмарков (Lei et al., 2025): Spider2-Lite (BQ+Snow+SQLite), Spider2-Snow, Spider2-DBT, Spider2 (full agent setting). Хост-репозиторий — `xlang-ai/Spider2`.

### SQLGlot
Python библиотека для парсинга, переписывания, генерации SQL в multiple dialects. См. [10_REFERENCES/02_repos_and_codebases.md](../10_REFERENCES/02_repos_and_codebases.md).

### Supervisor (Phase28S1Supervisor v2)
Daemon thread на S1 kernel, watching for `snow_full_v28_revert_a/_DONE` file. При обнаружении — auto-launches Lite-Snow chain. Hardened: Drive heartbeat файл, log файл, outer try/except, integrity check before firing. См. [08_CUSTOM_TOOLS/09_resilience_patterns.md](../08_CUSTOM_TOOLS/09_resilience_patterns.md).

---

## T

### task_db
В runner: значение `task['db']` или `task['db_id']`, upcased — Spider2 specific catalog/database name (e.g., `PATENTS`, `GA360`). Используется для per-task partitioning BM25 (Phase 27 F1).

### Three-part identifier
В Snow/BQ: `catalog.schema.table` (Snow), `project.dataset.table` (BQ). Phase 27 F1 enforces в pack rendering и в AST guard.

### TimestampTrunc (SQLGlot exp class)
SQLGlot's representation Snowflake's `DATE_TRUNC(unit, expr)`. F4 wrap walks this node type to catch NUMBER/VARIANT date arguments.

---

## V

### v18 / v18.1 / v22 / v24 / v27 / v28
Internal phase version tags. v18 — schema-first pivot (Phase 18). v18.1 — repair sprint (Phase 19). v22 — A1+A2+A3. v24 — sequential runner orchestration. v27 — F1 grounding. v28 — F4 + F4c (Phase 28 closure includes revert of F2a).

### v28-revert-A
Final committed Snow stack (commit `ad5493b`, Phase 28 closure). Includes: F1 + F4 + F4c, без F2a (reverted), без prompt rule «UPPERCASE columns are unquoted» (reverted), col:TYPE rendering kept.

### VARIANT (Snowflake type)
Snowflake's «semi-structured» type — holds JSON. На PATENTS columns like `assignee`, `citation`, `claims_localized` хранятся как VARIANT. F4 wrap имеет VARIANT branch (`x::DATE`); может быть false-positive на JSON-object VARIANT-ах (sf_bq091 case).

---

## W

### Warehouse-scale catalog
В нашем смысле — catalog с тысячами таблиц и десятками тысяч колонок per database. Spider2-Snow PATENTS — пример: одна database, несколько hundred tables. Это — режим, для которого Phase 17 BM25 defaults (80/20) недостаточны.

---

## Y

### YYYYMMDD format
Numeric encoding of date as 8-digit integer (e.g., 20231215 для 15 декабря 2023). На Spider2-Snow PATENTS многие date columns хранятся в этом формате как `NUMBER(38,0)`. F4 wrap-аргумент — `TO_DATE(TO_VARCHAR(x), 'YYYYMMDD')`.

---

## См. также

- [05_acronyms.md](./05_acronyms.md) — acronyms (короткие abbreviations)
- [07_METRICS_AND_RESULTS/01_metric_definitions.md](../07_METRICS_AND_RESULTS/01_metric_definitions.md) — точные формальные определения метрик
- [10_REFERENCES/01_papers.md](../10_REFERENCES/01_papers.md) — цитаты на статьи
