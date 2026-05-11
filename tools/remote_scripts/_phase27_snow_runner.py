"""Phase 27 STAGE F1 — fixed Snow runner.

Closes all three v26 catalog-leak vectors:
  1. Linker call uses db_filter (correct path).
  2. BM25 index built per-task over the task_db subset (not global 587K).
  3. Pack all_columns side-channel filtered to task_db (defense in builder).

Plus Step 4: SQLGlot AST guard rejects any candidate SQL whose FROM/JOIN
references a foreign catalog. Two-part names are auto-filled with task_db.

Configurable for either lane:
  jsonl_path: Spider2-Lite jsonl (filter to Snow lane via alias_filter)
              OR Spider2-Snow jsonl (all 547 tasks).
  alias_filter_set: when given, keep only tasks whose db_id ∈ this set
                     (used for Lite-Snow lane to drop BQ/SQLite tasks).
  run_id: unique per-run directory under outputs/spider2_<lane>/runs/.

Run as BG thread on bridge. Writes per-task to Drive.
"""
import os, sys, json, time, traceback, threading, gc, re
from pathlib import Path
from collections import Counter

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
EVAL = DRV / 'repo/src/evaluation'
if str(EVAL) not in sys.path:
    sys.path.insert(0, str(EVAL))


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
    if not sql:
        return (False, 'empty_sql', '')
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
        if 'invalid identifier' in emL or 'does not exist' in emL:
            return (False, 'invalid_identifier', em)
        if 'syntax error' in emL:
            return (False, 'syntax_error', em)
        if 'incompatible' in emL or 'does not match' in emL:
            return (False, 'type_mismatch', em)
        return (False, type(e).__name__, em)


def _snow_parse_ok(sql):
    try:
        import sqlglot
        return (sqlglot.parse_one(sql, read='snowflake') is not None, '')
    except Exception as e:
        return (False, f'{type(e).__name__}:{str(e)[:200]}')


def _snow_schema_valid_ast(sql, pack, extra_allowed_cols=None):
    """AST validator that checks identifier residency against pack tables/columns.

    Phase 27 correction 2: `extra_allowed_cols` is a set of column names
    that are valid because they exist anywhere in the task_db catalog
    (not necessarily in the chosen pack tables). The all_columns
    side-channel from Phase 22 is local to pack-tables only and was
    silently dropping valid task_db columns that BM25 didn't surface.
    EXPLAIN remains the hard gate; relaxing the AST validator here
    removes false rejections without adding false passes.
    """
    try:
        import sqlglot, sqlglot.expressions as E
        ast = sqlglot.parse_one(sql, read='snowflake')
    except Exception as e:
        return (False, f'parse_failed:{type(e).__name__}')
    if ast is None:
        return (False, 'parse_returned_none')
    tables_allowed = set(); cols_allowed = set()
    for t in pack.get('tables', []) or []:
        db = (t.get('db') or '').upper(); sch = (t.get('schema') or '').upper(); tab = (t.get('table') or '').upper()
        for tn in {tab, f'{sch}.{tab}', f'{db}.{sch}.{tab}'}:
            if tn:
                tables_allowed.add(tn.upper())
        for c in t.get('columns', []) or []:
            cn = (c.get('name') or '').upper()
            if cn: cols_allowed.add(cn)
        for cn in t.get('all_columns', []) or []:
            cu = (cn or '').upper()
            if cu: cols_allowed.add(cu)
    # Phase 27 correction 2: union with task_db-wide column set
    if extra_allowed_cols:
        cols_allowed |= {c.upper() for c in extra_allowed_cols if c}
    aliases = set(); ctes = set()
    for cte in ast.find_all(E.CTE):
        nm = cte.alias_or_name
        if nm: ctes.add(nm.upper())
    for tbl in ast.find_all(E.Table):
        if tbl.alias: aliases.add(tbl.alias.upper())
    # Phase 27 fix: SELECT-side aliases (`expr AS alias`) are valid
    # references in same-query ORDER BY / GROUP BY / outer SELECT.
    # Don't false-positive-reject them when used un-qualified.
    select_aliases = set()
    for al in ast.find_all(E.Alias):
        a = al.alias_or_name
        if a:
            select_aliases.add(a.upper())
    cols_allowed |= select_aliases
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
        if nu not in cols_allowed:
            unkC.append(nm)
    if unkT or unkC:
        return (False, f'unknown_tables={unkT[:6]}, unknown_cols={unkC[:8]}')
    return (True, '')


