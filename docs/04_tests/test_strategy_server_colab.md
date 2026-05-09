# Test strategy — server + Colab split

## 1. What must pass without Colab

These tests run on the server without GPU:

```bash
pytest -q tests/unit
pytest -q tests/integration/test_nl2chart_mock.py
```

Coverage:

- contracts validation;
- mock extraction client;
- adapter;
- type/role inference;
- CPU visualization;
- artifact store;
- `/api/nl2chart` in mock mode;
- Colab client with mocked HTTP responses.

## 2. What requires real Colab

Manual or smoke tests:

```bash
curl https://<colab-tunnel>/health
curl -X POST https://<colab-tunnel>/extract -H 'Content-Type: application/json' -d @demo_data/extraction_requests/time_series.json
```

Coverage:

- model loaded;
- GPU info;
- SQL generation;
- SELECT-only validation;
- row limit;
- metadata inference;
- `DataExtractionResponse` shape.

## 3. Server -> Colab smoke

Run when Colab is online:

```bash
export EXTRACTION_MODE=colab
export TEXT_TO_SQL_SERVICE_URL=https://<colab-tunnel>

curl http://127.0.0.1:8100/api/runtime
curl -X POST http://127.0.0.1:8100/api/nl2chart -H 'Content-Type: application/json' -d @demo_data/nl2chart_requests/time_series.json
```

Save:

- `/api/runtime` JSON;
- `/api/nl2chart` JSON;
- server logs;
- Colab logs;
- artifact JSON/spec/table.

## 4. Required E2E scenarios

| № | Scenario | Mode | Expected |
|---:|---|---|---|
| 1 | Time series | mock and colab | line chart or valid table fallback |
| 2 | Category comparison | mock and colab | bar chart |
| 3 | Top-N | mock and colab | table or bar |
| 4 | Empty result | mock | safe empty result response |
| 5 | Colab unavailable | colab with tunnel off | safe error `colab_unavailable` |
| 6 | Metadata incomplete | mock | fallback with warning |

## 5. What to send to ChatGPT

After mock tests:

- `pytest` output;
- `/api/runtime` JSON;
- three `/api/nl2chart` mock responses.

After Colab tests:

- Colab `/health` JSON;
- Colab `/extract` JSON;
- GPU info;
- error logs if model failed.

After interservice smoke:

- server `/api/nl2chart` response in `EXTRACTION_MODE=colab`;
- matching server and Colab request_id logs;
- artifact spec/table;
- UI screenshot or description.

After final review:

- `docs/final_integration_review_server_colab.md`;
- pass/fail table for all E2E scenarios;
- remaining risks.
