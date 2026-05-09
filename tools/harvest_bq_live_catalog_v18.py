"""harvest_bq_live_catalog_v18.py — local launcher.

Pushes a self-contained harvest function to the Colab /exec bridge and
starts it as a background thread. The thread queries
`INFORMATION_SCHEMA.COLUMNS` (and TABLES + TABLE_OPTIONS for descriptions)
for each Spider2-Lite-BQ project.dataset combo and writes one JSON line
per column into a Drive-resident jsonl. Errors are recorded as their own
lines with kind="error".

After completion the launcher pulls the file back to outputs/cache/.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BRIDGE_FILE = REPO / 'tools' / '.bridge_url'
BQ_MAP = REPO / 'outputs' / 'cache' / 'spider2_bq_alias_map.json'
LOCAL_OUT = REPO / 'outputs' / 'cache' / 'spider2_bq_live_catalog_v18.jsonl'
LOCAL_LOG = REPO / 'outputs' / 'cache' / 'spider2_bq_live_catalog_v18.log'


def bridge_url() -> str:
    return BRIDGE_FILE.read_text(encoding='utf-8').strip().rstrip('/')


def bridge_exec(code: str, timeout: int = 90) -> dict:
    payload = json.dumps({'code': code}).encode('utf-8')
    req = urllib.request.Request(bridge_url() + '/exec', data=payload,
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


# ----- Colab-side harvest function (sent verbatim to bridge) -----
HARVEST_TEMPLATE = r'''
def harvest_bq_live_v18(alias_map, run_id):
    """Run inside Colab kernel. Writes one jsonl on Drive.

    alias_map: {alias: [project.dataset, ...]}
    run_id:   e.g. "v18_2026-05-09"
    """
    import os, json, time, traceback, threading
    DRV = "/content/drive/MyDrive/diploma_plan_sql"
    OUT_DIR = os.path.join(DRV, "outputs", "cache")
    os.makedirs(OUT_DIR, exist_ok=True)
    OUT_FILE = os.path.join(OUT_DIR, "spider2_bq_live_catalog_v18.jsonl")
    LOG_FILE = os.path.join(OUT_DIR, "spider2_bq_live_catalog_v18.log")
    DONE_FILE = os.path.join(OUT_DIR, "_BQ_HARVEST_DONE")
    PROG_FILE = os.path.join(OUT_DIR, "_BQ_HARVEST_PROGRESS")
    for p in (OUT_FILE, LOG_FILE, DONE_FILE, PROG_FILE):
        try: os.remove(p)
        except FileNotFoundError: pass

    def _w(o, fh):
        fh.write(json.dumps(o, ensure_ascii=False, default=str) + "\n")

    def _runner():
        from google.cloud import bigquery
        client = bigquery.Client()
        proj_dataset = []
        for alias, items in alias_map.items():
            for it in items:
                if "." in it:
                    p, d = it.split(".", 1)
                    proj_dataset.append((alias, p, d))
        total = len(proj_dataset)
        done = 0
        n_columns = 0
        n_tables = 0
        n_errors = 0
        with open(LOG_FILE, "w", encoding="utf-8") as logfh, \
             open(OUT_FILE, "w", encoding="utf-8") as fh:
            for (alias, proj, dset) in proj_dataset:
                logfh.write(f"START alias={alias} proj={proj} dset={dset}\n"); logfh.flush()
                try:
                    # COLUMNS
                    sql_cols = (
                        f"SELECT table_schema, table_name, column_name, data_type, "
                        f"is_nullable, ordinal_position, description "
                        f"FROM `{proj}.{dset}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`"
                    )
                    # COLUMN_FIELD_PATHS gives nested paths too. Fall back to COLUMNS if needed.
                    try:
                        rows = list(client.query(sql_cols).result(timeout=60))
                    except Exception as e_paths:
                        sql_cols2 = (
                            f"SELECT table_schema, table_name, column_name, data_type, "
                            f"is_nullable, ordinal_position FROM "
                            f"`{proj}.{dset}.INFORMATION_SCHEMA.COLUMNS`"
                        )
                        rows = list(client.query(sql_cols2).result(timeout=60))
                    for r in rows:
                        rec = dict(r.items())
                        rec["alias"] = alias
                        rec["project"] = proj
                        rec["dataset"] = dset
                        rec["kind"] = "column_or_field_path"
                        _w(rec, fh)
                        n_columns += 1
                    # TABLES with description
                    sql_tab = (
                        f"SELECT table_schema, table_name, table_type, "
                        f"creation_time FROM `{proj}.{dset}.INFORMATION_SCHEMA.TABLES`"
                    )
                    try:
                        for r in client.query(sql_tab).result(timeout=30):
                            rec = dict(r.items())
                            rec["alias"] = alias
                            rec["project"] = proj
                            rec["dataset"] = dset
                            rec["kind"] = "table"
                            _w(rec, fh)
                            n_tables += 1
                    except Exception as e_tab:
                        logfh.write(f"  TAB_ERR alias={alias} {type(e_tab).__name__} {str(e_tab)[:200]}\n")
                    fh.flush()
                    logfh.write(f"OK alias={alias} cols~{n_columns} tabs~{n_tables}\n"); logfh.flush()
                except Exception as exc:
                    n_errors += 1
                    err_rec = {
                        "kind": "error", "alias": alias, "project": proj, "dataset": dset,
                        "error_type": type(exc).__name__, "error": str(exc)[:600],
                    }
                    _w(err_rec, fh); fh.flush()
                    logfh.write(f"ERR alias={alias} {type(exc).__name__} {str(exc)[:200]}\n")
                    logfh.flush()
                finally:
                    done += 1
                    with open(PROG_FILE, "w") as pf:
                        pf.write(json.dumps({"done": done, "total": total,
                                              "columns": n_columns, "tables": n_tables,
                                              "errors": n_errors}))
        with open(DONE_FILE, "w") as df:
            df.write(json.dumps({"done": done, "total": total,
                                  "columns": n_columns, "tables": n_tables,
                                  "errors": n_errors,
                                  "ts": time.time()}))

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    return {"started": True, "out_file": OUT_FILE, "done_file": DONE_FILE,
             "progress_file": PROG_FILE, "log_file": LOG_FILE}
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--poll-every', type=int, default=30)
    args = ap.parse_args()

    if not BQ_MAP.is_file():
        print('ERR: alias map not built; run audit step first'); return 2
    alias_map = json.loads(BQ_MAP.read_text(encoding='utf-8'))
    n_tasks = sum(len(v) for v in alias_map.values())
    print(f'BQ alias map: {len(alias_map)} aliases, {n_tasks} project.dataset combos')

    # 1. Inject + start
    starter = (HARVEST_TEMPLATE + "\n"
               f"_amap = {json.dumps(alias_map)}\n"
               "result = harvest_bq_live_v18(_amap, 'v18')\n"
               "import json as _j\nprint('===STARTED===');print(_j.dumps(result));print('===STARTED_END===')\n")
    print('Starting harvest BG thread...')
    t0 = time.time()
    r = bridge_exec(starter, timeout=60)
    out = r.get('stdout', '')
    if '===STARTED===' not in out:
        print('NO_START; tail:\n', out[-2000:]); return 2
    started = json.loads(out.split('===STARTED===\n', 1)[1].split('\n===STARTED_END===', 1)[0])
    print(f'  started: {started}')

    # 2. Poll
    poll_code = (
        "import os, json\n"
        "DRV='/content/drive/MyDrive/diploma_plan_sql'\n"
        "PROG=os.path.join(DRV,'outputs','cache','_BQ_HARVEST_PROGRESS')\n"
        "DONE=os.path.join(DRV,'outputs','cache','_BQ_HARVEST_DONE')\n"
        "out={'done_marker': os.path.isfile(DONE), 'progress': None}\n"
        "if os.path.isfile(PROG):\n"
        "    out['progress']=json.loads(open(PROG).read())\n"
        "if os.path.isfile(DONE):\n"
        "    out['final']=json.loads(open(DONE).read())\n"
        "print('===STATUS==='); print(json.dumps(out)); print('===STATUS_END===')\n"
    )
    last = None
    for poll_i in range(120):
        time.sleep(args.poll_every)
        try:
            r2 = bridge_exec(poll_code, timeout=30)
        except Exception as e:
            print(f'  poll_err: {type(e).__name__}'); continue
        out2 = r2.get('stdout', '')
        if '===STATUS===' not in out2: continue
        s = json.loads(out2.split('===STATUS===\n', 1)[1].split('\n===STATUS_END===', 1)[0])
        prog = s.get('progress')
        cur = (prog.get('done'), prog.get('total'), prog.get('errors')) if prog else None
        if cur != last:
            elapsed = int(time.time() - t0)
            print(f'  [{elapsed:5}s] {prog}')
            last = cur
        if s.get('done_marker'):
            print(f'  FINAL: {s.get("final")}'); break
    else:
        print('  TIMEOUT'); return 1

    # 3. Pull jsonl
    pull_code = (
        "import base64, os, json\n"
        "DRV='/content/drive/MyDrive/diploma_plan_sql'\n"
        "F=os.path.join(DRV,'outputs','cache','spider2_bq_live_catalog_v18.jsonl')\n"
        "L=os.path.join(DRV,'outputs','cache','spider2_bq_live_catalog_v18.log')\n"
        "with open(F,'rb') as fh: data=base64.b64encode(fh.read()).decode()\n"
        "log=open(L).read() if os.path.isfile(L) else ''\n"
        "out={'data':data,'log':log,'size':os.path.getsize(F)}\n"
        "print('===PULL==='); print(json.dumps(out)); print('===PULL_END===')\n"
    )
    r3 = bridge_exec(pull_code, timeout=90)
    out3 = r3.get('stdout', '')
    p = json.loads(out3.split('===PULL===\n', 1)[1].split('\n===PULL_END===', 1)[0])
    LOCAL_OUT.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_OUT.write_bytes(base64.b64decode(p['data']))
    LOCAL_LOG.write_text(p['log'], encoding='utf-8')
    print(f'pulled {p["size"]} bytes -> {LOCAL_OUT.relative_to(REPO).as_posix()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
