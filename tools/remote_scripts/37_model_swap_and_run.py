# Stage 5: model swap (free Qwen Coder, load second model) + B0/B1 smoke10.
# Fallback chain: Llama-3.1-8B-Instruct (gated, may fail) -> Qwen2.5-7B-Instruct
# (non-Coder, non-gated; cleanest size-matched comparator).

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
TASK_LOG = OUTPUTS / 'logs' / 'model_swap_bg_task_log.txt'

mm = sys.modules['__main__']
def _from_main(name): return getattr(mm, name, None)

if 'MODEL_SWAP_BG_THREAD' in globals() and MODEL_SWAP_BG_THREAD.is_alive():
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
        task_log('MODEL_SWAP_BG_START')

        # ---- free current model ----
        import torch
        old_model = mm.__dict__.get('model')
        old_tok = mm.__dict__.get('tokenizer')
        if old_model is not None:
            del old_model
        if old_tok is not None:
            del old_tok
        if 'model' in mm.__dict__: del mm.__dict__['model']
        if 'tokenizer' in mm.__dict__: del mm.__dict__['tokenizer']
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        task_log(f'freed prior model; VRAM={torch.cuda.memory_allocated()//(1024*1024)} MB')

        # ---- try candidate models in order ----
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        candidates = [
            'meta-llama/Llama-3.1-8B-Instruct',
            'Qwen/Qwen2.5-7B-Instruct',         # non-Coder, non-gated, same family
            'mistralai/Mistral-7B-Instruct-v0.3',
        ]
        loaded_id = None
        new_model = None
        new_tok = None
        for mid in candidates:
            try:
                task_log(f'trying to load: {mid}')
                tok = AutoTokenizer.from_pretrained(mid, trust_remote_code=True)
                qcfg = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                                          bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
                m = AutoModelForCausalLM.from_pretrained(mid, trust_remote_code=True,
                                                         device_map='auto', quantization_config=qcfg)
                m.eval()
                new_model = m; new_tok = tok; loaded_id = mid
                task_log(f'LOADED {mid}, VRAM={torch.cuda.memory_allocated()//(1024*1024)} MB')
                break
            except Exception as exc:
                task_log(f'FAILED to load {mid}: {type(exc).__name__}: {str(exc)[:200]}')
                continue

        if new_model is None:
            task_log('MODEL_SWAP_BG_FAILED no candidate model loaded')
            return

        # promote into main scope (bridge globals helpers reference mm.model)
        mm.__dict__['model'] = new_model
        mm.__dict__['tokenizer'] = new_tok

        # ---- helpers (use main scope's ones) ----
        make_prompt = _from_main('make_prompt')
        make_b1_prompt = _from_main('make_b1_prompt')
        lexical_schema_linking = _from_main('lexical_schema_linking')
        extract_sql = _from_main('extract_sql')
        execute_sql = _from_main('execute_sql')
        tables_map = _from_main('tables_map')
        db_paths = _from_main('db_paths')
        FunctionTimedOut = _from_main('FunctionTimedOut')

        smoke10 = json.loads((SPIDER_DIR/'subsets'/'smoke_10.json').read_text(encoding='utf-8'))

        def gen(prompt, max_new=192):
            messages = [{'role':'user','content':prompt}]
            rendered = new_tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = new_tok(rendered, return_tensors='pt')
            inputs = {k: v.to(new_model.device) for k,v in inputs.items()}
            with torch.no_grad():
                out = new_model.generate(**inputs, max_new_tokens=max_new, do_sample=False,
                                         pad_token_id=new_tok.eos_token_id)
            return new_tok.decode(out[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)

        def evaluate(item, sql):
            executable, match = False, False
            err_t, err_m = '', ''
            try:
                pred = execute_sql(db_paths[item['db_id']], sql)
                executable = True
                gold = execute_sql(db_paths[item['db_id']], item['query'])
                match = sorted(pred) == sorted(gold)
                if not match: err_t = 'result_mismatch'
            except FunctionTimedOut as exc:
                err_t, err_m = 'timeout', repr(exc)
            except Exception as exc:
                err_t, err_m = type(exc).__name__, str(exc)
            return executable, match, err_t, err_m

        def write_run(prefix, records, started, extra_kvs):
            pred_p = OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl'
            metr_p = OUTPUTS/'metrics'/f'{prefix}_metrics.csv'
            sum_p = OUTPUTS/'tables'/f'{prefix}_summary.csv'
            run_p = OUTPUTS/'logs'/f'{prefix}_runlog.txt'
            err_p = OUTPUTS/'tables'/f'{prefix}_error_cases.md'
            ex_p = OUTPUTS/'tables'/f'{prefix}_examples.md'
            pred_p.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in records), encoding='utf-8')
            total = len(records)
            exec_count = sum(1 for r in records if r['executable'])
            match_count = sum(1 for r in records if r['execution_match'])
            ex = match_count / total if total else 0.0
            base = {'run_id': prefix, 'model': loaded_id, 'subset': 'smoke_10', 'n': total,
                    'execution_match_count': match_count, 'ex': ex, 'executable_count': exec_count}
            base.update(extra_kvs)
            with metr_p.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=list(base.keys())); w.writeheader(); w.writerow(base)
            with sum_p.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=['metric','value']); w.writeheader()
                for k,v in [('completed','true'),('EX',ex),('executable_count',exec_count),('total',total),
                            ('model',loaded_id),('subset','smoke_10')]+list(extra_kvs.items()):
                    w.writerow({'metric':k,'value':v})
            run_p.write_text(textwrap.dedent(f'''
            {prefix} run log
            checked_at: {dt.datetime.now(dt.timezone.utc).isoformat()}
            model: {loaded_id}
            subset: smoke_10
            total: {total}
            executable_count: {exec_count}
            execution_match_count: {match_count}
            EX: {ex}
            elapsed_seconds: {time.time()-started:.2f}
            ''').strip()+'\n', encoding='utf-8')
            cols = ['idx','question','db_id','generated_sql','executable','execution_match','error_type']
            err_p.write_text(f'# {prefix} Error Cases\n\n'+_md([records[i] for i in range(len(records)) if not records[i]['execution_match']], cols), encoding='utf-8')
            ex_p.write_text(f'# {prefix} Examples\n\n'+_md(records[:5], cols), encoding='utf-8')
            return base

        def _md(rows, cols):
            rows = list(rows)
            lines = ['|'+'|'.join(cols)+'|', '|'+'|'.join(['---']*len(cols))+'|']
            for r in rows:
                v = []
                for c in cols:
                    x = r.get(c,'')
                    if isinstance(x,(list,dict)): x = json.dumps(x, ensure_ascii=False)
                    v.append(str(x).replace('|','\\|').replace('\n','<br>')[:700])
                lines.append('|'+'|'.join(v)+'|')
            return '\n'.join(lines)+'\n'

        # ---- B0 with new model ----
        task_log(f'=== B0 smoke10 with {loaded_id} ===')
        b0_records = []
        t0 = time.time()
        prefix_safe = loaded_id.replace('/','_').replace('-','_').lower()
        for i, item in enumerate(smoke10):
            try:
                p = make_prompt(item)
                raw = gen(p, max_new=192)
                sql = extract_sql(raw)
                ex, match, et, em = evaluate(item, sql)
            except Exception as exc:
                raw, sql = '', ''
                ex, match = False, False
                et, em = 'gen_failed', f'{type(exc).__name__}: {exc}'
            rec = {'idx':i,'question':item['question'],'db_id':item['db_id'],
                   'gold_sql':item['query'],'generated_raw':raw,'generated_sql':sql,
                   'executable':ex,'execution_match':match,
                   'error_type':et,'error_message':em}
            b0_records.append(rec)
            (OUTPUTS/'predictions'/f'b0_{prefix_safe}_smoke10_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in b0_records), encoding='utf-8')
            task_log(f'  B0[{loaded_id}] {i:>2} {item["db_id"]:<25} exec={ex} match={match} err={et!r}')
        b0_summary = write_run(f'b0_{prefix_safe}_smoke10', b0_records, t0,
                               {'quantization':'4bit_bitsandbytes_config','schema_strategy':'full_schema',
                                'comparator_role':'cross_model_baseline'})
        task_log(f'B0[{loaded_id}]_DONE EX={b0_summary["ex"]:.4f}')

        # ---- B1 with new model ----
        task_log(f'=== B1 smoke10 with {loaded_id} ===')
        b1_records = []
        t0 = time.time()
        for i, item in enumerate(smoke10):
            link = lexical_schema_linking(item['question'], item['db_id'], tables_map)
            try:
                p = make_b1_prompt(item, link)
                raw = gen(p, max_new=192)
                sql = extract_sql(raw)
                ex, match, et, em = evaluate(item, sql)
            except Exception as exc:
                raw, sql = '', ''
                ex, match = False, False
                et, em = 'gen_failed', f'{type(exc).__name__}: {exc}'
            rec = {'idx':i,'question':item['question'],'db_id':item['db_id'],
                   'gold_sql':item['query'],'generated_raw':raw,'generated_sql':sql,
                   'executable':ex,'execution_match':match,
                   'error_type':et,'error_message':em,
                   'selected_tables':link['selected_tables'],
                   'schema_reduction_ratio':link['reduction_ratio'],
                   'fallback_used':link['fallback_used']}
            b1_records.append(rec)
            (OUTPUTS/'predictions'/f'b1_{prefix_safe}_smoke10_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in b1_records), encoding='utf-8')
            task_log(f'  B1[{loaded_id}] {i:>2} {item["db_id"]:<25} sel={len(link["selected_tables"])} exec={ex} match={match} err={et!r}')
        avg_red = sum(r['schema_reduction_ratio'] for r in b1_records)/len(b1_records)
        b1_summary = write_run(f'b1_{prefix_safe}_smoke10', b1_records, t0,
                               {'quantization':'4bit_bitsandbytes_config','schema_strategy':'lexical_schema_linking',
                                'avg_reduction_ratio':avg_red,
                                'comparator_role':'cross_model_baseline'})
        task_log(f'B1[{loaded_id}]_DONE EX={b1_summary["ex"]:.4f}')

        task_log(f'COMPARATOR_MODEL_LOADED={loaded_id}')
        task_log('MODEL_SWAP_BG_DONE')
    except Exception:
        task_log('MODEL_SWAP_BG_FAILED')
        task_log(traceback.format_exc())


MODEL_SWAP_BG_THREAD = threading.Thread(target=background_main, name='model-swap-bg', daemon=True)
MODEL_SWAP_BG_THREAD.start()
print('STARTED=True thread=model-swap-bg')
print(f'TASK_LOG={TASK_LOG}')
