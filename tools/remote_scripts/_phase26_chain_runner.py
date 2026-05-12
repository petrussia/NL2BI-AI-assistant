"""Phase 26 — extended chain daemon on bridge kernel.

Picks up after Snow FULL finishes; runs Lite-Snow → Lite-SQLite →
(wait DBT) → Spider1 → BIRD sequentially under shared GPU lock.

DBT runs LOCALLY (subprocess on Windows). The chain writes a
`READY_FOR_DBT` marker on Drive; my local Claude session detects it,
launches DBT FULL 68, and writes `DBT_DONE` marker. The chain then
proceeds to Spider1.

Requires: planner+emitter loaded as `_MDL_PLAN`/`_MDL_EMIT`,
`_phase25_snow_full_runner` Snow EXPLAIN logic in globals.
"""
import os, sys, json, time, traceback, threading, gc
from pathlib import Path

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
RUNTIME = DRV / 'outputs/runtime/phase26_chain'
RUNTIME.mkdir(parents=True, exist_ok=True)
LOG = RUNTIME / 'chain.log'
STATE = RUNTIME / 'state.json'


def _log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line, flush=True)
    with LOG.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def _set_state(d):
    STATE.write_text(json.dumps(d, default=str))


def _wait_marker(path: Path, label: str, poll_s: int = 60, timeout_s: int = 86400):
    """Block until path appears or timeout. Returns True if found."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if path.is_file():
            return True
        time.sleep(poll_s)
    _log(f'{label} TIMEOUT waiting for {path}')
    return False


def _poll_done(run_dir: Path, label: str, poll_s: int = 60, timeout_s: int = 14400):
    """Wait for _DONE in run_dir. Returns True if done. False if _FAILED or timeout."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if (run_dir / '_DONE').is_file():
            _log(f'{label} _DONE detected')
            return True
        if (run_dir / '_FAILED').is_file():
            _log(f'{label} _FAILED detected')
            return False
        time.sleep(poll_s)
    _log(f'{label} TIMEOUT after {timeout_s}s')
    return False


