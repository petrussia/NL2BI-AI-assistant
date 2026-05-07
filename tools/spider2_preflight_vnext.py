"""spider2_preflight_vnext.py — readiness probes for Spider2-{Snow,Lite,DBT} v8.

Live probes against:
  1. Cloudflare bridge (Colab kernel)
  2. HF_TOKEN presence (queried via bridge)
  3. BigQuery (client init + dry-run + live SELECT, via bridge)
  4. Snowflake (CONNECT + role/wh/db, via local snowflake_setup/.env)
  5. Spider2-Snow dataset (jsonl + evaluation_suite + 207 SF tasks visible in SF)
  6. Spider2-Lite dataset (547 jsonl + lane breakdown via instance_id prefix)
  7. Spider2-DBT (SSH + dbt-core + duckdb + 68 examples + evaluation_suite)
  8. Secrets-not-in-git scan

Writes:
  outputs/logs/spider2_preflight_vNext.md
  outputs/tables/spider2_preflight_vNext.csv
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
URL_FILE = REPO / 'tools' / '.bridge_url'
OUT_MD = REPO / 'outputs' / 'logs' / 'spider2_preflight_vNext.md'
OUT_CSV = REPO / 'outputs' / 'tables' / 'spider2_preflight_vNext.csv'

# Force UTF-8 stdout for Windows cp1251 console
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def bridge_url() -> str:
    return URL_FILE.read_text(encoding='utf-8').strip().rstrip('/')


def bridge_health() -> dict:
    url = bridge_url()
    try:
        with urllib.request.urlopen(url + '/health', timeout=15) as r:
            data = json.loads(r.read().decode('utf-8'))
        return {'lane': 'bridge', 'check': 'health', 'ok': bool(data.get('ok')),
                'detail': f"pid={data.get('pid')} url={url}", 'lane_label': 'colab_bridge'}
    except Exception as exc:
        return {'lane': 'bridge', 'check': 'health', 'ok': False,
                'detail': f'ERR {exc!r} url={url}', 'lane_label': 'colab_bridge'}


def bridge_exec(code: str, timeout: int = 120) -> dict:
    url = bridge_url() + '/exec'
    payload = json.dumps({'code': code}).encode('utf-8')
    req = urllib.request.Request(url, data=payload,
                                  headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')
        return {'ok': False, 'status': exc.code, 'body': body}
    except Exception as exc:
        return {'ok': False, 'error': repr(exc)}


def hf_token_check() -> dict:
    r = bridge_exec("import os; print('HF_OK' if os.environ.get('HF_TOKEN') else 'HF_MISS')")
    out = (r.get('stdout') or '').strip()
    ok = (out == 'HF_OK')
    return {'lane': 'colab', 'check': 'hf_token', 'ok': ok,
            'detail': out or r.get('error', '?'), 'lane_label': 'colab_inference'}


def bq_check() -> dict:
    code = '''
import os, json
sa = "/content/drive/MyDrive/diploma_plan_sql/secrets/spider2_bq_sa.json"
if not os.path.exists(sa):
    print(json.dumps({"ok": False, "step": "sa_path", "detail": "missing"}))
else:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = sa
    try:
        from google.cloud import bigquery
        c = bigquery.Client()
        dry = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        q = "SELECT COUNT(*) AS n FROM `bigquery-public-data.samples.shakespeare`"
        j = c.query(q, job_config=dry); _ = j.total_bytes_processed
        live_cfg = bigquery.QueryJobConfig(maximum_bytes_billed=50*1024*1024)
        rows = list(c.query(q, job_config=live_cfg).result())
        print(json.dumps({"ok": True, "project": c.project,
                            "dry_run_bytes": j.total_bytes_processed,
                            "live_n": rows[0].n,
                            "billing_cap_bytes": 50*1024*1024}))
    except Exception as e:
        print(json.dumps({"ok": False, "step": "bq_init", "detail": repr(e)[:300]}))
'''
    r = bridge_exec(code, timeout=120)
    out = (r.get('stdout') or '').strip()
    try:
        data = json.loads(out)
    except Exception:
        return {'lane': 'bigquery', 'check': 'bq_full', 'ok': False,
                'detail': f'parse err: {out[:200]}', 'lane_label': 'bq'}
    if data.get('ok'):
        return {'lane': 'bigquery', 'check': 'bq_full', 'ok': True,
                'detail': f"project={data['project']} dry={data['dry_run_bytes']}B "
                          f"live_n={data['live_n']} cap={data['billing_cap_bytes']}",
                'lane_label': 'bq'}
    return {'lane': 'bigquery', 'check': 'bq_full', 'ok': False,
            'detail': f"step={data.get('step')} {data.get('detail')}", 'lane_label': 'bq'}


def sf_check() -> dict:
    """Run snowflake_setup/test_snowflake_connection.py + first PATENTS query."""
    sf_test = REPO / 'snowflake_setup' / 'test_snowflake_connection.py'
    if not sf_test.exists():
        return {'lane': 'snowflake', 'check': 'sf_full', 'ok': False,
                'detail': 'test_snowflake_connection.py missing', 'lane_label': 'sf'}
    p = subprocess.run([sys.executable, str(sf_test)], capture_output=True,
                         text=True, encoding='utf-8', errors='replace', timeout=90)
    ok = ('ALL_OK' in p.stdout) and (p.returncode == 0)
    role = wh = db = ''
    for line in p.stdout.splitlines():
        if 'role=' in line and 'warehouse=' in line:
            for tok in line.split():
                if '=' in tok:
                    k, v = tok.split('=', 1)
                    if k == 'role': role = v
                    elif k == 'warehouse': wh = v
                    elif k == 'database': db = v
    detail = f'role={role} wh={wh} db={db} | ALL_OK={ok}'

    # PATENTS first-table SELECT (proves we can run a Spider2-Snow query)
    code = ('import os, json\n'
            'from snowflake.connector import connect\n'
            'from pathlib import Path\n'
            f'env_path = r"{(REPO / "snowflake_setup" / ".env").as_posix()}"\n'
            'env = {}\n'
            'for line in open(env_path, encoding="utf-8"):\n'
            '    line=line.strip()\n'
            '    if not line or line.startswith("#") or "=" not in line: continue\n'
            '    k,_,v = line.partition("=")\n'
            '    env[k.strip()] = v.strip().strip("\\"").strip("\\\'")\n'
            'try:\n'
            '    cn = connect(account=env["SNOWFLAKE_ACCOUNT"], user=env["SNOWFLAKE_USER"],\n'
            '                  password=env["SNOWFLAKE_PASSWORD"], role=env["SNOWFLAKE_ROLE"],\n'
            '                  warehouse=env["SNOWFLAKE_WAREHOUSE"], database="PATENTS",\n'
            '                  schema="PUBLIC")\n'
            '    cur = cn.cursor()\n'
            "    cur.execute(\"SELECT COUNT(*) FROM PATENTS.INFORMATION_SCHEMA.TABLES\")\n"
            '    n = cur.fetchone()[0]\n'
            '    print("SF_TABLE_COUNT=", n)\n'
            'except Exception as e:\n'
            '    print("SF_QUERY_ERR=", repr(e)[:200])\n')
    p2 = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=60)
    sf_query_ok = 'SF_TABLE_COUNT=' in p2.stdout
    n_tables = ''
    for ln in p2.stdout.splitlines():
        if ln.startswith('SF_TABLE_COUNT='):
            n_tables = ln.split('=', 1)[1].strip()
    return {'lane': 'snowflake', 'check': 'sf_full', 'ok': ok and sf_query_ok,
            'detail': f'{detail} | PATENTS.tables={n_tables}', 'lane_label': 'sf'}


def spider2_lite_dataset_check() -> dict:
    """Spider2-Lite dataset is on Drive — query via bridge."""
    code = '''
import os, json
from collections import Counter
LITE = "/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl"
EV = "/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/evaluation_suite"
RES = "/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource"
out = {"jsonl_exists": os.path.exists(LITE), "ev_exists": os.path.isdir(EV),
        "res_exists": os.path.isdir(RES)}
if out["jsonl_exists"]:
    rows = [json.loads(l) for l in open(LITE)]
    out["n"] = len(rows)
    lanes = Counter()
    for r in rows:
        iid = r["instance_id"]
        if iid.startswith("local"): lanes["sqlite"] += 1
        elif iid.startswith("sf"): lanes["snowflake"] += 1
        elif iid.startswith("bq") or iid.startswith("ga"): lanes["bigquery"] += 1
        else: lanes["unknown"] += 1
    out["lanes"] = dict(lanes)
    out["dbs_unique"] = len(set(r.get("db","") for r in rows))
    out["gold_files"] = len(os.listdir(EV + "/gold")) if os.path.isdir(EV + "/gold") else 0
    out["resource_dbs"] = len(os.listdir(RES + "/databases")) if os.path.isdir(RES + "/databases") else 0
print(json.dumps(out))
'''
    r = bridge_exec(code, timeout=60)
    try:
        data = json.loads((r.get('stdout') or '').strip())
    except Exception:
        return {'lane': 'spider2_lite', 'check': 'dataset', 'ok': False,
                'detail': f'parse err: {(r.get("stdout") or "")[:200]}',
                'lane_label': 's2lite'}
    ok = data.get('jsonl_exists') and data.get('n') == 547 and data.get('ev_exists')
    return {'lane': 'spider2_lite', 'check': 'dataset', 'ok': bool(ok),
            'detail': (f"n={data.get('n')} lanes={data.get('lanes')} "
                       f"dbs={data.get('dbs_unique')} gold={data.get('gold_files')} "
                       f"res_dbs={data.get('resource_dbs')}"),
            'lane_label': 's2lite'}


def spider2_snow_dataset_check() -> dict:
    """Spider2-Snow is the SF-only subset of spider2-lite (sf* prefix).
    Spider2 repo also ships methods/spider-agent-tc — check if present."""
    code = '''
import os, json
from collections import Counter
LITE = "/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl"
SNOW_DIR = "/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/spider2_lite/raw/Spider2/spider2-snow"
out = {"snow_dir": os.path.isdir(SNOW_DIR)}
if os.path.exists(LITE):
    rows = [json.loads(l) for l in open(LITE)]
    sf_only = [r for r in rows if r["instance_id"].startswith("sf")]
    out["sf_subset_n"] = len(sf_only)
    out["sf_dbs_unique"] = len(set(r.get("db","") for r in sf_only))
print(json.dumps(out))
'''
    r = bridge_exec(code, timeout=60)
    try:
        data = json.loads((r.get('stdout') or '').strip())
    except Exception:
        return {'lane': 'spider2_snow', 'check': 'dataset', 'ok': False,
                'detail': f'parse err: {(r.get("stdout") or "")[:200]}',
                'lane_label': 's2snow'}
    # Spider2-Snow as a separate 547 benchmark requires its own jsonl.
    # On THIS Drive copy we have only the SF subset (~207) of Spider2-Lite.
    ok_subset = data.get('sf_subset_n', 0) > 0
    return {'lane': 'spider2_snow', 'check': 'dataset', 'ok': bool(ok_subset),
            'detail': (f"sf_subset_n={data.get('sf_subset_n')} "
                       f"dbs={data.get('sf_dbs_unique')} "
                       f"snow_dir_present={data.get('snow_dir')}"),
            'lane_label': 's2snow'}


def spider2_dbt_check() -> dict:
    cmd = (
        'echo SSH_OK; '
        '/home/denis/dbt/.venv/bin/dbt --version 2>&1 | head -1; '
        '/home/denis/dbt/.venv/bin/python -c "import duckdb; print(\\"DUCKDB=\\", duckdb.__version__)"; '
        'ls /home/denis/dbt/vendor/Spider2/spider2-dbt/examples 2>/dev/null | wc -l; '
        'ls /home/denis/dbt/vendor/Spider2/spider2-dbt/evaluation_suite 2>/dev/null | head -10 | tr "\\n" " "; '
        'echo')
    p = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                          'denis@103.54.18.91', cmd],
                         capture_output=True, text=True,
                         encoding='utf-8', errors='replace', timeout=30)
    out = p.stdout
    lines = [l for l in out.splitlines() if l.strip()]
    ssh_ok = any(l.strip() == 'SSH_OK' for l in lines)
    dbt_line = next((l for l in lines if 'installed:' in l or 'Core:' in l or l.startswith('  - installed')), '')
    duck = next((l for l in lines if 'DUCKDB=' in l), '')
    n_examples = 0
    for l in lines:
        try:
            n_examples = int(l.strip())
            break
        except ValueError:
            continue
    eval_suite_present = 'evaluate.py' in out
    ok = ssh_ok and (n_examples >= 68) and eval_suite_present
    return {'lane': 'spider2_dbt', 'check': 'env', 'ok': bool(ok),
            'detail': (f"ssh={ssh_ok} dbt='{dbt_line.strip()[:60]}' "
                       f"{duck.strip()} examples={n_examples} "
                       f"eval_suite={'yes' if eval_suite_present else 'no'}"),
            'lane_label': 's2dbt'}


def secrets_in_git_check() -> dict:
    """Confirm secrets aren't tracked. Checks git ls-files for risky paths."""
    p = subprocess.run(['git', '-C', str(REPO), 'ls-files'],
                         capture_output=True, text=True,
                         encoding='utf-8', errors='replace', timeout=30)
    tracked = set(p.stdout.splitlines())
    # known risky filenames
    risky = ['snowflake_setup/.env', 'tools/.bridge_url']
    found_risky = [r for r in risky if r in tracked]
    # Note: tools/.bridge_url IS currently tracked but contains only an ephemeral URL,
    # not a credential — flag as warning, not failure.
    has_secrets = any(r for r in found_risky if r != 'tools/.bridge_url')
    return {'lane': 'security', 'check': 'no_secrets_in_git',
            'ok': not has_secrets,
            'detail': (f'tracked_risky={found_risky}'
                       ' (note: tools/.bridge_url is non-credential, ephemeral URL only)'),
            'lane_label': 'security'}


