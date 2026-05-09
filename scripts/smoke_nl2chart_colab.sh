#!/usr/bin/env bash
set -euo pipefail

: "${SERVER_URL:=http://127.0.0.1:8100}"
: "${EXTRACTION_MODE:=colab}"

curl -sS "${SERVER_URL}/api/runtime"
printf '\n'
curl -sS -X POST "${SERVER_URL}/api/nl2chart" \
  -H 'Content-Type: application/json' \
  -d '{"user_query":"Покажи динамику продаж по месяцам","data_source_id":"demo_sales"}'
printf '\n'

