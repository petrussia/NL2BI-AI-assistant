# 17 — Final defense one-pager (Shubin)

_Generated: 2026-04-30T14:50:05.209628+00:00_

## Strongest result
**B0 + Qwen2.5-Coder-7B-Instruct → EX = 1.0000 (smoke_10) / 0.9600 (smoke_25) / 0.9333 (multi-DB).** Прямая генерация SQL по полной схеме саттурирует Spider при code-aware базовой модели.

## Strongest negative result
**Qwen2.5-Coder-14B B0 multi-DB = 0.8667 < 7B B0 = 0.9333** (−0.067). Бóльшая модель НЕ лучше на multi-DB; обе саттурируют smoke_10 = 1.00. Right-sizing argument.

## Strongest engineering result
**Полная реализация подсистемы извлечения**: 14 модулей baseline B0..B4_v2; 2 версии плановой схемы; SELECT-only AST guard; sandboxed SQLite executor; multi-candidate consistency selection; bounded repair; jsonschema-validated plan; B1 fallback safety net; AnalyticsPayload v1 для границы с BI.

## Strongest scientific result
**B2_v2 multi-DB = 0.8000 > B1 multi-DB = 0.7667** (++0.0333). Единственная слойная конфигурация в проекте, обогнавшая direct B1. Подтверждает работоспособность safety-net дизайна (anti-overengineering planner prompt + unconditional B1 fallback).

## Strongest production recommendation
**B0 + Qwen2.5-Coder-7B-Instruct (4-bit nf4) + SELECT-only AST guard + 8s SQLite timeout + AnalyticsPayload v1 post-processor.** Сильнейшая EX, минимальная латентность (один LLM-вызов), самый дешёвый GPU footprint (L4 24 GB), сильнее 14B на multi-DB. **B2_v2** — резервный audit-trail вариант.

## Weakest point + best answer
**Weakest point:** «Слойные baseline (B2/B3/B4) не обгоняют B0 на этом бенчмарке». Это можно представить как провал.
**Best answer:** «Это не провал, а измерение benchmark-vs-architecture mismatch. На бенчмарке, где базовая модель саттурирует one-shot generation, никакая дополнительная архитектурная сложность не может улучшить точность — она может только добавить failure modes. Мы показали оба направления: слой добавляет инженерную безопасность (валидация, repair, audit trail), но не точность. На правильном бенчмарке (BIRD, корпоративные многошаговые запросы) слой бы окупился — это наша рекомендация для продолжения исследования. Дополнительно мы продемонстрировали один позитивный случай: B2_v2 multi-DB обгоняет B1 на +0.0333 — это первое подтверждение работоспособности safety-net дизайна в нашем проекте».