def _phase26_chain():
    g = globals()
    _log('=== PHASE 26 CHAIN START ===')
    _set_state({'phase': 'wait_snow_full', 'started_at': time.time()})

    # Stage 0: wait for current Snow FULL to finish
    snow_dir = DRV / 'outputs/spider2_snow/runs/snow_full_v25'
    _log('STAGE 0: waiting for snow_full_v25 _DONE')
    ok = _poll_done(snow_dir, 'snow_full_v25', poll_s=60, timeout_s=43200)  # 12h max
    if not ok:
        _log('Snow FULL did not finish OK; aborting chain')
        _set_state({'phase': 'failed', 'reason': 'snow_full_v25_not_done'})
        return

    # Stage 1: Lite-Snow 207
    _set_state({'phase': 'lite_snow_running'})
    _log('STAGE 1: launching Lite-Snow 207')
    try:
        # Reuse phase25 snow runner with alias filter to Lite-Snow lane only
        run_id = 'lite_snow_full_v26'
        out_dir = DRV / 'outputs/spider2_lite/runs' / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        # Get Lite-Snow alias set
        LR = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/snowflake'
        snow_set = set(os.listdir(LR)) if LR.is_dir() else set()
        _log(f'  Lite-Snow alias filter: {len(snow_set)} aliases')

        # Reuse Phase 25 Snow runner func (already in globals after previous uploads)
        # but with filter set; we create a wrapper that re-uses _run_snow_diag-style logic.
        # Simpler: call _run_phase26_snow_lane directly (defined below).
        _run_phase26_snow_lane(run_id, out_dir, alias_filter=snow_set,
                                  jsonl_path=DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl',
                                  label='Lite-Snow')
    except Exception as e:
        _log(f'STAGE 1 EXCEPTION: {type(e).__name__}: {e}')
        _set_state({'phase': 'failed', 'reason': f'lite_snow:{type(e).__name__}'})
        return

    # Stage 2: Lite-SQLite 135
    _set_state({'phase': 'lite_sqlite_running'})
    _log('STAGE 2: launching Lite-SQLite 135')
    try:
        run_id = 'lite_sqlite_full_v26'
        out_dir = DRV / 'outputs/spider2_lite/runs' / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        _run_phase26_sqlite_lane(run_id, out_dir, label='Lite-SQLite')
    except Exception as e:
        _log(f'STAGE 2 EXCEPTION: {type(e).__name__}: {e}')

    # Stage 3: Wait for DBT FULL 68 (local subprocess)
    _set_state({'phase': 'wait_dbt'})
    _log('STAGE 3: signaling READY_FOR_DBT and waiting')
    ready_dbt = RUNTIME / 'READY_FOR_DBT_v26'
    ready_dbt.write_text(json.dumps({'ts': time.time()}))
    dbt_done = RUNTIME / 'DBT_DONE_v26'
    ok = _wait_marker(dbt_done, 'DBT_DONE_v26', poll_s=60, timeout_s=43200)
    if ok:
        _log('STAGE 3: DBT_DONE detected, proceeding')

    # Stage 4: Spider1 dev sample 300
    _set_state({'phase': 'spider1_running'})
    _log('STAGE 4: launching Spider1 dev sample 300')
    try:
        run_id = 'spider1_dev300_v26'
        out_dir = DRV / 'outputs/spider1/runs' / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        _run_phase26_spider1_lane(run_id, out_dir, sample_size=300, label='Spider1-dev300')
    except Exception as e:
        _log(f'STAGE 4 EXCEPTION: {type(e).__name__}: {e}')

    # Stage 5: BIRD mini-dev 250
    _set_state({'phase': 'bird_running'})
    _log('STAGE 5: launching BIRD mini-dev 250')
    try:
        run_id = 'bird_minidev250_v26'
        out_dir = DRV / 'outputs/bird/runs' / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        _run_phase26_bird_lane(run_id, out_dir, sample_size=250, label='BIRD-minidev250')
    except Exception as e:
        _log(f'STAGE 5 EXCEPTION: {type(e).__name__}: {e}')

    _set_state({'phase': 'done', 'finished_at': time.time()})
    _log('=== PHASE 26 CHAIN DONE ===')


# ---- Stage runners ----

