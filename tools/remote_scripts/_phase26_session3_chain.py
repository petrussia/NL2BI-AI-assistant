"""Phase 26 — session 3 chain daemon (Lite-Snow → Lite-SQLite).

Stages:
  1. Lite-Snow 207 — Snowflake lane within Spider2-Lite, with EXPLAIN.
  2. Lite-SQLite 135 — SQLite lane via sqlite3 stdlib.

Requires planner+emitter loaded via _phase26_session_prep.
Also requires Snow connector creds in env (SNOWFLAKE_*).
"""
import os, sys, json, time, traceback, threading, gc, re
from pathlib import Path
from collections import Counter

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
RUNTIME = DRV / 'outputs/runtime/phase26_session3'
RUNTIME.mkdir(parents=True, exist_ok=True)
LOG = RUNTIME / 'chain.log'
STATE = RUNTIME / 'state.json'
EVAL = DRV / 'repo/src/evaluation'
if str(EVAL) not in sys.path: sys.path.insert(0, str(EVAL))


def _log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line, flush=True)
    with LOG.open('a', encoding='utf-8') as f: f.write(line + '\n')


def _set_state(d):
    STATE.write_text(json.dumps(d, default=str))


def _gen(prompt, max_new=900):
    g = globals()
    tok = g['_TOK_EMIT']; mdl = g['_MDL_EMIT']; prof = g['_PROF_EMIT']
    import torch
    nt = bool(getattr(prof, 'non_thinking_mode', False))
    msgs = [{'role': 'user', 'content': prompt}]
    extra = {'enable_thinking': False} if nt else {}
    try:
        enc = tok.apply_chat_template(msgs, return_tensors='pt',
                                          add_generation_prompt=True,
                                          return_dict=True, **extra)
    except TypeError:
        enc = tok.apply_chat_template(msgs, return_tensors='pt',
                                          add_generation_prompt=True,
                                          return_dict=True)
    enc = {k: v.to(mdl.device) for k, v in enc.items()}
    with torch.no_grad():
        out = mdl.generate(**enc, max_new_tokens=max_new,
                              do_sample=False, temperature=0.0,
                              pad_token_id=tok.eos_token_id)
    gen = out[0][enc['input_ids'].shape[1]:]
    return tok.decode(gen, skip_special_tokens=True)


def _gen_planner(prompt, max_new=1100):
    g = globals()
    tok = g['_TOK_PLAN']; mdl = g['_MDL_PLAN']; prof = g['_PROF_PLAN']
    import torch
    nt = bool(getattr(prof, 'non_thinking_mode', False))
    msgs = [{'role': 'user', 'content': prompt}]
    extra = {'enable_thinking': False} if nt else {}
    try:
        enc = tok.apply_chat_template(msgs, return_tensors='pt',
                                          add_generation_prompt=True,
                                          return_dict=True, **extra)
    except TypeError:
        enc = tok.apply_chat_template(msgs, return_tensors='pt',
                                          add_generation_prompt=True,
                                          return_dict=True)
    enc = {k: v.to(mdl.device) for k, v in enc.items()}
    with torch.no_grad():
        out = mdl.generate(**enc, max_new_tokens=max_new,
                              do_sample=False, temperature=0.0,
                              pad_token_id=tok.eos_token_id)
    gen = out[0][enc['input_ids'].shape[1]:]
    return tok.decode(gen, skip_special_tokens=True)


def _extract_sql(raw):
    if not raw: return ''
    m = re.search(r'```sql\s*\n?([\s\S]*?)```', raw, re.IGNORECASE)
    if m: return m.group(1).strip()
    m = re.search(r'```\s*\n?([\s\S]*?)```', raw)
    if m:
        cand = m.group(1).strip()
        if any(kw in cand.upper() for kw in ('SELECT', 'WITH')): return cand
    upper = raw.upper()
    for tag in ('WITH ', 'SELECT '):
        idx = upper.find(tag)
        if idx >= 0: return raw[idx:].strip()
    return raw.strip()


# --- Snow EXPLAIN (same as Phase 25 patched) ---
_SNOW_CONN = {}


