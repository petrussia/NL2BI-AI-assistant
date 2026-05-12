# 3.2.11 Полная диаграмма pipeline

Этот файл собирает all architectural pieces в один общий flow с lane-specific branches. Используется как primary reference figure в защитной презентации и в основном тексте ВКР.

## Master flowchart

```mermaid
flowchart TD
    Q[Natural-language вопрос Q]
    DB[task.db hint optional<br/>+ task.alias]
    EK[External knowledge K<br/>optional]
    
    Q --> SL
    DB --> CAT
    CAT[Live INFORMATION_SCHEMA catalog]
    
    CAT -->|Snow Lite-Snow| PARTITION[Per-task partition<br/>filter rows where c.db == task.db<br/>Phase 27 F1]
    CAT -->|BQ| BQCAT[Use full catalog<br/>~428K cols]
    CAT -->|SQLite| SQLCAT[Use tables.json<br/>direct schema text]
    CAT -->|DBT| DBTCTX[Read DBT project files<br/>models, schema.yml]
    
    PARTITION --> SL[Schema Linker BM25 v18<br/>top_columns=200 top_tables=40<br/>Snow Phase 27]
    BQCAT --> SL2[Schema Linker BM25 v18<br/>top_columns=80 top_tables=20]
    SQLCAT --> NS[No schema linker<br/>direct prompt with full schema]
    DBTCTX --> DBA[DBT-aware agent<br/>edits multi-file]
    
    SL --> PB[Pack Builder v18<br/>max_tables=10 max_cols=22<br/>+ PK FK injection]
    SL2 --> PB2[Pack Builder v18<br/>max_tables=8 max_cols=22<br/>+ wildcards + join_hints]
    
    PB --> RENDER[Render Snow prompt<br/>3-part names + col:TYPE<br/>+ dialect rules]
    PB2 --> RENDER2[Render BQ prompt]
    
    RENDER --> PL[Planner Qwen3-Coder-30B-A3B<br/>Plan-JSON output]
    RENDER2 --> PL
    NS --> EMIT_S[Family B direct emit<br/>Coder-7B]
    EK --> PL
    EK --> EMIT_S
    
    PL --> JV{JSON Schema<br/>Validator}
    JV -->|fail retry x1| PL
    JV -->|ok| AV{AST Validator<br/>closed-set check}
    AV -->|fail retry x1| PL
    AV -->|exhausted| FB_FALLBACK[Family B fallback<br/>no plan]
    AV -->|ok| FACTORIES
    
    FACTORIES[Candidate Factories]
    FACTORIES -->|BQ| FA[Family A<br/>BQ template render]
    FACTORIES -->|all lanes| FBR[Family B<br/>Coder-7B emit]
    FACTORIES -->|BQ| FC[Family C<br/>JOIN-aware]
    
    FA --> CA[Cand A]
    FBR --> CB[Cand B]
    FC --> CC[Cand C]
    FB_FALLBACK --> CB
    EMIT_S --> CB
    
    CA --> V_BQ[Per-candidate validators<br/>BQ dry_run]
    CB --> V_SNOW{Lane?}
    CC --> V_BQ
    
    V_SNOW -->|Snow| F1G[F1 AST Identifier Guard<br/>Phase 27]
    V_SNOW -->|BQ| V_BQ
    V_SNOW -->|SQLite| V_SQL[SQLite execute]
    V_SNOW -->|DBT| V_DBT[Multi-file edits<br/>dbt build]
    
    F1G -->|sqlglot ParseError| F1FB[F4c regex fallback<br/>Phase 28]
    F1G -->|catalog leak| GUARD_FAIL[Raise IdentifierLeakError]
    F1G -->|ok or autofill| F4W[F4 wrap_date_fn_on_nondate<br/>NUMBER VARIANT cast<br/>Phase 28]
    F1FB --> F4W
    
    F4W --> SVN[Snow AST schema_valid]
    SVN --> PARSE_OK[parse_ok via SQLGlot]
    PARSE_OK --> SNOW_EX[Snow EXPLAIN engine validator]
    
    V_BQ --> SEL[Candidate Selector v18<br/>priority dry_run > parse > sv > A]
    SNOW_EX --> OUT_SNOW[Final SQL Snow]
    V_SQL --> OUT_SQLITE[Final SQL SQLite]
    V_DBT --> OUT_DBT[Final DBT edits]
    
    SEL --> OUT_BQ[Final SQL BQ]
    
    OUT_BQ --> METRICS[Write metrics<br/>predictions.jsonl<br/>traces.jsonl<br/>progress.json]
    OUT_SNOW --> METRICS
    OUT_SQLITE --> METRICS
    OUT_DBT --> METRICS
```

