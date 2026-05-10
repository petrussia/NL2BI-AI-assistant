# Public Access On Current Server

Public URL:

- `http://103.54.18.109/`

Runtime services:

- `nl2bi-api.service` runs FastAPI on `127.0.0.1:8100`.
- `nl2bi-web.service` runs the Next.js standalone server on `127.0.0.1:3002`.
- nginx listens on `103.54.18.109:80` and proxies to `127.0.0.1:3002`.

Server-only configuration files:

- `/etc/nl2bi-ai-assistant.env`
- `/etc/systemd/system/nl2bi-api.service`
- `/etc/systemd/system/nl2bi-web.service`
- `/etc/nginx/sites-available/nl2bi-ai-assistant`
- `/etc/nginx/sites-enabled/nl2bi-ai-assistant`

Notes:

- The runtime env uses production mode, mock extraction, local CPU visualization, local artifacts, and the local auth DB.
- Auth secret/settings were copied from the existing server env under `/home/superset_ai/`; secret values are not stored in this repo.
- HTTPS is not configured here because port `443` is already owned by the existing `amnezia-xray` container on this server.

Verification performed on 2026-05-10:

- `systemctl is-active nl2bi-api.service nl2bi-web.service nginx` returned `active` for all three services.
- `curl -fsS http://103.54.18.109/api/server/health` returned `{"status":"ok","service":"nl2bi-gateway"}`.
- `curl -fsSI http://103.54.18.109/` returned `HTTP/1.1 200 OK`.
- External HTTP header check through `api.hackertarget.com` returned `HTTP/1.1 200 OK` from `nginx/1.24.0`.
- Chromium/Playwright public-site smoke passed against `http://103.54.18.109/`.

Browser evidence:

- `docs/e2e_results/public_site/public_site_results.json`
- `docs/e2e_results/public_site/public_site_contact_sheet.png`
- `docs/e2e_results/public_site/*.png`
