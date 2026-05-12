# 1.1 Постановка задачи

## 1.1.1 NL2BI как подзадача NL2SQL

Тема данной работы — построение интерпретируемого агента **Natural Language to Business Intelligence (NL2BI)**, способного по тексту бизнес-вопроса генерировать корректный SQL-запрос (либо набор изменений в DBT-проекте), который выполняется на реальной enterprise data-warehouse и возвращает ответ, согласующийся с эталоном.

NL2BI — практическое сужение более общей задачи **NL2SQL (Natural Language to SQL)**, исследовавшейся в литературе с 2017 года (Spider 1.0 [Yu et al., 2018]) и получившей в 2023–2024 годах значительный рост качества с появлением больших языковых моделей. От «классического» NL2SQL — в смысле single-database, normalized schema, SELECT-only — NL2BI отличается следующими дополнительными требованиями (см. подробное обсуждение в [02_motivation_and_relevance.md](./02_motivation_and_relevance.md)):

| Аспект | Классический NL2SQL (Spider 1.0, BIRD) | NL2BI (Spider 2.0 family) |
|---|---|---|
| **Engine** | SQLite, in-memory | BigQuery, Snowflake, DuckDB, локальный SQLite |
| **Schema scale** | 5-50 таблиц на БД, ≤30 колонок на таблицу | сотни таблиц, тысячи колонок, иногда — десятки тысяч (полный INFORMATION_SCHEMA varehouse) |
| **Normalization** | как правило 3NF/BCNF, минимум FK-цепочек | разная, в том числе denormalized `wide` таблицы и VARIANT/STRUCT поля |
| **Dialects** | один (SQLite) | множественные: BigQuery legacy/Standard SQL, Snowflake, DuckDB, иногда DBT macros и Jinja |
| **External knowledge** | редко | часто — domain-specific knowledge required to disambiguate terms |
| **Multi-step transformations** | нет | DBT-уровень — multi-file edits, dependency graph, `models/`, `seeds/`, `tests/` |
| **Evaluation** | exact match / execution match на однострочном SQL | multiset row match, table+column match для DBT, дополнительные проверки на `ORDER BY` стабильность |

В рамках работы NL2BI рассматривается на двух уровнях:

1. **Уровень одиночного SQL-запроса**: вход — natural-language вопрос плюс «схема» (метаданные базы), выход — один SQL-запрос, который при выполнении на реальной БД возвращает результат, совпадающий по multiset rows с эталоном. Это покрывает Spider2-Lite, Spider2-Snow и (как контрольная группа классики) Spider 1.0 / BIRD.
2. **Уровень DBT-проекта**: вход — natural-language задача на трансформацию данных в существующем DBT-репозитории, выход — серия file-level edits (создать новую `model.sql`, изменить существующую, добавить `schema.yml` тест), которые после `dbt build` приводят к ожидаемой выходной таблице. Это Spider2-DBT.

## 1.1.2 Формальное определение задачи

### Уровень одиночного SQL-запроса

Пусть:
- $Q$ — natural-language вопрос (строка),
- $\mathcal{S}$ — схема целевой БД, представленная как множество таблиц $\{T_1, \ldots, T_n\}$, где каждая таблица $T_i$ — кортеж $(D_i, \text{schema}_i, \text{name}_i, \text{cols}_i)$, где $D_i$ — имя catalog/database, $\text{cols}_i$ — список колонок с типами,
- $\mathcal{E}$ — engine (например, BigQuery или Snowflake) с заданным dialect-ом,
- $K$ — необязательное external knowledge (например, бизнес-определение метрики).

Требуется построить функцию $f: (Q, \mathcal{S}, \mathcal{E}, K) \rightarrow \text{SQL}$, такую, что для эталона $\text{SQL}^*$ выполнено:

$$
\text{exec}(\mathcal{E}, f(Q, \mathcal{S}, \mathcal{E}, K)) \overset{\text{multiset}}{=} \text{exec}(\mathcal{E}, \text{SQL}^*)
$$

