"""Phase 23 — launch Lite/BQ FULL 547 diagnostic in BG on bridge.

This sends the full v22 runner (same as run_spider2_v18_bq_pilot.py) but with
limit=600 (effectively all 547 BQ tasks) and run_id=lite_full_diagnostic_v23.

The BG thread writes per-task to Drive; we don't poll synchronously here —
just kick off and verify _STARTED. Subsequent polling happens via separate
status calls (so tunnel rotation doesn't kill the run).
"""
# This file is invoked as a code-file via tools/exec_remote.py and runs INSIDE
# the bridge kernel (not locally). It assumes the kernel has already loaded:
#   _MDL_PLAN, _MDL_EMIT, _TOK_PLAN, _TOK_EMIT, _PROF_PLAN, _PROF_EMIT
#   (confirmed by the STAGE 0 audit — _V18_MODELS_READY=True)
# It defines start_v23_bq_full_bg + v23_status and kicks off the BG thread.
import os, sys, json, time, traceback, threading
from pathlib import Path

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
LITE_JSONL = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl'
BQ_CATALOG = DRV / 'outputs/cache/spider2_bq_live_catalog_v18.jsonl'
RUNS_BASE = DRV / 'outputs/spider2_lite/runs'
EVAL_DIR = DRV / 'repo/src/evaluation'
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

g = globals()


def _gen(tok, mdl, prof, prompt, max_new):
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
    return _gen(g['_TOK_PLAN'], g['_MDL_PLAN'], g['_PROF_PLAN'], prompt, max_new)


def _gen_emitter(prompt, max_new=900):
    return _gen(g['_TOK_EMIT'], g['_MDL_EMIT'], g['_PROF_EMIT'], prompt, max_new)


def _v18_plan(prompt, pack, max_attempts=2):
    import structured_plan_v18 as sp
    raw = ''
    last_err = None
    last_plan = None
    last_val = None
    cur_prompt = prompt
    retry_used = False
    for attempt in range(1, max_attempts + 1):
        raw = _gen_planner(cur_prompt)
        try:
            cand = sp.parse_plan(raw)
        except Exception as e:
            last_err = f'parse_err:{type(e).__name__}:{str(e)[:200]}'
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
              'attempts': max_attempts, 'last_parse_err': last_err,
              'retry_used': retry_used}


