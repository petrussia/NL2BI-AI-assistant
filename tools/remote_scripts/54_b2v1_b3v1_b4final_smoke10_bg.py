# Unified BG: swap to Qwen2.5-Coder-7B-Instruct, then run
# B2_v1, B3_v1, B4_final on smoke10 in sequence. Saves per-baseline artefacts.

import csv
import datetime as dt
import gc
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
TASK_LOG = OUTPUTS / 'logs' / 'b2v1_b3v1_b4final_bg_task_log.txt'

mm = sys.modules['__main__']
def _from_main(name): return getattr(mm, name, None)

if 'B2_B3_B4_BG_THREAD' in globals() and B2_B3_B4_BG_THREAD.is_alive():
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
        task_log('B2_B3_B4_BG_START')

        # ===== Swap to Qwen-Coder =====
        import torch
        cur_model = mm.__dict__.get('model'); cur_tok = mm.__dict__.get('tokenizer')
        cur_model_id = getattr(cur_model, 'name_or_path', '') if cur_model else None
        if cur_model_id != MODEL_ID:
            task_log(f'swapping model: {cur_model_id} -> {MODEL_ID}')
            if cur_model is not None: del cur_model
            if cur_tok is not None: del cur_tok
            for k in ('model','tokenizer'):
                if k in mm.__dict__: del mm.__dict__[k]
            gc.collect(); torch.cuda.empty_cache(); torch.cuda.synchronize()
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
            tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
            qcfg = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                                      bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
            new_model = AutoModelForCausalLM.from_pretrained(MODEL_ID, trust_remote_code=True,
                                                             device_map='auto', quantization_config=qcfg)
            new_model.eval()
            mm.__dict__['model'] = new_model; mm.__dict__['tokenizer'] = tok
            task_log(f'loaded {MODEL_ID}; VRAM={torch.cuda.memory_allocated()//(1024*1024)} MB')
        else:
            task_log(f'model already {MODEL_ID}; skipping swap')

        model = mm.__dict__['model']; tokenizer = mm.__dict__['tokenizer']

        # Imports of helpers
        eval_path = str(REPO / 'src' / 'evaluation')
        if eval_path not in sys.path: sys.path.insert(0, eval_path)
        for mod in ('baselines_b2_v1','baselines_b3_v1','baselines_b4_final','query_analysis'):
            if mod in sys.modules: del sys.modules[mod]
        import baselines_b2_v1 as b2v1
        import baselines_b3_v1 as b3v1
        import baselines_b4_final as b4f
        import query_analysis as qa

        tables_map = _from_main('tables_map'); db_paths = _from_main('db_paths')
        lexical_schema_linking = _from_main('lexical_schema_linking')
        build_reduced_schema_context = _from_main('build_reduced_schema_context')
        extract_sql = _from_main('extract_sql'); execute_sql = _from_main('execute_sql')
        FunctionTimedOut = _from_main('FunctionTimedOut')

        smoke10 = json.loads((SPIDER_DIR/'subsets'/'smoke_10.json').read_text(encoding='utf-8'))
        plan_schema_v1 = json.loads((REPO/'docs'/'plan_schema_v1.json').read_text(encoding='utf-8'))

        def gen(prompt, max_new=192, num_return_sequences=1, do_sample=False, temperature=1.0, top_p=1.0):
            messages = [{'role':'user','content':prompt}]
            rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(rendered, return_tensors='pt')
            inputs = {k:v.to(model.device) for k,v in inputs.items()}
            kwargs = dict(max_new_tokens=max_new, pad_token_id=tokenizer.eos_token_id)
            if do_sample:
                kwargs.update(do_sample=True, temperature=temperature, top_p=top_p,
                              num_return_sequences=num_return_sequences)
            else:
                kwargs.update(do_sample=False)
            with torch.no_grad():
                out = model.generate(**inputs, **kwargs)
            n_in = inputs['input_ids'].shape[1]
            return [tokenizer.decode(seq[n_in:], skip_special_tokens=True) for seq in out]

        def evaluate_one(item, sql, db_for_pred=None):
            executable, match = False, False
            err_t, err_m, rows = '', '', None
            try:
                rows = execute_sql(db_paths[db_for_pred or item['db_id']], sql)
                executable = True
                gold = execute_sql(db_paths[item['db_id']], item['query'])
                match = sorted(rows) == sorted(gold)
                if not match: err_t = 'result_mismatch'
            except FunctionTimedOut as exc:
                err_t, err_m = 'timeout', repr(exc)
            except Exception as exc:
                err_t, err_m = type(exc).__name__, str(exc)
            return executable, match, err_t, err_m, rows

        def _md(rows, cols):
            lines = ['|'+'|'.join(cols)+'|', '|'+'|'.join(['---']*len(cols))+'|']
            for r in rows:
                v = []
                for c in cols:
                    x = r.get(c, '')
                    if isinstance(x,(list,dict)): x = json.dumps(x, ensure_ascii=False)
                    v.append(str(x).replace('|','\\|').replace('\n','<br>')[:700])
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
            base = {'run_id':prefix,'model':MODEL_ID,'subset':'smoke_10','n':total,
                    'execution_match_count':match_count,'ex':ex,'executable_count':exec_count}
            base.update(extra_kvs)
            with metr_p.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=list(base.keys())); w.writeheader(); w.writerow(base)
            with sum_p.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=['metric','value']); w.writeheader()
                for k,v in [('completed','true'),('EX',ex),('executable_count',exec_count),('total',total),
                            ('model',MODEL_ID),('subset','smoke_10')]+list(extra_kvs.items()):
                    w.writerow({'metric':k,'value':v})
            run_p.write_text(textwrap.dedent(f'''
            {prefix} run log
            checked_at: {dt.datetime.now(dt.timezone.utc).isoformat()}
            model: {MODEL_ID}
            subset: smoke_10
            total: {total}; exec_count: {exec_count}; match_count: {match_count}; EX: {ex}
            elapsed_seconds: {time.time()-started:.2f}
            extra: {json.dumps(extra_kvs, ensure_ascii=False)}
            ''').strip()+'\n', encoding='utf-8')
            cols = ['idx','question','db_id','generated_sql','executable','execution_match','error_type']
            if any('plan_valid' in r for r in records): cols.insert(3, 'plan_valid')
            err_rows = [r for r in records if not r['execution_match']]
            err_p.write_text(f'# {prefix} Error Cases\n\n'+_md(err_rows[:25], cols), encoding='utf-8')
            ex_p.write_text(f'# {prefix} Examples\n\n'+_md(records[:5], cols), encoding='utf-8')
            return base

        # ===== B2_v1 smoke10 =====
        task_log('=== B2_v1 smoke10 ===')
        b2v1_records = []; t0 = time.time()
        for i, item in enumerate(smoke10):
            link = lexical_schema_linking(item['question'], item['db_id'], tables_map)
            reduced_ctx = build_reduced_schema_context(item['db_id'], link['selected_table_indexes'], tables_map)
            plan_raw=''; plan_parsed=None; plan_valid=False; plan_error=''
            try:
                pp = b2v1.make_plan_prompt(item['question'], reduced_ctx)
                plan_raw = gen(pp, max_new=320)[0]
                plan_parsed, plan_valid, plan_error = b2v1.parse_and_validate_plan(plan_raw, plan_schema_v1)
            except Exception as exc:
                plan_error = f'planner_failed: {type(exc).__name__}: {exc}'
            generated_raw=''; generated_sql=''; executable=False; execution_match=False
            error_type=''; error_message=''
            if plan_valid:
                try:
                    sp = b2v1.make_plan_to_sql_prompt(item['question'], plan_parsed, reduced_ctx)
                    generated_raw = gen(sp, max_new=192)[0]
                    generated_sql = extract_sql(generated_raw)
                    executable, execution_match, error_type, error_message, _ = evaluate_one(item, generated_sql)
                except Exception as exc:
                    error_type, error_message = 'sql_gen_failed', f'{type(exc).__name__}: {exc}'
            else:
                error_type='plan_invalid'; error_message=plan_error
            rec = {'idx':i,'question':item['question'],'db_id':item['db_id'],'gold_sql':item['query'],
                   'plan_raw':plan_raw,'plan_parsed':plan_parsed,'plan_valid':plan_valid,'plan_error':plan_error,
                   'generated_raw':generated_raw,'generated_sql':generated_sql,
                   'executable':executable,'execution_match':execution_match,
                   'error_type':error_type,'error_message':error_message,
                   'selected_tables':link['selected_tables'],
                   'schema_reduction_ratio':link['reduction_ratio']}
            b2v1_records.append(rec)
            (OUTPUTS/'predictions'/'b2v1_spider_smoke10_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in b2v1_records), encoding='utf-8')
            task_log(f'  B2v1 {i:>2} {item["db_id"]:<25} plan_valid={plan_valid} exec={executable} match={execution_match} err={error_type!r}')
        s = write_run('b2v1_spider_smoke10', b2v1_records, t0,
                      {'quantization':'4bit_bitsandbytes_config','schema_strategy':'lexical_schema_linking',
                       'planner':'json_plan_v1 + patches',
                       'plan_valid_count':sum(1 for r in b2v1_records if r['plan_valid']),
                       'plan_parse_failures':sum(1 for r in b2v1_records if r['plan_parsed'] is None),
                       'avg_reduction_ratio':sum(r['schema_reduction_ratio'] for r in b2v1_records)/len(b2v1_records)})
        task_log(f'B2v1_DONE EX={s["ex"]:.4f}')

        # ===== B3_v1 smoke10 =====
        task_log('=== B3_v1 smoke10 ===')
        b3v1_records = []; t0 = time.time()
        for i, item in enumerate(smoke10):
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
            generated_raw=''; generated_sql=''; executable=False; execution_match=False
            error_type=''; error_message=''
            if plan_valid:
                try:
                    sp = b3v1.make_b3v1_sql_prompt(item['question'], plan_parsed, ctx)
                    generated_raw = gen(sp, max_new=192)[0]
                    generated_sql = extract_sql(generated_raw)
                    executable, execution_match, error_type, error_message, _ = evaluate_one(item, generated_sql)
                except Exception as exc:
                    error_type, error_message = 'sql_gen_failed', f'{type(exc).__name__}: {exc}'
            else:
                error_type='plan_invalid'; error_message=plan_error
            rec = {'idx':i,'question':item['question'],'db_id':item['db_id'],'gold_sql':item['query'],
                   'plan_raw':plan_raw,'plan_parsed':plan_parsed,'plan_valid':plan_valid,'plan_error':plan_error,
                   'generated_raw':generated_raw,'generated_sql':generated_sql,
                   'executable':executable,'execution_match':execution_match,
                   'error_type':error_type,'error_message':error_message,
                   'selected_tables':link['selected_tables'],
                   'schema_reduction_ratio':link['reduction_ratio'],
                   'knowledge_enabled': len(tables_map[item['db_id']].get('table_names_original') or []) >= 5}
            b3v1_records.append(rec)
            (OUTPUTS/'predictions'/'b3v1_spider_smoke10_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in b3v1_records), encoding='utf-8')
            task_log(f'  B3v1 {i:>2} {item["db_id"]:<25} plan_valid={plan_valid} exec={executable} match={execution_match} err={error_type!r}')
        # B3v1 retrieval examples
        ex_md = ['# B3_v1 Retrieval Examples (smoke10, first 5)\n']
        for i, rec in enumerate(b3v1_records[:5]):
            tobj = tables_map[rec['db_id']]
            ctx = b3v1.adaptive_b3_context(rec['db_id'],
                                           lexical_schema_linking(rec['question'], rec['db_id'], tables_map),
                                           tobj, for_planner=True)
            ex_md.append(f"## idx {rec['idx']} db={rec['db_id']}\n- Question: {rec['question']}\n- knowledge_enabled: {rec['knowledge_enabled']}\n```\n{ctx}\n```\n")
        (OUTPUTS/'tables'/'b3v1_retrieval_examples.md').write_text('\n'.join(ex_md), encoding='utf-8')

        s = write_run('b3v1_spider_smoke10', b3v1_records, t0,
                      {'quantization':'4bit_bitsandbytes_config',
                       'schema_strategy':'adaptive_dual_retrieval (knowledge OFF when <5 tables)',
                       'planner':'json_plan_v1 + patches (compact prompt)',
                       'plan_valid_count':sum(1 for r in b3v1_records if r['plan_valid']),
                       'plan_parse_failures':sum(1 for r in b3v1_records if r['plan_parsed'] is None),
                       'avg_reduction_ratio':sum(r['schema_reduction_ratio'] for r in b3v1_records)/len(b3v1_records),
                       'knowledge_enabled_count':sum(1 for r in b3v1_records if r['knowledge_enabled'])})
        task_log(f'B3v1_DONE EX={s["ex"]:.4f}')

        # ===== B4_final smoke10 =====
        task_log('=== B4_final smoke10 ===')
        b4f_records = []; t0 = time.time()
        repaired_count = 0; rejected_unsafe_total = 0
        b4f_examples = []
        for i, item in enumerate(smoke10):
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
            cand_results = []; cand_safe_flags = []; generated_sql = ''
            executable=False; execution_match=False; error_type=''; error_message=''
            repaired = False; selection_reason = ''
            if plan_valid:
                try:
                    sp = b3v1.make_b3v1_sql_prompt(item['question'], plan_parsed, ctx)
                    raw_candidates = gen(sp, max_new=192, num_return_sequences=3, do_sample=True,
                                         temperature=0.7, top_p=0.95)
                    parsed_candidates = [extract_sql(r) for r in raw_candidates]
                    safe_candidates = []
                    for sql in parsed_candidates:
                        ok, reason = b4f.is_safe_select(sql)
                        cand_safe_flags.append({'sql':sql[:200],'ok':ok,'reason':reason})
                        if not ok: rejected_unsafe_total += 1; continue
                        safe_candidates.append(sql)
                    for sql in safe_candidates:
                        ex_, em_, et_, emsg_, rows = evaluate_one(item, sql)
                        cand_results.append((sql, ex_, rows or [], et_))
                    chosen, selection_reason = b4f.consistency_pick(cand_results)
                    generated_sql = chosen or ''
                    if not any(ex_ for _, ex_, _, _ in cand_results):
                        # repair
                        if cand_results:
                            prev_sql = cand_results[0][0]; err = cand_results[0][3] or 'no_executable'
                        else:
                            prev_sql = (parsed_candidates[0] if parsed_candidates else ''); err = 'all_unsafe'
                        rep_prompt = b4f.make_repair_prompt(item['question'], plan_parsed, ctx, prev_sql, err)
                        rep_raw = gen(rep_prompt, max_new=192, num_return_sequences=1, do_sample=False)[0]
                        rep_sql = extract_sql(rep_raw)
                        ok, reason = b4f.is_safe_select(rep_sql)
                        if ok:
                            ex_, em_, et_, emsg_, _ = evaluate_one(item, rep_sql)
                            if ex_:
                                generated_sql = rep_sql; executable=True; execution_match = em_
                                error_type = et_ if not em_ else ''; error_message = emsg_
                                repaired=True; selection_reason='repair_succeeded'; repaired_count += 1
                            else:
                                executable=False; execution_match=False
                                error_type='no_executable_after_repair'; error_message=emsg_
                        else:
                            executable=False; error_type=f'repair_unsafe:{reason}'
                    else:
                        ex_, em_, et_, emsg_, _ = evaluate_one(item, generated_sql)
                        executable=ex_; execution_match=em_; error_type=et_; error_message=emsg_
                except Exception as exc:
                    error_type='sql_gen_failed'; error_message=f'{type(exc).__name__}: {exc}'
            else:
                error_type='plan_invalid'; error_message=plan_error
            if i < 5:
                b4f_examples.append({'idx':i,'db_id':item['db_id'],'question':item['question'],
                                     'cand_safe_flags':cand_safe_flags,
                                     'cand_results':[{'sql':s[:200],'executable':ex_,'error_type':et_}
                                                     for s,ex_,_,et_ in cand_results],
                                     'chosen_sql':generated_sql[:200],
                                     'selection_reason':selection_reason,'repaired':repaired})
            rec = {'idx':i,'question':item['question'],'db_id':item['db_id'],'gold_sql':item['query'],
                   'plan_raw':plan_raw,'plan_parsed':plan_parsed,'plan_valid':plan_valid,'plan_error':plan_error,
                   'generated_sql':generated_sql,
                   'cand_safe_flags':cand_safe_flags,
                   'cand_results':[{'sql':s[:200],'executable':ex_,'error_type':et_} for s,ex_,_,et_ in cand_results],
                   'selection_reason':selection_reason,'repaired':repaired,
                   'executable':executable,'execution_match':execution_match,
                   'error_type':error_type,'error_message':error_message,
                   'selected_tables':link['selected_tables'],
                   'schema_reduction_ratio':link['reduction_ratio']}
            b4f_records.append(rec)
            (OUTPUTS/'predictions'/'b4_final_spider_smoke10_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in b4f_records), encoding='utf-8')
            task_log(f'  B4f {i:>2} {item["db_id"]:<25} plan_valid={plan_valid} cand={len(cand_results)} chosen={selection_reason!r} exec={executable} match={execution_match} err={error_type!r}')
        # B4_final candidate examples
        sel_md = ['# B4_final Candidate Examples (smoke10, first 5)\n']
        for ex in b4f_examples:
            sel_md.append(f"## idx={ex['idx']} db={ex['db_id']}\n- Question: {ex['question']}\n- Safety flags:")
            for cs in ex['cand_safe_flags']:
                sel_md.append(f"  - ok={cs['ok']} reason={cs['reason']!r} sql=`{cs['sql']}`")
            sel_md.append(f"- Cand exec results:")
            for cr in ex['cand_results']:
                sel_md.append(f"  - executable={cr['executable']} error_type={cr['error_type']!r} sql=`{cr['sql']}`")
            sel_md.append(f"- Chosen: `{ex['chosen_sql']}`")
            sel_md.append(f"- Selection reason: `{ex['selection_reason']}`")
            sel_md.append(f"- Repaired: `{ex['repaired']}`")
            sel_md.append('')
        (OUTPUTS/'tables'/'b4_final_candidate_examples.md').write_text('\n'.join(sel_md), encoding='utf-8')

        s = write_run('b4_final_spider_smoke10', b4f_records, t0,
                      {'quantization':'4bit_bitsandbytes_config',
                       'schema_strategy':'adaptive_dual_retrieval',
                       'planner':'json_plan_v1 + patches',
                       'plan_valid_count':sum(1 for r in b4f_records if r['plan_valid']),
                       'plan_parse_failures':sum(1 for r in b4f_records if r['plan_parsed'] is None),
                       'multi_candidate':3,'repair_max':1,
                       'repaired_count':repaired_count,
                       'rejected_unsafe_total':rejected_unsafe_total,
                       'avg_reduction_ratio':sum(r['schema_reduction_ratio'] for r in b4f_records)/len(b4f_records)})
        task_log(f'B4f_DONE EX={s["ex"]:.4f} repaired={repaired_count} rejected={rejected_unsafe_total}')

        task_log('B2_B3_B4_BG_DONE')
    except Exception:
        task_log('B2_B3_B4_BG_FAILED')
        task_log(traceback.format_exc())


B2_B3_B4_BG_THREAD = threading.Thread(target=background_main, name='b2v1-b3v1-b4f-smoke10-bg', daemon=True)
B2_B3_B4_BG_THREAD.start()
print('STARTED=True thread=b2v1-b3v1-b4f-smoke10-bg')
print(f'TASK_LOG={TASK_LOG}')