«multiset» означает совпадение наборов строк без учёта порядка и без учёта дубликатов-по-строкам (стандартная метрика evaluation в Spider1/BIRD/Spider2-Lite — `execute_ok` или `EX`).

### Уровень DBT-проекта

Пусть:
- $Q$ — natural-language задача,
- $\mathcal{P}_0$ — состояние DBT-проекта (множество файлов),
- $\mathcal{P}^*$ — эталонное конечное состояние,
- $\mathcal{D}$ — Docker-окружение, в котором выполняется `dbt build`.

Требуется построить агента $g: (Q, \mathcal{P}_0, \mathcal{D}) \rightarrow \mathcal{P}_1$, такого, что при условии `dbt build` отрабатывает без ошибок, и

$$
\text{output\_tables}(\mathcal{P}_1) \overset{\text{table+column}}{=} \text{output\_tables}(\mathcal{P}^*)
$$

где «table+column» — критерий совпадения по структуре + содержимому всех output `models/`, заданных в задании.

## 1.1.3 Базовые допущения

В работе принимаются следующие допущения, важные для интерпретации результатов:

1. **Closed-set assumption на этапе планирования.** Schema linker возвращает набор кандидатных таблиц + колонок. Planner оперирует только этим набором. Если эталонный SQL обращается к таблице, которая не попала в pack — задача невыполнима без перетряхивания pack-а (см. failure mode «table hallucination» в [09_RESULTS_ANALYSIS/06_failure_analysis_remaining.md](../09_RESULTS_ANALYSIS/06_failure_analysis_remaining.md)).
2. **Open-weight constraint.** Используются только модели, чьи веса публично распространяются. Конкретно — Qwen3-Coder-30B-A3B (MoE 30B общих параметров, ~3B активных) как planner и Qwen2.5-Coder-7B как emitter. Нет вызовов закрытых API (OpenAI, Anthropic, Google). Это ограничение принципиально для одного из исследовательских вопросов: «насколько далеко доходит open-weight стэк с ≤30B параметрами при правильном scaffold-е».
3. **Single architecture across benchmarks.** Один и тот же agent stack (с lane-specific дополнениями только в dialect handlers) применяется ко всем бенчмаркам. Не подгоняем разную архитектуру под Spider1 vs Spider2-Snow.
4. **No fine-tuning.** Никакого supervised fine-tuning (SFT) или reinforcement learning поверх Qwen-моделей. Только prompt engineering и pipeline orchestration.
5. **Live catalogs over packaged schemas.** Для Spider2-Lite и Spider2-Snow используются live `INFORMATION_SCHEMA.COLUMNS` запросы к BigQuery/Snowflake (snapshot, сделанный единократно), а не packaged `schemas.json` из репозитория Spider2. Это даёт более точные имена колонок и типы, особенно для Snow-таблиц, где имена хранятся в нижнем регистре (этот факт сыграл решающую роль в Phase 28, см. ниже).
6. **Reproducibility constraint.** Любой эксперимент должен быть полностью воспроизводимым по сохранённому commit-у. Для этого все интервенции коммитятся в репозиторий до запуска FULL прогона.

## 1.1.4 Чем NL2BI отличается от классической литературы

Главное практическое отличие, выявленное в ходе работы, — **scale schema**. Бенчмарки Spider 1.0 и BIRD оперируют схемами с десятками таблиц и сотнями колонок. Любой schema linker, разумно отранжировавший все таблицы по top-30 BM25 score, гарантированно содержит все нужные таблицы. На Spider2-Snow:

- catalog файл `spider2_snow_live_catalog_v18.jsonl` содержит ~587K колонок (рассчитан по нашему probe в Phase 27),
- 152 уникальных database в составе бенчмарка (PATENTS, GA360, CYBERSYN, TCGA, GITHUB_REPOS, и т.д., см. полный список в `03_BENCHMARKS/06_spider2_snow.md`),
- каждая отдельная database может содержать до нескольких сотен таблиц.

