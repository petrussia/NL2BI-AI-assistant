# Target repository structure — server + Colab

```text
NL2BI-AI-assistant/
├── apps/
│   └── web/                                  # Next.js UI
├── services/
│   ├── gateway/                              # FastAPI app on server
│   │   ├── api/
│   │   │   ├── main.py
│   │   │   └── routers/
│   │   │       ├── chats.py
│   │   │       ├── health.py
│   │   │       ├── nl2chart.py
│   │   │       ├── runtime.py
│   │   │       └── artifacts.py
│   │   ├── auth/
│   │   ├── chat/
│   │   └── settings.py
│   ├── orchestrator/
│   │   └── nl2chart_orchestrator.py
│   ├── extraction_client/
│   │   ├── base.py
│   │   ├── mock_client.py
│   │   ├── colab_client.py
│   │   └── disabled_client.py
│   ├── adapter/
│   │   ├── extraction_to_visualization.py
│   │   ├── analytics_payload_v1.py
│   │   ├── role_inference.py
│   │   ├── type_mapping.py
│   │   └── aggregation_inference.py
│   ├── visualization/
│   │   ├── cpu_visualization_service.py
│   │   ├── rules.py
│   │   ├── validation.py
│   │   └── render.py
│   └── artifacts/
│       └── artifact_store.py
├── contracts/
│   ├── common.py
│   ├── extraction.py
│   ├── visualization.py
│   └── nl2chart.py
├── colab/
│   ├── README.md
│   ├── text_to_sql_colab_server.ipynb
│   └── text_to_sql_colab_server.py
├── demo_data/
│   ├── extraction_fixtures/
│   ├── extraction_requests/
│   └── nl2chart_requests/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── smoke/
├── docs/
│   ├── runtime_split.md
│   ├── server_runbook.md
│   ├── colab_runbook.md
│   └── integration_smoke_checklist.md
├── artifacts/                                # gitignored local artifact storage
├── data/                                     # gitignored auth/demo db data
├── docker-compose.server.yml
├── .env.example
└── README.md
```

## Dependency boundary

Server requirements must not include:

```text
torch
transformers
bitsandbytes
accelerate
langchain-openai
openai
mcp-use
```

Colab requirements may include:

```text
torch
transformers
bitsandbytes
accelerate
fastapi
uvicorn
pyngrok or cloudflared setup
sqlglot
pandas
```
