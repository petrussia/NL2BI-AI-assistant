# Prompt 01 — Codex: server runtime bootstrap and cleanup

Ты работаешь в репозитории `petrussia/NL2BI-AI-assistant` на ветке `integration/server-colab-nl2chart-mvp`.

## Цель

Подготовить server-runtime: основной сайт и backend без GPU. Сервер одновременно является dev и production-like машиной. Локальной dev-среды в плане нет.

Нужно перенести/адаптировать из `SHUBINDENIS/superset_ai` только полезные части пользовательского чата и backend shell, но удалить Superset/MCP/OpenAI runtime.

## Runtime split

### Server dev+prod

На сервере должны работать:

- Next.js chat UI;
- FastAPI backend;
- auth/register/login;
- chat sessions/history;
- artifacts в сообщениях;
- health/ready/runtime endpoints;
- future `/api/nl2chart`.

### Colab runtime

Colab будет внешним HTTP inference service. На этом этапе Colab не трогай.

## Жёсткие ограничения

1. Не импортируй `torch`, `transformers`, `bitsandbytes`, `accelerate` в server runtime.
2. Не используй OpenAI API.
3. Не требуй `OPENAI_API_KEY` для старта backend.
4. Не переноси Superset runtime, MCP runtime, `mcp-use`, `langchain-openai`, `openai`.
5. Не оставляй обязательных env-переменных `SUPERSET_*`, `OPENAI_*`.
6. Не ломай auth/chat persistence, если она переносится.
7. Не коммить секреты.

## Что сделать

1. Изучить текущую структуру `NL2BI-AI-assistant` и donor `superset_ai`.
2. Предложить и создать структуру:

```text
apps/web
services/gateway
services/orchestrator
services/extraction_client
services/adapter
services/visualization
services/artifacts
contracts
colab
demo_data
tests
docs
```

3. Перенести или адаптировать:
   - Next.js frontend shell/chat;
   - FastAPI app shell;
   - auth/chat routers;
   - health router;
   - artifacts schema in messages.
4. Удалить или отключить:
   - Superset pages/routes: preview/recommend/share/scan;
   - Superset API routes;
   - MCP clients;
   - OpenAI/LangChain agent;
   - runtime config checks for OpenAI/Superset.
5. Переименовать продукт в `NL2BI AI Assistant`.
6. Добавить `GET /api/runtime`, который возвращает:

```json
{
  "server_runtime": true,
  "gpu_in_backend": false,
  "extraction_mode": "mock",
  "visualization_mode": "local_cpu",
  "colab_service_url_configured": false,
  "server_allows_llm_imports": false
}
```

7. Добавить `.env.example` для server runtime:

```env
APP_ENV=development
EXTRACTION_MODE=mock
TEXT_TO_SQL_SERVICE_URL=
TEXT_TO_SQL_TIMEOUT_SECONDS=60
VISUALIZATION_MODE=local_cpu
ARTIFACT_STORAGE=local
ARTIFACT_DIR=./artifacts
DEMO_DATA_DIR=./demo_data
AUTH_DB_PATH=./data/auth.db
AUTH_JWT_SECRET=dev-only-change-me
DEBUG_SQL_VISIBLE=false
```

8. Добавить docs:
   - `docs/runtime_split.md`;
   - `docs/server_runbook.md`.

## Проверки

Запусти всё, что реально возможно на сервере без GPU:

```bash
python -m pytest -q || true
npm run build || true
python -m uvicorn services.gateway.api.main:app --host 0.0.0.0 --port 8100
curl http://127.0.0.1:8100/api/health
curl http://127.0.0.1:8100/api/runtime
```

Если команды отличаются из-за фактической структуры, используй реальные команды и объясни.

## Acceptance criteria

- Backend стартует без `OPENAI_API_KEY`.
- Server requirements не содержат `torch`, `transformers`, `bitsandbytes`, `openai`, `langchain-openai`, `mcp-use`.
- `/api/health` работает.
- `/api/runtime` работает и показывает `gpu_in_backend=false`.
- Superset/MCP/OpenAI не являются частью default server path.
- Chat/auth shell сохранён или создан минимальный заменитель.

## Итоговый отчёт

В конце выведи:

1. Changed files.
2. Что было перенесено из `superset_ai`.
3. Что было удалено/отключено.
4. Server commands to run.
5. Test/build outputs.
6. Known issues.
7. What to send to ChatGPT after this stage:
   - this report;
   - `git status`;
   - top-level tree;
   - `/api/runtime` JSON;
   - `/api/health` JSON.
