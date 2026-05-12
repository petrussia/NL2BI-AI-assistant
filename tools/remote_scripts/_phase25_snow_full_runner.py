"""Phase 25 — Spider2-Snow FULL 547 runner with engine-side EXPLAIN.

Uses the v18 schema-linking + planner + Coder-7B direct-emit pipeline
(no v22 BQ-specific renderer; Snow has no Family A/C in v18). Per-task
flow:
  1. Schema-link question vs Snow live catalog (586,472 cols).
  2. Build pack (lane='snow').
  3. Plan via Qwen3-Coder-30B-A3B-Instruct -> JSON, validate.
  4. Family B Coder-7B direct emit with Snow-dialect prompt.
  5. AST schema_valid against pack (case-insensitive Snow IDs).
  6. parse_ok via sqlglot read='snowflake'.
  7. **Snow EXPLAIN** → execute_ok (compile-only, no warehouse spend
     for actual data fetch).

Strict policy:
  - Acquires the Phase 24 GPU lock before launch.
  - Single BG thread on bridge.
  - Snow connection pooled per-DB to avoid reconnect cost.

Outputs into <DRIVE>/outputs/spider2_snow/runs/<run_id>/.
"""
# This file is uploaded to the bridge eval dir and imported by the launcher.
import os, sys, json, time, traceback, gc, threading, re
from pathlib import Path
from collections import Counter

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
SNOW_JSONL = DRV / 'external_benchmarks/spider2_snow/raw/Spider2/spider2-snow/spider2-snow.jsonl'
SNOW_CATALOG = DRV / 'outputs/cache/spider2_snow_live_catalog_v18.jsonl'
SNOW_RUNS_BASE = DRV / 'outputs/spider2_snow/runs'
EVAL_DIR = DRV / 'repo/src/evaluation'
LOCK_DIR = DRV / 'outputs/runtime'
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))


def _serialize_lock():
    g = globals()
    if g.get('_PHASE25_SNOW_LOCK') is None:
        g['_PHASE25_SNOW_LOCK'] = threading.Lock()
    return g['_PHASE25_SNOW_LOCK']


def _gen(tok, mdl, prof, prompt, max_new):
    LOCK = _serialize_lock()
    with LOCK:
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
    return _gen(g['_TOK_PLAN'], g['_MDL_PLAN'], g['_PROF_PLAN'], prompt, max_new)


def _gen_emitter(prompt, max_new=900):
    g = globals()
    return _gen(g['_TOK_EMIT'], g['_MDL_EMIT'], g['_PROF_EMIT'], prompt, max_new)


def _v18_plan_snow(prompt, pack, max_attempts=2):
    import structured_plan_v18 as sp
    raw = ''
    last_plan = None; last_val = None
    cur_prompt = prompt
    retry_used = False
    for attempt in range(1, max_attempts + 1):
        raw = _gen_planner(cur_prompt)
        try:
            cand = sp.parse_plan(raw)
        except Exception:
            continue
        v = sp.validate_plan(cand, pack)
        last_plan = cand; last_val = v
        if v.ok:
            return {'plan': cand, 'validation': v, 'raw': raw,
                      'attempts': attempt, 'retry_used': retry_used}
        if attempt < max_attempts:
            cur_prompt = sp._retry_prompt(prompt, v.reasons, cand)
            retry_used = True
    return {'plan': last_plan, 'validation': last_val, 'raw': raw,
              'attempts': max_attempts, 'retry_used': retry_used}


def _extract_sql(raw):
    if not raw:
        return ''
    m = re.search(r'```sql\s*\n?([\s\S]*?)```', raw, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r'```\s*\n?([\s\S]*?)```', raw)
    if m:
        cand = m.group(1).strip()
        if any(kw in cand.upper() for kw in ('SELECT', 'WITH')):
            return cand
    upper = raw.upper()
    for tag in ('WITH ', 'SELECT '):
        idx = upper.find(tag)
        if idx >= 0:
            return raw[idx:].strip()
    return raw.strip()


def _snow_direct_prompt(question, pack, ek=''):
    table_lines = []
    for t in pack.get('tables', []):
        cols = ', '.join(c.get('name', '') for c in t.get('columns', [])[:22])
        fq = f'{t.get("db","")}.{t.get("schema","")}.{t.get("table","")}'
        table_lines.append(f'  {fq}: {cols}')
    schema_block = '\n'.join(table_lines)
    ek_block = f'\n\nExternal knowledge:\n{ek}' if ek else ''
    return (
        'You are a SQL expert. Write a single Snowflake SQL query that answers the question.\n'
        'Use ONLY tables and columns from the schema below. Use Snowflake syntax '
        '(UPPERCASE_IDENTIFIERS, three-part names DB.SCHEMA.TABLE, no `bigquery-public-data.` prefixes, '
        'no _TABLE_SUFFIX).\n\n'
        f'Schema:\n{schema_block}{ek_block}\n\n'
        f'Question: {question}\n\nReturn only the SQL inside a ```sql ... ``` block.'
    )


