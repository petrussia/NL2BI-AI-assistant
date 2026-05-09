# Server Runbook — NL2BI AI Assistant

## Backend

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest -q
python3 -m uvicorn services.gateway.api.main:app --host 0.0.0.0 --port 8100
```

Health checks:

```bash
curl http://127.0.0.1:8100/api/health
curl http://127.0.0.1:8100/api/ready
curl http://127.0.0.1:8100/api/runtime
```

Mock pipeline:

```bash
curl -X POST http://127.0.0.1:8100/api/nl2chart \
  -H 'Content-Type: application/json' \
  -d @demo_data/nl2chart_requests/time_series.json
```

## Frontend

```bash
cd apps/web
npm install
npm run build
npm run dev -- --hostname 0.0.0.0 --port 3001
```

The Next.js frontend proxies server API calls through `/api/server/*`.
Set a different backend URL with:

```env
SERVER_API_BASE_URL=http://127.0.0.1:8100
```

## Colab Mode

```bash
export EXTRACTION_MODE=colab
export TEXT_TO_SQL_SERVICE_URL=https://<colab-tunnel>
export TEXT_TO_SQL_TIMEOUT_SECONDS=60
python3 -m uvicorn services.gateway.api.main:app --host 0.0.0.0 --port 8100
```

Smoke:

```bash
python3 scripts/smoke_server_colab.py
```

Broken Colab URL should return a safe `colab_unavailable` error and must not
return stack traces.

