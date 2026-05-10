# Resource plan — server dev+prod + Colab Pro+

## 1. Available resources

| Resource | Role |
|---|---|
| Server without GPU, 8 GB RAM | dev + production-like runtime for website/backend/adapter/visualization |
| Google Colab Pro+ | GPU runtime for Text-to-SQL LLM and optional LLM experiments |
| Google Drive | model cache/artifact cache for Colab experiments |

There is no separate local development machine in this plan.

## 2. Server resource allocation

Server should run:

| Component | Expected RAM | Notes |
|---|---:|---|
| FastAPI gateway | 0.5–1.5 GB | auth, chat, orchestrator, clients |
| Next.js web | 0.5–1.5 GB | depends on dev/prod mode |
| SQLite/Postgres demo/auth DB | 0.2–1 GB | SQLite preferred for MVP on 8 GB server |
| Adapter | <0.5 GB | CPU-only |
| CPU visualization B0/B1/B2 | 0.5–2 GB | depends on table size and rendering |
| Artifact storage process | minimal | local volume |
| OS/headroom | 2–3 GB | keep free memory |

Recommended table limits for MVP:

- inline rows from Colab to server: max 1,000 rows;
- columns: max 50;
- render rows: max 500;
- artifact TTL/manual cleanup;
- payload max size: start with 5–10 MB.

## 3. Server must NOT run

- LLM model weights;
- `torch`;
- `transformers`;
- `bitsandbytes`;
- `accelerate`;
- model benchmark loops;
- Superset/MCP;
- OpenAI/LangChain runtime.

## 4. Colab resource allocation

Colab runs:

| Component | GPU/RAM need | Notes |
|---|---:|---|
| Qwen2.5-Coder-7B-Instruct 4-bit | ~12–16 GB VRAM practical | Good MVP Text-to-SQL baseline |
| 14B 4-bit model | ~18–24 GB VRAM | Try only on L4/A100 and short context |
| 24B+ models | 32+ GB VRAM likely | Not recommended for MVP |
| FastAPI endpoint | small CPU RAM | model dominates |
| SQLite demo DB | small | keep local to Colab or receive schema/data from server |

Colab expected limitations:

- tunnel URL changes;
- runtime can disconnect;
- GPU not guaranteed;
- low concurrency;
- not suitable as production storage.

## 5. Runtime modes

| Mode | Server | Colab | Purpose |
|---|---|---|---|
| `mock` | required | off | stable demo and tests |
| `colab` | required | on | real LLM inference demo |
| `disabled` | required | off | safe failure mode |

## 6. Recommended MVP limits

```env
TEXT_TO_SQL_TIMEOUT_SECONDS=60
EXTRACT_TIMEOUT_MS=8000
EXTRACT_ROW_LIMIT=1000
VISUALIZATION_RENDER_ROW_LIMIT=500
MAX_RESULT_COLUMNS=50
MAX_INLINE_PAYLOAD_MB=10
```

## 7. Human effort

| Task | Owner | Estimate |
|---|---|---:|
| Server cleanup from donor `superset_ai` | shared/Codex | 1–2 days |
| Contracts + mock pipeline | shared/Codex | 1–2 days |
| CPU visualization wrapper | Peter/Codex | 1–3 days |
| Colab `/extract` service | Denis/Claude | 2–4 days |
| Server Colab client + smoke | shared/Codex | 1 day |
| Frontend artifacts | shared/Codex | 1–2 days |
| Stabilization/final review | all | 2–4 days |

## 8. Demo strategy

Always prepare demo in this order:

1. Show server mock mode works.
2. Show Colab `/health` works.
3. Show Colab `/extract` works.
4. Show server `/api/nl2chart` calls Colab.
5. Show chat artifact.
6. Turn off/wrong Colab URL and show safe fallback error.

This makes the demo robust even if Colab becomes unstable.
