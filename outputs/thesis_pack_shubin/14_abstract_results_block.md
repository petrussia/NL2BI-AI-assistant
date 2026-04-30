# 14 — Abstract / annotation block

_Generated: 2026-04-30T14:50:05.209628+00:00_

## Russian abstract (для аннотации)

> Реализована подсистема извлечения данных естественного языка в SQL для гетерогенного массива источников. Архитектура — пятиуровневая лестница baseline (B0..B4) с компонентами лексического схемного линкования, JSON-плановой генерации с jsonschema-валидацией, dual retrieval, multi-candidate sampling с consistency-выбором, bounded repair и SELECT-only AST safety-guard'ом. Эксперименты на трёх подмножествах Spider (n=10/25/30) и четырёх моделях класса 7B-14B показали: прямая B0 + Qwen2.5-Coder-7B-Instruct достигает EX = 1.0000 / 0.9600 / 0.9333 и является сильнейшей конфигурацией; слойная B2_v2 на multi-DB обгоняет B1 на +0.0333 — единственный позитивный layered результат; больший Coder-14B не превосходит 7B на multi-DB. Покрытие ТЗ — 100% по физическим артефактам.

## English abstract (для possible English summary)

> A natural-language to SQL extraction subsystem is implemented over a heterogeneous source array. The architecture is a five-tier baseline ladder (B0..B4) with components for lexical schema linking, jsonschema-validated JSON plan generation, dual retrieval, multi-candidate sampling with consistency selection, bounded repair, and a SELECT-only AST safety guard. Experiments on three Spider subsets (n=10/25/30) and four 7B-14B-class models show: direct B0 + Qwen2.5-Coder-7B-Instruct achieves EX = 1.0000 / 0.9600 / 0.9333 and is the strongest configuration; layered B2_v2 on multi-DB beats B1 by +0.0333 — the only positive layered result; the larger Coder-14B does not outperform the 7B on multi-DB. TZ coverage is 100% by physical-evidence rule.

## Compact 5-bullet results summary

- **Strongest direct:** B0 + Qwen-Coder-7B → 1.0000 / 0.9600 / 0.9333.
- **Strongest layered:** B2_v2 + Qwen-Coder-7B on multi-DB = 0.8000, beats B1 (0.7667) by +0.0333.
- **Bigger model finding:** Qwen-Coder-14B B0 multi-DB = 0.8667, **lower** than 7B = 0.9333; ties on smoke_10.
- **Mandatory model block:** 3 of 4 evaluated (Qwen-Coder-7B, Qwen-Instruct-7B, Llama-3.1-8B); DeepSeek environmentally blocked.
- **TZ coverage:** 100% (16/16 items by physical-evidence rule).
