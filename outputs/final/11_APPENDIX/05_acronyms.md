# Приложение Б.5 — Список сокращений (Acronyms)

Все сокращения и аббревиатуры, используемые в работе. Развёрнутые определения — см. [01_glossary.md](./01_glossary.md).

---

| Acronym | Развёрнуто | Категория |
|---|---|---|
| **AST** | Abstract Syntax Tree | SQL / parsing |
| **BF16** | bfloat16 (16-bit floating point с float32 exponent range) | ML / inference |
| **BIRD** | Big bench for laRge-scale Database grounded text-to-SQL evaluation | Бенчмарк |
| **BM25** | Best Matching 25 (retrieval-ranking function) | Information retrieval |
| **BQ** | BigQuery (Google Cloud Platform data warehouse) | Engine |
| **CTE** | Common Table Expression (`WITH name AS ...`) | SQL |
| **DAG** | Directed Acyclic Graph | Computer science |
| **DBT** | data build tool (transformation framework) | Tooling |
| **DSR-SQL** | Decoupled Schema-aware Reasoning SQL | NL2SQL system |
| **EM** | Exact Match (token-level metric) | Метрика |
| **EX** | Execution Accuracy | Метрика |
| **F1 / F2a / F4 / F4c** | Phase 27/28 dialect interventions (code names) | Phase 28 (см. glossary) |
| **FK** | Foreign Key | Schema |
| **FQN** | Fully Qualified Name (three-part identifier) | SQL / identifiers |
| **FUSE** | Filesystem in USErspace (Drive mount mechanism в Colab) | System / IO |
| **GA360** | Google Analytics 360 (Spider2-Snow database) | Бенчмарк / database |
| **GB** | gigabyte (10⁹ bytes) | Storage |
| **GCP** | Google Cloud Platform | Cloud |
| **GPU** | Graphics Processing Unit | Hardware |
| **HF** | Hugging Face (`HF_TOKEN`, `huggingface_hub`) | ML / tooling |
| **HSE** | Higher School of Economics (Высшая школа экономики) | Институт |
| **iid** | instance_id (unique task identifier) | Dataset |
| **JSON** | JavaScript Object Notation | Format |
| **LLM** | Large Language Model | ML |
| **MoE** | Mixture of Experts | ML / model architecture |
| **NL2BI** | Natural Language to Business Intelligence | Задача |
| **NL2SQL** | Natural Language to SQL | Задача |
| **OOM** | Out Of Memory (типично — GPU CUDA OOM) | System / runtime |
| **PK** | Primary Key | Schema |
| **PR** | Pull Request (Git) | Tooling |
| **PROD** | Production (environment) | DevOps |
| **PyPI** | Python Package Index | Tooling |
| **RAG** | Retrieval-Augmented Generation | ML pattern |
| **RQ** | Research Question | Methodology |
| **S1 / S2 / S3** | Session 1 / 2 / 3 (Colab kernel instances) | Internal naming |
| **SFT** | Supervised Fine-Tuning | ML |
| **SOTA** | State-of-the-Art | Metrics / comparison |
| **SQL** | Structured Query Language | Format |
| **SSH** | Secure Shell | Networking |
| **sv** | schema_valid (краткое в логах) | Метрика |
| **TB** | terabyte (10¹² bytes) | Storage |
| **TCGA** | The Cancer Genome Atlas (Spider2-Snow database) | Бенчмарк / database |
| **TOC** | Table Of Contents | Документация |
| **VARIANT** | Snowflake semi-structured type (JSON-holder) | SQL type |
| **VRAM** | Video RAM (GPU memory) | Hardware |
| **ВКР** | Выпускная Квалификационная Работа (Russian thesis term) | Документация |
| **YYYYMMDD** | 8-digit numeric date encoding | Format |
| **v18 / v22 / v24 / v27 / v28** | Internal phase version tags | Methodology |

---

## Категории

**Бенчмарки и dataset**: BIRD, GA360, TCGA, Spider 1.0, Spider 2.0 (Lite / Snow / DBT).

**Метрики**: EM, EX, sv (schema_valid), parse_ok, dry_run_ok.

**Hardware и runtime**: BF16, FUSE, GPU, OOM, S1/S2/S3, VRAM.

**ML / architecture**: LLM, MoE, RAG, SFT, SOTA.

**SQL / схемы**: AST, CTE, FK, FQN, PK, SQL, VARIANT.

**Tooling**: DBT, HF, JSON, PyPI, SSH.

**Methodology**: NL2BI, NL2SQL, RQ.

**Phase coding**: F1, F2a, F4, F4c (см. [01_glossary.md](./01_glossary.md) для подробностей), v18, v22, v24, v27, v28.

---

## Сокращения, упоминаемые ОДИН раз (не вынесенные выше)

Некоторые acronyms упоминаются в работе ровно один раз — мы их не выносим в основную таблицу, чтобы не утяжелять. Полный список таких single-mentions содержится в:

- `outputs/REPORT_PHASE*.md` — каждый Phase report имеет свой контекст,
- `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md` — large research dossier с десятками system names (DAIL-SQL, CHESS, DTS-SQL, MAC-SQL, и т.д.), которые перенесены в [02_RELATED_WORK/02_sota_systems_2024_2026.md](../02_RELATED_WORK/02_sota_systems_2024_2026.md) с full спецификацией.
