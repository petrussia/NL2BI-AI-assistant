"""Phase 23 — launch Lite/Snow + Spider2-Snow FULL diagnostic in BG on bridge.

Two BG threads, both with no_execute=True (Snow connector not auth'd on
bridge kernel; this is a partial diagnostic producing schema_valid +
parse_ok via local sqlglot Snowflake dialect, NO engine-side execute_ok).

Produces:
  outputs/spider2_lite/runs/lite_full_diagnostic_v23_snow/         (Lite/Snow lane, 207 tasks)
  outputs/spider2_snow/runs/snow_full_diagnostic_v23/              (Spider2-Snow benchmark, 547 tasks)

Each writes predictions/traces/progress per-task (resumable on tunnel rotation).
"""
import os, sys, json, time, traceback, threading, re
from pathlib import Path

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
LITE_JSONL = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl'
SNOW_JSONL = DRV / 'external_benchmarks/spider2_snow/raw/Spider2/spider2-snow/spider2-snow.jsonl'
SNOW_CATALOG = DRV / 'outputs/cache/spider2_snow_live_catalog_v18.jsonl'
LITE_RUNS_BASE = DRV / 'outputs/spider2_lite/runs'
SNOW_RUNS_BASE = DRV / 'outputs/spider2_snow/runs'
EVAL_DIR = DRV / 'repo/src/evaluation'
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

g = globals()


def _gen_emitter_local(prompt, max_new=900):
    """Reuse loaded Coder-7B; same _gen as v18 BQ runner."""
    import torch
    tok = g['_TOK_EMIT']; mdl = g['_MDL_EMIT']; prof = g['_PROF_EMIT']
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


def _gen_planner_local(prompt, max_new=1100):
    import torch
    tok = g['_TOK_PLAN']; mdl = g['_MDL_PLAN']; prof = g['_PROF_PLAN']
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