def _snow_direct_prompt(question, pack, ek=''):
    """Snow direct emit prompt with three-part name rules + task_db hint.

    Phase 28: column types are rendered inline (col:TYPE). The emitter
    is asked to wrap date-arithmetic on NUMBER/VARIANT columns with an
    explicit cast; a deterministic post-pass (snow_dialect_fixer_v28)
    is the safety net if it forgets.
    """
    task_db = (pack.get('alias') or '').upper()
    table_lines = []
    for t in pack.get('tables', []):
        # Phase 28: pass through DATA_TYPE so the planner knows when a
        # date function needs a cast wrapper.
        col_strs = []
        for c in t.get('columns', [])[:22]:
            nm = c.get('name', '')
            ty = (c.get('type') or '').split('(')[0]  # strip NUMBER(38,0)->NUMBER
            col_strs.append(f'{nm}:{ty}' if ty else nm)
        cols = ', '.join(col_strs)
        fq = f'{task_db}.{t.get("schema","")}.{t.get("table","")}'
        table_lines.append(f'  {fq}: {cols}')
    schema_block = '\n'.join(table_lines)
    ek_block = f'\n\nExternal knowledge:\n{ek}' if ek else ''
    return (
        'You are a SQL expert. Write a single Snowflake SQL query.\n'
        'Use ONLY tables/columns from the schema below.\n\n'
        'Snowflake rules:\n'
        f'- ALWAYS three-part identifiers: {task_db}.SCHEMA.TABLE\n'
        f'- Available database for this query: {task_db}.\n'
        f'- Do NOT reference any other database.\n'
        '- Quote mixed-case identifiers: "ParticipantBarcode".\n'
        '- Use LATERAL FLATTEN(INPUT => col), NOT UNNEST.\n'
        '- Use IFF(c,a,b) or CASE WHEN. QUALIFY for window-row filter.\n'
        '- Date arithmetic on non-DATE columns requires explicit cast:\n'
        "  NUMBER (e.g. YYYYMMDD int) -> TO_DATE(TO_VARCHAR(col), 'YYYYMMDD')\n"
        '  VARIANT -> col::DATE; JSON path: col:field::DATE\n'
        '  Column types are shown as col:TYPE after each name in the schema below.\n\n'
        f'Schema:\n{schema_block}{ek_block}\n\n'
        f'Question: {question}\n\nReturn only SQL inside ```sql ... ``` block.'
    )


def _inject_pk_fk(pack, cat_subset):
    """Phase 27 correction 3: force-inject PK/FK-shaped columns from the
    full catalog into each chosen pack table. BM25 systematically
    under-ranks these (low token overlap with the question) but they are
    needed for JOIN paths in ~70% of multi-table queries.

    Heuristic (case-insensitive, last-segment of field_path):
      'id', '<table_singular>_id', '<table_singular>_sk', '*_pk', '*_fk',
      '*_id', '*_key', '*_sk'.

    Mutates `pack` in place. Cap injected cols at 4 per table to keep
    prompt budget intact.
    """
    by_tbl = {}
    for c in cat_subset:
        key = (c.db, c.schema, c.table)
        by_tbl.setdefault(key, []).append(c)

    injected_total = 0
    for t in pack.get('tables', []):
        key = (t['db'], t['schema'], t['table'])
        tbl_cols = by_tbl.get(key, [])
        existing_lc = {(c.get('name') or '').lower() for c in t.get('columns', [])}
        tbl_singular = t['table'].lower().rstrip('s')
        injected_for_table = 0
        for c in tbl_cols:
            if injected_for_table >= 4:
                break
            cn_full = (c.field_path or c.column or '').lower()
            cn_last = cn_full.split('.')[-1]
            if not cn_last or cn_full in existing_lc:
                continue
            is_key = (
                cn_last == 'id'
                or cn_last == f'{tbl_singular}_id'
                or cn_last == f'{tbl_singular}_sk'
                or cn_last.endswith('_pk')
                or cn_last.endswith('_fk')
                or cn_last.endswith('_id')
                or cn_last.endswith('_key')
                or cn_last.endswith('_sk')
            )
            if is_key:
                t['columns'].append({
                    'name': c.field_path or c.column,
                    'type': c.data_type or '',
                    'nullable': c.is_nullable or '',
                    'description': '[PK/FK heuristic]',
                })
                existing_lc.add(cn_full)
                injected_for_table += 1
                injected_total += 1
    return injected_total


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