def _snow_parse_ok(sql):
    try:
        import sqlglot
        ast = sqlglot.parse_one(sql, read='snowflake')
        return (ast is not None, '')
    except Exception as e:
        return (False, f'{type(e).__name__}:{str(e)[:200]}')


def _snow_schema_valid(sql, pack):
    """Case-insensitive AST validation against pack (Snow dialect)."""
    try:
        import sqlglot
        import sqlglot.expressions as E
        ast = sqlglot.parse_one(sql, read='snowflake')
    except Exception as e:
        return (False, f'parse_failed:{type(e).__name__}')
    if ast is None:
        return (False, 'parse_failed:None')

    tables_allowed = set()
    cols_allowed_global = set()
    for t in pack.get('tables', []) or []:
        db = (t.get('db') or '').upper()
        sch = (t.get('schema') or '').upper()
        tab = (t.get('table') or '').upper()
        for tn in {tab, f'{sch}.{tab}', f'{db}.{sch}.{tab}'}:
            if tn:
                tables_allowed.add(tn.upper())
        for c in t.get('columns', []) or []:
            cn = (c.get('name') or '').upper()
            if cn: cols_allowed_global.add(cn)
        for cn in t.get('all_columns', []) or []:
            cu = (cn or '').upper()
            if cu: cols_allowed_global.add(cu)

    aliases = set(); cte_names = set()
    for cte in ast.find_all(E.CTE):
        nm = cte.alias_or_name
        if nm: cte_names.add(nm.upper())
    for tbl in ast.find_all(E.Table):
        if tbl.alias: aliases.add(tbl.alias.upper())

    unknown_tables = []; unknown_cols = []
    for tbl in ast.find_all(E.Table):
        nm = tbl.name
        if nm and nm.upper() not in tables_allowed and nm.upper() not in cte_names:
            full = '.'.join([p.name for p in tbl.parts]).upper() if hasattr(tbl, 'parts') else nm.upper()
            if full not in tables_allowed:
                if nm.upper() not in {t.split('.')[-1] for t in tables_allowed}:
                    unknown_tables.append(nm)

    for col in ast.find_all(E.Column):
        nm = col.name
        if not nm: continue
        nu = nm.upper()
        if nu == '*': continue
        if col.table:
            tu = col.table.upper()
            if tu in aliases or tu in cte_names: continue
            if tu in {t.split('.')[-1] for t in tables_allowed}: continue
        if nu not in cols_allowed_global:
            unknown_cols.append(nm)

    if unknown_tables or unknown_cols:
        return (False, f'unknown_tables={unknown_tables[:6]}, unknown_cols={unknown_cols[:8]}')
    return (True, '')


# ---- Snow EXPLAIN connection cache ---------------------------------

_SNOW_CONN_CACHE = {}  # keyed by (account, user) -> connection


def _snow_connect():
    if 'main' in _SNOW_CONN_CACHE:
        try:
            c = _SNOW_CONN_CACHE['main']
            c.cursor().execute('SELECT 1').fetchone()
            return c
        except Exception:
            del _SNOW_CONN_CACHE['main']
    import snowflake.connector
    c = snowflake.connector.connect(
        account=os.environ['SNOWFLAKE_ACCOUNT'],
        user=os.environ['SNOWFLAKE_USER'],
        password=os.environ['SNOWFLAKE_PASSWORD'],
        role=os.environ.get('SNOWFLAKE_ROLE') or None,
        warehouse=os.environ.get('SNOWFLAKE_WAREHOUSE') or None,
    )
    _SNOW_CONN_CACHE['main'] = c
    return c


