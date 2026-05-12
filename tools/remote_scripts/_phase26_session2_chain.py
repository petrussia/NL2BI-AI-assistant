"""Phase 26 — session 2 chain daemon.

Stages:
  1. Wait for DBT_DONE_v26 marker on Drive (DBT FULL 68 runs locally,
     calling session 2 bridge for inference; local writes marker on done).
  2. Spider1 dev sample 300.
  3. BIRD mini-dev 250.

Requires planner+emitter loaded via _phase26_session_prep.
"""
import os, sys, json, time, traceback, threading, gc
from pathlib import Path
from collections import Counter

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
RUNTIME = DRV / 'outputs/runtime/phase26_session2'
RUNTIME.mkdir(parents=True, exist_ok=True)
LOG = RUNTIME / 'chain.log'
STATE = RUNTIME / 'state.json'

EVAL = DRV / 'repo/src/evaluation'
if str(EVAL) not in sys.path: sys.path.insert(0, str(EVAL))


def _log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line, flush=True)
    with LOG.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def _set_state(d):
    STATE.write_text(json.dumps(d, default=str))


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
    import re
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


def _wait_marker(path: Path, label: str, poll_s: int = 60, timeout_s: int = 86400):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if path.is_file(): return True
        time.sleep(poll_s)
    _log(f'{label} TIMEOUT')
    return False


def _ensure_spider1():
    """Download Spider1 if missing."""
    SPIDER_DIR = DRV / 'data/spider'
    if (SPIDER_DIR / 'dev.json').is_file() and (SPIDER_DIR / 'tables.json').is_file():
        return True
    _log('Spider1 data missing; downloading...')
    import subprocess
    SPIDER_DIR.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'gdown'], check=True)
        tmp = DRV / '.tmp/spider_download'
        tmp.mkdir(parents=True, exist_ok=True)
        zip_path = tmp / 'spider.zip'
        if zip_path.exists(): zip_path.unlink()
        subprocess.run([sys.executable, '-m', 'gdown', '--fuzzy',
                          'https://drive.google.com/uc?id=1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J',
                          '-O', str(zip_path)], check=True)
        import zipfile, shutil
        ex = tmp / 'extract'
        if ex.exists(): shutil.rmtree(ex)
        ex.mkdir(parents=True)
        with zipfile.ZipFile(zip_path) as zf: zf.extractall(ex)
        all_p = list(ex.rglob('*'))
        for fn in ['dev.json', 'tables.json', 'train_spider.json', 'train_others.json']:
            ms = [p for p in all_p if p.is_file() and p.name == fn]
            if ms: shutil.copy2(ms[0], SPIDER_DIR / fn)
        db_src = next((p for p in all_p if p.is_dir() and p.name == 'database' and list(p.rglob('*.sqlite'))), None)
        if db_src and not (SPIDER_DIR / 'database').is_dir():
            shutil.copytree(db_src, SPIDER_DIR / 'database')
        _log(f'Spider1 download done: dev.json exists={ (SPIDER_DIR/"dev.json").is_file()}')
        return (SPIDER_DIR / 'dev.json').is_file()
    except Exception as e:
        _log(f'Spider1 download FAILED: {type(e).__name__}: {e}')
        return False


def _ensure_bird_mini():
    """Use existing 30-task subset OR download mini-dev."""
    BIRD = DRV / 'external_benchmarks/bird_mini_dev'
    candidates = [
        BIRD / 'processed/minidev_250.json',
        BIRD / 'processed/mini_dev.json',
        BIRD / 'processed/bird_minidev_30_diverse.json',
    ]
    for c in candidates:
        if c.is_file(): return c
    return None


