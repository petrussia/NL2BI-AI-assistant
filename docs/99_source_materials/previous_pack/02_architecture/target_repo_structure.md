# Target repo structure

Recommended structure for `petrussia/NL2BI-AI-assistant` after integration.

```text
NL2BI-AI-assistant/
├── README.md
├── pyproject.toml
├── package.json                         # optional root workspace scripts
├── docker-compose.mvp.yml
├── .env.example
├── apps/
│   └── web/                              # Next.js from superset_ai/frontend-next
│       ├── src/app/login/
│       ├── src/app/register/
│       ├── src/app/app/chat/
│       ├── src/app/api/[...path]/route.ts
│       └── src/components/artifacts/
├── services/
│   ├── gateway/
│   │   ├── api/
│   │   │   ├── main.py
│   │   │   ├── routers/
│   │   │   │   ├── auth.py
│   │   │   │   ├── chats.py
│   │   │   │   ├── nl2chart.py
│   │   │   │   ├── artifacts.py
│   │   │   │   ├── health.py
│   │   │   │   └── frontend_logs.py
│   │   │   └── deps.py
│   │   ├── core/
│   │   │   ├── orchestrator.py
│   │   │   ├── extract_client.py
│   │   │   ├── visualize_client.py
│   │   │   ├── artifact_store.py
│   │   │   └── chat_formatter.py
│   │   └── data/
│   ├── extract/
│   │   ├── api.py
│   │   ├── service.py
│   │   ├── pipeline/
│   │   │   └── denis_code_here_or_imports
│   │   └── tests/
│   └── visualize/
│       ├── api.py
│       ├── service.py
│       ├── runtime_adapter.py
│       ├── pipeline/
│       │   └── peter_code_here_or_imports
│       └── tests/
├── packages/
│   ├── contracts/
│   │   ├── nl2bi_contracts.py
│   │   ├── errors.py
│   │   └── tests/
│   ├── adapter/
│   │   ├── extraction_to_visualization.py
│   │   ├── analytics_payload_v1.py
│   │   ├── type_mapping.py
│   │   ├── role_inference.py
│   │   └── tests/
│   └── artifacts/
│       ├── local_store.py
│       ├── models.py
│       └── tests/
├── tests/
│   ├── fixtures/
│   │   ├── time_series_extraction_response.json
│   │   ├── category_comparison_extraction_response.json
│   │   ├── topn_extraction_response.json
│   │   ├── empty_result_extraction_response.json
│   │   └── incomplete_metadata_extraction_response.json
│   ├── contract/
│   ├── integration/
│   └── e2e/
└── docs/
    ├── architecture.md
    ├── api_contract.md
    ├── runbook.md
    └── testing.md
```

## Import strategy

### Conservative import

Keep donor code under temporary names until cleanup completes:

```text
legacy_superset_ai_import/
```

Then gradually move useful parts into `apps/web` and `services/gateway`.

### Direct import

Copy only required directories directly:

```text
superset-ai-assistant-mcp/frontend-next -> apps/web
superset-ai-assistant-mcp/api -> services/gateway/api
superset-ai-assistant-mcp/backend/auth_service.py -> services/gateway/core/auth_service.py
```

Direct import is cleaner but requires careful path rewrites.

## Branch plan

```text
main
└── integration/nl2chart-mvp
    ├── feat/import-chat-shell
    ├── feat/contracts-adapter
    ├── feat/extract-service
    ├── feat/visualize-service
    ├── feat/nl2chart-gateway
    └── feat/e2e-demo
```
