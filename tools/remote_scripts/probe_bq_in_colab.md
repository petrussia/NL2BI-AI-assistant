# BigQuery credentials probe — paste into a Colab cell

The harness sandbox refuses to send service-account JSON content through
the `exec_remote.py` bridge (correctly — it would put the key into the
local repo file and the HTTPS POST body). Run this verification yourself
inside a Colab cell. The key stays in your kernel only.

## Step 1 — paste this cell, replace KEY_DICT, run

```python
# In-memory BQ probe. Key is NEVER written to disk and NEVER persisted
# beyond this kernel.
import os, sys, json
from pathlib import Path

KEY_DICT = {
    # paste full contents of your spider2-key.json here
    # ... type, project_id, private_key_id, private_key, client_email, ...
}

PROJECT = KEY_DICT['project_id']

try:
    from google.cloud import bigquery
    from google.oauth2 import service_account
except ImportError:
    !pip -q install google-cloud-bigquery google-auth
    from google.cloud import bigquery
    from google.oauth2 import service_account

import google.cloud.bigquery as _bq
print(f'BQ_VERSION: {_bq.__version__}')

creds = service_account.Credentials.from_service_account_info(KEY_DICT)
print(f'CREDS_OK email={creds.service_account_email}')

client = bigquery.Client(project=PROJECT, credentials=creds)
print(f'CLIENT_OK project={client.project}')

# 1) free dry run
try:
    j = client.query('SELECT 1', job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
    print(f'DRY_RUN_OK estimated_bytes={j.total_bytes_processed}')
except Exception as e:
    print(f'DRY_RUN_FAIL {type(e).__name__}: {e}')

# 2) actual SELECT 1, capped 100 MB billing
try:
    cfg = bigquery.QueryJobConfig(maximum_bytes_billed=10**8)
    j = client.query('SELECT 1 AS one', job_config=cfg)
    print(f'SELECT_1_OK rows={list(j.result(timeout=60))} bytes_billed={j.total_bytes_billed}')
except Exception as e:
    print(f'SELECT_1_FAIL {type(e).__name__}: {str(e)[:400]}')

# 3) datasets owned by this project
try:
    ids = [d.dataset_id for d in client.list_datasets(max_results=50)]
    print(f'OWN_DATASETS n={len(ids)} ids={ids[:30]}')
except Exception as e:
    print(f'LIST_DATASETS_FAIL {type(e).__name__}: {str(e)[:300]}')

# 4) bigquery-public-data access (Spider2 leans on it)
try:
    cfg = bigquery.QueryJobConfig(maximum_bytes_billed=10**8)
    q = 'SELECT COUNT(*) AS n FROM `bigquery-public-data.samples.shakespeare`'
    j = client.query(q, job_config=cfg)
    print(f'PUBLIC_DATA_OK rows={list(j.result(timeout=60))} bytes_billed={j.total_bytes_billed}')
except Exception as e:
    print(f'PUBLIC_DATA_FAIL {type(e).__name__}: {str(e)[:400]}')

# 5) Spider2 raw layout (no creds needed)
S2 = Path('/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/spider2_lite')
print(f'\nSPIDER2_ROOT_EXISTS: {S2.exists()}')
if S2.exists():
    seen = 0
    for sub in S2.rglob('*'):
        rel = sub.relative_to(S2)
        if len(rel.parts) > 3: continue
        kind = 'D' if sub.is_dir() else 'F'
        print(f'  {kind} d{len(rel.parts)} {rel}'); seen += 1
        if seen > 80: print('  ...'); break

# 6) optional: install creds for downstream agent runner (only if you
#    want this kernel to authenticate to BQ for the next runner cell).
#    Comment out if you want to keep creds short-lived.
#
# import json
# from pathlib import Path
# secrets = Path('/content/drive/MyDrive/diploma_plan_sql/secrets')
# secrets.mkdir(parents=True, exist_ok=True)
# p = secrets / 'spider2_bq_sa.json'
# p.write_text(json.dumps(KEY_DICT))
# os.chmod(p, 0o600)
# os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(p)
# print(f'PERSISTED_KEY_TO {p}')
```

## Step 2 — paste the printout back

Copy the lines starting with `BQ_VERSION:` through the Spider2 layout
listing and paste back into chat. I do not need the key contents — only
the diagnostic output. From that I can decide:

- if `SELECT_1_OK` and `PUBLIC_DATA_OK` are green → BigQuery lane (mode A)
  is enabled; I will lay out the per-item routing using whatever
  `OWN_DATASETS` and `PUBLIC_DATA_OK` together cover.
- if `CREDS_FAIL` or `SELECT_1_FAIL` → key is broken or billing is off;
  I will fall back to mode C (structural-only) without spending more
  cycles on the BQ wiring.

## Notes

- The `secrets/spider2_bq_sa.json` write is commented out by default.
  Persisting the key to Drive is fine **only** if you want subsequent
  Colab cells (the FULL agent runner) to authenticate without re-pasting.
  Drive is private, but a leaked Drive sharing link would expose it.
- If you ever run `git status` and see this `secrets/` path tracked,
  STOP — the path is local-only on the Colab Drive, never inside the
  git repo. The repo at `D:\HSE\Диплом\NL2BI-AI-assistant\` does not
  mirror Drive.
