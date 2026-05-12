"""Phase 25 — resume Lite-BQ FULL v25 from where Drive predictions left off.

Reads <DRIVE>/outputs/spider2_lite/runs/lite_bq_full_v25/predictions.jsonl,
collects already-completed instance_ids, and starts the BG runner with the
remaining task list. Predictions for new tasks are APPENDED (not overwritten).

Use after a Colab kernel restart. Idempotent: if all 205 are done, just
writes _DONE marker and exits.
"""
import os, sys, json, time, traceback, gc, threading, re
from pathlib import Path
from collections import Counter

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
LITE_JSONL = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl'
BQ_CATALOG = DRV / 'outputs/cache/spider2_bq_live_catalog_v18.jsonl'
RUNS_BASE = DRV / 'outputs/spider2_lite/runs'
EVAL_DIR = DRV / 'repo/src/evaluation'
LOCK_DIR = DRV / 'outputs/runtime'
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))


def _serialize_lock():
    g = globals()
    if g.get('_PHASE25_GEN_LOCK') is None:
        g['_PHASE25_GEN_LOCK'] = threading.Lock()
    return g['_PHASE25_GEN_LOCK']


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


def _v18_plan(prompt, pack, max_attempts=2):
    import structured_plan_v18 as sp
    raw = ''
    last_plan = None; last_val = None
    cur_prompt = prompt; retry_used = False
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