def _run_phase27_snow(run_id, jsonl_path, *, alias_filter_set=None,
                            instance_ids_set=None,
                            limit=None, out_subdir='spider2_snow'):
    """Phase 27 STAGE F1 Snow runner.

    For each task:
      - filter catalog to TABLE_CATALOG == task.db (uppercase compare)
      - build per-task BM25 SchemaLinker on the subset
      - query with db_filter=task.db.upper()
      - build pack (defense filter active inside builder)
      - planner + emitter; AST-guard the SQL via snow_identifier_guard_v27
      - on IdentifierLeakError → mark schema_invalid catalog_leak_<dbs>
      - else → snow EXPLAIN, classify outcome
    """
    import importlib
    for mod in ['schema_linking_v18', 'schema_pack_builder_v18',
                  'structured_plan_v18', 'snow_identifier_guard_v27',
                  'snow_dialect_fixer_v28']:
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
    import schema_linking_v18 as sl
    import schema_pack_builder_v18 as sb
    import structured_plan_v18 as sp
    import snow_identifier_guard_v27 as guard
    # Phase 28 F2a + F4 dialect post-passes. Optional: if the module is
    # missing the runner falls back to v27-only behavior.
    try:
        import snow_dialect_fixer_v28 as fixer
    except Exception:
        fixer = None

    out_dir = DRV / 'outputs' / out_subdir / 'runs' / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / '_STARTED').write_text(json.dumps({
        'run_id': run_id, 'phase': 27, 'mode': 'F1_snow', 'ts': time.time()}))

    # Pre-load entire catalog once into a list (~5 GB JSON; we'll partition per task)
    cat_path = DRV / 'outputs/cache/spider2_snow_live_catalog_v18.jsonl'
    full_catalog = sl.load_catalog_jsonl(cat_path, 'snow')
    print(f'[{run_id}] catalog loaded: {len(full_catalog)} cols', flush=True)

    # Partition catalog by db (uppercase) for fast per-task subset retrieval
    from collections import defaultdict
    cat_by_db = defaultdict(list)
    for c in full_catalog:
        cat_by_db[c.db.upper()].append(c)
    print(f'[{run_id}] catalog partitioned by db: {len(cat_by_db)} unique DBs '
            f'(sizes: min={min(len(v) for v in cat_by_db.values())}, '
            f'max={max(len(v) for v in cat_by_db.values())}, '
            f'avg={sum(len(v) for v in cat_by_db.values())//len(cat_by_db)})',
          flush=True)

    # Load tasks
    tasks = []
    with open(jsonl_path, encoding='utf-8') as fh:
        for ln in fh:
            if not ln.strip(): continue
            t = json.loads(ln)
            alias = t.get('db') or t.get('db_id') or ''
            if alias_filter_set is not None and alias not in alias_filter_set:
                continue
            if instance_ids_set is not None and t.get('instance_id') not in instance_ids_set:
                continue
            tasks.append(t)
    if limit: tasks = tasks[:limit]
    print(f'[{run_id}] tasks selected: {len(tasks)}', flush=True)

    pf = open(out_dir / 'predictions.jsonl', 'w', encoding='utf-8')
    tf = open(out_dir / 'traces.jsonl', 'w', encoding='utf-8')
    err = Counter()
    n=0; n_plan_ok=0; n_sv=0; n_parse=0; n_exec=0
    n_guard_leak=0; n_guard_rewrite=0
    # Phase 28 counters
    n_guard_regex_fallback=0; n_requoted=0; n_wrapped=0
    t0 = time.time()

    for task in tasks:
        n += 1
        tid = task.get('instance_id') or f't{n}'
        task_db = (task.get('db') or task.get('db_id') or '').upper()
        question = task.get('question') or task.get('instruction') or ''
        ek = task.get('external_knowledge') or ''
        trace = {'instance_id': tid, 'task_db': task_db}
        try:
            # Per-task catalog subset
            cat_subset = cat_by_db.get(task_db, [])
            if not cat_subset:
                # task_db not in catalog (rare); fall through to empty pack
                err['no_catalog_for_task_db'] += 1
                pf.write(json.dumps({'instance_id': tid, 'task_db': task_db,
                                          'sql': '', 'lane': 'snow_v27',
                                          'error': 'no_catalog_for_task_db'}) + '\n'); pf.flush()
                tf.write(json.dumps(trace, default=str) + '\n'); tf.flush()
                continue
            # Per-task BM25 index
            linker = sl.SchemaLinker(cat_subset)
            # Phase 27 correction 1: scale retrieval window 2.5x to surface
            # more candidate tables on warehouse-scale catalogs while
            # keeping the final pack prompt budget unchanged.
            link = linker.query(question, db_filter=task_db,
                                    top_columns=200, top_tables=40)
            pack = sb.build_pack(link, lane='snow', alias=task_db,
                                    max_tables=10, max_cols_per_table=22,
                                    all_catalog_cols=cat_subset)
            # Phase 27 correction 3: PK/FK injection
            n_pk_fk = _inject_pk_fk(pack, cat_subset)
            trace['pk_fk_injected'] = n_pk_fk
            top_t = pack['tables'][0] if pack['tables'] else None
            trace['pack_n_tables'] = len(pack['tables'])
            unique_dbs_in_pack = {t['db'] for t in pack['tables']}
            trace['pack_unique_dbs'] = sorted(unique_dbs_in_pack)
            assert unique_dbs_in_pack.issubset({task_db}), \
                f'pack leak detected: {unique_dbs_in_pack} vs task_db={task_db}'

            # Planner
            plan_prompt = sb.pack_to_planner_prompt(pack, question, external_knowledge=ek)
            pr = _v18_plan(plan_prompt, pack)
            if pr.get('validation') and getattr(pr['validation'], 'ok', False):
                n_plan_ok += 1
            trace['plan_ok'] = bool(pr.get('validation') and getattr(pr['validation'], 'ok', False))

            # Emitter
            emit_prompt = _snow_direct_prompt(question, pack, ek)
            sql_raw = _gen(emit_prompt, max_new=900)
            sql = _extract_sql(sql_raw)
            trace['sql_pre_guard'] = sql[:300]

            # AST guard (Phase 27 Step 4 + Phase 28 F4c fail-open on parse error)
            guard_info = None
            try:
                sql_fixed, guard_info = guard.guard_and_fix_snow_sql(sql, task_db)
                if guard_info.get('rewrote_n'):
                    n_guard_rewrite += guard_info['rewrote_n']
                if guard_info.get('fallback') == 'regex_only':
                    n_guard_regex_fallback += 1
                sql = sql_fixed
                trace['guard'] = guard_info
            except guard.IdentifierLeakError as e:
                msg = str(e)
                trace['guard_error'] = msg
                if msg.startswith('catalog_leak'):
                    n_guard_leak += 1
                    err_class = 'catalog_leak'
                elif msg.startswith('parse_error_sqlglot'):
                    err_class = 'parse_error_guard'
                else:
                    err_class = 'guard_other'
                err[err_class] += 1
                pf.write(json.dumps({
                    'instance_id': tid, 'task_db': task_db, 'sql': sql, 'lane': 'snow_v27',
                    'schema_valid': False, 'parse_ok': False, 'explain_ok': False,
                    'guard_error': msg[:300],
                }, default=str) + '\n'); pf.flush()
                tf.write(json.dumps(trace, default=str) + '\n'); tf.flush()
                continue

            # Phase 28 F4 only (post-revert): F2a was reverted because the
            # PUBLICATIONS catalog stores columns lowercase, so upper-casing
            # broke previously-working lowercase-quoted column refs. F2a
            # function still exists in snow_dialect_fixer_v28 for record but
            # is NOT called in the pipeline. See REPORT_PHASE28 §6.
            task_db_all_cols = {
                (c.field_path or c.column) for c in cat_subset
                if (c.field_path or c.column)
            }
            if fixer is not None:
                col_types = {}
                for c in cat_subset:
                    nm = (c.field_path or c.column or '')
                    if not nm: continue
                    col_types[nm.upper()] = (c.data_type or '')
                try:
                    sql_b, info_b = fixer.wrap_date_fn_on_nondate(sql, col_types)
                    sql = sql_b
                    trace['f4'] = info_b
                    n_wrapped += info_b.get('wrapped_n', 0)
                except Exception as e:
                    trace['f4_error'] = f'{type(e).__name__}:{str(e)[:120]}'
            sv_ok, sv_msg = _snow_schema_valid_ast(sql, pack,
                                                          extra_allowed_cols=task_db_all_cols)
            pa_ok, pa_msg = _snow_parse_ok(sql)
            if sv_ok: n_sv += 1
            if pa_ok: n_parse += 1

            if pa_ok:
                ex_ok, ex_class, ex_msg = _snow_explain(
                    sql,
                    db=top_t['db'] if top_t else None,
                    schema=top_t['schema'] if top_t else None,
                )
            else:
                ex_ok, ex_class, ex_msg = False, 'parse_error', pa_msg
            if ex_ok: n_exec += 1

            err_class = 'ok' if (sv_ok and pa_ok and ex_ok) else (
                'parse_error' if not pa_ok else
                ('schema_invalid' if not sv_ok else ex_class))
            err[err_class] += 1
            pf.write(json.dumps({
                'instance_id': tid, 'task_db': task_db, 'sql': sql, 'lane': 'snow_v27',
                'schema_valid': sv_ok, 'parse_ok': pa_ok, 'explain_ok': ex_ok,
                'explain_class': ex_class,
                'guard_rewrote_n': (guard_info or {}).get('rewrote_n', 0),
            }, default=str) + '\n'); pf.flush()
            trace.update({'schema_valid': sv_ok, 'parse_ok': pa_ok,
                            'sv_msg': (sv_msg or '')[:300],
                            'pa_msg': (pa_msg or '')[:200],
                            'explain_ok': ex_ok, 'explain_class': ex_class,
                            'explain_msg': ex_msg[:200] if ex_msg else ''})
        except Exception as e:
            trace['error_type'] = type(e).__name__
            trace['error'] = str(e)[:400]
            trace['traceback'] = traceback.format_exc()[:1500]
            pf.write(json.dumps({'instance_id': tid, 'task_db': task_db,
                                      'sql': '', 'lane': 'snow_v27',
                                      'error': type(e).__name__}) + '\n'); pf.flush()
            err[type(e).__name__] += 1
        tf.write(json.dumps(trace, default=str) + '\n'); tf.flush()

        if n % 5 == 0:
            try:
                import torch; gc.collect(); torch.cuda.empty_cache()
            except Exception: pass

        with open(out_dir / 'progress.json', 'w') as f:
            f.write(json.dumps({
                'n_total': n, 'n_target': len(tasks),
                'plan_ok': n_plan_ok, 'schema_valid': n_sv,
                'parse_ok': n_parse, 'execute_ok': n_exec,
                'guard_leaks': n_guard_leak, 'guard_rewrites': n_guard_rewrite,
                'guard_regex_fallback': n_guard_regex_fallback,
                'requoted_n': n_requoted, 'wrapped_n': n_wrapped,
                'err_top': err.most_common(8),
                'wall_sec': round(time.time()-t0, 1), 'last_task': tid,
            }, default=str))

    pf.close(); tf.close()
    with open(out_dir / 'metrics.csv', 'w') as f:
        f.write(f'metric,value\nn,{n}\nplan_validation_ok,{n_plan_ok}\n'
                  f'chosen_schema_valid,{n_sv}\nparse_ok,{n_parse}\n'
                  f'execute_ok,{n_exec}\nguard_leaks,{n_guard_leak}\n'
                  f'guard_rewrites,{n_guard_rewrite}\n'
                  f'guard_regex_fallback,{n_guard_regex_fallback}\n'
                  f'requoted_n,{n_requoted}\nwrapped_n,{n_wrapped}\n')
    with open(out_dir / 'error_taxonomy.csv', 'w') as f:
        f.write('error_class,count\n')
        for k, v in err.most_common(): f.write(f'{k},{v}\n')
    (out_dir / '_DONE').write_text(json.dumps({
        'n_total': n, 'plan_ok': n_plan_ok, 'schema_valid': n_sv,
        'parse_ok': n_parse, 'execute_ok': n_exec,
        'guard_leaks': n_guard_leak, 'guard_rewrites': n_guard_rewrite,
        'guard_regex_fallback': n_guard_regex_fallback,
        'requoted_n': n_requoted, 'wrapped_n': n_wrapped,
        'wall_sec': round(time.time()-t0, 1), 'ts': time.time()}))
    print(f'[{run_id}] DONE n={n} sv={n_sv} parse={n_parse} exec={n_exec} '
            f'guard_leaks={n_guard_leak} guard_rewrites={n_guard_rewrite}',
          flush=True)


# --- Sync upload of guard module + builder patch to Drive before any run ---

def _upload_modules_to_drive():
    """Force-sync the local v27 modules + patched builder + Phase 28 fixer to Drive."""
    import base64
    src_files = [
        ('repo/src/evaluation/schema_pack_builder_v18.py', '__PACK_B64__'),
        ('repo/src/evaluation/snow_identifier_guard_v27.py', '__GUARD_B64__'),
        ('repo/src/evaluation/snow_dialect_fixer_v28.py', '__FIXER_B64__'),
    ]
    for relpath, b64 in src_files:
        dst = DRV / relpath
        dst.write_bytes(base64.b64decode(b64))
        print(f'uploaded {relpath} ({dst.stat().st_size} B)')


# Register helpers in globals
globals()['_PHASE27_RUN_SNOW'] = _run_phase27_snow
globals()['_PHASE27_UPLOAD_MODULES'] = _upload_modules_to_drive
print('PHASE27_SNOW_RUNNER_REGISTERED')