## Sequence diagram — single task на Snow lane (после Phase 28)

```mermaid
sequenceDiagram
    autonumber
    actor U as User script
    participant R as Runner
    participant L as Schema Linker
    participant B as Pack Builder
    participant P as Planner 30B-A3B
    participant V as Validators JSON+AST
    participant E as Emitter Coder-7B
    participant G as F1 AST Guard
    participant FX as F4 Dialect Fixer
    participant S as Snow EXPLAIN

    U->>R: load catalog, partition by db
    R->>R: select task, get task_db, question
    R->>L: linker = SchemaLinker(cat_subset)
    R->>L: link = linker.query(Q, db_filter=task_db, top_columns=200, top_tables=40)
    L-->>R: top-K hits
    R->>B: build_pack(link, lane=snow, alias=task_db, max_tables=10, max_cols=22)
    B-->>R: pack with all_columns
    R->>R: inject_pk_fk(pack, cat_subset)
    R->>R: render prompt (3-part names, col:TYPE, dialect rules)
    
    R->>P: planner generate plan-JSON
    P-->>R: raw plan
    R->>V: parse_plan + validate_plan(pack)
    
    alt validator fails
        V-->>R: failed validation
        R->>P: retry with feedback
        P-->>R: re-emit
        R->>V: re-validate
    end
    
    V-->>R: ok plan
    R->>E: emitter prompt (pack, Q, dialect rules)
    E-->>R: SQL text
    R->>R: _extract_sql(raw)
    R->>G: guard_and_fix_snow_sql(sql, task_db)
    
    alt SQLGlot ParseError
        G->>G: regex_catalog_leak_check (F4c)
        G-->>R: sql unchanged + fallback=regex_only
    else catalog_leak detected
        G-->>R: IdentifierLeakError → fail task
    else ok
        G-->>R: sql_fixed (autofilled catalog if needed)
    end
    
    R->>FX: wrap_date_fn_on_nondate(sql, col_types)
    FX-->>R: sql with wraps (TO_DATE/TO_VARCHAR/CAST)
    
    R->>V: _snow_schema_valid_ast(sql, pack, extra_allowed_cols=task_db_cols)
    V-->>R: schema_valid bool
    R->>V: _snow_parse_ok(sql)
    V-->>R: parse_ok bool
    
    alt parse_ok
        R->>S: cur.execute("EXPLAIN " + sql)
        S-->>R: ok / error
    end
    
    R->>R: write predictions.jsonl, traces.jsonl, progress.json
    R->>R: every 10 tasks: pf.close()+reopen (Drive FUSE sync)
```

## Lane-specific shortcuts

### Spider 1.0 / BIRD shortcut path

```mermaid
flowchart LR
    Q[Question]
    SCH[tables.json packaged schema]
    Q --> EMIT[Family B emit<br/>Coder-7B direct]
    SCH --> EMIT
    EMIT --> SQ_EX[SQLite execute]
    SQ_EX --> OUT[Final SQL]
```

Никакого planner-а, никакого validator-а в режиме fast-path. Использовалось в Phase 1-17. Дав 94% / 88% EX без оверхеда planner-а.

После Phase 18 — added planner option (закрытое-set planning), но измеренный `-0.033 EX` cost — direct emit достаточен на этих бенчмарках.

### Spider2-DBT path

```mermaid
flowchart LR
    Q[Task]
    PROJ[Existing DBT project files]
    Q --> AG[Agent ReAct-style]
    PROJ --> AG
    AG --> ED[Multi-file edits<br/>models/, schema.yml]
    ED --> BUILD[dbt build]
    BUILD --> CMP[Compare output tables<br/>against gold DuckDB]
    CMP --> OK[task_success bool]
```

Совершенно другая архитектура — нет single-SQL emit. Phase 31 territory для replacing this stack with Databao-style scaffold (см. research dossier §4).

## End-to-end timing breakdown (Snow lane single task)

| Stage | Wall time |
|---|---|
| Catalog partition (per-task BM25 build) | ~50-300ms |
| BM25 query | ~10-50ms |
| Pack build + PK/FK inject | ~5-20ms |
| Render prompts | <5ms |
| **Planner LLM call** | **~60-90s** |
| JSON/AST validate | <50ms |
| (если retry) re-planner | +60s |
| **Emitter LLM call** | **~10-30s** |
| F1 guard + F4 wrap + AST validate | <100ms |
| **Snow EXPLAIN** | **~0.5-2s** |
| Write trace + predictions + progress | <100ms |
| **Total per task** | **~70-150s** |