При таких числах классический BM25 с дефолтными параметрами (top_columns=80, top_tables=20), откалиброванный под Spider1/BIRD, гарантирует пропуск нужной таблицы для большинства Spider2-Snow задач. Это потребовало специфической интервенции (per-task partitioning + retrieval window scaling, Phase 27 F1, см. [04_ARCHITECTURE/03_schema_linker_v18_bm25.md](../04_ARCHITECTURE/03_schema_linker_v18_bm25.md)).

Второе важное отличие — **case-sensitivity catalog identifiers**. Snowflake, в отличие от SQLite и BigQuery, по умолчанию folds unquoted identifiers в UPPER case. Однако если таблица создана с `CREATE TABLE "lower_case_name"`, имя хранится буквально в нижнем регистре. На практике, в Spider2-Snow PATENTS — все 37 колонок таблицы `PUBLICATIONS` сохранены **в нижнем регистре** (например, `family_id`, `grant_date`). Это эмпирический факт, обнаруженный probe-ом catalog-а в Phase 28, и он опроверг initial гипотезу, которая стоила одного итерационного цикла регрессии (см. полную story в [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md)).

Третье отличие — **dialect runtime quirks**. Snowflake требует cast NUMBER в DATE для `EXTRACT(YEAR FROM …)` если колонка имеет тип `NUMBER(38,0)` (типичный формат хранения YYYYMMDD). BigQuery wildcard tables требуют `_TABLE_SUFFIX BETWEEN`. DBT-задачи требуют изменения `dbt_project.yml` и `schema.yml`. Каждый dialect handler — отдельная интервенция, отслеживаемая через phase reports.

## 1.1.5 Что НЕ является задачей

Чтобы оставить scope обозримым, в работе явно НЕ решаются следующие задачи:

- **Open-domain conversational interface** (multi-turn dialogue с пользователем). Каждый вопрос — single-shot.
- **Disambiguation through user feedback** (агент не задаёт уточняющих вопросов).
- **Schema authoring** (мы не предлагаем оптимальную схему хранения для warehouse).
- **Query optimization** (минимизация cost / latency запроса не оценивается). Достаточно того, что SQL выполняется и возвращает корректный multiset.
- **Closed API integration** (никаких OpenAI / Anthropic / Google Cloud Vertex AI вызовов в основной pipeline; единственное упоминание закрытых моделей — в Related Work для сравнения SOTA).

---

## Ссылки на источники для этого раздела

| Утверждение | Источник |
|---|---|
| Spider 1.0 был представлен в 2018 году | Yu et al., 2018 — см. [10_REFERENCES/01_papers.md](../10_REFERENCES/01_papers.md) |
| Spider2-Snow catalog ~587K колонок | Замер в `tools/remote_scripts/_phase27_step1_diagnostic.py`, упоминается в `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` §1 |
| PATENTS.PATENTS.PUBLICATIONS columns хранятся lowercase | Catalog probe в `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §6 |
| BM25 default параметры (80/20) откалиброваны под Spider1/BIRD | Зафиксировано в `outputs/REPORT_PHASE27_F1_SNOW_GROUNDING.md` §6 (side finding про retrieval window) |
| Single-architecture constraint, no fine-tuning | Принцип проекта, описан в `outputs/PROJECT_CONTEXT_FOR_RESEARCHER.md` |

---

## Что дальше

→ [02_motivation_and_relevance.md](./02_motivation_and_relevance.md) — почему NL2BI задача актуальна именно сейчас, индустриальный контекст
→ [03_research_questions.md](./03_research_questions.md) — три исследовательских вопроса, которые ведут диссертацию
→ [04_thesis_contributions.md](./04_thesis_contributions.md) — итоговые claims защиты
→ [04_ARCHITECTURE/01_overview_single_architecture.md](../04_ARCHITECTURE/01_overview_single_architecture.md) — как именно мы реализовали $f(Q, \mathcal{S}, \mathcal{E}, K)$
