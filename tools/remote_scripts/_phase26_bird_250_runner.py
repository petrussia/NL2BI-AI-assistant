"""Phase 26 — BIRD mini-dev 250 standalone runner (replaces partial 30 run).

Uses minidev_250.json that was just sliced from the official 500-task
mini_dev_sqlite.json. DB files at raw/minidev/minidev/MINIDEV/dev_databases/.
Passes BIRD `evidence` field as external knowledge (BIRD's documented
prompting convention).

Launches as BG thread on session 2 bridge.
"""
import os, sys, json, time, traceback, threading, gc, re, sqlite3
from pathlib import Path
from collections import Counter

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
EVAL = DRV / 'repo/src/evaluation'
if str(EVAL) not in sys.path: sys.path.insert(0, str(EVAL))


def _gen_emit(prompt, max_new=600):
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


def _bird_schema_text(db_path: Path) -> str:
    try:
        con = sqlite3.connect(str(db_path), timeout=15)
        cur = con.cursor()
        cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        rows = cur.fetchall()[:30]
        con.close()
        return '\n\n'.join(f'-- {nm}\n{ddl}' for nm, ddl in rows if ddl)
    except Exception:
        return ''


def _run_bird_250():
    BIRD = DRV / 'external_benchmarks/bird_mini_dev'
    DB_ROOT = BIRD / 'raw/minidev/minidev/MINIDEV/dev_databases'
    src = BIRD / 'processed/minidev_250.json'
    if not src.is_file():
        print('BIRD 250 source not found:', src, flush=True)
        return
    with open(src, encoding='utf-8') as f: tasks = json.load(f)
    print(f'BIRD 250: loaded {len(tasks)} tasks', flush=True)

    out_dir = DRV / 'outputs/bird/runs/bird_minidev250_v26b'
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / '_STARTED').write_text(json.dumps({'phase': 26, 'mode': 'bird250',
                                                       'src': str(src), 'ts': time.time()}))
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
        qid = task.get('question_id', n)
        db_id = task.get('db_id') or ''
        q = task.get('question') or ''
        ek = task.get('evidence') or ''
        gold = task.get('SQL') or ''
        diff = task.get('difficulty') or ''
        tid = f'{db_id}__q{qid}'
        trace = {'instance_id': tid, 'db_id': db_id, 'difficulty': diff}
        try:
            db_path = DB_ROOT / db_id / f'{db_id}.sqlite'
            sch = _bird_schema_text(db_path) if db_path.is_file() else ''
            prompt_parts = [
                'You are a SQL expert. Write a single SQLite SQL query.',
                f'Schema:\n{sch}',
            ]
            if ek: prompt_parts.append(f'Evidence (knowledge to apply):\n{ek}')
            prompt_parts.append(f'Question: {q}')
            prompt_parts.append('Return only SQL inside ```sql ... ``` block.')
            prompt = '\n\n'.join(prompt_parts)
            sql = _extract_sql(_gen_emit(prompt, max_new=500))

            try:
                import sqlglot
                pa_ok = sqlglot.parse_one(sql, read='sqlite') is not None
            except Exception: pa_ok = False
            if pa_ok: n_parse += 1

            ex_ok, ex_class = False, 'parse_error'
            if pa_ok and db_path.is_file():
                try:
                    con = sqlite3.connect(str(db_path), timeout=15)
                    cur = con.cursor()
                    cur.execute(sql)
                    cur.fetchmany(10)
                    con.close()
                    ex_ok = True; ex_class = 'ok'
                except Exception as e:
                    try: con.close()
                    except Exception: pass
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
            trace.update({'parse_ok': pa_ok, 'execute_ok': ex_ok, 'execute_class': ex_class})
        except Exception as e:
            err[type(e).__name__] += 1
            pf.write(json.dumps({'instance_id': tid, 'sql': '',
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
        f.write('metric,value\n')
        f.write(f'n,{n}\nparse_ok,{n_parse}\nexecute_ok,{n_exec}\n')
    with open(error_p, 'w') as f:
        f.write('error_class,count\n')
        for k, v in err.most_common(): f.write(f'{k},{v}\n')
    (out_dir / '_DONE').write_text(json.dumps({
        'n_total': n, 'parse_ok': n_parse, 'execute_ok': n_exec,
        'wall_sec': round(time.time()-t0, 1), 'ts': time.time()}))
    print(f'BIRD 250 DONE: n={n} parse={n_parse} exec={n_exec}', flush=True)


if globals().get('_PHASE26_BIRD250_THREAD') and globals()['_PHASE26_BIRD250_THREAD'].is_alive():
    print('BIRD250 already running')
else:
    th = threading.Thread(target=_run_bird_250, daemon=True, name='Phase26BIRD250')
    th.start()
    globals()['_PHASE26_BIRD250_THREAD'] = th
    print('BIRD250_STARTED')
