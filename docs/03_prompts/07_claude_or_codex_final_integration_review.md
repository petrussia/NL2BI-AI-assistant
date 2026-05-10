# Prompt 07 — Final integration review: server + Colab NL2BI MVP

Ты работаешь как integration reviewer. Нужно проверить готовую реализацию в `petrussia/NL2BI-AI-assistant` на ветке `integration/server-colab-nl2chart-mvp`.

## Цель

Сделать финальную сверку после всех этапов:

- server-runtime;
- colab-runtime;
- contracts;
- adapter;
- `/api/nl2chart`;
- frontend artifacts;
- fallback modes;
- tests;
- resource split.

## Проверить архитектурные правила

1. Server без GPU.
2. Server не импортирует `torch`, `transformers`, `bitsandbytes` в default runtime.
3. Server не использует OpenAI API.
4. Server не требует Superset/MCP.
5. Colab — внешний HTTP API, не frontend/backend.
6. Server supports `EXTRACTION_MODE=mock|colab|disabled`.
7. Colab outage is handled safely.
8. Contracts are Pydantic validated.
9. SQL generation happens only in extraction/Colab layer.
10. Visualization does not generate SQL.

## Проверить endpoints

Server:

```text
GET /api/health
GET /api/ready
GET /api/runtime
POST /api/nl2chart
GET /api/artifacts/{artifact_id}
```

Colab:

```text
GET /health
POST /extract
POST /reload_model
```

## Run E2E scenarios

Run or inspect evidence for:

1. Time series -> line chart.
2. Category comparison -> bar chart.
3. Top-N -> table/bar.
4. Empty SQL result -> safe empty result response.
5. Colab unavailable -> safe fallback/error.
6. Metadata incomplete -> fallback with warning.
7. Business mode hides SQL.
8. Technical mode can show debug SQL if enabled.

## Required output file

Create `docs/final_integration_review_server_colab.md`.

Structure:

```markdown
# Final Integration Review — Server + Colab NL2BI MVP

## 1. Snapshot
- branch
- commit
- server runtime
- colab runtime
- env summary with secrets redacted

## 2. Runtime split compliance
| Rule | Pass/Fail | Evidence | Notes |

## 3. Endpoint matrix
| Endpoint | Runtime | Pass/Fail | Evidence |

## 4. Contract validation
| Contract | Pass/Fail | Notes |

## 5. E2E scenarios
| Scenario | Mode | Expected | Actual | Pass/Fail | Response file |

## 6. Interservice logs by request_id
- server request_id
- colab request_id
- latency
- errors/warnings

## 7. Fallback behavior
- mock mode
- disabled mode
- Colab unavailable
- invalid Colab response

## 8. Test coverage
- unit
- integration
- smoke
- frontend build

## 9. Remaining risks
| Risk | Impact | Owner | Fix |

## 10. What to send to ChatGPT
- this review
- five `/api/nl2chart` JSON responses
- `/api/runtime` JSON
- Colab `/health` JSON
- screenshots or UI notes
```

## Acceptance criteria

Review must be honest. If something is missing, mark `fail` or `partial`, not `pass`.

## What to send to ChatGPT after this stage

Send:

1. `docs/final_integration_review_server_colab.md`.
2. `/api/runtime` JSON.
3. Colab `/health` JSON.
4. JSON responses for all E2E scenarios.
5. Test/build output.
6. Screenshots or concise UI description.
