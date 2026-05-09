# Interservice smoke checklist — Server -> Colab -> Server

## Before smoke

- [ ] Server backend is running.
- [ ] Server frontend is optional but recommended.
- [ ] Colab service is running.
- [ ] Colab tunnel URL is known.
- [ ] Server `.env` has:

```env
EXTRACTION_MODE=colab
TEXT_TO_SQL_SERVICE_URL=https://<colab-tunnel>
TEXT_TO_SQL_TIMEOUT_SECONDS=60
VISUALIZATION_MODE=local_cpu
```

## Check 1 — Colab health direct

```bash
curl https://<colab-tunnel>/health
```

Expected:

- `status=ok`;
- `model_loaded=true` or clear model status;
- `server_role=colab-runtime`;
- GPU info present.

## Check 2 — Server runtime

```bash
curl http://127.0.0.1:8100/api/runtime
```

Expected:

- `extraction_mode=colab`;
- `gpu_in_backend=false`;
- `colab_service_url_configured=true`;
- `colab_available=true` if health check enabled.

## Check 3 — Direct Colab extract

```bash
curl -X POST https://<colab-tunnel>/extract \
  -H 'Content-Type: application/json' \
  -d @demo_data/extraction_requests/time_series.json
```

Expected:

- `DataExtractionResponse`;
- same `request_id`;
- `sql.query` present or structured error;
- `result_table.columns` explicit;
- `result_table.rows` records;
- `field_metadata` present.

## Check 4 — Server nl2chart through Colab

```bash
curl -X POST http://127.0.0.1:8100/api/nl2chart \
  -H 'Content-Type: application/json' \
  -d @demo_data/nl2chart_requests/time_series.json
```

Expected:

- `Nl2ChartResponse`;
- status `success` or `partial_success`;
- selected view or table;
- warnings if metadata inferred;
- no raw stack traces.

## Check 5 — Colab unavailable

Temporarily set wrong URL or stop Colab.

```bash
curl -X POST http://127.0.0.1:8100/api/nl2chart \
  -H 'Content-Type: application/json' \
  -d @demo_data/nl2chart_requests/time_series.json
```

Expected:

- status `failed` or safe `partial_success` if fallback implemented;
- error code `colab_unavailable` or `extraction_timeout`;
- no server crash;
- no raw traceback.

## Evidence to save

- [ ] `/api/runtime` JSON.
- [ ] Colab `/health` JSON.
- [ ] Direct Colab `/extract` JSON.
- [ ] Server `/api/nl2chart` JSON.
- [ ] Server logs for request_id.
- [ ] Colab logs for request_id.
- [ ] Artifact JSON/spec/table.
- [ ] UI screenshot/description if frontend is connected.
