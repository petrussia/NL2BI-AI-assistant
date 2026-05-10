# Prompt index — server + Colab version

Use prompts in this order.

| № | Prompt file | Who uses | Runtime | Goal | After this, send to ChatGPT |
|---:|---|---|---|---|---|
| 1 | `01_codex_server_runtime_bootstrap_cleanup.md` | Codex | Server dev+prod | Import/clean donor chat/backend, remove Superset/OpenAI/MCP | Codex report, tree, git status, health/build result |
| 2 | `02_codex_server_contracts_orchestrator_mock.md` | Codex | Server dev+prod | Contracts, mock extraction, adapter, orchestrator, `/api/nl2chart` | `/api/runtime` JSON, `/api/nl2chart` mock JSON, pytest output |
| 3 | `03_claude_colab_text_to_sql_endpoint.md` | Claude / Denis | Colab Pro+ | Build Colab `POST /extract` GPU inference endpoint | `/health` JSON, `/extract` JSON, GPU info, Claude report |
| 4 | `04_codex_server_cpu_visualization.md` | Codex / Peter | Server dev+prod | CPU Text-to-Visualization wrapper B0/B1/B2/fallback | visualization tests, example `VisualizationResponse` |
| 5 | `05_codex_server_colab_client_and_smoke.md` | Codex | Server dev+prod + Colab | Server `ColabExtractionClient`, env, smoke server->Colab | `/api/nl2chart` colab JSON, server+Colab logs by request_id |
| 6 | `06_codex_frontend_chat_artifacts.md` | Codex | Server dev+prod | Show chart/table/warning/error artifacts in chat UI | screenshot/description, assistant message artifact JSON, build result |
| 7 | `07_claude_or_codex_final_integration_review.md` | Claude or Codex | Server + Colab | Final review, E2E checklist, risk table | final review, pass/fail table, all 5 E2E JSON responses |

## Global instruction for all prompts

- Work in `petrussia/NL2BI-AI-assistant`.
- Use branch `integration/server-colab-nl2chart-mvp`.
- Server is both dev and production-like machine.
- There is no separate local-dev environment.
- Do not use OpenAI API.
- Do not require Superset.
- Do not include MCP runtime.
- Do not leak secrets.
- Server must be CPU-only.
- Colab is external GPU inference API.
- Server must support mock/fallback if Colab is unavailable.
- After each implementation, output a report with:
  - changed files;
  - tests run;
  - command outputs;
  - failures;
  - next steps;
  - exact curl examples.