def _snow_connect():
    if 'main' in _SNOW_CONN:
        try:
            _SNOW_CONN['main'].cursor().execute('SELECT 1').fetchone()
            return _SNOW_CONN['main']
        except Exception:
            del _SNOW_CONN['main']
    import snowflake.connector
    c = snowflake.connector.connect(
        account=os.environ['SNOWFLAKE_ACCOUNT'],
        user=os.environ['SNOWFLAKE_USER'],
        password=os.environ['SNOWFLAKE_PASSWORD'],
        role=os.environ.get('SNOWFLAKE_ROLE') or None,
        warehouse=os.environ.get('SNOWFLAKE_WAREHOUSE') or None,
    )
    _SNOW_CONN['main'] = c
    return c


def _snow_explain(sql, *, db=None, schema=None):
    if not sql: return (False, 'empty_sql', '')
    try:
        c = _snow_connect()
        cur = c.cursor()
        if db:
            try: cur.execute(f'USE DATABASE "{db}"')
            except Exception: pass
        if schema:
            try: cur.execute(f'USE SCHEMA "{schema}"')
            except Exception: pass
    except Exception as e:
        return (False, 'connect_fail', f'{type(e).__name__}: {str(e)[:300]}')
    try:
        cur.execute(f'EXPLAIN {sql}')
        cur.fetchall()
        return (True, 'ok', '')
    except Exception as e:
        em = str(e)[:300]; emL = em.lower()
        if 'invalid identifier' in emL or 'does not exist' in emL: return (False, 'invalid_identifier', em)
        if 'syntax error' in emL: return (False, 'syntax_error', em)
        if 'incompatible' in emL or 'does not match' in emL: return (False, 'type_mismatch', em)
        return (False, type(e).__name__, em)


def _snow_parse_ok(sql):
    try:
        import sqlglot
        return (sqlglot.parse_one(sql, read='snowflake') is not None, '')
    except Exception as e:
        return (False, f'{type(e).__name__}:{str(e)[:200]}')


def _snow_schema_valid(sql, pack):
    try:
        import sqlglot, sqlglot.expressions as E
        ast = sqlglot.parse_one(sql, read='snowflake')
    except Exception as e:
        return (False, f'parse_failed:{type(e).__name__}')
    if ast is None: return (False, 'parse_failed')
    tables_allowed = set(); cols_allowed = set()
    for t in pack.get('tables', []) or []:
        db = (t.get('db') or '').upper(); sch = (t.get('schema') or '').upper(); tab = (t.get('table') or '').upper()
        for tn in {tab, f'{sch}.{tab}', f'{db}.{sch}.{tab}'}:
            if tn: tables_allowed.add(tn.upper())
        for c in t.get('columns', []) or []:
            cn = (c.get('name') or '').upper()
            if cn: cols_allowed.add(cn)
        for cn in t.get('all_columns', []) or []:
            cu = (cn or '').upper()
            if cu: cols_allowed.add(cu)
    aliases = set(); ctes = set()
    for cte in ast.find_all(E.CTE):
        nm = cte.alias_or_name
        if nm: ctes.add(nm.upper())
    for tbl in ast.find_all(E.Table):
        if tbl.alias: aliases.add(tbl.alias.upper())
    unkT, unkC = [], []
    for tbl in ast.find_all(E.Table):
        nm = tbl.name
        if nm and nm.upper() not in tables_allowed and nm.upper() not in ctes:
            full = '.'.join(p.name for p in tbl.parts).upper() if hasattr(tbl, 'parts') else nm.upper()
            if full not in tables_allowed and nm.upper() not in {t.split('.')[-1] for t in tables_allowed}:
                unkT.append(nm)
    for col in ast.find_all(E.Column):
        nm = col.name
        if not nm or nm == '*': continue
        nu = nm.upper()
        if col.table:
            tu = col.table.upper()
            if tu in aliases or tu in ctes: continue
            if tu in {t.split('.')[-1] for t in tables_allowed}: continue
        if nu not in cols_allowed: unkC.append(nm)
    if unkT or unkC:
        return (False, f'unknown_tables={unkT[:6]}, unknown_cols={unkC[:8]}')
    return (True, '')


def _snow_direct_prompt(question, pack, ek=''):
    table_lines = []
    for t in pack.get('tables', []):
        cols = ', '.join(c.get('name', '') for c in t.get('columns', [])[:22])
        fq = f'{t.get("db","")}.{t.get("schema","")}.{t.get("table","")}'
        table_lines.append(f'  {fq}: {cols}')
    schema_block = '\n'.join(table_lines)
    ek_block = f'\n\nExternal knowledge:\n{ek}' if ek else ''
    return ('You are a SQL expert. Write a single Snowflake SQL query.\n'
              'Use ONLY tables/columns from the schema. Snowflake syntax (UPPERCASE_IDENTIFIERS, '
              'three-part names DB.SCHEMA.TABLE).\n\n'
              f'Schema:\n{schema_block}{ek_block}\n\n'
              f'Question: {question}\n\nReturn only SQL inside ```sql ... ``` block.')


