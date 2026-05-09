# Ограничения и blocker-статус (для отдельной секции в общей ВКР)

## Ограничения исследования
1. **Семейство бенчмарков ограничено Spider и его срезами** + два внешних слайса (BIRD-Mini-Dev для полной EX-оценки и Spider 2.0-Lite для структурных метрик). Заявления о доминировании B0 могут не переноситься на корпоративные NL→SQL workloads с нечёткими сущностями, многошаговыми запросами и реальными доменными корпусами.
2. **Аппаратная конфигурация:** все эксперименты на NVIDIA L4 24 GB и NVIDIA A100 80 GB в 4-битном nf4 квантовании bitsandbytes (для 7B-8B-моделей) или BF16 (для 14B). Абсолютные значения EX могут вырасти на fp16/bf16 на более мощном железе, но относительный порядок baseline ожидаемо стабилен.
3. **Малые подмножества** (n=10/25/30): широкие confidence intervals. Преимущество B2_v2 над B1 на multi-DB +0.0333 EX — небольшая абсолютная дельта; на корпоративных бенчмарках ожидается воспроизведение, но без гарантии.
4. **Метрика EX** (Execution Match) рассматривает только совпадение результирующих строк с gold SQL и не различает «правильные строки случайно» от семантически верного SQL.
5. **Стратегия декодирования различается между уровнями:** B0/B1/B2/B3 используют greedy decoding (`do_sample=False`), B4 — multi-candidate sampling (k=3, T=0.7, top_p=0.95). Парные дельты внутри одной модели частично отражают это различие.

## Blocker-статус (открытые)

| Item | Класс | Путь разблокировки |
|---|---|---|
| **DeepSeek-Coder-V2-Lite-Instruct** | environmental: trust_remote_code модельный код ссылается на символ `is_torch_fx_available`, удалённый из `transformers` ≥ 4.40 (в текущем kernel `transformers 5.0.0`). Изолированная установка через `pip install --target` упирается в `dependency_versions_check`. | Свежий Colab notebook с `transformers==4.39.3` pinned ДО любого import. Полный пошаговый чеклист — в `outputs/tables/deepseek_blocker_reproduction_checklist.csv`. ETA ~30 мин. |
| **Spider 2.0-Lite EX** | environmental: gold SQL targetирует BigQuery/Snowflake/DuckDB-extensions, требующие cloud credentials | Provision BigQuery/Snowflake account и загрузка таблиц в warehouse. За пределами project scope. Используются структурные метрики (96-100% safe-SELECT rate подтверждает структурную состоятельность подсистемы). |
| **Editorial polish архитектурного и операционного документа** | human writing | ~2-3 ч ручной работы Шубина |
| **Применение patch-map к docx-черновикам** | human writing | ~1-2 ч в соответствии с `outputs/thesis_pack_shubin/16_docx_apply_order.md` |

**Других blocker-ов нет.** Engineering scope подсистемы извлечения закрыт.