def start_v23_bq_full_bg(run_id, limit=None, no_execute=False):
    """Launch BG thread that processes ALL BQ tasks (or up to `limit`).
    Writes per-task to Drive (predictions/traces flushed) so tunnel rotation
    is safe. Markers: _STARTED, _DONE, _FAILED, progress.json (every task).
    """
    out_dir = RUNS_BASE / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    started_p = out_dir / '_STARTED'
    started_p.write_text(json.dumps({'run_id': run_id, 'limit': limit,
                                          'no_execute': no_execute,
                                          'phase': 23,
                                          'ts': time.time()}))

    def _runner():
        try:
            import schema_linking_v18 as sl
            import schema_pack_builder_v18 as sb
            import structured_plan_v18 as sp
            import spider2_candidate_factory_v18 as cf
            import candidate_selector_v18 as cs

            all_tasks = []
            with open(LITE_JSONL, encoding='utf-8') as fh:
                for ln in fh:
                    if ln.strip():
                        all_tasks.append(json.loads(ln))
            BQ_BASE = DRV / 'external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/bigquery'
            bq_aliases = set(os.listdir(BQ_BASE)) if BQ_BASE.is_dir() else set()
            bq_tasks = [t for t in all_tasks if t.get('db', '') in bq_aliases or t.get('db_id', '') in bq_aliases]
            if limit:
                tasks = bq_tasks[:limit]
            else:
                tasks = bq_tasks
            print(f'BQ tasks selected: {len(tasks)} of {len(bq_tasks)} BQ available; total Lite={len(all_tasks)}', flush=True)

            catalog_cols = sl.load_catalog_jsonl(BQ_CATALOG, 'bq')
            print(f'catalog columns indexed: {len(catalog_cols)}', flush=True)
            linker = sl.SchemaLinker(catalog_cols)

            preds_p = out_dir / 'predictions.jsonl'
            traces_p = out_dir / 'traces.jsonl'
            recall_p = out_dir / 'schema_linking_recall.csv'
            metrics_p = out_dir / 'metrics.csv'
            error_p = out_dir / 'error_taxonomy.csv'
            progress_p = out_dir / 'progress.json'
            preds_fh = open(preds_p, 'w', encoding='utf-8')
            traces_fh = open(traces_p, 'w', encoding='utf-8')
            recall_fh = open(recall_p, 'w', encoding='utf-8')
            recall_fh.write('instance_id,alias,n_columns_indexed,n_tables_indexed,top_db,top_table,top_table_score,pack_token_budget\n')

            from collections import Counter
            err_counter = Counter()
            family_counter = Counter()
            n_parse_ok = 0; n_schema_valid = 0; n_dry_ok = 0; n_plan_ok = 0
            n_total = 0
            t_start = time.time()

            for ti, task in enumerate(tasks):
                n_total += 1
                tid = task.get('instance_id') or task.get('id') or task.get('question_id') or f't{n_total}'
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
                    top_db = pack['databases'][0]['name'] if pack['databases'] else ''
                    recall_fh.write(','.join([
                        tid, alias,
                        str(link.n_columns_indexed), str(link.n_tables_indexed),
                        top_db,
                        f'{top_table["db"]}.{top_table["schema"]}.{top_table["table"]}' if top_table else '',
                        str(top_table['score']) if top_table else '0',
                        str(pack.get('token_budget_used', 0)),
                    ]) + '\n'); recall_fh.flush()
                    trace['pack_top_table'] = f'{top_table["db"]}.{top_table["schema"]}.{top_table["table"]}' if top_table else None
                    trace['pack_n_tables'] = len(pack['tables'])
                    trace['pack_n_columns'] = sum(len(t['columns']) for t in pack['tables'])
                    trace['pack_n_all_columns'] = sum(len(t.get('all_columns') or []) for t in pack['tables'])
                    trace['pack_token_budget'] = pack.get('token_budget_used', 0)
                    trace['pack_join_hints'] = len(pack.get('join_hints') or [])

                    plan_prompt = sb.pack_to_planner_prompt(pack, question, external_knowledge=ek)
                    plan_res = _v18_plan(plan_prompt, pack)
                    plan = plan_res.get('plan')
                    val = plan_res.get('validation')
                    plan_valid = bool(val and getattr(val, 'ok', False))
                    if plan_valid: n_plan_ok += 1
                    trace['plan_attempts'] = plan_res.get('attempts')
                    trace['plan_validation_ok'] = plan_valid
                    trace['plan_validation_reasons'] = list(getattr(val, 'reasons', [])) if val else []

                    cands = cf.emit_candidates(question, pack, plan, external_knowledge=ek,
                                                    lane='bq', _gen_fn=_gen_emitter)
                    trace['n_candidates'] = len(cands)
                    trace['emitted_families'] = sorted(set(c.get('family', '?') for c in cands))

                    sel = cs.select(cands, pack, do_dry_run=not no_execute)
                    chosen = sel.get('chosen') or {}
                    chosen_sql = chosen.get('sql', '')
                    if chosen.get('parse_ok'): n_parse_ok += 1
                    if chosen.get('schema_valid'): n_schema_valid += 1
                    if chosen.get('dry_run_ok'): n_dry_ok += 1
                    chosen_family = chosen.get('family', '?')
                    family_counter[chosen_family] += 1
                    trace['evals'] = sel.get('evals')
                    trace['chosen_family'] = chosen_family
                    trace['chosen_error_class'] = chosen.get('error_class')
                    trace['task_wall_sec'] = round(time.time() - t_task, 2)

                    pred_rec = {'instance_id': tid, 'sql': chosen_sql,
                                  'chosen_family': chosen_family,
                                  'lane': 'bq',
                                  'schema_valid': chosen.get('schema_valid'),
                                  'parse_ok': chosen.get('parse_ok'),
                                  'dry_run_ok': chosen.get('dry_run_ok')}
                    preds_fh.write(json.dumps(pred_rec) + '\n'); preds_fh.flush()

                    err_class = chosen.get('error_class') or ('ok' if chosen.get('parse_ok') and chosen.get('dry_run_ok') else 'none')
                    err_counter[err_class] += 1
                except Exception as exc:
                    trace['error_type'] = type(exc).__name__
                    trace['error'] = str(exc)[:400]
                    trace['traceback'] = traceback.format_exc()[:1500]
                    pred_rec = {'instance_id': tid, 'sql': '', 'lane': 'bq',
                                  'error': trace['error_type']}
                    preds_fh.write(json.dumps(pred_rec) + '\n'); preds_fh.flush()
                    err_counter[trace['error_type']] += 1
                traces_fh.write(json.dumps(trace, default=str) + '\n'); traces_fh.flush()

                # Per-task progress checkpoint (overwrite)
                with open(progress_p, 'w') as pfh:
                    pfh.write(json.dumps({
                        'n_total': n_total, 'n_target': len(tasks),
                        'plan_ok': n_plan_ok, 'schema_valid': n_schema_valid,
                        'parse_ok': n_parse_ok, 'execute_ok': n_dry_ok,
                        'family_counts': dict(family_counter),
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
                mfh.write(f'execute_ok,{n_dry_ok}\n')
                for fam, count in family_counter.most_common():
                    mfh.write(f'chosen_family_{fam},{count}\n')
            with open(error_p, 'w') as efh:
                efh.write('error_class,count\n')
                for k, v in err_counter.most_common():
                    efh.write(f'{k},{v}\n')

            def _r(n, d):
                return '0.0%' if d == 0 else f'{n/d*100:.1f}%'
            with open(out_dir / 'readout.md', 'w', encoding='utf-8') as rfh:
                rfh.write(f'# Spider2-Lite-BQ FULL diagnostic — `{run_id}`\n\n')
                rfh.write('| metric | value | rate |\n|---|---:|---:|\n')
                rfh.write(f'| n_total | {n_total} | — |\n')
                rfh.write(f'| plan_validation_ok | {n_plan_ok} | {_r(n_plan_ok,n_total)} |\n')
                rfh.write(f'| chosen_schema_valid | {n_schema_valid} | {_r(n_schema_valid,n_total)} |\n')
                rfh.write(f'| parse_ok | {n_parse_ok} | {_r(n_parse_ok,n_total)} |\n')
                rfh.write(f'| execute_ok (BQ dry_run) | {n_dry_ok} | {_r(n_dry_ok,n_total)} |\n')
                rfh.write('\n## Family choice\n\n| family | count | rate |\n|---|---:|---:|\n')
                for fam, count in family_counter.most_common():
                    rfh.write(f'| `{fam}` | {count} | {_r(count, n_total)} |\n')
                rfh.write('\n## Error taxonomy\n\n| error_class | count |\n|---|---:|\n')
                for k, v in err_counter.most_common():
                    rfh.write(f'| `{k}` | {v} |\n')
            with open(out_dir / '_DONE', 'w') as df:
                df.write(json.dumps({
                    'n_total': n_total, 'plan_ok': n_plan_ok,
                    'schema_valid': n_schema_valid, 'parse_ok': n_parse_ok,
                    'execute_ok': n_dry_ok,
                    'family_counts': dict(family_counter),
                    'wall_sec': round(time.time() - t_start, 1),
                    'ts': time.time()}))
        except Exception as exc:
            with open(out_dir / '_FAILED', 'w') as ff:
                ff.write(json.dumps({'error_type': type(exc).__name__,
                                          'error': str(exc)[:400],
                                          'traceback': traceback.format_exc()[:2000],
                                          'ts': time.time()}))

    threading.Thread(target=_runner, daemon=True).start()
    return {'run_id': run_id, 'out_dir': str(out_dir), 'started': True}


def v23_status(run_id):
    out_dir = RUNS_BASE / run_id
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


# --- Persist these symbols across bridge calls so the BG thread can be
# polled later via fresh /exec calls without re-uploading the runner. ---
g['_PHASE23_START_BQ_FULL'] = start_v23_bq_full_bg
g['_PHASE23_STATUS'] = v23_status

# Kick off
RUN_ID = 'lite_full_diagnostic_v23_bq'
res = start_v23_bq_full_bg(run_id=RUN_ID, limit=None, no_execute=False)
print('PHASE23_BQ_FULL_STARTED')
print(json.dumps(res, default=str))
print('PHASE23_BQ_FULL_STARTED_END')