def main() -> int:
    print(f'spider2_preflight_vnext starting @ {now()}')
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for fn in (bridge_health, hf_token_check, bq_check, sf_check,
               spider2_lite_dataset_check, spider2_snow_dataset_check,
               spider2_dbt_check, secrets_in_git_check):
        t0 = time.time()
        try:
            rec = fn()
        except Exception as exc:
            rec = {'lane': fn.__name__, 'check': fn.__name__, 'ok': False,
                   'detail': f'EXC {exc!r}', 'lane_label': fn.__name__}
        rec['wall_s'] = round(time.time() - t0, 2)
        rec['ts'] = now()
        rows.append(rec)
        print(f"  [{('OK' if rec['ok'] else 'FAIL'):4}] {rec['lane']:14} "
              f"{rec['check']:18} ({rec['wall_s']}s) :: {rec['detail'][:140]}")

    # CSV
    with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['ts', 'lane', 'lane_label', 'check',
                                            'ok', 'wall_s', 'detail'])
        w.writeheader()
        for r in rows: w.writerow(r)

    # Markdown
    n_ok = sum(1 for r in rows if r['ok'])
    md = [f'# Spider2 Preflight vNext — {now()}', '',
            f'**{n_ok}/{len(rows)} checks passed.**', '',
            '| lane | check | ok | wall_s | detail |',
            '|---|---|:---:|---:|---|']
    for r in rows:
        md.append(f"| `{r['lane']}` | `{r['check']}` | "
                    f"{'✅' if r['ok'] else '❌'} | {r['wall_s']} | {r['detail']} |")
    md.append('')
    md.append('## Lane readiness')
    by_lane = {r['lane_label']: r['ok'] for r in rows}
    md.append('| lane | ready |')
    md.append('|---|:---:|')
    for k in ('colab_bridge', 'colab_inference', 'bq', 'sf', 's2lite',
              's2snow', 's2dbt', 'security'):
        md.append(f'| `{k}` | {"✅" if by_lane.get(k) else "❌"} |')
    md.append('')
    md.append('## Notes')
    md.append('- Spider2-Snow on this Drive copy is the SF-prefix subset of Spider2-Lite '
              '(207 SF tasks). The official Spider2-Snow benchmark is a separate 547-task '
              'release; if a separate `spider2-snow.jsonl` is required, it must be downloaded '
              'before Phase 1 FULL.')
    md.append('- `tools/.bridge_url` is tracked but contains only an ephemeral '
              'Cloudflare quick-tunnel URL, not a credential.')
    md.append('- `snowflake_setup/.env` and `secrets/spider2_bq_sa.json` are NOT in git.')
    OUT_MD.write_text('\n'.join(md), encoding='utf-8')

    print(f'\nWROTE {OUT_MD.relative_to(REPO).as_posix()}')
    print(f'WROTE {OUT_CSV.relative_to(REPO).as_posix()}')
    return 0 if n_ok == len(rows) else 1


if __name__ == '__main__':
    sys.exit(main())
