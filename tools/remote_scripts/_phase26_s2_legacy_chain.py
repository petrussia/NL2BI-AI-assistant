"""Phase 26 — S2 long-form legacy chain after DBT FINAL18 done.

Stages:
  0. Wait for DBT_FINAL18_DONE marker (written by local watcher after
     dbt_full_v26_final18_done_local.json appears).
  1. Spider1 FULL dev — all 1034 examples (uses already-downloaded data).
  2. Download full BIRD dev (~1534 examples) if missing.
  3. BIRD FULL dev — 1534 examples.

Uses already-loaded planner+emitter on session 2.
"""
import os, sys, json, time, traceback, threading, gc, re, sqlite3, subprocess
from pathlib import Path
from collections import Counter

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
RUNTIME = DRV / 'outputs/runtime/phase26_s2_legacy'
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


def _set_state(d): STATE.write_text(json.dumps(d, default=str))


def _wait_marker(p, label, poll_s=60, timeout_s=86400):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if p.is_file(): return True
        time.sleep(poll_s)
    _log(f'{label} TIMEOUT')
    return False


def _gen(prompt, max_new=600):
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


def _run_spider1_full(out_dir):
    SPIDER_DIR = DRV / 'data/spider'
    with open(SPIDER_DIR / 'dev.json', encoding='utf-8') as f: dev = json.load(f)
    with open(SPIDER_DIR / 'tables.json', encoding='utf-8') as f: tables = json.load(f)
    db_to_sch = {t['db_id']: t for t in tables}
    tasks = dev  # ALL 1034
    _log(f'Spider1 FULL: {len(tasks)} tasks')

    def schema_text(db_id):
        s = db_to_sch.get(db_id)
        if not s: return ''
        tn = s['table_names_original']
        lines = []
        for col in s['column_names_original'][1:]:
            ti, cn = col
            if 0 <= ti < len(tn): lines.append(f'  {tn[ti]}.{cn}')
        return f'Tables: {tn}\nColumns:\n' + '\n'.join(lines[:200])

    (out_dir / '_STARTED').write_text(json.dumps({'phase': 26, 'mode': 'spider1_full', 'ts': time.time()}))
    pf = open(out_dir / 'predictions.jsonl', 'w', encoding='utf-8')
    tf = open(out_dir / 'traces.jsonl', 'w', encoding='utf-8')
    err = Counter(); n=0; n_parse=0; n_exec=0; n_match=0
    t0 = time.time()
    for task in tasks:
        n += 1
        db_id = task['db_id']; q = task['question']
        gold = task.get('query', '')
        tid = f'{db_id}__{n:05d}'
        trace = {'instance_id': tid, 'db_id': db_id}
        try:
            sch = schema_text(db_id)
            prompt = (f'You are a SQL expert. Write one SQLite query.\nSchema:\n{sch}\n\n'
                       f'Question: {q}\n\nReturn only SQL inside ```sql ... ``` block.')
            sql = _extract_sql(_gen(prompt, max_new=400))
            try:
                import sqlglot
                pa_ok = sqlglot.parse_one(sql, read='sqlite') is not None
            except Exception: pa_ok = False
            if pa_ok: n_parse += 1
            ex_ok, ex_class = False, 'parse_error'
            if pa_ok:
                db_path = SPIDER_DIR / 'database' / db_id / f'{db_id}.sqlite'
                if db_path.is_file():
                    try:
                        con = sqlite3.connect(str(db_path), timeout=15)
                        con.cursor().execute(sql).fetchmany(10)
                        con.close()
                        ex_ok = True; ex_class = 'ok'
                    except Exception as e:
                        ex_class = type(e).__name__
                else: ex_class = 'no_db'
            if ex_ok: n_exec += 1
            match = sql.strip().lower() == gold.strip().lower() if gold else False
            if match: n_match += 1
            err_class = 'ok' if ex_ok else ('parse_error' if not pa_ok else ex_class)
            err[err_class] += 1
            pf.write(json.dumps({
                'instance_id': tid, 'db_id': db_id, 'sql': sql, 'gold_sql': gold,
                'parse_ok': pa_ok, 'execute_ok': ex_ok, 'execute_class': ex_class,
                'exact_match_gold': match,
            }) + '\n'); pf.flush()
            trace.update({'parse_ok': pa_ok, 'execute_ok': ex_ok})
        except Exception as e:
            err[type(e).__name__] += 1
            pf.write(json.dumps({'instance_id': tid, 'sql': '', 'error': type(e).__name__}) + '\n'); pf.flush()
            trace['error_type'] = type(e).__name__
        tf.write(json.dumps(trace, default=str) + '\n'); tf.flush()
        if n % 20 == 0:
            try:
                import torch; gc.collect(); torch.cuda.empty_cache()
            except Exception: pass
        with open(out_dir / 'progress.json', 'w') as f:
            f.write(json.dumps({
                'n_total': n, 'n_target': len(tasks),
                'parse_ok': n_parse, 'execute_ok': n_exec, 'exact_match_gold': n_match,
                'err_top': err.most_common(8), 'wall_sec': round(time.time()-t0,1),
                'last_task': tid,
            }, default=str))
    pf.close(); tf.close()
    with open(out_dir / 'metrics.csv', 'w') as f:
        f.write(f'metric,value\nn,{n}\nparse_ok,{n_parse}\nexecute_ok,{n_exec}\nexact_match_gold,{n_match}\n')
    with open(out_dir / 'error_taxonomy.csv', 'w') as f:
        f.write('error_class,count\n')
        for k, v in err.most_common(): f.write(f'{k},{v}\n')
    (out_dir / '_DONE').write_text(json.dumps({
        'n_total': n, 'parse_ok': n_parse, 'execute_ok': n_exec,
        'exact_match_gold': n_match, 'wall_sec': round(time.time()-t0,1), 'ts': time.time()}))
    _log(f'Spider1 FULL DONE n={n} parse={n_parse} exec={n_exec} match={n_match}')


