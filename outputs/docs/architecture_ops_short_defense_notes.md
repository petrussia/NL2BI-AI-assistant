# Architecture + Operations — short defense notes

_Generated: 2026-04-30T14:50:05.209628+00:00_

## 1-минутная архитектура
NL question → query analysis (intent + signals) → schema linker (lex) → planner v2 (jsonschema-validated, B1 fallback на ошибку) → SQL synthesizer (полная схема + план) → SELECT-only AST guard → multi-cand+repair (B4 family) → SQLite executor (8s timeout) → postprocess → AnalyticsPayload v1 → BI subsystem of Petukhov.

## 1-минутный production answer
**B0 + Qwen2.5-Coder-7B-Instruct (4-bit) + AST guard + 8s timeout + AnalyticsPayload v1.** EX = 1.0000 / 0.9600 / 0.9333. Один LLM-вызов на запрос. 7B сильнее 14B на multi-DB.

## 1-минутный safety story
Three layers: regex AST guard → sandboxed SQLite с 8-секундным `func_timeout` → per-item logging с raw model output, gold SQL, executable/match flags. Слойные baseline (B2_v2/B3_v2/B4_v2) добавляют jsonschema-validated plan + bounded repair + B1 fallback safety net.

## 1-минутный negative-result story
Layered planning не обгоняет B0 на Spider с code-aware base model — это clean negative result. Bigger model (14B) тоже не обгоняет 7B на multi-DB. ОНО positive layered result: B2_v2 multi-DB beats B1 by +0.0333 — это первый и единственный layered win в проекте.

## 1-минутный boundary с Петуховым
Один интерфейс — JSON+CSV payload `AnalyticsPayload v1` (см. `outputs/docs/io_contracts.md`). Все экспериментальные результаты — только подсистема извлечения. Визуализация / BI / UX — Петухов.
