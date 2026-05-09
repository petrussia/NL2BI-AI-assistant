# Executive summary — новая версия с разделением server-runtime и colab-runtime

## Главный вывод

Систему нужно реализовывать как **серверный CPU-прототип с внешним Colab GPU inference API**.

На сервере должны жить стабильные части:

- Next.js чат;
- FastAPI backend;
- auth/chat history;
- `POST /api/nl2chart`;
- orchestrator;
- adapter `DataExtractionResponse -> VisualizationRequest`;
- CPU Text-to-Visualization B0/B1/B2;
- artifact storage;
- mock/fallback режимы;
- health/ready/runtime endpoints.

В Colab должны жить только тяжёлые модели:

- Text-to-SQL LLM Дениса;
- optional LLM visualization quality mode, если понадобится позже;
- FastAPI endpoint `POST /extract`;
- model loading, SQL generation, safe SQL execution, `DataExtractionResponse`.

## Почему так

Сервер без GPU и с 8 GB RAM не должен запускать 7B/14B модели. Он должен быть стабильной точкой входа для пользователя. Colab Pro+ даёт GPU, но его runtime временный, URL tunnel меняется, сессия может отключаться. Поэтому сервер обязан иметь `EXTRACTION_MODE=mock|colab|disabled` и не падать при недоступном Colab.

## MVP success criteria

MVP считается собранным, когда:

1. На сервере работает чат.
2. На сервере работает `POST /api/nl2chart` в `EXTRACTION_MODE=mock`.
3. В Colab работает `GET /health` и `POST /extract`.
4. На сервере работает `POST /api/nl2chart` в `EXTRACTION_MODE=colab`.
5. Ответ Colab нормализуется adapter'ом.
6. CPU visualization возвращает таблицу или Vega-Lite-like chart spec.
7. В чате отображается artifact.
8. При выключенном Colab сервер возвращает безопасную ошибку, а не stack trace.
9. Тесты серверной части проходят без GPU.
10. В репозитории есть runbook, contracts, fixtures, smoke checklist.

## Что не делать

- Не запускать LLM на сервере.
- Не импортировать `torch`, `transformers`, `bitsandbytes` в основной backend.
- Не использовать OpenAI API.
- Не возвращать frontend'у внутренние ошибки tunnel/Colab как есть.
- Не полагаться на Colab для хранения пользовательской истории или артефактов.
- Не тащить Superset/MCP runtime в новый проект.
