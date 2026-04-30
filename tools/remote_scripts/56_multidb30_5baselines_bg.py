# Stage 8: B0 + B1 + B2_v1 + B3_v1 + B4_final on multidb_30 (single BG).
# Uses Qwen2.5-Coder-7B-Instruct. Saves per-baseline incrementally so that
# partial completion is recoverable if the kernel dies mid-way.

import csv
import datetime as dt
import json
import sys
import textwrap
import threading
import time
import traceback
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
SPIDER_DIR = PROJECT_ROOT / 'data' / 'spider'
OUTPUTS = PROJECT_ROOT / 'outputs'
REPO = PROJECT_ROOT / 'repo'
for sub in ['logs','metrics','predictions','tables']:
    (OUTPUTS / sub).mkdir(parents=True, exist_ok=True)

MODEL_ID = 'Qwen/Qwen2.5-Coder-7B-Instruct'
TASK_LOG = OUTPUTS / 'logs' / 'multidb30_5b_bg_task_log.txt'

mm = sys.modules['__main__']
def _from_main(name): return getattr(mm, name, None)

if 'MULTIDB30_5B_BG_THREAD' in globals() and MULTIDB30_5B_BG_THREAD.is_alive():
    print('BG already running')
    raise SystemExit(0)


def task_log(msg):
    line = f'[{dt.datetime.now(dt.timezone.utc).isoformat()}] {msg}'
    print(line)
    with TASK_LOG.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def background_main():
    try:
        TASK_LOG.write_text('', encoding='utf-8')
        task_log('MULTIDB30_5B_BG_START')

        # ensure model is Qwen-Coder
        import gc, torch
        cur_model = mm.__dict__.get('model'); cur_tok = mm.__dict__.get('tokenizer')
        cur_id = getattr(cur_model, 'name_or_path', '') if cur_model else ''
        if cur_id != MODEL_ID:
            task_log(f'swapping model: {cur_id} -> {MODEL_ID}')
            if cur_model is not None: del cur_model
            if cur_tok is not None: del cur_tok
            for k in ('model','tokenizer'):
                if k in mm.__dict__: del mm.__dict__[k]
            gc.collect(); torch.cuda.empty_cache(); torch.cuda.synchronize()
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
            tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
            qcfg = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                                      bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
            new_m = AutoModelForCausalLM.from_pretrained(MODEL_ID, trust_remote_code=True,
                                                         device_map='auto', quantization_config=qcfg)
            new_m.eval()
            mm.__dict__['model'] = new_m; mm.__dict__['tokenizer'] = tok
            task_log(f'loaded {MODEL_ID}; VRAM={torch.cuda.memory_allocated()//(1024*1024)} MB')
        else:
            task_log('model already Qwen-Coder')
        model = mm.__dict__['model']; tokenizer = mm.__dict__['tokenizer']

        eval_path = str(REPO / 'src' / 'evaluation')
        if eval_path not in sys.path: sys.path.insert(0, eval_path)
        for mod in ('baselines_b2_v1','baselines_b3_v1','baselines_b4_final'):
            if mod in sys.modules: del sys.modules[mod]
        import baselines_b2_v1 as b2v1
        import baselines_b3_v1 as b3v1
        import baselines_b4_final as b4f

        tables_map = _from_main('tables_map'); db_paths = _from_main('db_paths')
        lexical_schema_linking = _from_main('lexical_schema_linking')
        build_reduced_schema_context = _from_main('build_reduced_schema_context')
        make_prompt = _from_main('make_prompt'); make_b1_prompt = _from_main('make_b1_prompt')
        extract_sql = _from_main('extract_sql'); execute_sql = _from_main('execute_sql')
        FunctionTimedOut = _from_main('FunctionTimedOut')

        items = json.loads((SPIDER_DIR/'subsets'/'multidb_30.json').read_text(encoding='utf-8'))
        plan_schema_v1 = json.loads((REPO/'docs'/'plan_schema_v1.json').read_text(encoding='utf-8'))
        task_log(f'multidb_30 N={len(items)}')

        def gen(prompt, max_new=192, num_return_sequences=1, do_sample=False, temperature=1.0, top_p=1.0):
            messages = [{'role':'user','content':prompt}]
            rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(rendered, return_tensors='pt')
            inputs = {k:v.to(model.device) for k,v in inputs.items()}
            kw = dict(max_new_tokens=max_new, pad_token_id=tokenizer.eos_token_id)
            if do_sample: kw.update(do_sample=True, temperature=temperature, top_p=top_p,
                                    num_return_sequences=num_return_sequences)
            else: kw.update(do_sample=False)
            with torch.no_grad():
                out = model.generate(**inputs, **kw)
            n_in = inputs['input_ids'].shape[1]
            return [tokenizer.decode(seq[n_in:], skip_special_tokens=True) for seq in out]

        def evaluate(item, sql):
            ex, m = False, False; et, em, rows = '', '', None
            try:
                rows = execute_sql(db_paths[item['db_id']], sql)
                ex = True
                gold = execute_sql(db_paths[item['db_id']], item['query'])
                m = sorted(rows) == sorted(gold)
                if not m: et = 'result_mismatch'
            except FunctionTimedOut as exc:
                et, em = 'timeout', repr(exc)
            except Exception as exc:
                et, em = type(exc).__name__, str(exc)
            return ex, m, et, em, rows

        def _md(rows, cols):
            lines = ['|'+'|'.join(cols)+'|', '|'+'|'.join(['---']*len(cols))+'|']
            for r in rows:
                v = []
                for c in cols:
                    x = r.get(c, '')
                    if isinstance(x,(list,dict)): x = json.dumps(x, ensure_ascii=False)
                    v.append(str(x).replace('|','\\|').replace('\n','<br>')[:600])
                lines.append('|'+'|'.join(v)+'|')
            return '\n'.join(lines)+'\n'

        def write_run(prefix, records, started, extra_kvs):
            pred_p = OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl'
            metr_p = OUTPUTS/'metrics'/f'{prefix}_metrics.csv'
            sum_p = OUTPUTS/'tables'/f'{prefix}_summary.csv'
            run_p = OUTPUTS/'logs'/f'{prefix}_runlog.txt'
            err_p = OUTPUTS/'tables'/f'{prefix}_error_cases.md'
            ex_p = OUTPUTS/'tables'/f'{prefix}_examples.md'
            pred_p.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in records), encoding='utf-8')
            total = len(records); exec_count = sum(1 for r in records if r['executable'])
            match_count = sum(1 for r in records if r['execution_match'])
            ex = match_count/total if total else 0.0
            base = {'run_id':prefix,'model':MODEL_ID,'subset':'multidb_30','n':total,
                    'execution_match_count':match_count,'ex':ex,'executable_count':exec_count}
            base.update(extra_kvs)
            with metr_p.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=list(base.keys())); w.writeheader(); w.writerow(base)
            with sum_p.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=['metric','value']); w.writeheader()
                for k,v in [('completed','true'),('EX',ex),('executable_count',exec_count),('total',total),
                            ('model',MODEL_ID),('subset','multidb_30')]+list(extra_kvs.items()):
                    w.writerow({'metric':k,'value':v})
            run_p.write_text(textwrap.dedent(f'''
            {prefix} run log
            checked_at: {dt.datetime.now(dt.timezone.utc).isoformat()}
            model: {MODEL_ID}
            subset: multidb_30
            total: {total}; exec_count: {exec_count}; match_count: {match_count}; EX: {ex}
            elapsed_seconds: {time.time()-started:.2f}
            extra: {json.dumps(extra_kvs, ensure_ascii=False)}
            ''').strip()+'\n', encoding='utf-8')
            cols = ['idx','question','db_id','generated_sql','executable','execution_match','error_type']
            if any('plan_valid' in r for r in records): cols.insert(3, 'plan_valid')
            err_rows = [r for r in records if not r['execution_match']]
            err_p.write_text(f'# {prefix} Error Cases\n\n'+_md(err_rows[:30], cols), encoding='utf-8')
            ex_p.write_text(f'# {prefix} Examples\n\n'+_md(records[:5], cols), encoding='utf-8')
            return base

        # --- B0 ---
        task_log('=== B0 multidb_30 ===')
        recs = []; t0 = time.time()
        for i, item in enumerate(items):
            try:
                p = make_prompt(item); raw = gen(p, max_new=192)[0]; sql = extract_sql(raw)
                ex, m, et, em, _ = evaluate(item, sql)
            except Exception as exc:
                raw, sql = '', ''
                ex, m = False, False
                et, em = 'gen_failed', f'{type(exc).__name__}: {exc}'
            rec = {'idx':i,'question':item['question'],'db_id':item['db_id'],'gold_sql':item['query'],
                   'generated_raw':raw,'generated_sql':sql,'executable':ex,'execution_match':m,
                   'error_type':et,'error_message':em}
            recs.append(rec)
            (OUTPUTS/'predictions'/'b0_multidb30_v2_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in recs), encoding='utf-8')
            task_log(f'  B0 {i:>2} {item["db_id"]:<28} exec={ex} match={m} err={et!r}')
        s = write_run('b0_multidb30_v2', recs, t0, {'quantization':'4bit_bitsandbytes_config','schema_strategy':'full_schema'})
        task_log(f'B0_multidb30_v2_DONE EX={s["ex"]:.4f}')

        # --- B1 ---
        task_log('=== B1 multidb_30 ===')
        recs = []; t0 = time.time()
        for i, item in enumerate(items):
            link = lexical_schema_linking(item['question'], item['db_id'], tables_map)
            try:
                p = make_b1_prompt(item, link); raw = gen(p, max_new=192)[0]; sql = extract_sql(raw)
                ex, m, et, em, _ = evaluate(item, sql)
            except Exception as exc:
                raw, sql = '', ''
                ex, m = False, False
                et, em = 'gen_failed', f'{type(exc).__name__}: {exc}'
            rec = {'idx':i,'question':item['question'],'db_id':item['db_id'],'gold_sql':item['query'],
                   'generated_raw':raw,'generated_sql':sql,'executable':ex,'execution_match':m,
                   'error_type':et,'error_message':em,
                   'selected_tables':link['selected_tables'],
                   'schema_reduction_ratio':link['reduction_ratio'],
                   'fallback_used':link['fallback_used']}
            recs.append(rec)
            (OUTPUTS/'predictions'/'b1_multidb30_v2_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in recs), encoding='utf-8')
            task_log(f'  B1 {i:>2} {item["db_id"]:<28} sel={len(link["selected_tables"])} exec={ex} match={m} err={et!r}')
        avg = sum(r['schema_reduction_ratio'] for r in recs)/len(recs)
        s = write_run('b1_multidb30_v2', recs, t0,
                      {'quantization':'4bit_bitsandbytes_config','schema_strategy':'lexical_schema_linking',
                       'avg_reduction_ratio':avg})
        task_log(f'B1_multidb30_v2_DONE EX={s["ex"]:.4f}')

        # --- B2_v1 ---
        task_log('=== B2_v1 multidb_30 ===')
        recs = []; t0 = time.time()
        for i, item in enumerate(items):
            link = lexical_schema_linking(item['question'], item['db_id'], tables_map)
            reduced_ctx = build_reduced_schema_context(item['db_id'], link['selected_table_indexes'], tables_map)
            plan_raw=''; plan_parsed=None; plan_valid=False; plan_error=''
            try:
                pp = b2v1.make_plan_prompt(item['question'], reduced_ctx)
                plan_raw = gen(pp, max_new=320)[0]
                plan_parsed, plan_valid, plan_error = b2v1.parse_and_validate_plan(plan_raw, plan_schema_v1)
            except Exception as exc:
                plan_error = f'planner_failed: {type(exc).__name__}: {exc}'
            generated_raw=''; generated_sql=''
            ex_=False; m=False; et=''; em=''
            if plan_valid:
                try:
                    sp = b2v1.make_plan_to_sql_prompt(item['question'], plan_parsed, reduced_ctx)
                    generated_raw = gen(sp, max_new=192)[0]
                    generated_sql = extract_sql(generated_raw)
                    ex_, m, et, em, _ = evaluate(item, generated_sql)
                except Exception as exc:
                    et, em = 'sql_gen_failed', f'{type(exc).__name__}: {exc}'
            else:
                et='plan_invalid'; em=plan_error
            rec = {'idx':i,'question':item['question'],'db_id':item['db_id'],'gold_sql':item['query'],
                   'plan_raw':plan_raw,'plan_parsed':plan_parsed,'plan_valid':plan_valid,'plan_error':plan_error,
                   'generated_raw':generated_raw,'generated_sql':generated_sql,
                   'executable':ex_,'execution_match':m,'error_type':et,'error_message':em,
                   'selected_tables':link['selected_tables'],
                   'schema_reduction_ratio':link['reduction_ratio']}
            recs.append(rec)
            (OUTPUTS/'predictions'/'b2v1_multidb30_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in recs), encoding='utf-8')
            task_log(f'  B2v1 {i:>2} {item["db_id"]:<28} plan_valid={plan_valid} exec={ex_} match={m} err={et!r}')
        avg = sum(r['schema_reduction_ratio'] for r in recs)/len(recs)
        s = write_run('b2v1_multidb30', recs, t0,
                      {'quantization':'4bit_bitsandbytes_config','schema_strategy':'lexical_schema_linking',
                       'planner':'json_plan_v1 + patches',
                       'plan_valid_count':sum(1 for r in recs if r['plan_valid']),
                       'plan_parse_failures':sum(1 for r in recs if r['plan_parsed'] is None),
                       'avg_reduction_ratio':avg})
        task_log(f'B2v1_multidb30_DONE EX={s["ex"]:.4f}')

        # --- B3_v1 ---
        task_log('=== B3_v1 multidb_30 ===')
        recs = []; t0 = time.time()
        for i, item in enumerate(items):
            link = lexical_schema_linking(item['question'], item['db_id'], tables_map)
            tobj = tables_map[item['db_id']]
            ctx = b3v1.adaptive_b3_context(item['db_id'], link, tobj, for_planner=True)
            plan_raw=''; plan_parsed=None; plan_valid=False; plan_error=''
            try:
                pp = b3v1.make_b3v1_plan_prompt(item['question'], ctx)
                plan_raw = gen(pp, max_new=320)[0]
                plan_parsed, plan_valid, plan_error = b2v1.parse_and_validate_plan(plan_raw, plan_schema_v1)
            except Exception as exc:
                plan_error = f'planner_failed: {type(exc).__name__}: {exc}'
            generated_raw=''; generated_sql=''
            ex_=False; m=False; et=''; em=''
            if plan_valid:
                try:
                    sp = b3v1.make_b3v1_sql_prompt(item['question'], plan_parsed, ctx)
                    generated_raw = gen(sp, max_new=192)[0]
                    generated_sql = extract_sql(generated_raw)
                    ex_, m, et, em, _ = evaluate(item, generated_sql)
                except Exception as exc:
                    et, em = 'sql_gen_failed', f'{type(exc).__name__}: {exc}'
            else:
                et='plan_invalid'; em=plan_error
            rec = {'idx':i,'question':item['question'],'db_id':item['db_id'],'gold_sql':item['query'],
                   'plan_raw':plan_raw,'plan_parsed':plan_parsed,'plan_valid':plan_valid,'plan_error':plan_error,
                   'generated_raw':generated_raw,'generated_sql':generated_sql,
                   'executable':ex_,'execution_match':m,'error_type':et,'error_message':em,
                   'selected_tables':link['selected_tables'],
                   'schema_reduction_ratio':link['reduction_ratio'],
                   'knowledge_enabled':len(tobj.get('table_names_original') or tobj.get('table_names') or []) >= 5}
            recs.append(rec)
            (OUTPUTS/'predictions'/'b3v1_multidb30_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in recs), encoding='utf-8')
            task_log(f'  B3v1 {i:>2} {item["db_id"]:<28} plan_valid={plan_valid} exec={ex_} match={m} err={et!r}')
        avg = sum(r['schema_reduction_ratio'] for r in recs)/len(recs)
        s = write_run('b3v1_multidb30', recs, t0,
                      {'quantization':'4bit_bitsandbytes_config',
                       'schema_strategy':'adaptive_dual_retrieval',
                       'planner':'json_plan_v1 + patches',
                       'plan_valid_count':sum(1 for r in recs if r['plan_valid']),
                       'plan_parse_failures':sum(1 for r in recs if r['plan_parsed'] is None),
                       'avg_reduction_ratio':avg,
                       'knowledge_enabled_count':sum(1 for r in recs if r['knowledge_enabled'])})
        task_log(f'B3v1_multidb30_DONE EX={s["ex"]:.4f}')

        # --- B4_final ---
        task_log('=== B4_final multidb_30 ===')
        recs = []; t0 = time.time()
        repaired = 0; rejected_unsafe = 0
        for i, item in enumerate(items):
            link = lexical_schema_linking(item['question'], item['db_id'], tables_map)
            tobj = tables_map[item['db_id']]
            ctx = b3v1.adaptive_b3_context(item['db_id'], link, tobj, for_planner=True)
            plan_raw=''; plan_parsed=None; plan_valid=False; plan_error=''
            try:
                pp = b3v1.make_b3v1_plan_prompt(item['question'], ctx)
                plan_raw = gen(pp, max_new=320)[0]
                plan_parsed, plan_valid, plan_error = b2v1.parse_and_validate_plan(plan_raw, plan_schema_v1)
            except Exception as exc:
                plan_error = f'planner_failed: {type(exc).__name__}: {exc}'
            cand_results = []; cand_safe = []; generated_sql=''
            ex_=False; m=False; et=''; em=''; rep=False; sel=''
            if plan_valid:
                try:
                    sp = b3v1.make_b3v1_sql_prompt(item['question'], plan_parsed, ctx)
                    raw_cands = gen(sp, max_new=192, num_return_sequences=3, do_sample=True,
                                    temperature=0.7, top_p=0.95)
                    parsed_cands = [extract_sql(r) for r in raw_cands]
                    safe_cands = []
                    for sql in parsed_cands:
                        ok, reason = b4f.is_safe_select(sql)
                        cand_safe.append({'sql':sql[:200],'ok':ok,'reason':reason})
                        if not ok: rejected_unsafe += 1; continue
                        safe_cands.append(sql)
                    for sql in safe_cands:
                        a, b, c, d, rows = evaluate(item, sql)
                        cand_results.append((sql, a, rows or [], c))
                    chosen, sel = b4f.consistency_pick(cand_results)
                    generated_sql = chosen or ''
                    if not any(a for _, a, _, _ in cand_results):
                        if cand_results:
                            prev = cand_results[0][0]; err = cand_results[0][3] or 'no_executable'
                        else:
                            prev = (parsed_cands[0] if parsed_cands else ''); err = 'all_unsafe'
                        rp = b4f.make_repair_prompt(item['question'], plan_parsed, ctx, prev, err)
                        rraw = gen(rp, max_new=192, num_return_sequences=1, do_sample=False)[0]
                        rsql = extract_sql(rraw)
                        ok, reason = b4f.is_safe_select(rsql)
                        if ok:
                            a, b, c, d, _ = evaluate(item, rsql)
                            if a:
                                generated_sql = rsql; ex_=True; m=b; et=c if not b else ''; em=d
                                rep=True; sel='repair_succeeded'; repaired += 1
                            else:
                                ex_=False; m=False; et='no_executable_after_repair'; em=d
                        else:
                            ex_=False; et=f'repair_unsafe:{reason}'
                    else:
                        a, b, c, d, _ = evaluate(item, generated_sql)
                        ex_=a; m=b; et=c; em=d
                except Exception as exc:
                    et='sql_gen_failed'; em=f'{type(exc).__name__}: {exc}'
            else:
                et='plan_invalid'; em=plan_error
            rec = {'idx':i,'question':item['question'],'db_id':item['db_id'],'gold_sql':item['query'],
                   'plan_raw':plan_raw,'plan_parsed':plan_parsed,'plan_valid':plan_valid,'plan_error':plan_error,
                   'generated_sql':generated_sql,
                   'cand_safe_flags':cand_safe,
                   'cand_results':[{'sql':s[:200],'executable':a,'error_type':c} for s,a,_,c in cand_results],
                   'selection_reason':sel,'repaired':rep,
                   'executable':ex_,'execution_match':m,'error_type':et,'error_message':em,
                   'selected_tables':link['selected_tables'],
                   'schema_reduction_ratio':link['reduction_ratio']}
            recs.append(rec)
            (OUTPUTS/'predictions'/'b4_final_multidb30_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in recs), encoding='utf-8')
            task_log(f'  B4f {i:>2} {item["db_id"]:<28} plan_valid={plan_valid} cand={len(cand_results)} chosen={sel!r} exec={ex_} match={m} err={et!r}')
        avg = sum(r['schema_reduction_ratio'] for r in recs)/len(recs)
        s = write_run('b4_final_multidb30', recs, t0,
                      {'quantization':'4bit_bitsandbytes_config',
                       'schema_strategy':'adaptive_dual_retrieval',
                       'planner':'json_plan_v1 + patches',
                       'plan_valid_count':sum(1 for r in recs if r['plan_valid']),
                       'plan_parse_failures':sum(1 for r in recs if r['plan_parsed'] is None),
                       'multi_candidate':3,'repair_max':1,
                       'repaired_count':repaired,'rejected_unsafe_total':rejected_unsafe,
                       'avg_reduction_ratio':avg})
        task_log(f'B4f_multidb30_DONE EX={s["ex"]:.4f} repaired={repaired} rejected={rejected_unsafe}')

        task_log('MULTIDB30_5B_BG_DONE')
    except Exception:
        task_log('MULTIDB30_5B_BG_FAILED')
        task_log(traceback.format_exc())


MULTIDB30_5B_BG_THREAD = threading.Thread(target=background_main, name='multidb30-5b-bg', daemon=True)
MULTIDB30_5B_BG_THREAD.start()
print('STARTED=True thread=multidb30-5b-bg')
print(f'TASK_LOG={TASK_LOG}')
