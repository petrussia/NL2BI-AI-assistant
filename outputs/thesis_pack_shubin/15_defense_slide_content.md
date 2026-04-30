# 15 — Defense slide content (Shubin)

_Generated: 2026-04-30T14:50:05.209628+00:00_

Use these as 8-10 slides for the defense talk. Each slide is one self-contained block.

---

## Slide 1: Проблема
- Извлечение данных из гетерогенного массива источников по NL-запросу.
- Цель: преобразовать естественный язык пользователя в безопасный SQL → нормализованные данные → готовый payload в подсистему BI (Петухов).
- Метрика: **Execution Match (EX)** — совпадение результирующих строк с gold SQL.

## Slide 2: Архитектура — лестница B0..B4
- B0: прямой SQL по полной схеме.
- B1: B0 + лексическое схемное линкование.
- B2: B1 + JSON-плановая генерация с jsonschema-валидацией.
- B3: B2 + dual retrieval.
- B4: B3 + multi-candidate sampling + bounded repair + SELECT-only AST guard.
- Каждый слой добавляет ровно один компонент → можно изолированно измерить вклад.

## Slide 3: Реализация
- 14 модулей в `repo/src/evaluation/` (B0..B4 + v1/v2 patches).
- 2 версии плановой схемы (`repo/docs/plan_schema*.json`).
- Bridge-инфраструктура для удалённого выполнения на Colab/A100.
- Полный набор предсказаний / метрик / ошибок per item.

## Slide 4: Эксперименты
- 3 подмножества Spider: smoke_10 (n=10), smoke_25 (n=25), **multidb_30** (n=30, 6 разных БД — научно главный срез).
- 4 модели: Qwen-Coder-7B (основная), Qwen-Instruct-7B (cross-model), Llama-3.1-8B (mandatory), Qwen-Coder-14B (comparator на A100 80 GB).
- 29 baseline-конфигураций в master matrix.

## Slide 5: Сильнейшие результаты (вставить master plot)

| Baseline | smoke_10 | smoke_25 | multidb_30 |
|---|---|---|---|
| **B0 + Coder-7B** | **1.0000** | **0.9600** | **0.9333** |
| B1 + Coder-7B | 1.0000 | 0.9600 | 0.7667 |
| **B2_v2 + Coder-7B** | 0.8000 | — | **0.8000** |
| B0 + Coder-14B | 1.0000 | — | 0.8667 |

## Slide 6: Положительный научный результат
- **B2_v2 на multi-DB обгоняет B1 на +0.0333** — единственная слойная конфигурация в проекте, обогнавшая прямую B1.
- Механизм: anti-overengineering planner prompt + unconditional B1 fallback на ошибку плана.

## Slide 7: Отрицательные научные результаты (с честностью)
1. **Слойная архитектура не обгоняет B0** — на Spider с code-aware base model B0 уже насыщает метрику.
2. **Bigger model is not better** — Qwen-Coder-14B (0.8667) проигрывает 7B (0.9333) на multi-DB.
- Это honest negative results, не failures: они дают чёткие production-ориентиры.

## Slide 8: Production-рекомендация
**B0 + Qwen2.5-Coder-7B-Instruct (4-bit) + SELECT-only AST guard + 8s SQLite timeout + AnalyticsPayload v1.**
- Сильнейшая EX (1.00 / 0.96 / 0.9333).
- Один LLM-вызов — минимальная задержка.
- 7B сильнее 14B на multi-DB → right-sizing.
- B2_v2 — audit-trail вариант для compliance/regulated workloads.

## Slide 9: Граница с Петуховым
- Единственный интерфейс: JSON+CSV `AnalyticsPayload v1` (`outputs/docs/io_contracts.md`).
- Все эксперименты, метрики, blocker'ы — только подсистема извлечения.
- Визуализация / BI / UX — зона Петухова, не входит в данную работу.

## Slide 10: ТЗ-покрытие и blocker'ы
- **100% (16/16)** по правилу физических артефактов.
- 3 из 4 mandatory моделей оценены; DeepSeek-Coder-V2-Lite — honest environmental blocker (не VRAM, а несовместимость `trust_remote_code` с современным `transformers`), документирован пошаговой инструкцией разблокировки в fresh kernel.

## (Optional) Slide 11: Q&A prep
- См. `outputs/thesis_pack_shubin/10_answers_to_expected_questions.md` (10 готовых ответов на ожидаемые вопросы комиссии).