def _v18_plan(prompt, pack, max_attempts=2):
    import structured_plan_v18 as sp
    last_plan = None; last_val = None
    cur = prompt
    for attempt in range(1, max_attempts + 1):
        raw = _gen_planner(cur)
        try: cand = sp.parse_plan(raw)
        except Exception: continue
        v = sp.validate_plan(cand, pack)
        last_plan = cand; last_val = v
        if v.ok:
            return {'plan': cand, 'validation': v, 'raw': raw, 'attempts': attempt}
        if attempt < max_attempts:
            cur = sp._retry_prompt(prompt, v.reasons, cand)
    return {'plan': last_plan, 'validation': last_val, 'raw': '', 'attempts': max_attempts}


def _run_lite_snow(out_dir):
    import schema_linking_v18 as sl
    import schema_pack_builder_v18 as sb
    LITE = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl'
    LR = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/snowflake'
    snow_set = set(os.listdir(LR)) if LR.is_dir() else set()
    _log(f'Lite-Snow alias filter: {len(snow_set)}')

    catalog = sl.load_catalog_jsonl(DRV / 'outputs/cache/spider2_snow_live_catalog_v18.jsonl', 'snow')
    linker = sl.SchemaLinker(catalog)

    tasks = []
    with open(LITE, encoding='utf-8') as fh:
        for ln in fh:
            if not ln.strip(): continue
            t = json.loads(ln)
            alias = t.get('db') or t.get('db_id') or ''
            if alias in snow_set: tasks.append(t)
    _log(f'Lite-Snow: {len(tasks)} tasks')

    (out_dir / '_STARTED').write_text(json.dumps({'phase': 26, 'mode': 'lite_snow', 'ts': time.time()}))
    pf = open(out_dir / 'predictions.jsonl', 'w', encoding='utf-8')
    tf = open(out_dir / 'traces.jsonl', 'w', encoding='utf-8')
    err = Counter(); n=0; n_plan=0; n_sv=0; n_parse=0; n_exec=0
    t0 = time.time()
    for task in tasks:
        n += 1
        tid = task.get('instance_id') or f't{n}'
        alias = task.get('db') or task.get('db_id') or ''
        q = task.get('question') or task.get('instruction') or ''
        ek = task.get('external_knowledge') or ''
        trace = {'instance_id': tid, 'alias': alias}
        try:
            link = linker.query(q, alias_filter=alias, top_columns=80, top_tables=20)
            pack = sb.build_pack(link, lane='snow', alias=alias, max_tables=8,
                                    max_cols_per_table=22, all_catalog_cols=catalog)
            top = pack['tables'][0] if pack['tables'] else None
            plan_p = sb.pack_to_planner_prompt(pack, q, external_knowledge=ek)
            pr = _v18_plan(plan_p, pack)
            if pr.get('validation') and getattr(pr['validation'], 'ok', False): n_plan += 1

            prompt = _snow_direct_prompt(q, pack, ek)
            sql = _extract_sql(_gen(prompt, max_new=900))
            sv_ok, _ = _snow_schema_valid(sql, pack)
            pa_ok, _ = _snow_parse_ok(sql)
            if sv_ok: n_sv += 1
            if pa_ok: n_parse += 1
            if pa_ok:
                ex_ok, ex_class, _ = _snow_explain(sql,
                                                          db=top['db'] if top else None,
                                                          schema=top['schema'] if top else None)
            else:
                ex_ok, ex_class = False, 'parse_error'
            if ex_ok: n_exec += 1
            err_class = 'ok' if (sv_ok and pa_ok and ex_ok) else (
                'parse_error' if not pa_ok else
                ('schema_invalid' if not sv_ok else ex_class))
            err[err_class] += 1
            pf.write(json.dumps({
                'instance_id': tid, 'sql': sql, 'lane': 'snow_lite',
                'schema_valid': sv_ok, 'parse_ok': pa_ok, 'explain_ok': ex_ok,
                'explain_class': ex_class,
            }, default=str) + '\n'); pf.flush()
            trace.update({'schema_valid': sv_ok, 'parse_ok': pa_ok, 'explain_ok': ex_ok})
        except Exception as e:
            err[type(e).__name__] += 1
            pf.write(json.dumps({'instance_id': tid, 'sql': '', 'lane': 'snow_lite',
                                      'error': type(e).__name__}) + '\n'); pf.flush()
            trace['error_type'] = type(e).__name__
        tf.write(json.dumps(trace, default=str) + '\n'); tf.flush()
        if n % 5 == 0:
            try:
                import torch; gc.collect(); torch.cuda.empty_cache()
            except Exception: pass
        with open(out_dir / 'progress.json', 'w') as f:
            f.write(json.dumps({
                'n_total': n, 'n_target': len(tasks),
                'plan_ok': n_plan, 'schema_valid': n_sv,
                'parse_ok': n_parse, 'execute_ok': n_exec,
                'err_top': err.most_common(8),
                'wall_sec': round(time.time()-t0, 1), 'last_task': tid,
            }, default=str))
    pf.close(); tf.close()
    with open(out_dir / 'metrics.csv', 'w') as f:
        f.write(f'metric,value\nn,{n}\nplan_validation_ok,{n_plan}\nchosen_schema_valid,{n_sv}\nparse_ok,{n_parse}\nexecute_ok,{n_exec}\n')
    with open(out_dir / 'error_taxonomy.csv', 'w') as f:
        f.write('error_class,count\n')
        for k, v in err.most_common(): f.write(f'{k},{v}\n')
    (out_dir / '_DONE').write_text(json.dumps({
        'n_total': n, 'plan_ok': n_plan, 'schema_valid': n_sv,
        'parse_ok': n_parse, 'execute_ok': n_exec,
        'wall_sec': round(time.time()-t0, 1), 'ts': time.time()}))
    _log(f'Lite-Snow DONE n={n} sv={n_sv} parse={n_parse} exec={n_exec}')