def _ensure_bird_dev():
    """Download full BIRD dev (~1534 tasks) if not present."""
    BIRD = DRV / 'external_benchmarks/bird_mini_dev'
    full_json = BIRD / 'raw/dev_20230702/dev.json'
    if full_json.is_file():
        _log(f'BIRD full dev already present at {full_json}')
        return full_json
    _log('BIRD full dev missing; attempting download...')
    raw = BIRD / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    zip_path = raw / 'dev.zip'
    try:
        if not zip_path.is_file() or zip_path.stat().st_size < 100_000:
            url = 'https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip'
            _log(f'Downloading {url}')
            subprocess.run(['curl', '-fL', '-o', str(zip_path), url], check=True, timeout=1800)
        import zipfile
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(raw)
        # Find dev.json
        for p in raw.rglob('dev.json'):
            if 'sqlite' not in p.parts and 'minidev' not in p.parts:
                return p
    except Exception as e:
        _log(f'BIRD download FAILED: {type(e).__name__}: {e}')
    return None


def _run_bird_full(out_dir):
    src = _ensure_bird_dev()
    if not src:
        _log('BIRD full data missing; SKIP')
        (out_dir / '_FAILED').write_text(json.dumps({'reason': 'no_data'}))
        return
    with open(src, encoding='utf-8') as f: tasks = json.load(f)
    _log(f'BIRD FULL dev: {len(tasks)} tasks from {src}')

    # DB root
    BIRD = src.parent
    DB_ROOT = BIRD / 'dev_databases'
    if not DB_ROOT.is_dir():
        for cand in BIRD.rglob('dev_databases'):
            if cand.is_dir(): DB_ROOT = cand; break

    def sch_text(db_id):
        db_path = DB_ROOT / db_id / f'{db_id}.sqlite'
        if not db_path.is_file(): return '', None
        try:
            con = sqlite3.connect(str(db_path), timeout=15)
            cur = con.cursor()
            cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            rows = cur.fetchall()[:30]
            con.close()
            return '\n\n'.join(f'-- {nm}\n{ddl}' for nm, ddl in rows if ddl), db_path
        except Exception:
            return '', db_path if db_path.is_file() else None

    (out_dir / '_STARTED').write_text(json.dumps({'phase': 26, 'mode': 'bird_full',
                                                       'src': str(src), 'db_root': str(DB_ROOT),
                                                       'ts': time.time()}))
    pf = open(out_dir / 'predictions.jsonl', 'w', encoding='utf-8')
    tf = open(out_dir / 'traces.jsonl', 'w', encoding='utf-8')
    err = Counter(); n=0; n_parse=0; n_exec=0
    t0 = time.time()
    for task in tasks:
        n += 1
        qid = task.get('question_id', n)
        db_id = task.get('db_id') or ''
        q = task.get('question') or ''
        ek = task.get('evidence') or ''
        gold = task.get('SQL') or task.get('gold_sql') or task.get('query') or ''
        diff = task.get('difficulty') or ''
        tid = f'{db_id}__q{qid:05d}'
        trace = {'instance_id': tid, 'db_id': db_id, 'difficulty': diff}
        try:
            sch, db_path = sch_text(db_id)
            parts = ['You are a SQL expert. Write a single SQLite SQL query.',
                       f'Schema:\n{sch}']
            if ek: parts.append(f'Evidence (knowledge to apply):\n{ek}')
            parts.append(f'Question: {q}')
            parts.append('Return only SQL inside ```sql ... ``` block.')
            sql = _extract_sql(_gen('\n\n'.join(parts), max_new=500))
            try:
                import sqlglot
                pa_ok = sqlglot.parse_one(sql, read='sqlite') is not None
            except Exception: pa_ok = False
            if pa_ok: n_parse += 1
            ex_ok, ex_class = False, 'parse_error'
            if pa_ok and db_path:
                try:
                    con = sqlite3.connect(str(db_path), timeout=15)
                    con.cursor().execute(sql).fetchmany(10)
                    con.close()
                    ex_ok = True; ex_class = 'ok'
                except Exception as e:
                    ex_class = type(e).__name__
            elif pa_ok:
                ex_class = 'no_db'
            if ex_ok: n_exec += 1
            err_class = 'ok' if ex_ok else ('parse_error' if not pa_ok else ex_class)
            err[err_class] += 1
            pf.write(json.dumps({
                'instance_id': tid, 'question_id': qid, 'db_id': db_id,
                'difficulty': diff, 'sql': sql, 'gold_sql': gold,
                'parse_ok': pa_ok, 'execute_ok': ex_ok, 'execute_class': ex_class,
                'evidence_chars': len(ek),
            }) + '\n'); pf.flush()
            trace.update({'parse_ok': pa_ok, 'execute_ok': ex_ok})
        except Exception as e:
            err[type(e).__name__] += 1
            pf.write(json.dumps({'instance_id': tid, 'sql': '', 'error': type(e).__name__}) + '\n'); pf.flush()
            trace['error_type'] = type(e).__name__
        tf.write(json.dumps(trace, default=str) + '\n'); tf.flush()
        if n % 20 == 0:
            try:
                import torch; gc.collect(); torch.cuda.empty_cache()
            except Exception: pass
        with open(out_dir / 'progress.json', 'w') as f:
            f.write(json.dumps({
                'n_total': n, 'n_target': len(tasks),
                'parse_ok': n_parse, 'execute_ok': n_exec,
                'err_top': err.most_common(8), 'wall_sec': round(time.time()-t0,1),
                'last_task': tid,
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
    _log(f'BIRD FULL DONE n={n} parse={n_parse} exec={n_exec}')


def _legacy_chain():
    _log('=== PHASE 26 S2 LEGACY CHAIN START ===')
    # Stage 0: wait DBT FINAL18 done marker
    _set_state({'phase': 'wait_dbt_final18'})
    marker = RUNTIME / 'DBT_FINAL18_DONE'
    _log('Stage 0: waiting for DBT_FINAL18_DONE marker')
    _wait_marker(marker, 'DBT_FINAL18_DONE', poll_s=30, timeout_s=14400)

    # Stage 1: Spider1 FULL 1034
    _set_state({'phase': 'spider1_full'})
    _log('Stage 1: Spider1 FULL 1034')
    out1 = DRV / 'outputs/spider1/runs/spider1_full_v26'
    out1.mkdir(parents=True, exist_ok=True)
    try:
        _run_spider1_full(out1)
    except Exception as e:
        _log(f'Spider1 FULL EXCEPTION: {type(e).__name__}: {e}')
        traceback.print_exc()

    # Stage 2: BIRD FULL 1534
    _set_state({'phase': 'bird_full'})
    _log('Stage 2: BIRD FULL 1534')
    out2 = DRV / 'outputs/bird/runs/bird_full_dev_v26'
    out2.mkdir(parents=True, exist_ok=True)
    try:
        _run_bird_full(out2)
    except Exception as e:
        _log(f'BIRD FULL EXCEPTION: {type(e).__name__}: {e}')
        traceback.print_exc()

    _set_state({'phase': 'done', 'ts': time.time()})
    _log('=== PHASE 26 S2 LEGACY CHAIN DONE ===')


if globals().get('_PHASE26_S2_LEGACY_THREAD') and globals()['_PHASE26_S2_LEGACY_THREAD'].is_alive():
    print('PHASE26_S2_LEGACY_ALREADY')
else:
    th = threading.Thread(target=_legacy_chain, daemon=True, name='Phase26S2Legacy')
    th.start()
    globals()['_PHASE26_S2_LEGACY_THREAD'] = th
    print('PHASE26_S2_LEGACY_STARTED')
