# Полная сводка результатов (для развёрнутого блока перед заключением)

## Общая статистика
- **88+ baseline-прогонов** в master matrix.
- **5 подмножеств:** 3 внутренних (Spider smoke_10/25, multi-DB 30) + 2 внешних (BIRD-Mini-Dev 30, Spider 2.0-Lite 30).
- **4 модели:** Qwen2.5-Coder-7B (основная), Qwen2.5-Coder-14B (right-sizing), Qwen2.5-7B-Instruct (cross-model), Llama-3.1-8B (mandatory).
- **DeepSeek-Coder-V2-Lite** — заблокирован environmental ABI; документирован.

## Сильнейшие конфигурации
| Категория | Конфигурация | Значение |
|---|---|---|
| Сильнейшая прямая | B0 + Qwen-Coder-7B | smoke_10 / smoke_25 / multi-DB = 1.0000 / 0.9600 / 0.9333 |
| Сильнейшая слойная (multi-DB win) | B2_v2 + Qwen-Coder-7B | multi-DB = 0.8000 (vs B1 = 0.7667, Δ +0.0333) |
| Слойная parity на smoke_25 | B2_v2/B3_v2/B4_v2 + Qwen-Coder-7B | smoke_25 = 0.9600 (= B0 = B1) |
| Mandatory model B0 best | Llama-3.1-8B B0 multi-DB | 0.8333 |
| Внешняя BIRD strongest | B0 + Qwen-Coder-7B BIRD | 0.2667 |

## Right-sizing аргумент
Qwen-Coder-14B vs 7B на multi-DB: B0 = 0.8667 (14B) vs 0.9333 (7B). Бóльшая модель НЕ улучшает EX и проигрывает 7B на 0.067.

## Эффект v2 safety-net дизайна
| Slice | v1 → v2 |
|---|---|
| B3 smoke_10 | 0.3000 → 0.8000 (+0.50) |
| B3 multi-DB | 0.4667 → 0.7333 (+0.27) |
| B4 smoke_10 | 0.3000 → 0.8000 (+0.50) |
| B4 multi-DB | 0.4667 → 0.7333 (+0.27) |

## Внешняя валидация
- **BIRD-Mini-Dev (полная EX):** Qwen-Coder-7B B0 = 0.2667, Llama-3.1-8B B0 = 0.1333. Координаты гораздо более суровые, чем на Spider.
- **Spider 2.0-Lite (структурные метрики, EX недоступен):** safe-SELECT rate 96-100% — pipeline структурно состоятелен на enterprise-схемах.
