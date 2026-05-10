# NL2BI Integration Pack v2 — server + Colab split

Эта версия пакета учитывает новое ограничение:

- **локальной dev-машины как отдельной среды нет**;
- **сервер без GPU на 8 GB RAM** используется одновременно как dev и production-like среда;
- **Google Colab Pro+** используется только как внешний GPU inference endpoint для LLM-моделей;
- основной сервер не должен импортировать `torch`, `transformers`, `bitsandbytes` и не должен запускать LLM.

## Как пользоваться пакетом

1. Сначала открой `00_overview/01_human_mini_plan_server_colab.md`.
2. Затем последовательно сам запускай подряд все промпты из `03_prompts/00_prompt_index_server_colab.md`.
3. После каждого этапа сохраняй отчёт инструмента в репозитории по шаблону из `06_checklists/when_to_upload_results_to_chatgpt.md` и ошибки помечай в md и вконце
4. После проверки межсервисного взаимодействия пришли мне:
   - отчёт Codex по серверу;
   - отчёт Claude/Colab по `/extract`;
   - JSON ответа `/api/nl2chart` в режиме `EXTRACTION_MODE=colab`;
   - скрин/описание результата в чате;
   - список упавших тестов, если есть.

## Новая целевая схема

```text
User
  -> Server: Next.js chat
  -> Server: FastAPI /api/nl2chart
  -> Server: Orchestrator
  -> Server: ExtractionClient
       -> mock fixtures OR Colab POST /extract
  -> Server: Adapter
  -> Server: CPU Visualization B0/B1/B2
  -> Server: Artifact storage
  -> Server: Chat response with table/chart artifact
```

Colab не является частью сайта. Colab — это временная замена GPU model server.