def _v18_plan_local(prompt, pack, max_attempts=2):
    import structured_plan_v18 as sp
    raw = ''
    last_plan = None
    last_val = None
    cur_prompt = prompt
    retry_used = False
    for attempt in range(1, max_attempts + 1):
        raw = _gen_planner_local(cur_prompt)
        try:
            cand = sp.parse_plan(raw)
        except Exception as e:
            continue
        v = sp.validate_plan(cand, pack)
        last_plan = cand
        last_val = v
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
    """Direct emitter prompt with Snowflake dialect hint."""
    table_lines = []
    for t in pack.get('tables', []):
        cols = ', '.join(c.get('name', '') for c in t.get('columns', [])[:22])
        fq = f'{t.get("db","")}.{t.get("schema","")}.{t.get("table","")}'
        table_lines.append(f'  {fq}: {cols}')
    schema_block = '\n'.join(table_lines)
    ek_block = f'\n\nExternal knowledge:\n{ek}' if ek else ''
    return (
        'You are a SQL expert. Write a single Snowflake SQL query that answers the question.\n'
        'Use ONLY tables and columns from the schema below. Use Snowflake syntax (UPPER_CASE_IDENTIFIERS, '
        'three-part names DB.SCHEMA.TABLE, no `bigquery-public-data.` prefixes).\n\n'
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
    """AST-aware schema validation against pack (Snow dialect).
    Mirrors candidate_selector_v18.schema_valid_against_pack but uses
    Snowflake dialect and case-insensitive ID compare."""
    try:
        import sqlglot
        import sqlglot.expressions as E
        ast = sqlglot.parse_one(sql, read='snowflake')
    except Exception as e:
        return (False, f'parse_failed:{type(e).__name__}')
    if ast is None:
        return (False, 'parse_failed:None')

    # Build allowed sets from pack (case-insensitive)
    tables_allowed = set()
    cols_allowed_per_table = {}
    cols_allowed_global = set()
    for t in pack.get('tables', []) or []:
        db = (t.get('db') or '').upper()
        sch = (t.get('schema') or '').upper()
        tab = (t.get('table') or '').upper()
        for tn in {tab, f'{sch}.{tab}', f'{db}.{sch}.{tab}'}:
            if tn:
                tables_allowed.add(tn.upper())
        cols = []
        for c in t.get('columns', []) or []:
            cn = (c.get('name') or '').upper()
            if cn:
                cols.append(cn)
                cols_allowed_global.add(cn)
        for cn in t.get('all_columns', []) or []:
            cu = (cn or '').upper()
            if cu:
                cols.append(cu)
                cols_allowed_global.add(cu)
        cols_allowed_per_table[tab] = set(cols)

    # Aliases / CTEs
    aliases = set()
    cte_names = set()
    for cte in ast.find_all(E.CTE):
        nm = cte.alias_or_name
        if nm:
            cte_names.add(nm.upper())
    for tbl in ast.find_all(E.Table):
        if tbl.alias:
            aliases.add(tbl.alias.upper())

    # Walk Tables and Columns
    unknown_tables = []
    unknown_cols = []
    for tbl in ast.find_all(E.Table):
        nm = tbl.name
        if nm and nm.upper() not in tables_allowed and nm.upper() not in cte_names:
            full = '.'.join([p.name for p in tbl.parts]).upper() if hasattr(tbl, 'parts') else nm.upper()
            if full not in tables_allowed:
                # try last-segment match
                if nm.upper() in {t.split('.')[-1] for t in tables_allowed}:
                    pass
                else:
                    unknown_tables.append(nm)

    for col in ast.find_all(E.Column):
        nm = col.name
        if not nm:
            continue
        nu = nm.upper()
        if nu == '*':
            continue
        # If qualified by alias/CTE, accept
        if col.table:
            tu = col.table.upper()
            if tu in aliases or tu in cte_names:
                continue
            if tu in {t.split('.')[-1] for t in tables_allowed}:
                continue
        if nu not in cols_allowed_global:
            unknown_cols.append(nm)

    if unknown_tables or unknown_cols:
        msg = ''
        if unknown_tables:
            msg += f'unknown_tables={unknown_tables[:6]}; '
        if unknown_cols:
            msg += f'unknown_cols={unknown_cols[:8]}'
        return (False, msg.strip())
    return (True, '')


def _run_snow_diag(run_id, runs_base, jsonl_path, alias_filter_set, *, limit=None):
    """Common Snow no-execute diagnostic runner. Filter is a set of
    aliases or None (process all)."""
    import schema_linking_v18 as sl
    import schema_pack_builder_v18 as sb

    out_dir = runs_base / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    started_p = out_dir / '_STARTED'
    started_p.write_text(json.dumps({'run_id': run_id, 'phase': 23,
                                          'no_execute': True, 'ts': time.time()}))
    preds_p = out_dir / 'predictions.jsonl'
    traces_p = out_dir / 'traces.jsonl'
    progress_p = out_dir / 'progress.json'
    metrics_p = out_dir / 'metrics.csv'
    error_p = out_dir / 'error_taxonomy.csv'

    # Load tasks
    tasks = []
    with open(jsonl_path, encoding='utf-8') as fh:
        for ln in fh:
            if not ln.strip():
                continue
            t = json.loads(ln)
            alias = t.get('db') or t.get('db_id') or ''
            if alias_filter_set is None or alias in alias_filter_set:
                tasks.append(t)
    if limit:
        tasks = tasks[:limit]
    print(f'[{run_id}] tasks selected: {len(tasks)}', flush=True)

    catalog_cols = sl.load_catalog_jsonl(SNOW_CATALOG, 'snow')
    print(f'[{run_id}] catalog columns indexed: {len(catalog_cols)}', flush=True)
    linker = sl.SchemaLinker(catalog_cols)

    from collections import Counter
    err_counter = Counter()
    n_total = 0; n_plan_ok = 0; n_schema_valid = 0; n_parse_ok = 0
    t_start = time.time()

    preds_fh = open(preds_p, 'w', encoding='utf-8')
    traces_fh = open(traces_p, 'w', encoding='utf-8')

    for ti, task in enumerate(tasks):
        n_total += 1
        tid = task.get('instance_id') or task.get('id') or f't{n_total}'
        alias = task.get('db') or task.get('db_id') or ''
        question = task.get('question') or task.get('instruction') or ''
        ek = task.get('external_knowledge') or ''
        trace = {'instance_id': tid, 'alias': alias, 'question': question}
        t_task = time.time()
        try:
            link = linker.query(question, alias_filter=alias,
                                    top_columns=80, top_tables=20)
            pack = sb.build_pack(link, lane='snow', alias=alias,
                                    max_tables=8, max_cols_per_table=22,
                                    all_catalog_cols=catalog_cols)
            top_table = pack['tables'][0] if pack['tables'] else None
            trace['pack_top_table'] = f'{top_table["db"]}.{top_table["schema"]}.{top_table["table"]}' if top_table else None
            trace['pack_n_tables'] = len(pack['tables'])
            trace['pack_n_columns'] = sum(len(t['columns']) for t in pack['tables'])
            trace['pack_n_all_columns'] = sum(len(t.get('all_columns') or []) for t in pack['tables'])
            trace['pack_token_budget'] = pack.get('token_budget_used', 0)

            plan_prompt = sb.pack_to_planner_prompt(pack, question, external_knowledge=ek)
            plan_res = _v18_plan_local(plan_prompt, pack)
            val = plan_res.get('validation')
            plan_valid = bool(val and getattr(val, 'ok', False))
            if plan_valid:
                n_plan_ok += 1
            trace['plan_validation_ok'] = plan_valid
            trace['plan_validation_reasons'] = list(getattr(val, 'reasons', [])) if val else []

            # Family B (Coder-7B direct) — only family for Snow (no v18 Snow renderer)
            prompt = _snow_direct_prompt(question, pack, ek)
            sql_raw = _gen_emitter_local(prompt, max_new=900)
            sql = _extract_sql(sql_raw)

            sv_ok, sv_msg = _snow_schema_valid(sql, pack)
            pa_ok, pa_msg = _snow_parse_ok(sql)
            if sv_ok:
                n_schema_valid += 1
            if pa_ok:
                n_parse_ok += 1

            err_class = 'ok' if (sv_ok and pa_ok) else (
                'parse_error' if not pa_ok else 'schema_invalid'
            )
            err_counter[err_class] += 1

            pred_rec = {'instance_id': tid, 'sql': sql, 'lane': 'snow',
                          'chosen_family': 'B', 'schema_valid': sv_ok,
                          'parse_ok': pa_ok, 'dry_run_ok': None,
                          'sv_msg': sv_msg, 'parse_msg': pa_msg}
            preds_fh.write(json.dumps(pred_rec, default=str) + '\n'); preds_fh.flush()
            trace['chosen_family'] = 'B'
            trace['schema_valid'] = sv_ok; trace['parse_ok'] = pa_ok
            trace['sv_msg'] = sv_msg; trace['parse_msg'] = pa_msg
            trace['task_wall_sec'] = round(time.time() - t_task, 2)

        except Exception as exc:
            trace['error_type'] = type(exc).__name__
            trace['error'] = str(exc)[:400]
            trace['traceback'] = traceback.format_exc()[:1500]
            pred_rec = {'instance_id': tid, 'sql': '', 'lane': 'snow',
                          'error': trace['error_type']}
            preds_fh.write(json.dumps(pred_rec) + '\n'); preds_fh.flush()
            err_counter[trace['error_type']] += 1

        traces_fh.write(json.dumps(trace, default=str) + '\n'); traces_fh.flush()

        with open(progress_p, 'w') as pfh:
            pfh.write(json.dumps({
                'n_total': n_total, 'n_target': len(tasks),
                'plan_ok': n_plan_ok, 'schema_valid': n_schema_valid,
                'parse_ok': n_parse_ok, 'execute_ok': None,
                'err_top': err_counter.most_common(8),
                'wall_sec': round(time.time() - t_start, 1),
                'last_task': tid,
            }, default=str))

    preds_fh.close(); traces_fh.close()

    with open(metrics_p, 'w') as mfh:
        mfh.write('metric,value\n')
        mfh.write(f'n,{n_total}\n')
        mfh.write(f'plan_validation_ok,{n_plan_ok}\n')
        mfh.write(f'chosen_schema_valid,{n_schema_valid}\n')
        mfh.write(f'parse_ok,{n_parse_ok}\n')
        mfh.write('execute_ok,NA_no_auth\n')
    with open(error_p, 'w') as efh:
        efh.write('error_class,count\n')
        for k, v in err_counter.most_common():
            efh.write(f'{k},{v}\n')

    def _r(n, d):
        return '0.0%' if d == 0 else f'{n/d*100:.1f}%'
    with open(out_dir / 'readout.md', 'w', encoding='utf-8') as rfh:
        rfh.write(f'# Snow FULL diagnostic — `{run_id}` (no_execute)\n\n')
        rfh.write('| metric | value | rate |\n|---|---:|---:|\n')
        rfh.write(f'| n_total | {n_total} | — |\n')
        rfh.write(f'| plan_validation_ok | {n_plan_ok} | {_r(n_plan_ok,n_total)} |\n')
        rfh.write(f'| chosen_schema_valid | {n_schema_valid} | {_r(n_schema_valid,n_total)} |\n')
        rfh.write(f'| parse_ok | {n_parse_ok} | {_r(n_parse_ok,n_total)} |\n')
        rfh.write('| execute_ok | NA | Snow connector unauthenticated on bridge kernel |\n')
        rfh.write('\n## Error taxonomy\n\n| error_class | count |\n|---|---:|\n')
        for k, v in err_counter.most_common():
            rfh.write(f'| `{k}` | {v} |\n')

    with open(out_dir / '_DONE', 'w') as df:
        df.write(json.dumps({
            'n_total': n_total, 'plan_ok': n_plan_ok,
            'schema_valid': n_schema_valid, 'parse_ok': n_parse_ok,
            'execute_ok': None,
            'wall_sec': round(time.time() - t_start, 1),
            'ts': time.time()}))


def start_v23_lite_snow_full_bg(run_id):
    out_dir = LITE_RUNS_BASE / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    LR = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/snowflake'
    snow_set = set(os.listdir(LR)) if LR.is_dir() else set()
    print(f'Lite-Snow lane filter: {len(snow_set)} aliases', flush=True)

    def _runner():
        try:
            _run_snow_diag(run_id, LITE_RUNS_BASE, LITE_JSONL, snow_set)
        except Exception as exc:
            with open(LITE_RUNS_BASE / run_id / '_FAILED', 'w') as ff:
                ff.write(json.dumps({'error_type': type(exc).__name__,
                                          'error': str(exc)[:400],
                                          'traceback': traceback.format_exc()[:2000],
                                          'ts': time.time()}))

    threading.Thread(target=_runner, daemon=True).start()
    return {'run_id': run_id, 'out_dir': str(LITE_RUNS_BASE / run_id), 'started': True}


def start_v23_spider2_snow_full_bg(run_id):
    out_dir = SNOW_RUNS_BASE / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    def _runner():
        try:
            _run_snow_diag(run_id, SNOW_RUNS_BASE, SNOW_JSONL, alias_filter_set=None)
        except Exception as exc:
            with open(SNOW_RUNS_BASE / run_id / '_FAILED', 'w') as ff:
                ff.write(json.dumps({'error_type': type(exc).__name__,
                                          'error': str(exc)[:400],
                                          'traceback': traceback.format_exc()[:2000],
                                          'ts': time.time()}))

    threading.Thread(target=_runner, daemon=True).start()
    return {'run_id': run_id, 'out_dir': str(SNOW_RUNS_BASE / run_id), 'started': True}


def v23_status_lite(run_id):
    return _v23_status_path(LITE_RUNS_BASE / run_id, run_id)


def v23_status_snow(run_id):
    return _v23_status_path(SNOW_RUNS_BASE / run_id, run_id)


def _v23_status_path(out_dir, run_id):
    if not out_dir.is_dir():
        return {'run_id': run_id, 'exists': False}
    s = {'run_id': run_id, 'exists': True,
          'started': (out_dir/'_STARTED').is_file(),
          'done': (out_dir/'_DONE').is_file(),
          'failed': (out_dir/'_FAILED').is_file()}
    pf = out_dir/'predictions.jsonl'
    s['n_predictions'] = sum(1 for _ in open(pf, encoding='utf-8')) if pf.is_file() else 0
    if (out_dir/'progress.json').is_file():
        try:
            s['progress'] = json.loads((out_dir/'progress.json').read_text())
        except Exception:
            pass
    if (out_dir/'_DONE').is_file():
        s['summary'] = json.loads((out_dir/'_DONE').read_text())
    if (out_dir/'_FAILED').is_file():
        s['failure'] = json.loads((out_dir/'_FAILED').read_text())
    return s


# Persist symbols
g['_PHASE23_START_LITE_SNOW_FULL'] = start_v23_lite_snow_full_bg
g['_PHASE23_START_SPIDER2_SNOW_FULL'] = start_v23_spider2_snow_full_bg
g['_PHASE23_STATUS_LITE'] = v23_status_lite
g['_PHASE23_STATUS_SNOW'] = v23_status_snow

# Note: the BQ FULL is already running and using model VRAM. Snow runs share
# the same models; running them concurrently would serialize on GPU. We start
# the Spider2-Snow BG thread first (largest, 547 tasks), but actual generation
# will wait for BQ FULL to release per-token GPU lock. To avoid HF generate
# deadlock under concurrent calls, we DELAY-start the Snow runs until BQ FULL
# is past 80% complete (poll-based gate), launched separately later.
print('PHASE23_SNOW_RUNNERS_REGISTERED')
print(json.dumps({
    'lite_snow_run_id': 'lite_full_diagnostic_v23_snow',
    'spider2_snow_run_id': 'snow_full_diagnostic_v23',
    'note': 'launchers registered; will be started after BQ FULL reaches saturation to avoid GPU contention',
}))
print('PHASE23_SNOW_RUNNERS_REGISTERED_END')
