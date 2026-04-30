# Личный вклад (Шубин Денис Алексеевич)

Подсистема интерпретации запросов и извлечения данных по технологии NL→SQL — полностью авторская разработка, выполненная в рамках совместной ВКР с Петуховым (см. контракт интеграции).

## Авторский вклад в архитектуру и реализацию
- **Лестница из 5 baseline-уровней (B0..B4)** с явным промежуточным JSON-планом, лексическим schema linking, dual retrieval, multi-candidate sampling и bounded repair.
- **14 модулей** в `repo/src/evaluation/` (baselines, postprocess, query_analysis, retrieval, external_benchmark_adapters), включая три версии каждого слойного baseline (v0/v1/v2) для иллюстрации архитектурной эволюции.
- **Две версии плановой схемы** (`repo/docs/plan_schema.json`, `plan_schema_v1.json`) с jsonschema-валидацией Draft 2020-12.
- **Trio-уровневая защита исполнения SQL**: regex AST guard (SELECT-only), sandboxed `func_timeout`-обёртка SQLite (8 с), per-item structured logging.
- **Контракт `AnalyticsPayload v1`** для границы с подсистемой Петухова + reference-реализация `postprocess.build_analytics_payload`.
- **Bridge-инфраструктура** для удалённого выполнения экспериментов на Colab/A100/H100 (`tools/exec_remote.py` + Flask + cloudflared + `tools/remote_scripts/` ladder из 90+ скриптов).

## Авторский вклад в экспериментальную часть
- **88+ baseline-конфигураций** на 5 подмножествах × 4 моделях с полными артефактами (predictions, metrics, runlogs, error_cases, examples) per run.
- **Внешняя валидация на BIRD-Mini-Dev** (полная EX-оценка) и **Spider 2.0-Lite** (структурные метрики); адаптеры в `external_benchmark_adapters.py`.
- **v2 safety-net дизайн** (ключевая методологическая находка): отключение синтезированного knowledge channel + безусловный B1-fallback при ошибке плана — восстанавливает катастрофическую регрессию v1 (+0.50 EX на smoke_10, +0.27 на multi-DB).
- **Right-sizing исследование** (Qwen-Coder-7B vs 14B) и **mandatory model coverage** (Llama-3.1-8B полностью оценён, DeepSeek документирован как environmental blocker).

## Граница ответственности с Петуховым
Подсистема **визуализации и аналитического представления** (BI-дашборды, графический интерфейс пользователя, отчёты) — за пределами авторского scope; принадлежит Петухову. Единственный интерфейс между подсистемами — JSON+CSV payload `AnalyticsPayload v1` (см. `outputs/docs/io_contracts.md`). Все экспериментальные результаты, метрики, архитектурные решения и blocker-артефакты, представленные в данной работе, относятся **исключительно** к подсистеме извлечения данных.
