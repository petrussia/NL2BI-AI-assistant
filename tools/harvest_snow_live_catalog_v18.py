"""harvest_snow_live_catalog_v18.py — local launcher.

Mirrors `harvest_bq_live_catalog_v18.py` for Snow. Connects with the SF
service-user creds in `secrets/snowflake.json` and harvests:
  - INFORMATION_SCHEMA.SCHEMATA
  - INFORMATION_SCHEMA.TABLES
  - INFORMATION_SCHEMA.COLUMNS
for the canonical 152 Spider2-Snow databases.

Output: outputs/cache/spider2_snow_live_catalog_v18.jsonl (one record per
column, plus error/skip records).
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
SNOW_DB_LIST = REPO / 'outputs' / 'cache' / 'spider2_snow_db_list.json'
LOCAL_OUT = REPO / 'outputs' / 'cache' / 'spider2_snow_live_catalog_v18.jsonl'
LOCAL_LOG = REPO / 'outputs' / 'cache' / 'spider2_snow_live_catalog_v18.log'


def bridge_url() -> str:
    return BRIDGE_FILE.read_text(encoding='utf-8').strip().rstrip('/')


def bridge_exec(code: str, timeout: int = 90) -> dict:
    payload = json.dumps({'code': code}).encode('utf-8')
    req = urllib.request.Request(bridge_url() + '/exec', data=payload,
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


HARVEST_TEMPLATE = r'''
def harvest_snow_live_v18(db_list, run_id):
    """Run inside Colab kernel."""
    import os, json, time, traceback, threading
    DRV = "/content/drive/MyDrive/diploma_plan_sql"
    OUT_DIR = os.path.join(DRV, "outputs", "cache")
    os.makedirs(OUT_DIR, exist_ok=True)
    OUT_FILE = os.path.join(OUT_DIR, "spider2_snow_live_catalog_v18.jsonl")
    LOG_FILE = os.path.join(OUT_DIR, "spider2_snow_live_catalog_v18.log")
    DONE_FILE = os.path.join(OUT_DIR, "_SNOW_HARVEST_DONE")
    PROG_FILE = os.path.join(OUT_DIR, "_SNOW_HARVEST_PROGRESS")
    for p in (OUT_FILE, LOG_FILE, DONE_FILE, PROG_FILE):
        try: os.remove(p)
        except FileNotFoundError: pass

    def _w(o, fh):
        fh.write(json.dumps(o, ensure_ascii=False, default=str) + "\n")

    def _runner():
        try:
            with open(os.path.join(DRV, "secrets", "snowflake.json")) as fh:
                creds = json.load(fh)
            import snowflake.connector
            conn = snowflake.connector.connect(
                user=creds["user"], password=creds["password"],
                account=creds["account"],
                warehouse=creds.get("warehouse"),
                role=creds.get("role"),
            )
            cur = conn.cursor()
        except Exception as e:
            with open(LOG_FILE, "w", encoding="utf-8") as logfh:
                logfh.write(f"CONNECT_FAIL {type(e).__name__}: {e}\n")
            with open(DONE_FILE, "w") as df:
                df.write(json.dumps({"connect_fail": str(e)[:400]}))
            return
        total = len(db_list)
        done = 0
        n_columns = 0
        n_tables = 0
        n_errors = 0
        with open(LOG_FILE, "w", encoding="utf-8") as logfh, \
             open(OUT_FILE, "w", encoding="utf-8") as fh:
            for db in db_list:
                logfh.write(f"START db={db}\n"); logfh.flush()
                try:
                    # COLUMNS — one query per DB (covers all schemas)
                    sql = (
                        f'SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, '
                        f'COLUMN_NAME, DATA_TYPE, IS_NULLABLE, ORDINAL_POSITION, '
                        f'COMMENT '
                        f'FROM "{db}".INFORMATION_SCHEMA.COLUMNS '
                        f"WHERE TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA')"
                    )
                    cur.execute(sql)
                    cols = [c[0] for c in cur.description]
                    for row in cur.fetchall():
                        rec = dict(zip(cols, row))
                        rec["database"] = db
                        rec["kind"] = "column"
                        _w(rec, fh)
                        n_columns += 1
                    # TABLES + descriptions
                    sql_tab = (
                        f'SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE, COMMENT, '
                        f'ROW_COUNT, BYTES '
                        f'FROM "{db}".INFORMATION_SCHEMA.TABLES '
                        f"WHERE TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA')"
                    )
                    try:
                        cur.execute(sql_tab)
                        cols_t = [c[0] for c in cur.description]
                        for row in cur.fetchall():
                            rec = dict(zip(cols_t, row))
                            rec["database"] = db
                            rec["kind"] = "table"
                            _w(rec, fh)
                            n_tables += 1
                    except Exception as e_tab:
                        logfh.write(f"  TAB_ERR db={db} {type(e_tab).__name__} {str(e_tab)[:200]}\n")
                    fh.flush()
                    logfh.write(f"OK db={db} cols~{n_columns} tabs~{n_tables}\n"); logfh.flush()
                except Exception as exc:
                    n_errors += 1
                    err_rec = {"kind": "error", "database": db,
                                 "error_type": type(exc).__name__,
                                 "error": str(exc)[:600]}
                    _w(err_rec, fh); fh.flush()
                    logfh.write(f"ERR db={db} {type(exc).__name__} {str(exc)[:200]}\n")
                    logfh.flush()
                finally:
                    done += 1
                    with open(PROG_FILE, "w") as pf:
                        pf.write(json.dumps({"done": done, "total": total,
                                              "columns": n_columns, "tables": n_tables,
                                              "errors": n_errors}))
            try:
                cur.close(); conn.close()
            except Exception: pass
        with open(DONE_FILE, "w") as df:
            df.write(json.dumps({"done": done, "total": total,
                                  "columns": n_columns, "tables": n_tables,
                                  "errors": n_errors, "ts": time.time()}))

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    return {"started": True, "out_file": OUT_FILE, "done_file": DONE_FILE,
             "progress_file": PROG_FILE, "log_file": LOG_FILE}
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--poll-every', type=int, default=30)
    args = ap.parse_args()

    if not SNOW_DB_LIST.is_file():
        print('ERR: Snow DB list missing; run audit first'); return 2
    db_list = json.loads(SNOW_DB_LIST.read_text(encoding='utf-8'))
    print(f'Snow DB list: {len(db_list)} databases')

    starter = (HARVEST_TEMPLATE + "\n"
               f"_dbs = {json.dumps(db_list)}\n"
               "result = harvest_snow_live_v18(_dbs, 'v18')\n"
               "import json as _j\nprint('===STARTED===');print(_j.dumps(result));print('===STARTED_END===')\n")
    print('Starting Snow harvest BG thread...')
    t0 = time.time()
    r = bridge_exec(starter, timeout=60)
    out = r.get('stdout', '')
    if '===STARTED===' not in out:
        print('NO_START; tail:\n', out[-2000:]); return 2
    started = json.loads(out.split('===STARTED===\n', 1)[1].split('\n===STARTED_END===', 1)[0])
    print(f'  started: {started}')

    poll_code = (
        "import os, json\n"
        "DRV='/content/drive/MyDrive/diploma_plan_sql'\n"
        "PROG=os.path.join(DRV,'outputs','cache','_SNOW_HARVEST_PROGRESS')\n"
        "DONE=os.path.join(DRV,'outputs','cache','_SNOW_HARVEST_DONE')\n"
        "out={'done_marker': os.path.isfile(DONE), 'progress': None}\n"
        "if os.path.isfile(PROG):\n"
        "    out['progress']=json.loads(open(PROG).read())\n"
        "if os.path.isfile(DONE):\n"
        "    out['final']=json.loads(open(DONE).read())\n"
        "print('===STATUS==='); print(json.dumps(out)); print('===STATUS_END===')\n"
    )
    last = None
    for poll_i in range(180):
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

    pull_code = (
        "import base64, os, json\n"
        "DRV='/content/drive/MyDrive/diploma_plan_sql'\n"
        "F=os.path.join(DRV,'outputs','cache','spider2_snow_live_catalog_v18.jsonl')\n"
        "L=os.path.join(DRV,'outputs','cache','spider2_snow_live_catalog_v18.log')\n"
        "with open(F,'rb') as fh: data=base64.b64encode(fh.read()).decode()\n"
        "log=open(L).read() if os.path.isfile(L) else ''\n"
        "out={'data':data,'log':log,'size':os.path.getsize(F)}\n"
        "print('===PULL==='); print(json.dumps(out)); print('===PULL_END===')\n"
    )
    r3 = bridge_exec(pull_code, timeout=120)
    out3 = r3.get('stdout', '')
    p = json.loads(out3.split('===PULL===\n', 1)[1].split('\n===PULL_END===', 1)[0])
    LOCAL_OUT.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_OUT.write_bytes(base64.b64decode(p['data']))
    LOCAL_LOG.write_text(p['log'], encoding='utf-8')
    print(f'pulled {p["size"]} bytes -> {LOCAL_OUT.relative_to(REPO).as_posix()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
