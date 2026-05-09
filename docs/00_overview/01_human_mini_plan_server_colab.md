# Короткий план для человека: что, куда и когда грузить

## Среды

| Среда | Назначение | Что туда грузить | Что туда НЕ грузить |
|---|---|---|---|
| **Server dev+prod** | Основной сайт и backend без GPU, 8 GB RAM | репозиторий `NL2BI-AI-assistant`, Next.js, FastAPI, contracts, adapter, CPU visualization, fixtures, artifacts | LLM weights, `torch`, `transformers`, `bitsandbytes`, Superset/MCP, OpenAI API |
| **Google Colab Pro+** | Внешний GPU inference service | `colab/text_to_sql_colab_server.ipynb` или `.py`, модель Text-to-SQL, demo DB/schema, tunnel | frontend, chat history, artifact storage сайта, пользовательские секреты в notebook cells |
| **ChatGPT / сюда** | Архитектурная сверка после этапов | отчёты Codex/Claude, результаты тестов, JSON ответов, ошибки, скрин/описание UI | приватные токены, пароли, приватные connection strings |

## Этап 0 — подготовить сервер и ветку

**Где:** server dev+prod.

**Что сделать:**

1. Клонировать/обновить `petrussia/NL2BI-AI-assistant`.
2. Создать ветку `integration/server-colab-nl2chart-mvp`.
3. Убедиться, что сервер может запускать Python/FastAPI и Node/Next.js.
4. Не устанавливать GPU-зависимости в основной server environment.

**Что загрузить в Codex:**

- `03_prompts/01_codex_server_runtime_bootstrap_cleanup.md`.

**Что прислать мне после этапа:**

- краткий отчёт Codex;
- дерево верхнего уровня репозитория;
- список удалённых/оставленных частей `superset_ai`;
- результат `git status`;
- результат server health/build, если уже есть.

## Этап 1 — server mock pipeline

**Где:** server dev+prod.

**Что сделать:**

1. Добавить contracts.
2. Добавить mock extraction fixtures.
3. Добавить adapter.
4. Добавить CPU visualization fallback/B1/B2.
5. Добавить orchestrator и `POST /api/nl2chart`.
6. Проверить, что всё работает без Colab.

**Что загрузить в Codex:**

- `03_prompts/02_codex_server_contracts_orchestrator_mock.md`;
- затем `03_prompts/04_codex_server_cpu_visualization.md`.

**Команды/проверки:**

```bash
pytest -q
curl http://127.0.0.1:8100/api/health
curl http://127.0.0.1:8100/api/runtime
curl -X POST http://127.0.0.1:8100/api/nl2chart \
  -H 'Content-Type: application/json' \
  -d @demo_data/nl2chart_requests/time_series.json
```

**Что прислать мне после этапа:**

- отчёт Codex;
- JSON ответа `/api/runtime`;
- JSON ответа `/api/nl2chart` в `EXTRACTION_MODE=mock`;
- список тестов и результат `pytest`;
- если есть UI — скрин/описание artifact в чате.

## Этап 2 — Colab Text-to-SQL service

**Где:** Google Colab Pro+.

**Что сделать:**

1. Открыть Colab notebook.
2. Загрузить/смонтировать код `colab/text_to_sql_colab_server.ipynb` или `.py`.
3. Загрузить Text-to-SQL модель.
4. Поднять FastAPI service.
5. Открыть tunnel через cloudflared/ngrok.
6. Проверить `GET /health` и `POST /extract`.

**Что загрузить в Claude/Colab:**

- `03_prompts/03_claude_colab_text_to_sql_endpoint.md`.

**Команды/проверки:**

```bash
curl https://<colab-tunnel>/health
curl -X POST https://<colab-tunnel>/extract \
  -H 'Content-Type: application/json' \
  -d @demo_data/extraction_requests/time_series.json
```

**Что прислать мне после этапа:**

- отчёт Claude;
- JSON `/health`;
- JSON `/extract` на 1–3 demo-запросах;
- название GPU и VRAM из Colab;
- ошибки загрузки модели, если были;
- tunnel URL можно прислать, но без токенов и секретов.

## Этап 3 — server -> Colab integration

**Где:** server dev+prod + Google Colab Pro+.

**Что сделать:**

1. На сервере выставить:

```env
EXTRACTION_MODE=colab
TEXT_TO_SQL_SERVICE_URL=https://<colab-tunnel>
TEXT_TO_SQL_TIMEOUT_SECONDS=60
VISUALIZATION_MODE=local_cpu
ARTIFACT_STORAGE=local
```

2. Проверить, что server вызывает Colab `/extract`.
3. Проверить, что Colab response проходит через adapter.
4. Проверить, что visualization строит artifact.
5. Проверить, что chat UI показывает результат.

**Что загрузить в Codex:**

- `03_prompts/05_codex_server_colab_client_and_smoke.md`.

**Команды/проверки:**

```bash
curl http://127.0.0.1:8100/api/runtime
curl -X POST http://127.0.0.1:8100/api/nl2chart \
  -H 'Content-Type: application/json' \
  -d @demo_data/nl2chart_requests/time_series.json
```

**Что прислать мне после этапа:**

- JSON `/api/runtime` с `extraction_mode=colab`;
- JSON `/api/nl2chart`;
- server logs по request_id;
- Colab logs по тому же request_id;
- artifact JSON/spec/table;
- скрин/описание результата в чате;
- список ошибок или warnings.

## Этап 4 — frontend artifacts

**Где:** server dev+prod.

**Что сделать:**

1. Подключить chat UI к `POST /api/nl2chart`.
2. Отображать artifact types:
   - `table`;
   - `chart_spec`;
   - `chart_image`, если есть PNG;
   - `warning`;
   - `error`;
   - `debug_sql` только в technical mode.
3. Добавить UI states: loading, Colab unavailable, empty result, metadata incomplete.

**Что загрузить в Codex:**

- `03_prompts/06_codex_frontend_chat_artifacts.md`.

**Что прислать мне после этапа:**

- отчёт Codex;
- скрин/описание чата с результатом;
- пример assistant message metadata/artifacts;
- результат frontend build, если запускался.

## Этап 5 — финальная сверка

**Где:** server dev+prod + Colab.

**Что сделать:**

1. Прогнать 5 E2E сценариев:
   - time series -> line;
   - category comparison -> bar;
   - top-N -> table/bar;
   - empty result -> safe error/empty table;
   - Colab unavailable -> safe fallback/error.
2. Сохранить результаты.
3. Выполнить integration review.

**Что загрузить в Claude/Codex:**

- `03_prompts/07_claude_or_codex_final_integration_review.md`.

**Что прислать мне после этапа:**

- финальный integration review;
- таблицу E2E сценариев: pass/fail;
- JSON всех 5 ответов `/api/nl2chart`;
- список remaining risks;
- ссылку/архив с обновлёнными docs/contracts/tests, если хочешь, чтобы я сверил итоговый план ВКР.