def _snow_explain(sql, *, db=None, schema=None, timeout_s=30):
    """EXPLAIN-based compile check. Returns (ok, error_class, error_msg)."""
    if not sql:
        return (False, 'empty_sql', '')
    try:
        c = _snow_connect()
        cur = c.cursor()
        # Set DB/schema context if known. The pack's lane='snow' tells us
        # which DB the task is about; we'll re-use Snow's query to set it.
        if db:
            try:
                cur.execute(f'USE DATABASE "{db}"')
            except Exception:
                pass
        if schema:
            try:
                cur.execute(f'USE SCHEMA "{schema}"')
            except Exception:
                pass
        # EXPLAIN does not execute; safe to run.
        # Snow's EXPLAIN syntax: EXPLAIN <stmt>
        cur.execute('SELECT SYSTEM$CANCEL_ALL_QUERIES()')  # cleanup leftovers
    except Exception as e:
        return (False, 'connect_fail', f'{type(e).__name__}: {str(e)[:300]}')

    try:
        cur.execute(f'EXPLAIN {sql}')
        # Just consume; if no exception, EXPLAIN compiled.
        cur.fetchall()
        return (True, 'ok', '')
    except Exception as e:
        et = type(e).__name__
        em = str(e)[:300]
        # Bucketize the error
        em_low = em.lower()
        if 'invalid identifier' in em_low or 'does not exist' in em_low:
            return (False, 'invalid_identifier', em)
        if 'syntax error' in em_low or 'unexpected' in em_low:
            return (False, 'syntax_error', em)
        if 'does not match' in em_low or 'incompatible' in em_low:
            return (False, 'type_mismatch', em)
        if 'not authorized' in em_low or 'access' in em_low:
            return (False, 'access_denied', em)
        return (False, et, em)


# ---- Main runner -----------------------------------------------------