def _run_phase26_snow_lane(run_id, out_dir, alias_filter, jsonl_path, label):
    """Run Snow runner with alias filter (subset of Spider2-Snow stack)."""
    sys.path.insert(0, str(DRV / 'repo/src/evaluation'))
    import schema_linking_v18 as sl
    import schema_pack_builder_v18 as sb
    from collections import Counter
    g = globals()

    snow_explain = g.get('_snow_explain')
    snow_schema_valid = g.get('_snow_schema_valid')
    snow_parse_ok = g.get('_snow_parse_ok')
    snow_direct_prompt = g.get('_snow_direct_prompt')
    extract_sql = g.get('_extract_sql')
    v18_plan_snow = g.get('_v18_plan_snow')
    gen_emitter = g.get('_gen_emitter')
    if not all([snow_explain, snow_schema_valid, snow_parse_ok,
                  snow_direct_prompt, extract_sql, v18_plan_snow, gen_emitter]):
        raise RuntimeError('Phase 25 Snow runner functions not in globals; '
                              'upload _phase25_snow_full_runner first.')

    started_p = out_dir / '_STARTED'
    started_p.write_text(json.dumps({'run_id': run_id, 'phase': 26, 'ts': time.time()}))
    preds_p = out_dir / 'predictions.jsonl'
    traces_p = out_dir / 'traces.jsonl'
    progress_p = out_dir / 'progress.json'
    metrics_p = out_dir / 'metrics.csv'
    error_p = out_dir / 'error_taxonomy.csv'

    catalog_cols = sl.load_catalog_jsonl(DRV / 'outputs/cache/spider2_snow_live_catalog_v18.jsonl', 'snow')
    linker = sl.SchemaLinker(catalog_cols)

    tasks = []
    with open(jsonl_path, encoding='utf-8') as fh:
        for ln in fh:
            if not ln.strip(): continue
            t = json.loads(ln)
            alias = t.get('db') or t.get('db_id') or ''
            if alias in alias_filter:
                tasks.append(t)
    _log(f'  {label}: {len(tasks)} tasks selected')

    err = Counter()
    n_total = 0; n_plan_ok = 0; n_sv = 0; n_parse = 0; n_exec = 0
    t_start = time.time()

    preds_fh = open(preds_p, 'w', encoding='utf-8')
    traces_fh = open(traces_p, 'w', encoding='utf-8')

    for task in tasks:
        n_total += 1
        tid = task.get('instance_id') or task.get('id') or f't{n_total}'
        alias = task.get('db') or task.get('db_id') or ''
        question = task.get('question') or task.get('instruction') or ''
        ek = task.get('external_knowledge') or ''
        trace = {'instance_id': tid, 'alias': alias}
        try:
            link = linker.query(question, alias_filter=alias, top_columns=80, top_tables=20)
            pack = sb.build_pack(link, lane='snow', alias=alias, max_tables=8,
                                    max_cols_per_table=22, all_catalog_cols=catalog_cols)
            top_t = pack['tables'][0] if pack['tables'] else None

            plan_prompt = sb.pack_to_planner_prompt(pack, question, external_knowledge=ek)
            pr = v18_plan_snow(plan_prompt, pack)
            if pr.get('validation') and getattr(pr['validation'], 'ok', False): n_plan_ok += 1

            prompt = snow_direct_prompt(question, pack, ek)
            sql_raw = gen_emitter(prompt, max_new=900)
            sql = extract_sql(sql_raw)
            sv_ok, _ = snow_schema_valid(sql, pack)
            pa_ok, _ = snow_parse_ok(sql)
            if sv_ok: n_sv += 1
            if pa_ok: n_parse += 1
            if pa_ok:
                ex_ok, ex_class, ex_msg = snow_explain(sql,
                                                              db=top_t['db'] if top_t else None,
                                                              schema=top_t['schema'] if top_t else None)
            else:
                ex_ok, ex_class, ex_msg = False, 'parse_error', ''
            if ex_ok: n_exec += 1
            err_class = 'ok' if (sv_ok and pa_ok and ex_ok) else (
                'parse_error' if not pa_ok else
                ('schema_invalid' if not sv_ok else ex_class))
            err[err_class] += 1

            preds_fh.write(json.dumps({
                'instance_id': tid, 'sql': sql, 'lane': 'snow',
                'schema_valid': sv_ok, 'parse_ok': pa_ok, 'explain_ok': ex_ok,
                'explain_class': ex_class,
            }, default=str) + '\n'); preds_fh.flush()
            trace.update({'schema_valid': sv_ok, 'parse_ok': pa_ok, 'explain_ok': ex_ok,
                            'explain_class': ex_class})
        except Exception as e:
            trace['error_type'] = type(e).__name__
            trace['error'] = str(e)[:300]
            err[trace['error_type']] += 1
            preds_fh.write(json.dumps({'instance_id': tid, 'sql': '', 'lane': 'snow',
                                          'error': trace['error_type']}) + '\n'); preds_fh.flush()
        traces_fh.write(json.dumps(trace, default=str) + '\n'); traces_fh.flush()

        if (n_total % 5) == 0:
            try:
                import torch; gc.collect(); torch.cuda.empty_cache()
            except Exception: pass

        with open(progress_p, 'w') as f:
            f.write(json.dumps({'n_total': n_total, 'n_target': len(tasks),
                                  'plan_ok': n_plan_ok, 'schema_valid': n_sv,
                                  'parse_ok': n_parse, 'execute_ok': n_exec,
                                  'err_top': err.most_common(8),
                                  'wall_sec': round(time.time() - t_start, 1),
                                  'last_task': tid}, default=str))

    preds_fh.close(); traces_fh.close()

    with open(metrics_p, 'w') as f:
        f.write('metric,value\n')
        f.write(f'n,{n_total}\nplan_validation_ok,{n_plan_ok}\nchosen_schema_valid,{n_sv}\nparse_ok,{n_parse}\nexecute_ok,{n_exec}\n')
    with open(error_p, 'w') as f:
        f.write('error_class,count\n')
        for k, v in err.most_common(): f.write(f'{k},{v}\n')

    (out_dir / '_DONE').write_text(json.dumps({
        'n_total': n_total, 'plan_ok': n_plan_ok, 'schema_valid': n_sv,
        'parse_ok': n_parse, 'execute_ok': n_exec,
        'wall_sec': round(time.time() - t_start, 1), 'ts': time.time()}))
    _log(f'  {label}: DONE n={n_total} sv={n_sv} ex={n_exec}')


