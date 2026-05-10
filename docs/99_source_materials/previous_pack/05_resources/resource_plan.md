# Resource Plan

## 1. Короткий вывод

Для MVP без Superset и без OpenAI API достаточно:

- **1 frontend/backend gateway CPU-сервис**: 2 vCPU, 2–4 GB RAM;
- **1 Text-to-Visualization fast CPU-сервис**: 2 vCPU, 4 GB RAM;
- **1 Text-to-SQL inference-сервис**: 1 GPU 16–24 GB VRAM, 4–8 vCPU, 24–32 GB RAM;
- **локальное/объектное хранилище артефактов**: 10–50 GB на MVP;
- **CI runner**: 2–4 vCPU, 4–8 GB RAM;
- **люди**: Денис, Пётр, 1 shared интегратор/frontend-backend роль; DevOps/test можно part-time.

Если upstream Дениса временно работает на mock/fixture или через уже поднятый Colab/runtime, MVP UI+gateway+visualize можно поднять вообще без GPU. Но полноценный Text-to-SQL без OpenAI API всё равно требует локальной LLM-инференс среды.

## 2. Ресурсы по режимам

### MVP demo / локальная разработка

| Компонент | Количество | CPU | RAM | GPU | Storage | Комментарий |
|---|---:|---:|---:|---:|---:|---|
| Next.js web | 1 | 0.5–1 vCPU | 512 MB–1 GB | нет | <1 GB | Chat UI |
| FastAPI gateway | 1 | 1–2 vCPU | 1–2 GB | нет | 1–5 GB | Auth, chat, orchestrator, artifacts metadata |
| Extract service | 1 | 4 vCPU | 16–24 GB | 1×16–24 GB VRAM | 30–80 GB | Qwen2.5-Coder-7B 4-bit + schema/data |
| Visualize service fast | 1 | 1–2 vCPU | 2–4 GB | нет | 1–5 GB | B1/B2 + pandas + vl-convert |
| Artifact storage | 1 volume | — | — | — | 10–20 GB | PNG/spec/table artifacts |
| Demo DB / SQLite/Postgres | 1 optional | 1 vCPU | 1–2 GB | нет | 1–10 GB | Demo source |
| CI runner | 1 | 2 vCPU | 4 GB | нет | 5–10 GB | Unit/build tests |

### MVP без собственной GPU

| Компонент | Количество | Требования |
|---|---:|---|
| Web + Gateway + Visualize | 1 machine | 4 vCPU, 8 GB RAM |
| Extract | external/manual | Colab/L4 or existing machine; called by HTTP/bridge or mocked for demo |
| Artifact storage | local | 10 GB |

Такой режим полезен для frontend/backend интеграции, но не является полноценным автономным NL2BI.

### Production-like single-node demo

| Компонент | Количество | CPU | RAM | GPU | Storage |
|---|---:|---:|---:|---:|---:|
| Web | 1 | 1 vCPU | 1 GB | нет | 1 GB |
| Gateway | 1 | 2 vCPU | 4 GB | нет | 10 GB |
| Extract model server | 1 | 8 vCPU | 32 GB | 1×24 GB VRAM | 100 GB |
| Visualize fast service | 1 | 2–4 vCPU | 4–8 GB | нет | 10 GB |
| Artifact storage | 1 | — | — | — | 50–100 GB |
| Demo/metadata DB | 1 | 2 vCPU | 4 GB | нет | 20–50 GB |

### Production-like with quality visualization LLM

| Компонент | Количество | GPU requirement | Комментарий |
|---|---:|---:|---|
| Extract Text-to-SQL | 1+ | 1×24 GB VRAM per active model | Qwen2.5-Coder-7B 4-bit comfortably on L4/3090 class |
| Visualize fast B1/B2 | 1+ | no GPU | Always sync fallback |
| Visualize quality B5a Qwen3-14B | 0–1 optional | 1×16–24 GB VRAM | Good candidate for async quality rerun |
| Visualize quality B5b Mistral 24B bnb4 | 0–1 optional | 1×32–48 GB VRAM | Faster in Peter table but larger VRAM requirement |
| Queue/worker | 1 | no GPU | For async quality jobs |

## 3. Ресурсы по людям

### MVP команда

