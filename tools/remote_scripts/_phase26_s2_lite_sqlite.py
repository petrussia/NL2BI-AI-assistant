"""Run Lite-SQLite 135 on S2 bridge in parallel with S3's Lite-Snow.
Uses separate run_id so no Drive conflict.
"""
import os, sys, json, time, traceback, threading, gc, re, sqlite3
from pathlib import Path
from collections import Counter

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
EVAL = DRV / 'repo/src/evaluation'
if str(EVAL) not in sys.path: sys.path.insert(0, str(EVAL))

g = globals()


def _gen(prompt, max_new=600):
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


def _run_sqlite_lane(run_id):
    LITE = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl'
    LR = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/sqlite'
    sqlite_set = set(os.listdir(LR)) if LR.is_dir() else set()
    out_dir = DRV / 'outputs/spider2_lite/runs' / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks = []
    with open(LITE, encoding='utf-8') as fh:
        for ln in fh:
            if not ln.strip(): continue
            t = json.loads(ln)
            alias = t.get('db') or t.get('db_id') or ''
            if alias in sqlite_set or alias in {'sqlite-sakila', 'Db-IMDB'}:
                tasks.append(t)
    print(f'[{run_id}] tasks selected: {len(tasks)}', flush=True)

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

    (out_dir / '_STARTED').write_text(json.dumps({'phase': 26, 'mode': 'lite_sqlite_s2', 'ts': time.time()}))
    pp = out_dir / 'predictions.jsonl'
    tp = out_dir / 'traces.jsonl'
    progress_p = out_dir / 'progress.json'
    metrics_p = out_dir / 'metrics.csv'
    error_p = out_dir / 'error_taxonomy.csv'
    pf = open(pp, 'w', encoding='utf-8')
    tf = open(tp, 'w', encoding='utf-8')
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
            prompt = f'You are a SQL expert. Write one SQLite query.\nSchema:\n{sch}\n\n'
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
            pf.write(json.dumps({'instance_id': tid, 'sql': sql, 'lane': 'sqlite',
                                      'parse_ok': pa_ok, 'execute_ok': ex_ok,
                                      'execute_class': ex_class}) + '\n'); pf.flush()
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
        with open(progress_p, 'w') as f:
            f.write(json.dumps({
                'n_total': n, 'n_target': len(tasks),
                'parse_ok': n_parse, 'execute_ok': n_exec,
                'err_top': err.most_common(8),
                'wall_sec': round(time.time()-t0, 1), 'last_task': tid,
            }, default=str))
    pf.close(); tf.close()
    with open(metrics_p, 'w') as f:
        f.write(f'metric,value\nn,{n}\nparse_ok,{n_parse}\nexecute_ok,{n_exec}\n')
    with open(error_p, 'w') as f:
        f.write('error_class,count\n')
        for k, v in err.most_common(): f.write(f'{k},{v}\n')
    (out_dir / '_DONE').write_text(json.dumps({
        'n_total': n, 'parse_ok': n_parse, 'execute_ok': n_exec,
        'wall_sec': round(time.time()-t0, 1), 'ts': time.time()}))
    print(f'[{run_id}] DONE n={n} parse={n_parse} exec={n_exec}', flush=True)


# Run as BG thread
RUN_ID = 'lite_sqlite_full_v26_s2'
if g.get('_PHASE26_S2_SQLITE_THREAD') and g['_PHASE26_S2_SQLITE_THREAD'].is_alive():
    print('PHASE26_S2_SQLITE_ALREADY')
else:
    th = threading.Thread(target=_run_sqlite_lane, args=(RUN_ID,),
                                  daemon=True, name='Phase26S2SQLite')
    th.start()
    g['_PHASE26_S2_SQLITE_THREAD'] = th
    print(f'PHASE26_S2_SQLITE_STARTED run_id={RUN_ID}')