def _run_phase26_sqlite_lane(run_id, out_dir, label):
    """Spider2-Lite SQLite lane (135 tasks). Uses sqlite3 stdlib for execute_ok."""
    sys.path.insert(0, str(DRV / 'repo/src/evaluation'))
    import schema_linking_v18 as sl
    import schema_pack_builder_v18 as sb
    import sqlite3, re
    from collections import Counter
    g = globals()

    _extract_sql = g.get('_extract_sql')
    _gen_emitter = g.get('_gen_emitter')
    if not _extract_sql or not _gen_emitter:
        raise RuntimeError('extract_sql/gen_emitter missing from globals')

    LITE_JSONL = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl'
    LR = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/sqlite'
    sqlite_set = set(os.listdir(LR)) if LR.is_dir() else set()

    started_p = out_dir / '_STARTED'
    started_p.write_text(json.dumps({'run_id': run_id, 'phase': 26, 'ts': time.time()}))
    preds_p = out_dir / 'predictions.jsonl'
    traces_p = out_dir / 'traces.jsonl'
    progress_p = out_dir / 'progress.json'
    metrics_p = out_dir / 'metrics.csv'
    error_p = out_dir / 'error_taxonomy.csv'

    tasks = []
    with open(LITE_JSONL, encoding='utf-8') as fh:
        for ln in fh:
            if not ln.strip(): continue
            t = json.loads(ln)
            alias = t.get('db') or t.get('db_id') or ''
            if alias in sqlite_set or alias in {'sqlite-sakila', 'Db-IMDB'}:
                tasks.append(t)
    _log(f'  {label}: {len(tasks)} tasks selected')

    def _build_schema_text(alias):
        # Find SQLite DB file
        db_dir = LR / alias
        if not db_dir.is_dir():
            # fallback: search local sqlite-sakila / Db-IMDB
            return ''
        sqlite_files = list(db_dir.glob('*.sqlite')) + list(db_dir.glob('*.db'))
        if not sqlite_files:
            return ''
        try:
            con = sqlite3.connect(str(sqlite_files[0]))
            cur = con.cursor()
            cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            schemas = []
            for nm, ddl in cur.fetchall()[:30]:
                schemas.append(f'-- {nm}\n{ddl}')
            con.close()
            return '\n\n'.join(schemas)
        except Exception:
            return ''

    def _direct_prompt(q, schema, ek=''):
        ek_block = f'\n\nExternal knowledge:\n{ek}' if ek else ''
        return ('You are a SQL expert. Write a single SQLite SQL query.\n'
                  f'Use ONLY tables/columns from the schema below.\n\n'
                  f'Schema:\n{schema}{ek_block}\n\n'
                  f'Question: {q}\n\nReturn only SQL inside ```sql ... ``` block.')

    def _execute_sqlite(sql, alias):
        db_dir = LR / alias
        if not db_dir.is_dir(): return (False, 'no_db', '')
        sqlite_files = list(db_dir.glob('*.sqlite')) + list(db_dir.glob('*.db'))
        if not sqlite_files: return (False, 'no_sqlite_file', '')
        try:
            con = sqlite3.connect(str(sqlite_files[0]))
            cur = con.cursor()
            cur.execute(sql)
            cur.fetchmany(10)  # small fetch to confirm execution
            con.close()
            return (True, 'ok', '')
        except Exception as e:
            try: con.close()
            except Exception: pass
            return (False, type(e).__name__, str(e)[:300])

    err = Counter()
    n_total = 0; n_parse = 0; n_exec = 0
    t_start = time.time()
    preds_fh = open(preds_p, 'w', encoding='utf-8')
    traces_fh = open(traces_p, 'w', encoding='utf-8')

    for task in tasks:
        n_total += 1
        tid = task.get('instance_id') or task.get('id') or f't{n_total}'
        alias = task.get('db') or task.get('db_id') or ''
        question = task.get('question') or task.get('instruction') or ''
        ek = task.get('external_knowledge') or ''
        trace = {'instance_id': tid, 'alias': alias}
        try:
            schema_text = _build_schema_text(alias)
            prompt = _direct_prompt(question, schema_text, ek)
            sql_raw = _gen_emitter(prompt, max_new=900)
            sql = _extract_sql(sql_raw)
            try:
                import sqlglot
                ast = sqlglot.parse_one(sql, read='sqlite')
                pa_ok = ast is not None
            except Exception:
                pa_ok = False
            if pa_ok: n_parse += 1
            ex_ok, ex_class, ex_msg = _execute_sqlite(sql, alias) if pa_ok else (False, 'parse_error', '')
            if ex_ok: n_exec += 1

            err_class = 'ok' if ex_ok else ('parse_error' if not pa_ok else ex_class)
            err[err_class] += 1
            preds_fh.write(json.dumps({
                'instance_id': tid, 'sql': sql, 'lane': 'sqlite',
                'parse_ok': pa_ok, 'execute_ok': ex_ok, 'execute_class': ex_class,
            }) + '\n'); preds_fh.flush()
            trace.update({'parse_ok': pa_ok, 'execute_ok': ex_ok, 'execute_class': ex_class})
        except Exception as e:
            trace['error_type'] = type(e).__name__
            err[type(e).__name__] += 1
            preds_fh.write(json.dumps({'instance_id': tid, 'sql': '', 'lane': 'sqlite',
                                          'error': type(e).__name__}) + '\n'); preds_fh.flush()
        traces_fh.write(json.dumps(trace, default=str) + '\n'); traces_fh.flush()

        if (n_total % 5) == 0:
            try:
                import torch; gc.collect(); torch.cuda.empty_cache()
            except Exception: pass

        with open(progress_p, 'w') as f:
            f.write(json.dumps({'n_total': n_total, 'n_target': len(tasks),
                                  'parse_ok': n_parse, 'execute_ok': n_exec,
                                  'err_top': err.most_common(8),
                                  'wall_sec': round(time.time() - t_start, 1),
                                  'last_task': tid}, default=str))

    preds_fh.close(); traces_fh.close()
    with open(metrics_p, 'w') as f:
        f.write('metric,value\n')
        f.write(f'n,{n_total}\nparse_ok,{n_parse}\nexecute_ok,{n_exec}\n')
    with open(error_p, 'w') as f:
        f.write('error_class,count\n')
        for k, v in err.most_common(): f.write(f'{k},{v}\n')
    (out_dir / '_DONE').write_text(json.dumps({
        'n_total': n_total, 'parse_ok': n_parse, 'execute_ok': n_exec,
        'wall_sec': round(time.time() - t_start, 1), 'ts': time.time()}))
    _log(f'  {label}: DONE n={n_total} parse={n_parse} exec={n_exec}')