def _run_lite_sqlite(out_dir):
    import sqlite3
    LITE = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl'
    LR = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/sqlite'
    sqlite_set = set(os.listdir(LR)) if LR.is_dir() else set()
    _log(f'Lite-SQLite alias filter: {len(sqlite_set)} + 2 fallback')

    tasks = []
    with open(LITE, encoding='utf-8') as fh:
        for ln in fh:
            if not ln.strip(): continue
            t = json.loads(ln)
            alias = t.get('db') or t.get('db_id') or ''
            if alias in sqlite_set or alias in {'sqlite-sakila', 'Db-IMDB'}:
                tasks.append(t)
    _log(f'Lite-SQLite: {len(tasks)} tasks')

    def sch_text(alias):
        d = LR / alias
        if not d.is_dir(): return ''
        files = list(d.glob('*.sqlite')) + list(d.glob('*.db'))
        if not files: return ''
        try:
            con = sqlite3.connect(str(files[0]), timeout=10)
            cur = con.cursor()
            cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            rows = cur.fetchall()[:30]
            con.close()
            return '\n\n'.join(f'-- {nm}\n{ddl}' for nm, ddl in rows)
        except Exception: return ''

    def exec_sqlite(sql, alias):
        d = LR / alias
        if not d.is_dir(): return (False, 'no_db')
        files = list(d.glob('*.sqlite')) + list(d.glob('*.db'))
        if not files: return (False, 'no_db_file')
        try:
            con = sqlite3.connect(str(files[0]), timeout=10)
            con.cursor().execute(sql).fetchmany(10)
            con.close()
            return (True, 'ok')
        except Exception as e:
            try: con.close()
            except Exception: pass
            return (False, type(e).__name__)

    (out_dir / '_STARTED').write_text(json.dumps({'phase': 26, 'mode': 'lite_sqlite', 'ts': time.time()}))
    pf = open(out_dir / 'predictions.jsonl', 'w', encoding='utf-8')
    tf = open(out_dir / 'traces.jsonl', 'w', encoding='utf-8')
    err = Counter(); n=0; n_parse=0; n_exec=0
    t0 = time.time()
    for task in tasks:
        n += 1
        tid = task.get('instance_id') or f't{n}'
        alias = task.get('db') or task.get('db_id') or ''
        q = task.get('question') or task.get('instruction') or ''
        ek = task.get('external_knowledge') or ''
        trace = {'instance_id': tid, 'alias': alias}
        try:
            sch = sch_text(alias)
            prompt = (f'You are a SQL expert. Write one SQLite query.\n'
                       f'Schema:\n{sch}\n\n')
            if ek: prompt += f'External knowledge:\n{ek}\n\n'
            prompt += f'Question: {q}\n\nReturn only SQL inside ```sql ... ``` block.'
            sql = _extract_sql(_gen(prompt, max_new=600))
            try:
                import sqlglot
                pa_ok = sqlglot.parse_one(sql, read='sqlite') is not None
            except Exception: pa_ok = False
            if pa_ok: n_parse += 1
            ex_ok, ex_class = exec_sqlite(sql, alias) if pa_ok else (False, 'parse_error')
            if ex_ok: n_exec += 1
            err_class = 'ok' if ex_ok else ('parse_error' if not pa_ok else ex_class)
            err[err_class] += 1
            pf.write(json.dumps({
                'instance_id': tid, 'sql': sql, 'lane': 'sqlite',
                'parse_ok': pa_ok, 'execute_ok': ex_ok, 'execute_class': ex_class,
            }) + '\n'); pf.flush()
            trace.update({'parse_ok': pa_ok, 'execute_ok': ex_ok})
        except Exception as e:
            err[type(e).__name__] += 1
            pf.write(json.dumps({'instance_id': tid, 'sql': '', 'lane': 'sqlite',
                                      'error': type(e).__name__}) + '\n'); pf.flush()
            trace['error_type'] = type(e).__name__
        tf.write(json.dumps(trace, default=str) + '\n'); tf.flush()
        if n % 10 == 0:
            try:
                import torch; gc.collect(); torch.cuda.empty_cache()
            except Exception: pass
        with open(out_dir / 'progress.json', 'w') as f:
            f.write(json.dumps({
                'n_total': n, 'n_target': len(tasks),
                'parse_ok': n_parse, 'execute_ok': n_exec,
                'err_top': err.most_common(8),
                'wall_sec': round(time.time()-t0, 1), 'last_task': tid,
            }, default=str))
    pf.close(); tf.close()
    with open(out_dir / 'metrics.csv', 'w') as f:
        f.write(f'metric,value\nn,{n}\nparse_ok,{n_parse}\nexecute_ok,{n_exec}\n')
    with open(out_dir / 'error_taxonomy.csv', 'w') as f:
        f.write('error_class,count\n')
        for k, v in err.most_common(): f.write(f'{k},{v}\n')
    (out_dir / '_DONE').write_text(json.dumps({
        'n_total': n, 'parse_ok': n_parse, 'execute_ok': n_exec,
        'wall_sec': round(time.time()-t0, 1), 'ts': time.time()}))
    _log(f'Lite-SQLite DONE n={n} parse={n_parse} exec={n_exec}')