def resume_v25_lite_bq_bg(run_id='lite_bq_full_v25'):
    """Resume Lite-BQ FULL by skipping already-done instance_ids."""
    out_dir = RUNS_BASE / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    preds_p = out_dir / 'predictions.jsonl'
    traces_p = out_dir / 'traces.jsonl'
    progress_p = out_dir / 'progress.json'
    metrics_p = out_dir / 'metrics.csv'
    error_p = out_dir / 'error_taxonomy.csv'
    family_p = out_dir / 'family_breakdown.csv'
    rewrite_p = out_dir / 'engine_rewrite_stats.csv'
    recall_p = out_dir / 'schema_linking_recall.csv'

    # Load prior preds
    done_ids = set()
    if preds_p.is_file():
        with open(preds_p, encoding='utf-8') as fh:
            for ln in fh:
                if not ln.strip(): continue
                try:
                    rec = json.loads(ln)
                    iid = rec.get('instance_id')
                    if iid: done_ids.add(iid)
                except Exception:
                    pass
    print(f'[resume] {len(done_ids)} prior preds found', flush=True)

    # Acquire lock
    from gpu_lock_v24 import GPULock
    lock = GPULock(LOCK_DIR / 'gpu_inference.lock')
    res = lock.acquire(run_id)
    if not res.get('acquired'):
        return {'started': False, 'lock_failure': res}

    (out_dir / '_RESUMED').write_text(json.dumps({'prior_done': len(done_ids),
                                                       'ts': time.time()}))

    def _runner():
        try:
            import schema_linking_v18 as sl
            import schema_pack_builder_v18 as sb
            import spider2_candidate_factory_v18 as cf
            import candidate_selector_v18 as cs
            import bigquery_engine_compat_v24 as bqcompat
            import torch
            gc.collect(); torch.cuda.empty_cache()

            # All BQ tasks
            all_tasks = []
            with open(LITE_JSONL, encoding='utf-8') as fh:
                for ln in fh:
                    if ln.strip(): all_tasks.append(json.loads(ln))
            BQ_BASE = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/bigquery'
            bq_aliases = set(os.listdir(BQ_BASE)) if BQ_BASE.is_dir() else set()
            bq_tasks = [t for t in all_tasks
                          if t.get('db', '') in bq_aliases or t.get('db_id', '') in bq_aliases]
            tasks = [t for t in bq_tasks if t.get('instance_id') not in done_ids]
            print(f'[resume] {len(tasks)} tasks remaining of {len(bq_tasks)}', flush=True)

            if not tasks:
                # already done; just finalize
                _finalize(out_dir, preds_p, metrics_p, error_p, family_p, rewrite_p)
                return

            catalog_cols = sl.load_catalog_jsonl(BQ_CATALOG, 'bq')
            print(f'[resume] catalog cols: {len(catalog_cols)}', flush=True)
            linker = sl.SchemaLinker(catalog_cols)

            # APPEND not WRITE (preserve prior predictions)
            preds_fh = open(preds_p, 'a', encoding='utf-8')
            traces_fh = open(traces_p, 'a', encoding='utf-8')
            recall_fh = open(recall_p, 'a', encoding='utf-8')

            # Replay prior counters from existing predictions
            err_counter = Counter()
            family_counter = Counter()
            rewrite_counter = Counter()
            rewrite_helpful_counter = Counter()
            n_parse_ok = 0; n_schema_valid = 0; n_dry_ok = 0; n_plan_ok = 0
            n_total_done_prior = 0
            with open(preds_p, encoding='utf-8') as fh:
                for ln in fh:
                    if not ln.strip(): continue
                    try:
                        r = json.loads(ln)
                    except Exception: continue
                    n_total_done_prior += 1
                    if r.get('schema_valid'): n_schema_valid += 1
                    if r.get('parse_ok'): n_parse_ok += 1
                    if r.get('dry_run_ok'): n_dry_ok += 1
                    fam = r.get('chosen_family', '?')
                    family_counter[fam] += 1
                    if r.get('schema_valid') and r.get('parse_ok') and r.get('dry_run_ok'):
                        err_counter['ok'] += 1
                    elif not r.get('parse_ok'):
                        err_counter['parse_error'] += 1
                    elif not r.get('schema_valid'):
                        err_counter['schema_invalid'] += 1
                    else:
                        err_counter['bq_dry_run_failed'] += 1
                    for rw in r.get('rewrites_emitted', []):
                        rewrite_counter[rw.split(':')[0]] += 1

            n_total = n_total_done_prior
            t_start = time.time()
            print(f'[resume] replayed counters: n={n_total} sv={n_schema_valid} '
                    f'parse={n_parse_ok} exec={n_dry_ok}', flush=True)

            for task in tasks:
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
                    pack = sb.build_pack(link, lane='bq', alias=alias,
                                            max_tables=8, max_cols_per_table=22,
                                            all_catalog_cols=catalog_cols)
                    top_table = pack['tables'][0] if pack['tables'] else None
                    plan_prompt = sb.pack_to_planner_prompt(pack, question, external_knowledge=ek)
                    plan_res = _v18_plan(plan_prompt, pack)
                    plan = plan_res.get('plan')
                    val = plan_res.get('validation')
                    plan_valid = bool(val and getattr(val, 'ok', False))
                    if plan_valid: n_plan_ok += 1
                    trace['plan_validation_ok'] = plan_valid

                    cands = cf.emit_candidates(question, pack, plan, external_knowledge=ek,
                                                  lane='bq', _gen_fn=_gen_emitter)
                    augmented = list(cands)
                    rewrites_emitted = []
                    for c in cands:
                        sql = c.get('sql') or ''
                        if not sql: continue
                        rew, log = bqcompat.rewrite_for_bq(sql)
                        if rew != sql:
                            augmented.append({
                                'family': f'{c.get("family", "?")}_v24',
                                'sql_raw': rew, 'sql': rew,
                                'meta': {**(c.get('meta') or {}),
                                          'rewrite_of': c.get('family'),
                                          'rewrites_applied': log}})
                            rewrites_emitted.extend(log)
                            for entry in log:
                                rewrite_counter[entry.split(':')[0]] += 1

                    sel = cs.select(augmented, pack, do_dry_run=True)
                    chosen = sel.get('chosen') or {}
                    chosen_sql = chosen.get('sql', '')
                    if chosen.get('parse_ok'): n_parse_ok += 1
                    if chosen.get('schema_valid'): n_schema_valid += 1
                    if chosen.get('dry_run_ok'): n_dry_ok += 1
                    chosen_family = chosen.get('family', '?')
                    family_counter[chosen_family] += 1

                    pred_rec = {'instance_id': tid, 'sql': chosen_sql,
                                  'chosen_family': chosen_family, 'lane': 'bq',
                                  'schema_valid': chosen.get('schema_valid'),
                                  'parse_ok': chosen.get('parse_ok'),
                                  'dry_run_ok': chosen.get('dry_run_ok'),
                                  'rewrites_emitted': rewrites_emitted}
                    preds_fh.write(json.dumps(pred_rec) + '\n'); preds_fh.flush()

                    err_class = chosen.get('error_class') or (
                        'ok' if (chosen.get('parse_ok') and chosen.get('dry_run_ok')) else 'none')
                    err_counter[err_class] += 1
                    trace.update({'chosen_family': chosen_family,
                                    'task_wall_sec': round(time.time() - t_task, 2)})
                except Exception as exc:
                    trace['error_type'] = type(exc).__name__
                    trace['error'] = str(exc)[:400]
                    pred_rec = {'instance_id': tid, 'sql': '', 'lane': 'bq',
                                  'error': trace['error_type']}
                    preds_fh.write(json.dumps(pred_rec) + '\n'); preds_fh.flush()
                    err_counter[trace['error_type']] += 1
                traces_fh.write(json.dumps(trace, default=str) + '\n'); traces_fh.flush()

                if (n_total % 5) == 0:
                    gc.collect(); torch.cuda.empty_cache()

                with open(progress_p, 'w') as pfh:
                    pfh.write(json.dumps({
                        'n_total': n_total, 'n_target': 205,
                        'plan_ok': n_plan_ok, 'schema_valid': n_schema_valid,
                        'parse_ok': n_parse_ok, 'execute_ok': n_dry_ok,
                        'family_counts': dict(family_counter),
                        'rewrite_counts': dict(rewrite_counter),
                        'err_top': err_counter.most_common(8),
                        'wall_sec_resumed': round(time.time() - t_start, 1),
                        'last_task': tid,
                    }, default=str))

            preds_fh.close(); traces_fh.close(); recall_fh.close()
            _finalize(out_dir, preds_p, metrics_p, error_p, family_p, rewrite_p,
                          extra_summary={'phase': 25, 'resumed_with_prior_done': len(done_ids)})
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
            except Exception: pass

    threading.Thread(target=_runner, daemon=True).start()
    return {'run_id': run_id, 'out_dir': str(out_dir), 'started': True,
              'prior_done': len(done_ids)}


