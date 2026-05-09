# План декомпозиции `SHUBINDENIS/superset_ai`

## Что сохранить

| Компонент | Почему полезен | Что изменить |
|---|---|---|
| `frontend-next` | Готовый Next.js shell, auth pages, chat UI, API calls | Переименовать продукт, убрать Superset страницы, добавить chart/table artifacts |
| `api/main.py` pattern | Готовый FastAPI entrypoint, CORS, routers, lifespan | Убрать Superset routers; добавить `nl2chart`, `artifacts`, `ready` |
| `api/routers/auth.py` | Login/register/session | Оставить почти без изменений |
| `api/routers/chats.py` | Chat CRUD and message persistence | Заменить `agent.chat()` на `nl2bi_orchestrator.run()` |
| `api/routers/frontend_logs.py` | Frontend logs | Оставить |
| `api/routers/health.py` | Health endpoint | Расширить readiness для extract/visualize |
| `api/schemas.py` | Existing DTO style | Разделить на auth/chat DTO и NL2BI DTO или перенести в contracts |
| `backend/auth_service.py` | Users/chats/messages persistence | Оставить; проверить storage path |
| Next.js catch-all `/api/[...path]` proxy | Уже решает proxy to FastAPI | Оставить и настроить на gateway URL |

## Что удалить

| Компонент | Причина удаления |
|---|---|
| `superset/` | Не нужен; пользователь не должен зависеть от Superset |
| `mcp-http`, `superset-init`, Superset docker services | Не нужны для NL2BI pipeline |
| `backend/mcp_client/*` | Superset-specific MCP runtime |
| `backend/us13_15_viz_service.py` в текущем виде | Superset preview/recommend/share; заменить на NL2BI visualization service client |
| `api/routers/viz.py` в текущем виде | Superset dataset/preview/share endpoints |
| `api/routers/scan.py` в текущем виде | Superset source scan |
| `langchain_openai`, `openai`, `mcp-use` | OpenAI/Superset agent no longer used |
| `OPENAI_API_KEY` validation | MVP must run without OpenAI token |
| Superset docs/runbooks | Keep only as historical context if needed |

## Replacement map

| Old concept | New concept |
|---|---|
| `SupersetAIAgent` | `Nl2biChatAgent` / `Nl2biOrchestrator` |
| MCP tools | direct service clients: `extract_client`, `visualize_client` |
| Superset chart/dashboard links | internal artifacts: PNG/spec/table |
| Preview/recommend/share pages | Chat-first artifacts, optional result page |
| `OPENAI_MODEL` | optional local model configs in extract/visualize services |
| Superset dataset id | `data_source.id` + `connection_ref` / demo source |
| Superset chart preview | Vega-Lite/spec/PNG rendered by visualization service |

## Concrete backend edits

### `api/main.py`

Before:

```python
from api.routers import auth, chats, frontend_logs, health, scan, viz
app.include_router(viz.router)
app.include_router(scan.router)
```

After:

```python
from api.routers import auth, chats, frontend_logs, health, nl2chart, artifacts
app.include_router(nl2chart.router)
app.include_router(artifacts.router)
```

### `api/routers/chats.py`

Before:

```python
agent = await agent_manager.get_or_create_agent(session_id, owner=username)
reply = await agent.chat(messages, response_style=..., detail_level=...)
```

After:

```python
orchestrator = get_nl2bi_orchestrator()
reply = await orchestrator.chat(
    session_id=session_id,
    username=username,
    messages=messages,
    response_style=resolved_response_style,
    detail_level=resolved_detail_level,
)
```

### `backend/ai_agent.py`

Option A: delete and create `backend/nl2bi_agent.py`.

Option B: keep filename temporarily but replace class body completely. Better option: delete/rename to avoid Superset/OpenAI coupling.

## Concrete frontend edits

### Navigation

Remove or hide:

- Preview;
- Recommend;
- Share;
- Scan.

Keep:

- Chat;
- Login;
- Register.

Add optional:

- Results/History if useful.

### Chat UI

Add renderers:

```text
components/artifacts/TableArtifact.tsx
components/artifacts/ChartImageArtifact.tsx
components/artifacts/VegaLiteArtifact.tsx
components/artifacts/ErrorArtifact.tsx
components/artifacts/WarningArtifact.tsx
components/artifacts/DebugSqlArtifact.tsx
```

### API client

Replace Superset API methods with:

```ts
sendChatMessage(sessionId, content, settings)
runNl2Chart({ user_query, data_source, presentation_preferences })
getArtifact(artifactId)
```

## Dependency cleanup

### Python remove candidates

- `langchain`;
- `langchain-core`;
- `langchain-openai`;
- `langgraph*` unless no longer needed;
- `openai`;
- `mcp`;
- `mcp-use`;
- `tiktoken` if only OpenAI tokenizer usage;
- Superset-only packages.

### Python keep/add

- `fastapi`;
- `uvicorn`;
- `pydantic`;
- `pydantic-settings`;
- `python-dotenv`;
- `httpx`;
- `orjson`;
- `PyJWT`;
- `pandas` for adapter/fixtures;
- `jsonschema`;
- `pytest`.

### Frontend keep

- `next`;
- `react`;
- `@tanstack/react-query`;
- `react-markdown`;
- `remark-gfm`;
- `lucide-react`;
- Tailwind stack.

### Frontend optional add

- `vega` / `vega-lite` / `react-vega` only if rendering spec client-side. Otherwise use PNG from backend.

## Definition of successful cleanup

- `grep -R "Superset" apps services packages` returns only historical docs or explicitly marked legacy text.
- `grep -R "OPENAI_API_KEY\|ChatOpenAI\|MCPAgent\|mcp_use" services apps packages` returns nothing in runtime code.
- `docker-compose.mvp.yml` contains no Superset services.
- `/api/health` does not require Superset/OpenAI.
- Chat message can produce fixture chart without external API token.