def _session3_chain():
    _log('=== PHASE 26 SESSION 3 CHAIN START ===')

    # Stage 1: Lite-Snow 207
    _set_state({'phase': 'lite_snow_running'})
    _log('Stage 1: Lite-Snow')
    out_snow = DRV / 'outputs/spider2_lite/runs/lite_snow_full_v26'
    out_snow.mkdir(parents=True, exist_ok=True)
    try:
        _run_lite_snow(out_snow)
    except Exception as e:
        _log(f'Lite-Snow EXCEPTION: {type(e).__name__}: {e}')
        traceback.print_exc()

    # Stage 2: Lite-SQLite 135
    _set_state({'phase': 'lite_sqlite_running'})
    _log('Stage 2: Lite-SQLite')
    out_sql = DRV / 'outputs/spider2_lite/runs/lite_sqlite_full_v26'
    out_sql.mkdir(parents=True, exist_ok=True)
    try:
        _run_lite_sqlite(out_sql)
    except Exception as e:
        _log(f'Lite-SQLite EXCEPTION: {type(e).__name__}: {e}')
        traceback.print_exc()

    _set_state({'phase': 'done', 'finished_at': time.time()})
    _log('=== PHASE 26 SESSION 3 CHAIN DONE ===')


if globals().get('_PHASE26_S3_THREAD') and globals()['_PHASE26_S3_THREAD'].is_alive():
    print('PHASE26_S3_ALREADY_RUNNING')
else:
    th = threading.Thread(target=_session3_chain, daemon=True, name='Phase26S3')
    th.start()
    globals()['_PHASE26_S3_THREAD'] = th
    print('PHASE26_S3_STARTED')