def _finalize(out_dir, preds_p, metrics_p, error_p, family_p, rewrite_p, *, extra_summary=None):
    """Write final tables/readout from preds_p."""
    err_counter = Counter()
    family_counter = Counter()
    rewrite_counter = Counter()
    n_total = 0; n_parse_ok = 0; n_schema_valid = 0; n_dry_ok = 0
    with open(preds_p, encoding='utf-8') as fh:
        for ln in fh:
            if not ln.strip(): continue
            try: r = json.loads(ln)
            except Exception: continue
            n_total += 1
            if r.get('schema_valid'): n_schema_valid += 1
            if r.get('parse_ok'): n_parse_ok += 1
            if r.get('dry_run_ok'): n_dry_ok += 1
            fam = r.get('chosen_family', '?')
            family_counter[fam] += 1
            if r.get('schema_valid') and r.get('parse_ok') and r.get('dry_run_ok'):
                err_counter['ok'] += 1
            elif not r.get('parse_ok'): err_counter['parse_error'] += 1
            elif not r.get('schema_valid'): err_counter['schema_invalid'] += 1
            else: err_counter['bq_dry_run_failed'] += 1
            for rw in r.get('rewrites_emitted', []) or []:
                rewrite_counter[rw.split(':')[0]] += 1

    with open(metrics_p, 'w') as mfh:
        mfh.write('metric,value\n')
        mfh.write(f'n,{n_total}\n')
        mfh.write(f'chosen_schema_valid,{n_schema_valid}\n')
        mfh.write(f'parse_ok,{n_parse_ok}\n')
        mfh.write(f'execute_ok,{n_dry_ok}\n')
        for fam, c in family_counter.most_common():
            mfh.write(f'chosen_family_{fam},{c}\n')
    with open(error_p, 'w') as efh:
        efh.write('error_class,count\n')
        for k, v in err_counter.most_common():
            efh.write(f'{k},{v}\n')
    with open(family_p, 'w') as fbfh:
        fbfh.write('family,chosen_count\n')
        for fam, c in family_counter.most_common(): fbfh.write(f'{fam},{c}\n')
    with open(rewrite_p, 'w') as rfh:
        rfh.write('rewrite_kind,emitted_count\n')
        for k, v in rewrite_counter.most_common(): rfh.write(f'{k},{v}\n')

    summary = {'n_total': n_total, 'schema_valid': n_schema_valid,
                'parse_ok': n_parse_ok, 'execute_ok': n_dry_ok,
                'family_counts': dict(family_counter),
                'rewrite_counts': dict(rewrite_counter),
                'ts': time.time()}
    if extra_summary: summary.update(extra_summary)
    with open(out_dir / '_DONE', 'w') as df:
        df.write(json.dumps(summary, default=str))


globals()['_PHASE25_RESUME_LITE_BQ'] = resume_v25_lite_bq_bg
print('PHASE25_RESUME_LITE_BQ_REGISTERED')