def _run_spider1_300(out_dir):
    SPIDER_DIR = DRV / 'data/spider'
    if not _ensure_spider1():
        _log('Spider1 SKIP no data')
        (out_dir / '_FAILED').write_text(json.dumps({'reason': 'no_data'}))
        return

    import sqlite3
    with open(SPIDER_DIR / 'dev.json', encoding='utf-8') as f: dev = json.load(f)
    with open(SPIDER_DIR / 'tables.json', encoding='utf-8') as f: tables = json.load(f)
    db_to_schema = {t['db_id']: t for t in tables}
    tasks = dev[:300]

    def schema_text(db_id):
        s = db_to_schema.get(db_id)
        if not s: return ''
        tn = s['table_names_original']
        lines = []
        for col in s['column_names_original'][1:]:
            ti, cn = col
            if 0 <= ti < len(tn): lines.append(f'  {tn[ti]}.{cn}')
        return f'Tables: {tn}\nColumns:\n' + '\n'.join(lines[:200])

    (out_dir / '_STARTED').write_text(json.dumps({'phase': 26, 'ts': time.time()}))
    pp = out_dir / 'predictions.jsonl'
    tp = out_dir / 'traces.jsonl'
    pf = open(pp, 'w', encoding='utf-8')
    tf = open(tp, 'w', encoding='utf-8')
    err = Counter(); n=0; n_parse=0; n_exec=0; n_match=0
    t0 = time.time()
    for task in tasks:
        n += 1
        db_id = task['db_id']; q = task['question']
        gold = task.get('query', '')
        tid = f'{db_id}__{n:04d}'
        trace = {'instance_id': tid, 'db_id': db_id}
        try:
            sch = schema_text(db_id)
            prompt = (f'You are a SQL expert. Write one SQLite query.\nSchema:\n{sch}\n\nQuestion: {q}\n'
                       'Return only SQL inside ```sql ... ``` block.')
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
                        con = sqlite3.connect(str(db_path), timeout=10)
                        con.cursor().execute(sql).fetchmany(10)
                        con.close()
                        ex_ok = True; ex_class = 'ok'
                    except Exception as e:
                        ex_class = type(e).__name__
                else:
                    ex_class = 'no_db'
            if ex_ok: n_exec += 1
            match = sql.strip().lower() == gold.strip().lower() if gold else False
            if match: n_match += 1
            err_class = 'ok' if ex_ok else ('parse_error' if not pa_ok else ex_class)
            err[err_class] += 1
            pf.write(json.dumps({
                'instance_id': tid, 'db_id': db_id, 'sql': sql,
                'gold_sql': gold, 'parse_ok': pa_ok, 'execute_ok': ex_ok,
                'execute_class': ex_class, 'exact_match_gold': match,
            }) + '\n'); pf.flush()
            trace.update({'parse_ok': pa_ok, 'execute_ok': ex_ok, 'exact_match': match})
        except Exception as e:
            err[type(e).__name__] += 1
            pf.write(json.dumps({'instance_id': tid, 'sql': '', 'error': type(e).__name__}) + '\n'); pf.flush()
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
                'exact_match_gold': n_match,
                'err_top': err.most_common(8),
                'wall_sec': round(time.time()-t0,1),
                'last_task': tid,
            }, default=str))
    pf.close(); tf.close()
    with open(out_dir / 'metrics.csv', 'w') as f:
        f.write('metric,value\n')
        f.write(f'n,{n}\nparse_ok,{n_parse}\nexecute_ok,{n_exec}\nexact_match_gold,{n_match}\n')
    with open(out_dir / 'error_taxonomy.csv', 'w') as f:
        f.write('error_class,count\n')
        for k, v in err.most_common(): f.write(f'{k},{v}\n')
    (out_dir / '_DONE').write_text(json.dumps({
        'n_total': n, 'parse_ok': n_parse, 'execute_ok': n_exec,
        'exact_match_gold': n_match, 'wall_sec': round(time.time()-t0,1), 'ts': time.time()}))
    _log(f'Spider1 DONE n={n} parse={n_parse} exec={n_exec} match={n_match}')