| Роль | Количество | Задачи |
|---|---:|---|
| Denis / Text-to-SQL | 1 | extraction service, SQL safety, row limit, DataExtractionResponse |
| Peter / Text-to-Visualization | 1 | visualize service, runtime adapter, B1/B2 fast path, rendering/fallback |
| Shared integration/backend/frontend | 1 | superset_ai cleanup, gateway, contracts, adapter, chat UI, Docker/CI |
| Reviewer/tester | 0.25–0.5 | manual smoke, e2e, risk review |
| DevOps | 0.25 | compose, env, deployment, logs |

Можно распределить shared роль между Петром и Денисом, но тогда MVP займёт дольше.

### Оценка трудозатрат

| Этап | Owner | Оценка |
|---|---|---:|
| Import/cleanup `superset_ai` | shared | 1–2 дня |
| Contracts + adapter fixtures | shared | 1–2 дня |
| Денис service wrapper | Denis | 2–4 дня |
| Пётр service wrapper | Peter | 2–4 дня |
| Gateway `POST /api/nl2chart` | shared | 1–2 дня |
| Frontend artifacts | shared/frontend | 1–3 дня |
| Docker/CI/smoke | shared/DevOps | 1–2 дня |
| Stabilization/debug | all | 2–5 дней |

Минимальный реалистичный MVP: **2–3 недели календарно** при параллельной работе 2–3 человек.

## 4. Python dependencies

### Gateway

```text
fastapi
uvicorn
pydantic
pydantic-settings
python-dotenv
httpx
orjson
PyJWT
python-multipart
pytest
```

### Adapter

```text
pandas
numpy
python-dateutil
jsonschema
pytest
```

### Extract service

```text
pandas
numpy
jsonschema
sqlglot
func-timeout or asyncio timeout mechanism
sqlite/postgres/clickhouse/trino client depending on datasource
transformers
torch
bitsandbytes
accelerate
```

### Visualize fast service

```text
pandas
numpy
jsonschema
altair
vl-convert-python
psutil
pytest
```

### Visualize quality optional

```text
torch
transformers
bitsandbytes
accelerate
model-specific processors
```

## 5. GPU model planning

| Model/mode | Purpose | Minimum practical VRAM | Recommended GPU |
|---|---|---:|---|
| Qwen2.5-Coder-7B-Instruct 4-bit | Text-to-SQL MVP | 12–16 GB | L4 24 GB / RTX 3090 24 GB / A10 24 GB |
| Qwen3-14B 4-bit | Visualization quality B5a | 16–24 GB | L4 24 GB / RTX 3090 24 GB |
| Mistral Small 24B bnb4 | Visualization quality B5b | 28–32+ GB | A100 40 GB / RTX 6000 Ada 48 GB |
| Gemma 12B | Not recommended in current mode | 16–24 GB | Only for experiments |
| Fast B1/B2 visualization | Production MVP | 0 GB | CPU only |

## 6. Latency targets

| Stage | MVP target | Notes |
|---|---:|---|
| Gateway validation/adapter | <100 ms | Small payloads |
| Text-to-SQL model generation | 2–15 s | Depends on local model/GPU/prompt |
| SQL execution | <=8 s timeout | Default from Денис experiments |
| Visualization fast B1/B2 | <1 s | Often milliseconds on small tables |
| Rendering PNG | <1–3 s | Depends on spec/data size |
| Total sync fast path | 5–25 s | UI should show progress |
| Quality LLM visualization | 6–70 s | Async only |

## 7. Storage

| Storage | MVP | Production-like |
|---|---:|---:|
| Model weights | 30–100 GB | 100–300 GB if multiple models |
| Artifacts | 10–20 GB | 50–500 GB with TTL/S3 |
| Logs | 1–5 GB | 10–100 GB with rotation |
| Demo/source data | 1–20 GB | depends on enterprise sources |
| CI cache | 5–20 GB | 20–100 GB |

## 8. Network and security

- No public exposure of extract/visualize raw services unless protected.
- Public entry should be Next.js/Gateway only.
- Artifacts must be scoped by user/session or signed with TTL.
- SQL debug should be hidden in business mode.
- Logs must redact tokens, connection strings, PII samples.
- Add rate limits for chat and `/api/nl2chart` after MVP.
