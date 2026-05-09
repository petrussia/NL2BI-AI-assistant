# Prompt index

Use prompts in this order.

| Prompt | Who uses | Goal |
|---|---|---|
| `01_codex_import_and_strip_superset_ai.md` | Codex | Import chat shell/backend from `superset_ai`, remove Superset/OpenAI runtime |
| `02_codex_common_backend_gateway.md` | Codex | Build `POST /api/nl2chart`, orchestrator, artifacts, health/ready |
| `03_claude_denis_extraction_service.md` | Claude / Denis | Wrap Text-to-SQL branch into `DataExtractionRequest/Response` service |
| `04_codex_peter_visualization_service.md` | Codex / Peter | Wrap Text-to-Visualization branch into `VisualizationRequest/Response` service |
| `05_codex_adapter_contract_tests.md` | Codex | Implement adapter and contract tests |
| `06_codex_frontend_chat_integration.md` | Codex | Update chat UI to render chart/table/warning/error artifacts |
| `07_codex_docker_ci_observability.md` | Codex | Add Docker, CI, logging, readiness, smoke checks |
| `08_claude_integration_review.md` | Claude | Review finished implementation against contracts and risks |

General instruction for all prompts:

- Work in `petrussia/NL2BI-AI-assistant`.
- Create or use branch `integration/nl2chart-mvp`.
- Do not use OpenAI API.
- Do not require Superset.
- Do not leak secrets.
- Keep changes small and testable.
- After each implementation, output: changed files, tests run, failures, next steps.