def _run_bird_250(out_dir):
    bird_path = _ensure_bird_mini()
    if not bird_path:
        _log('BIRD SKIP no data')
        (out_dir / '_FAILED').write_text(json.dumps({'reason': 'no_data'}))
        return
    with open(bird_path, encoding='utf-8') as f:
        all_tasks = json.load(f)
    tasks = all_tasks[:250]
    _log(f'BIRD source={bird_path.name} n={len(tasks)}')

    import sqlite3
    BIRD = DRV / 'external_benchmarks/bird_mini_dev'
    (out_dir / '_STARTED').write_text(json.dumps({'phase': 26, 'ts': time.time()}))
    pp = out_dir / 'predictions.jsonl'
    tp = out_dir / 'traces.jsonl'
    pf = open(pp, 'w', encoding='utf-8')
    tf = open(tp, 'w', encoding='utf-8')
    err = Counter(); n=0; n_parse=0; n_exec=0
    t0 = time.time()
    for task in tasks:
        n += 1
        db_id = task.get('db_id') or task.get('database_name') or ''
        q = task.get('question') or task.get('text') or ''
        gold = task.get('SQL') or task.get('gold_sql') or task.get('query') or ''
        tid = f'{db_id}__{n:04d}'
        trace = {'instance_id': tid, 'db_id': db_id}
        try:
            sch = task.get('schema') or task.get('schema_text') or ''
            prompt = (f'You are a SQL expert. Write one SQLite query.\nSchema:\n{sch}\n\nQuestion: {q}\n'
                       'Return only SQL inside ```sql ... ``` block.')
            sql = _extract_sql(_gen(prompt, max_new=400))
            try:
                import sqlglot
                pa_ok = sqlglot.parse_one(sql, read='sqlite') is not None
            except Exception: pa_ok = False
            if pa_ok: n_parse += 1
            ex_ok, ex_class = False, 'parse_error'
            if pa_ok:
                db_path = None
                for hint in [BIRD / 'databases' / db_id / f'{db_id}.sqlite',
                                BIRD / 'database' / db_id / f'{db_id}.sqlite']:
                    if hint.is_file(): db_path = hint; break
                if db_path:
                    try:
                        con = sqlite3.connect(str(db_path), timeout=10)
                        con.cursor().execute(sql).fetchmany(10)
                        con.close()
                        ex_ok = True; ex_class = 'ok'
                    except Exception as e:
                        ex_class = type(e).__name__
                else: ex_class = 'no_db'
            if ex_ok: n_exec += 1
            err_class = 'ok' if ex_ok else ('parse_error' if not pa_ok else ex_class)
            err[err_class] += 1
            pf.write(json.dumps({
                'instance_id': tid, 'db_id': db_id, 'sql': sql,
                'gold_sql': gold, 'parse_ok': pa_ok, 'execute_ok': ex_ok,
                'execute_class': ex_class,
            }) + '\n'); pf.flush()
            trace.update({'parse_ok': pa_ok, 'execute_ok': ex_ok})
        except Exception as e:
            err[type(e).__name__] += 1
            pf.write(json.dumps({'instance_id': tid, 'sql': '', 'error': type(e).__name__}) + '\n'); pf.flush()
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
                'wall_sec': round(time.time()-t0,1),
                'last_task': tid,
            }, default=str))
    pf.close(); tf.close()
    with open(out_dir / 'metrics.csv', 'w') as f:
        f.write('metric,value\n')
        f.write(f'n,{n}\nparse_ok,{n_parse}\nexecute_ok,{n_exec}\n')
    with open(out_dir / 'error_taxonomy.csv', 'w') as f:
        f.write('error_class,count\n')
        for k, v in err.most_common(): f.write(f'{k},{v}\n')
    (out_dir / '_DONE').write_text(json.dumps({
        'n_total': n, 'parse_ok': n_parse, 'execute_ok': n_exec,
        'wall_sec': round(time.time()-t0,1), 'ts': time.time()}))
    _log(f'BIRD DONE n={n} parse={n_parse} exec={n_exec}')


def _session2_chain():
    g = globals()
    _log('=== PHASE 26 SESSION 2 CHAIN START ===')
    _set_state({'phase': 'wait_dbt', 'started_at': time.time()})

    # Stage 1: wait for DBT FULL local subprocess to finish + write marker
    dbt_done = RUNTIME / 'DBT_DONE_v26'
    ready_marker = RUNTIME / 'READY_FOR_DBT_v26'
    ready_marker.write_text(json.dumps({'ts': time.time(),
                                              'msg': 'session 2 bridge ready; local should now run DBT FULL 68'}))
    _log('Stage 1: signaled READY_FOR_DBT_v26; waiting for DBT_DONE_v26')
    _wait_marker(dbt_done, 'DBT_DONE_v26', poll_s=60, timeout_s=86400)

    # Stage 2: Spider1 dev sample 300
    _set_state({'phase': 'spider1_running'})
    _log('Stage 2: Spider1 dev 300')
    spider1_dir = DRV / 'outputs/spider1/runs/spider1_dev300_v26'
    spider1_dir.mkdir(parents=True, exist_ok=True)
    try:
        _run_spider1_300(spider1_dir)
    except Exception as e:
        _log(f'Spider1 EXCEPTION: {type(e).__name__}: {e}')
        traceback.print_exc()

    # Stage 3: BIRD mini-dev 250
    _set_state({'phase': 'bird_running'})
    _log('Stage 3: BIRD mini-dev 250')
    bird_dir = DRV / 'outputs/bird/runs/bird_minidev250_v26'
    bird_dir.mkdir(parents=True, exist_ok=True)
    try:
        _run_bird_250(bird_dir)
    except Exception as e:
        _log(f'BIRD EXCEPTION: {type(e).__name__}: {e}')
        traceback.print_exc()

    _set_state({'phase': 'done', 'finished_at': time.time()})
    _log('=== PHASE 26 SESSION 2 CHAIN DONE ===')


if globals().get('_PHASE26_S2_THREAD') and globals()['_PHASE26_S2_THREAD'].is_alive():
    print('PHASE26_S2_ALREADY_RUNNING')
else:
    th = threading.Thread(target=_session2_chain, daemon=True, name='Phase26S2')
    th.start()
    globals()['_PHASE26_S2_THREAD'] = th
    print('PHASE26_S2_STARTED')
