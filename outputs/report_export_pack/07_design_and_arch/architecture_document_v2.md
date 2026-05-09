# Architecture Document — v2 (defense-final)

**Date:** 2026-04-30T14:50:05.209628+00:00
**Author:** Шубин Денис Алексеевич
**Scope:** подсистема извлечения данных NL→SQL. Подсистема визуализации (Петухов) — out of scope, кроме границы интерфейса.

## 1. Архитектурная лестница B0 → B4

```
[NL question]
     ↓
[Query Analysis]              (rule-based intent + signals; ТЗ 2.2.1)
     ↓
[Schema Linker (lex)]         (table×2 + col×1, min_score=0.5)
     ↓
[Planner v2]                  (jsonschema-validated JSON plan; B1 fallback on invalid plan)
     ↓
[SQL Synthesizer]             (full schema + plan)
     ↓
[Validation Gate]             (SELECT-only AST, regex on forbidden keywords)
     ↓
[Multi-Cand + Repair]         (B4 family only; k=3, T=0.7, top_p=0.95)
     ↓
[Executor]                    (SQLite read-only, 8s `func_timeout`)
     ↓
[Postprocess]                 (normalize_rows + compute_summary)
     ↓
[AnalyticsPayload v1]         (JSON+CSV → BI subsystem of Petukhov)
```

## 2. Что добавляет каждый слой и где он окупается

| Слой | Что добавляет | Где окупается | Где НЕ нужен |
|---|---|---|---|
| B0 | прямой SQL по полной схеме | **всегда** на Spider с code-aware base | — |
| B1 | сужение схемы лексическим линкером | small uniform DBs (smoke_10/25 — 50% prompt reduction без потери EX) | schema-diverse multi-DB (теряет 0.17 EX) |
| B2_v2 | JSON-плановый артефакт + safety net | multi-DB как audit-trail вариант (+0.0333 над B1) | smoke_10 — B0 уже = 1.0 |
| B3_v2 | dual retrieval (без knowledge-канала) | архитектурная подстраховка | накладные расходы без EX-выигрыша |
| B4_v2 | multi-cand + bounded repair + AST guard | **safety и audit-trail для production** | накладные расходы без EX-выигрыша на этом бенчмарке |

## 3. Production-рекомендация

**B0 + Qwen2.5-Coder-7B-Instruct (4-bit nf4) + SELECT-only AST guard + 8s SQLite timeout + AnalyticsPayload v1 post-processor.**

Обоснование:
- Сильнейшая EX по всем подмножествам (1.0000 / 0.9600 / 0.9333).
- Один LLM-вызов на запрос — минимальная задержка.
- 7B спокойно укладывается в L4 24 GB в 4-битной квантизации.
- **Сильнее, чем 14B** на multi-DB (0.9333 vs 0.8667) — 7B оказался правильным размером.
- B2_v2 — резервная audit-trail-конфигурация для случаев, когда downstream нужен JSON-план.

## 4. Trade-offs

| Решение | Плюсы | Минусы |
|---|---|---|
| B0 (полная схема) | Высшая EX | Большой prompt — нужен достаточный context window |
| B1 (lex-линкер) | -50% prompt | Over-pruning на разнообразных схемах |
| B2_v2 (план + fallback) | Audit trail + EX ≥ B1 | Лишний LLM-вызов (план), сложнее отладка |
| B4_v2 (multi-cand + repair) | Безопасность, переиспользуемые паттерны | 3-5× латентность, без EX-выигрыша |

## 5. Risk controls

- **AST-guard:** regex-проверка на запрет `INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/PRAGMA/ATTACH/DETACH/GRANT/REVOKE`. SQL должен начинаться с `SELECT` или `WITH ... SELECT`.
- **Sandbox:** SQLite read-only, обязательный `func_timeout` 8 сек.
- **Logging:** каждый предсказанный SQL логируется per-item с raw model output, gold SQL, executable/match флагами и error_type.
- **Reproducibility:** master matrix CSV/MD — single source of truth; каждый прогон → отдельный prefix → отдельный набор артефактов.

## 6. Failure handling

| Failure | Symptom | Recovery |
|---|---|---|
| Bridge tunnel dead | `getaddrinfo failed` | Re-run cell `7f6bca53`, обновить `tools/.bridge_url` |
| Drive content lost | пустые подкаталоги в `/content/drive/MyDrive/diploma_plan_sql/` | `31_restore_drive_spider.py` + `_upload_local_mirror_v2.py` |
| Model OOM | `CUDA out of memory` | Освободить prior model (BG скрипты делают это); уменьшить кол-во параллельных потоков |
| Plan invalid | `path=b1_fallback_invalid_plan` в predictions | Это **штатная** работа safety net; B1 fallback берёт SQL |
| SQL execution timeout | `error_type=timeout` | Per-query 8s budget; gold SQL тоже не должен превышать |

## 7. Граница с подсистемой Петухова

Единственный интерфейс — JSON+CSV payload `AnalyticsPayload v1`, спецификация в `outputs/docs/io_contracts.md`. Шубин эмитит, Петухов потребляет. Любые изменения схемы — двустороннее согласование.

## 8. Честные ограничения

1. **Один benchmark family** (Spider) — заявления о доминировании B0 могут не переноситься на BIRD/корпоративные NL→SQL.
2. **4-bit nf4 квантование** — абсолютные EX могут вырасти на fp16/bf16; относительный порядок baseline ожидаемо стабилен.
3. **Малые подмножества** (n=10/25/30) — широкие confidence intervals; +0.0333 advantage of B2_v2 над B1 на multi-DB — небольшая дельта в абсолюте.
4. **EX как метрика** не различает "правильные строки случайно" и "семантически верный SQL".
5. **DeepSeek-Coder-V2-Lite-Instruct не оценен** (environmental blocker, документирован).