def _run_phase26_spider1_lane(run_id, out_dir, sample_size, label):
    """Spider1 dev sample (first N examples)."""
    sys.path.insert(0, str(DRV / 'repo/src/evaluation'))
    import sqlite3
    from collections import Counter
    g = globals()

    SPIDER_DIR = DRV / 'data/spider'
    if not (SPIDER_DIR / 'dev.json').is_file():
        _log(f'  {label}: data missing, attempting download...')
        try:
            import subprocess
            subprocess.run(['/usr/bin/python', str(DRV / 'tools/remote_scripts/31_restore_drive_spider.py')], check=False)
        except Exception:
            pass
    if not (SPIDER_DIR / 'dev.json').is_file():
        _log(f'  {label}: no Spider1 data; SKIP')
        (out_dir / '_FAILED').write_text(json.dumps({'reason': 'no_data'}))
        return

    with open(SPIDER_DIR / 'dev.json', encoding='utf-8') as f:
        dev = json.load(f)
    tasks = dev[:sample_size]
    _log(f'  {label}: {len(tasks)} tasks selected (of {len(dev)} dev)')

    with open(SPIDER_DIR / 'tables.json', encoding='utf-8') as f:
        tables_data = json.load(f)
    db_to_schema = {t['db_id']: t for t in tables_data}

    def _schema_text(db_id):
        s = db_to_schema.get(db_id)
        if not s: return ''
        lines = []
        tn = s['table_names_original']
        for col in s['column_names_original'][1:]:
            tbl_idx, col_name = col
            t_name = tn[tbl_idx] if 0 <= tbl_idx < len(tn) else '?'
            lines.append(f'  {t_name}.{col_name}')
        return f'Tables: {tn}\nColumns:\n' + '\n'.join(lines[:200])

    def _execute_sqlite(sql, db_id):
        db_path = SPIDER_DIR / 'database' / db_id / f'{db_id}.sqlite'
        if not db_path.is_file(): return (False, 'no_db', '')
        try:
            con = sqlite3.connect(str(db_path))
            cur = con.cursor()
            cur.execute(sql)
            rows = cur.fetchmany(10)
            con.close()
            return (True, 'ok', f'rows={len(rows)}')
        except Exception as e:
            try: con.close()
            except Exception: pass
            return (False, type(e).__name__, str(e)[:300])

    extract_sql = g['_extract_sql']
    gen_emitter = g['_gen_emitter']
    started_p = out_dir / '_STARTED'
    started_p.write_text(json.dumps({'run_id': run_id, 'phase': 26, 'ts': time.time()}))
    preds_p = out_dir / 'predictions.jsonl'
    traces_p = out_dir / 'traces.jsonl'
    progress_p = out_dir / 'progress.json'
    metrics_p = out_dir / 'metrics.csv'
    error_p = out_dir / 'error_taxonomy.csv'
    err = Counter()
    n_total = 0; n_parse = 0; n_exec = 0; n_match_gold = 0
    t_start = time.time()
    preds_fh = open(preds_p, 'w', encoding='utf-8')
    traces_fh = open(traces_p, 'w', encoding='utf-8')

    for task in tasks:
        n_total += 1
        db_id = task['db_id']
        question = task['question']
        gold_sql = task.get('query', '')
        tid = f'{db_id}__{n_total:04d}'
        trace = {'instance_id': tid, 'db_id': db_id}
        try:
            schema = _schema_text(db_id)
            prompt = ('You are a SQL expert. Write a single SQLite SQL query.\n'
                       f'Schema:\n{schema}\n\nQuestion: {question}\n\n'
                       'Return only SQL inside ```sql ... ``` block.')
            sql_raw = gen_emitter(prompt, max_new=600)
            sql = extract_sql(sql_raw)
            try:
                import sqlglot
                ast = sqlglot.parse_one(sql, read='sqlite')
                pa_ok = ast is not None
            except Exception:
                pa_ok = False
            if pa_ok: n_parse += 1
            ex_ok, ex_class, _ = _execute_sqlite(sql, db_id) if pa_ok else (False, 'parse_error', '')
            if ex_ok: n_exec += 1
            # exact-match gold (lower stripped)
            match = sql.strip().lower() == gold_sql.strip().lower() if gold_sql else False
            if match: n_match_gold += 1

            err_class = 'ok' if ex_ok else ('parse_error' if not pa_ok else ex_class)
            err[err_class] += 1
            preds_fh.write(json.dumps({
                'instance_id': tid, 'db_id': db_id, 'sql': sql,
                'gold_sql': gold_sql, 'parse_ok': pa_ok, 'execute_ok': ex_ok,
                'execute_class': ex_class, 'exact_match_gold': match,
            }) + '\n'); preds_fh.flush()
            trace.update({'parse_ok': pa_ok, 'execute_ok': ex_ok, 'exact_match': match})
        except Exception as e:
            err[type(e).__name__] += 1
            preds_fh.write(json.dumps({'instance_id': tid, 'sql': '',
                                          'error': type(e).__name__}) + '\n'); preds_fh.flush()
            trace['error_type'] = type(e).__name__
        traces_fh.write(json.dumps(trace, default=str) + '\n'); traces_fh.flush()

        if (n_total % 5) == 0:
            try:
                import torch; gc.collect(); torch.cuda.empty_cache()
            except Exception: pass

        with open(progress_p, 'w') as f:
            f.write(json.dumps({'n_total': n_total, 'n_target': len(tasks),
                                  'parse_ok': n_parse, 'execute_ok': n_exec,
                                  'exact_match_gold': n_match_gold,
                                  'err_top': err.most_common(8),
                                  'wall_sec': round(time.time() - t_start, 1),
                                  'last_task': tid}, default=str))

    preds_fh.close(); traces_fh.close()
    with open(metrics_p, 'w') as f:
        f.write('metric,value\n')
        f.write(f'n,{n_total}\nparse_ok,{n_parse}\nexecute_ok,{n_exec}\nexact_match_gold,{n_match_gold}\n')
    with open(error_p, 'w') as f:
        f.write('error_class,count\n')
        for k, v in err.most_common(): f.write(f'{k},{v}\n')
    (out_dir / '_DONE').write_text(json.dumps({
        'n_total': n_total, 'parse_ok': n_parse, 'execute_ok': n_exec,
        'exact_match_gold': n_match_gold,
        'wall_sec': round(time.time() - t_start, 1), 'ts': time.time()}))
    _log(f'  {label}: DONE n={n_total} parse={n_parse} exec={n_exec} match_gold={n_match_gold}')