def start_v25_snow_full_bg(run_id):
    out_dir = SNOW_RUNS_BASE / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Acquire Phase 24 lock
    from gpu_lock_v24 import GPULock
    lock = GPULock(LOCK_DIR / 'gpu_inference.lock')
    res = lock.acquire(run_id)
    if not res.get('acquired'):
        return {'started': False, 'lock_failure': res}

    started_p = out_dir / '_STARTED'
    started_p.write_text(json.dumps({'run_id': run_id, 'phase': 25,
                                          'mode': 'snow_full',
                                          'no_execute': False,
                                          'engine_check': 'EXPLAIN',
                                          'ts': time.time()}))

    def _runner():
        try:
            import schema_linking_v18 as sl
            import schema_pack_builder_v18 as sb
            import torch
            gc.collect(); torch.cuda.empty_cache()

            # Verify Snow auth
            try:
                _ = _snow_connect()
            except Exception as e:
                with open(out_dir / '_FAILED', 'w') as f:
                    f.write(json.dumps({'error_type': 'snow_auth_fail',
                                          'error': str(e)[:400], 'ts': time.time()}))
                return

            tasks = []
            with open(SNOW_JSONL, encoding='utf-8') as fh:
                for ln in fh:
                    if ln.strip(): tasks.append(json.loads(ln))
            print(f'[{run_id}] Snow tasks: {len(tasks)}', flush=True)

            catalog_cols = sl.load_catalog_jsonl(SNOW_CATALOG, 'snow')
            print(f'[{run_id}] catalog cols: {len(catalog_cols)}', flush=True)
            linker = sl.SchemaLinker(catalog_cols)

            preds_p = out_dir / 'predictions.jsonl'
            traces_p = out_dir / 'traces.jsonl'
            recall_p = out_dir / 'schema_linking_recall.csv'
            metrics_p = out_dir / 'metrics.csv'
            error_p = out_dir / 'error_taxonomy.csv'
            db_break_p = out_dir / 'db_breakdown.csv'
            progress_p = out_dir / 'progress.json'
            preds_fh = open(preds_p, 'w', encoding='utf-8')
            traces_fh = open(traces_p, 'w', encoding='utf-8')
            recall_fh = open(recall_p, 'w', encoding='utf-8')
            recall_fh.write('instance_id,alias,n_columns_indexed,n_tables_indexed,top_db,top_table\n')

            err_counter = Counter()
            db_counter = Counter()
            db_exec_ok = Counter()
            n_total = 0; n_plan_ok = 0; n_schema_valid = 0; n_parse_ok = 0; n_exec_ok = 0
            t_start = time.time()

            for ti, task in enumerate(tasks):
                n_total += 1
                tid = task.get('instance_id') or task.get('id') or f't{n_total}'
                alias = task.get('db') or task.get('db_id') or ''
                question = task.get('question') or task.get('instruction') or ''
                ek = task.get('external_knowledge') or ''
                trace = {'instance_id': tid, 'alias': alias, 'question': question}
                t_task = time.time()
                db_counter[alias] += 1
                try:
                    link = linker.query(question, alias_filter=alias,
                                            top_columns=80, top_tables=20)
                    pack = sb.build_pack(link, lane='snow', alias=alias,
                                            max_tables=8, max_cols_per_table=22,
                                            all_catalog_cols=catalog_cols)
                    top_table = pack['tables'][0] if pack['tables'] else None
                    top_db = pack['databases'][0]['name'] if pack['databases'] else ''
                    recall_fh.write(','.join([
                        tid, alias, str(link.n_columns_indexed), str(link.n_tables_indexed),
                        top_db,
                        f'{top_table["db"]}.{top_table["schema"]}.{top_table["table"]}' if top_table else ''
                    ]) + '\n'); recall_fh.flush()
                    trace['pack_n_tables'] = len(pack['tables'])
                    trace['pack_n_columns'] = sum(len(t['columns']) for t in pack['tables'])
                    trace['pack_top_table'] = f'{top_table["db"]}.{top_table["schema"]}.{top_table["table"]}' if top_table else None

                    plan_prompt = sb.pack_to_planner_prompt(pack, question, external_knowledge=ek)
                    plan_res = _v18_plan_snow(plan_prompt, pack)
                    val = plan_res.get('validation')
                    plan_valid = bool(val and getattr(val, 'ok', False))
                    if plan_valid: n_plan_ok += 1
                    trace['plan_validation_ok'] = plan_valid

                    prompt = _snow_direct_prompt(question, pack, ek)
                    sql_raw = _gen_emitter(prompt, max_new=900)
                    sql = _extract_sql(sql_raw)

                    sv_ok, sv_msg = _snow_schema_valid(sql, pack)
                    pa_ok, pa_msg = _snow_parse_ok(sql)
                    if sv_ok: n_schema_valid += 1
                    if pa_ok: n_parse_ok += 1

                    # Engine EXPLAIN
                    db_top = top_table['db'] if top_table else None
                    sch_top = top_table['schema'] if top_table else None
                    if pa_ok:
                        ex_ok, ex_class, ex_msg = _snow_explain(sql, db=db_top, schema=sch_top)
                    else:
                        ex_ok, ex_class, ex_msg = False, 'parse_error', pa_msg
                    if ex_ok:
                        n_exec_ok += 1
                        db_exec_ok[alias] += 1

                    err_class = 'ok' if (sv_ok and pa_ok and ex_ok) else (
                        'parse_error' if not pa_ok else
                        ('schema_invalid' if not sv_ok else ex_class)
                    )
                    err_counter[err_class] += 1

                    pred_rec = {'instance_id': tid, 'sql': sql, 'lane': 'snow',
                                  'chosen_family': 'B',
                                  'schema_valid': sv_ok, 'parse_ok': pa_ok,
                                  'explain_ok': ex_ok,
                                  'sv_msg': sv_msg, 'parse_msg': pa_msg,
                                  'explain_class': ex_class,
                                  'explain_msg': ex_msg[:300] if ex_msg else ''}
                    preds_fh.write(json.dumps(pred_rec, default=str) + '\n'); preds_fh.flush()

                    trace.update({
                        'chosen_family': 'B', 'schema_valid': sv_ok,
                        'parse_ok': pa_ok, 'explain_ok': ex_ok,
                        'explain_class': ex_class,
                        'explain_msg': ex_msg[:200] if ex_msg else '',
                        'task_wall_sec': round(time.time() - t_task, 2),
                    })

                except Exception as exc:
                    trace['error_type'] = type(exc).__name__
                    trace['error'] = str(exc)[:400]
                    trace['traceback'] = traceback.format_exc()[:1500]
                    pred_rec = {'instance_id': tid, 'sql': '', 'lane': 'snow',
                                  'error': trace['error_type']}
                    preds_fh.write(json.dumps(pred_rec) + '\n'); preds_fh.flush()
                    err_counter[trace['error_type']] += 1
                traces_fh.write(json.dumps(trace, default=str) + '\n'); traces_fh.flush()

                if (n_total % 5) == 0:
                    gc.collect(); torch.cuda.empty_cache()

                with open(progress_p, 'w') as pfh:
                    pfh.write(json.dumps({
                        'n_total': n_total, 'n_target': len(tasks),
                        'plan_ok': n_plan_ok, 'schema_valid': n_schema_valid,
                        'parse_ok': n_parse_ok, 'execute_ok': n_exec_ok,
                        'err_top': err_counter.most_common(8),
                        'wall_sec': round(time.time() - t_start, 1),
                        'last_task': tid,
                    }, default=str))

            preds_fh.close(); traces_fh.close(); recall_fh.close()

            with open(metrics_p, 'w') as mfh:
                mfh.write('metric,value\n')
                mfh.write(f'n,{n_total}\n')
                mfh.write(f'plan_validation_ok,{n_plan_ok}\n')
                mfh.write(f'chosen_schema_valid,{n_schema_valid}\n')
                mfh.write(f'parse_ok,{n_parse_ok}\n')
                mfh.write(f'execute_ok,{n_exec_ok}\n')
            with open(error_p, 'w') as efh:
                efh.write('error_class,count\n')
                for k, v in err_counter.most_common():
                    efh.write(f'{k},{v}\n')
            with open(db_break_p, 'w') as bfh:
                bfh.write('db_alias,n_total,n_explain_ok\n')
                for k, v in db_counter.most_common():
                    bfh.write(f'{k},{v},{db_exec_ok.get(k,0)}\n')

            def _r(n,d): return '0.0%' if d==0 else f'{n/d*100:.1f}%'
            with open(out_dir / 'readout.md', 'w', encoding='utf-8') as rfh:
                rfh.write(f'# Spider2-Snow FULL — `{run_id}` (Phase 25, EXPLAIN-based)\n\n')
                rfh.write('| metric | value | rate |\n|---|---:|---:|\n')
                rfh.write(f'| n_total | {n_total} | — |\n')
                rfh.write(f'| plan_validation_ok | {n_plan_ok} | {_r(n_plan_ok,n_total)} |\n')
                rfh.write(f'| chosen_schema_valid | {n_schema_valid} | {_r(n_schema_valid,n_total)} |\n')
                rfh.write(f'| parse_ok | {n_parse_ok} | {_r(n_parse_ok,n_total)} |\n')
                rfh.write(f'| execute_ok (Snow EXPLAIN) | {n_exec_ok} | {_r(n_exec_ok,n_total)} |\n')
                rfh.write('\n## Error taxonomy\n\n| error_class | count |\n|---|---:|\n')
                for k, v in err_counter.most_common():
                    rfh.write(f'| `{k}` | {v} |\n')

            with open(out_dir / '_DONE', 'w') as df:
                df.write(json.dumps({
                    'n_total': n_total, 'plan_ok': n_plan_ok,
                    'schema_valid': n_schema_valid, 'parse_ok': n_parse_ok,
                    'execute_ok': n_exec_ok,
                    'wall_sec': round(time.time() - t_start, 1),
                    'ts': time.time()}))
        except Exception as exc:
            with open(out_dir / '_FAILED', 'w') as ff:
                ff.write(json.dumps({'error_type': type(exc).__name__,
                                          'error': str(exc)[:400],
                                          'traceback': traceback.format_exc()[:2000],
                                          'ts': time.time()}))
        finally:
            from gpu_lock_v24 import GPULock, free_gpu_cache
            try:
                GPULock(LOCK_DIR / 'gpu_inference.lock').release()
                free_gpu_cache()
                # Close Snow conn cache
                try:
                    if 'main' in _SNOW_CONN_CACHE:
                        _SNOW_CONN_CACHE['main'].close()
                        del _SNOW_CONN_CACHE['main']
                except Exception: pass
            except Exception: pass

    threading.Thread(target=_runner, daemon=True).start()
    return {'run_id': run_id, 'out_dir': str(out_dir), 'started': True}


def v25_snow_status(run_id):
    out_dir = SNOW_RUNS_BASE / run_id
    if not out_dir.is_dir(): return {'run_id': run_id, 'exists': False}
    s = {'run_id': run_id, 'exists': True,
          'started': (out_dir/'_STARTED').is_file(),
          'done': (out_dir/'_DONE').is_file(),
          'failed': (out_dir/'_FAILED').is_file()}
    pf = out_dir/'predictions.jsonl'
    s['n_predictions'] = sum(1 for _ in open(pf, encoding='utf-8')) if pf.is_file() else 0
    if (out_dir/'progress.json').is_file():
        try: s['progress'] = json.loads((out_dir/'progress.json').read_text())
        except Exception: pass
    if (out_dir/'_DONE').is_file():
        s['summary'] = json.loads((out_dir/'_DONE').read_text())
    if (out_dir/'_FAILED').is_file():
        s['failure'] = json.loads((out_dir/'_FAILED').read_text())
    return s


globals()['_PHASE25_START_SNOW_FULL'] = start_v25_snow_full_bg
globals()['_PHASE25_SNOW_STATUS'] = v25_snow_status
print('PHASE25_SNOW_RUNNER_REGISTERED')