Throughput: ~0.7-0.8 tasks/min. FULL 547 ≈ 11-13h wall.

## Component sizes (LOC)

| Component | File | Approx LOC |
|---|---|---|
| Schema linker v18 | `repo/src/evaluation/schema_linking_v18.py` | ~600 |
| Pack builder v18 | `repo/src/evaluation/schema_pack_builder_v18.py` | ~310 |
| Candidate factories | `repo/src/evaluation/spider2_candidate_factory_v18.py` | ~700+ |
| Candidate selector | `repo/src/evaluation/candidate_selector_v18.py` | ~150 |
| Structured plan + validator | `repo/src/evaluation/structured_plan_v18.py` | ~200 |
| Snow Identifier Guard (F1+F4c) | `repo/src/evaluation/snow_identifier_guard_v27.py` | ~140 |
| Snow Dialect Fixer (F4) | `repo/src/evaluation/snow_dialect_fixer_v28.py` | ~220 |
| Snow Runner (orchestration) | `tools/remote_scripts/_phase27_snow_runner.py` | ~620 |
| Model registry | `repo/src/evaluation/model_registry_v17.py` | (n/a measured) |
| **Total** | | **~3000+ LOC** |

## Phase mapping к components

| Phase | Что добавлено / изменено |
|---|---|
| Phase 17 | Model swap pilot10 — selected Coder family for emit |
| Phase 18 | Live catalogs + BM25 schema linker v18 + pack builder v18 + closed-set planner |
| Phase 19 | v18.1 repair sprint (7 patches на BQ pipeline) |
| Phase 20-21 | Identifier canonicalisation (FQN) — shared между lanes |
| Phase 22 | A1+A2+A3 — pack `all_columns`, join_hints, Family C |
| Phase 23 | FULL diagnostic blocked (GPU contention) — orchestration lesson |
| Phase 24 | Sequential runner + GPU lock + A4 BQ engine-compat rewrites |
| Phase 25 | Spider2-Snow FULL baseline (no methodological change) |
| Phase 26 | Researcher handoff (consolidated metrics + architecture description) |
| Phase 27 | F1 Snow grounding: per-task partition + 3-part rendering + AST guard + PK/FK injection + retrieval window |
| Phase 28 | F2a (REVERTED) + F4 date-cast wrap + F4c regex fallback + resume scaffolding + periodic flush |

## Cross-references

Все компоненты подробно покрыты в:
- [04_ARCHITECTURE/02_models_qwen3_qwen2.5.md](./02_models_qwen3_qwen2.5.md)
- [04_ARCHITECTURE/03_schema_linker_v18_bm25.md](./03_schema_linker_v18_bm25.md)
- [04_ARCHITECTURE/04_pack_builder_v18.md](./04_pack_builder_v18.md)
- [04_ARCHITECTURE/05_planner_emitter_decomposition.md](./05_planner_emitter_decomposition.md)
- [04_ARCHITECTURE/06_candidate_factories_family_abc.md](./06_candidate_factories_family_abc.md)
- [04_ARCHITECTURE/07_validators_json_ast_engine.md](./07_validators_json_ast_engine.md)
- [04_ARCHITECTURE/08_candidate_selector.md](./08_candidate_selector.md)
- [04_ARCHITECTURE/09_dialect_handlers_f1_f4.md](./09_dialect_handlers_f1_f4.md)
- [04_ARCHITECTURE/10_execution_engines.md](./10_execution_engines.md)
- Per-lane pipeline details: [05_PIPELINES/](../05_PIPELINES/)
- Implementation details per tool: [08_CUSTOM_TOOLS/](../08_CUSTOM_TOOLS/)

## Источники

| Утверждение | Источник |
|---|---|
| Component LOC counts | Direct reading of files в `repo/src/evaluation/` and `tools/remote_scripts/` |
| Phase mapping summary | `outputs/REPORT_PHASE26_RESEARCHER_HANDOFF.md` § "Phase progression"; phase reports индексированные в [11_APPENDIX/04_full_phase_report_index.md](../11_APPENDIX/04_full_phase_report_index.md) |
| Per-stage timing breakdown | `tools/remote_scripts/_phase27_snow_runner.py` wall_sec counter; pilot10 traces |
| Throughput ~0.7-0.8 tasks/min | Phase 28 FULL S1 in-flight measurement (108 tasks в 132 min observed runtime) |