def _run_phase26_bird_lane(run_id, out_dir, sample_size, label):
    """BIRD mini-dev sample. Uses bird_minidev_30 if 250 not available."""
    sys.path.insert(0, str(DRV / 'repo/src/evaluation'))
    import sqlite3
    from collections import Counter
    g = globals()

    BIRD_ROOT = DRV / 'external_benchmarks/bird_mini_dev'
    # Try MINIDEV.json (250) first; fallback to existing 30-task subset
    candidates = [
        BIRD_ROOT / 'processed' / 'minidev_250.json',
        BIRD_ROOT / 'processed' / 'mini_dev.json',
        BIRD_ROOT / 'processed' / 'bird_minidev_30_diverse.json',
    ]
    tasks = []
    src = None
    for c in candidates:
        if c.is_file():
            with open(c, encoding='utf-8') as f:
                tasks = json.load(f)
                src = c
                break
    if not tasks:
        _log(f'  {label}: no BIRD data; SKIP')
        (out_dir / '_FAILED').write_text(json.dumps({'reason': 'no_data'}))
        return
    tasks = tasks[:sample_size]
    _log(f'  {label}: {len(tasks)} tasks from {src.name}')

    extract_sql = g['_extract_sql']
    gen_emitter = g['_gen_emitter']
    started_p = out_dir / '_STARTED'
    started_p.write_text(json.dumps({'run_id': run_id, 'phase': 26, 'ts': time.time()}))
    preds_p = out_dir / 'predictions.jsonl'
    traces_p = out_dir / 'traces.jsonl'
    progress_p = out_dir / 'progress.json'
    metrics_p = out_dir / 'metrics.csv'
    error_p = out_dir / 'error_taxonomy.csv'
    err = Counter()
    n_total = 0; n_parse = 0; n_exec = 0
    t_start = time.time()
    preds_fh = open(preds_p, 'w', encoding='utf-8')
    traces_fh = open(traces_p, 'w', encoding='utf-8')

    for task in tasks:
        n_total += 1
        db_id = task.get('db_id') or task.get('database_name') or ''
        question = task.get('question') or task.get('text') or ''
        gold_sql = task.get('SQL') or task.get('gold_sql') or task.get('query') or ''
        tid = f'{db_id}__{n_total:04d}'
        trace = {'instance_id': tid, 'db_id': db_id}
        try:
            schema = task.get('schema') or task.get('schema_text') or ''
            prompt = ('You are a SQL expert. Write a single SQLite SQL query.\n'
                       f'Schema:\n{schema}\n\nQuestion: {question}\n\n'
                       'Return only SQL inside ```sql ... ``` block.')
            sql_raw = gen_emitter(prompt, max_new=600)
            sql = extract_sql(sql_raw)
            try:
                import sqlglot
                ast = sqlglot.parse_one(sql, read='sqlite')
                pa_ok = ast is not None
            except Exception:
                pa_ok = False
            if pa_ok: n_parse += 1

            # Try execution against BIRD SQLite DB
            db_path = None
            for hint in [BIRD_ROOT / 'databases' / db_id / f'{db_id}.sqlite',
                            BIRD_ROOT / 'database' / db_id / f'{db_id}.sqlite']:
                if hint.is_file():
                    db_path = hint; break
            ex_ok, ex_class = False, 'no_db'
            if db_path and pa_ok:
                try:
                    con = sqlite3.connect(str(db_path))
                    cur = con.cursor()
                    cur.execute(sql)
                    cur.fetchmany(10)
                    con.close()
                    ex_ok, ex_class = True, 'ok'
                except Exception as e:
                    try: con.close()
                    except Exception: pass
                    ex_class = type(e).__name__
            if ex_ok: n_exec += 1
            err_class = 'ok' if ex_ok else ('parse_error' if not pa_ok else ex_class)
            err[err_class] += 1
            preds_fh.write(json.dumps({
                'instance_id': tid, 'db_id': db_id, 'sql': sql,
                'gold_sql': gold_sql, 'parse_ok': pa_ok, 'execute_ok': ex_ok,
                'execute_class': ex_class,
            }) + '\n'); preds_fh.flush()
            trace.update({'parse_ok': pa_ok, 'execute_ok': ex_ok})
        except Exception as e:
            err[type(e).__name__] += 1
            preds_fh.write(json.dumps({'instance_id': tid, 'sql': '',
                                          'error': type(e).__name__}) + '\n'); preds_fh.flush()
            trace['error_type'] = type(e).__name__
        traces_fh.write(json.dumps(trace, default=str) + '\n'); traces_fh.flush()

        if (n_total % 5) == 0:
            try:
                import torch; gc.collect(); torch.cuda.empty_cache()
            except Exception: pass

        with open(progress_p, 'w') as f:
            f.write(json.dumps({'n_total': n_total, 'n_target': len(tasks),
                                  'parse_ok': n_parse, 'execute_ok': n_exec,
                                  'err_top': err.most_common(8),
                                  'wall_sec': round(time.time() - t_start, 1),
                                  'last_task': tid}, default=str))

    preds_fh.close(); traces_fh.close()
    with open(metrics_p, 'w') as f:
        f.write('metric,value\n')
        f.write(f'n,{n_total}\nparse_ok,{n_parse}\nexecute_ok,{n_exec}\n')
    with open(error_p, 'w') as f:
        f.write('error_class,count\n')
        for k, v in err.most_common(): f.write(f'{k},{v}\n')
    (out_dir / '_DONE').write_text(json.dumps({
        'n_total': n_total, 'parse_ok': n_parse, 'execute_ok': n_exec,
        'wall_sec': round(time.time() - t_start, 1), 'ts': time.time()}))
    _log(f'  {label}: DONE n={n_total} parse={n_parse} exec={n_exec}')


# Start daemon
if globals().get('_PHASE26_CHAIN_THREAD') and globals()['_PHASE26_CHAIN_THREAD'].is_alive():
    print('PHASE26_CHAIN_ALREADY_RUNNING')
else:
    th = threading.Thread(target=_phase26_chain, daemon=True, name='Phase26Chain')
    th.start()
    globals()['_PHASE26_CHAIN_THREAD'] = th
    print('PHASE26_CHAIN_STARTED')
