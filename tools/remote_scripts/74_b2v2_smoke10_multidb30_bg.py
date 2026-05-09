# Stage D2: B2_v2 BG. Uploads module then runs B2_v2 on smoke_10 and multidb_30
# using whichever Qwen-Coder model is currently loaded (works after Qwen14b BG).

import csv
import datetime as dt
import gc
import json
import os
import re
import sqlite3
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
    (OUTPUTS/sub).mkdir(parents=True, exist_ok=True)

MODEL_ID = 'Qwen/Qwen2.5-Coder-7B-Instruct'  # standardize on Coder-7B for fair comparison vs B2_v1
TASK_LOG = OUTPUTS / 'logs' / 'b2v2_bg_task_log.txt'

mm = sys.modules['__main__']
if 'B2V2_BG_THREAD' in globals() and B2V2_BG_THREAD.is_alive():
    print('BG already running'); raise SystemExit(0)

def task_log(msg):
    line = f'[{dt.datetime.now(dt.timezone.utc).isoformat()}] {msg}'
    print(line)
    with TASK_LOG.open('a', encoding='utf-8') as f:
        f.write(line+'\n')


def background_main():
    try:
        TASK_LOG.write_text('', encoding='utf-8')
        task_log('B2V2_BG_START')
        from func_timeout import FunctionTimedOut, func_timeout
        try:
            from jsonschema import Draft202012Validator
        except Exception:
            from jsonschema import Draft7Validator as Draft202012Validator

        # bootstrap helpers
        tables_map = {row['db_id']: row for row in
                      json.loads((SPIDER_DIR/'tables.json').read_text(encoding='utf-8'))}
        db_paths = {p.stem: p for p in (SPIDER_DIR/'database').rglob('*.sqlite')}
        smoke10 = json.loads((SPIDER_DIR/'subsets'/'smoke_10.json').read_text(encoding='utf-8'))
        multidb30 = json.loads((SPIDER_DIR/'subsets'/'multidb_30.json').read_text(encoding='utf-8'))
        plan_schema_v1 = json.loads((REPO/'docs'/'plan_schema_v1.json').read_text(encoding='utf-8'))
        plan_validator = Draft202012Validator(plan_schema_v1)

        STOP = {'a','an','the','of','in','on','at','for','to','from','by','with','is','are','was','were','what','which','who','whom','whose','how','many','much','show','list','find','give','me','all','each','every','any','do','does','did'}
        def _toks(s):
            parts = re.split(r'[\s_]+', str(s).lower())
            return {p for p in parts if p and p not in STOP and len(p) > 1}

        def build_full_schema(db_id):
            t = tables_map[db_id]
            tn = t.get('table_names_original') or t.get('table_names')
            cn = t.get('column_names_original') or t.get('column_names')
            by_table = {i: [] for i in range(len(tn))}
            for ti, col in cn:
                if ti >= 0: by_table.setdefault(ti, []).append(col)
            lines = [f'Database: {db_id}', 'Tables and columns:']
            for idx, name in enumerate(tn):
                lines.append(f'- {name}(' + ', '.join(by_table.get(idx, [])) + ')')
            return '\n'.join(lines)

        def lex_link(question, db_id, min_score=0.5):
            t = tables_map[db_id]
            tn = t.get('table_names_original') or t.get('table_names')
            cn = t.get('column_names_original') or t.get('column_names')
            qt = _toks(question)
            scores = {i: 0.0 for i in range(len(tn))}
            for i, name in enumerate(tn):
                scores[i] += len(qt & _toks(name)) * 2.0
            for ti, col in cn:
                if ti >= 0: scores[ti] += len(qt & _toks(col)) * 1.0
            above = [(i,s) for i,s in scores.items() if s >= min_score]
            above.sort(key=lambda x: -x[1])
            if not above:
                selected = list(range(len(tn))); fallback = True
            else:
                selected = sorted([i for i,_ in above]); fallback = False
            return {'selected_table_indexes': selected,
                    'selected_tables': [tn[i] for i in selected],
                    'reduction_ratio': len(selected)/len(tn) if tn else 1.0,
                    'fallback_used': fallback}

        def build_reduced_schema(db_id, selected_idx):
            t = tables_map[db_id]
            tn = t.get('table_names_original') or t.get('table_names')
            cn = t.get('column_names_original') or t.get('column_names')
            by_table = {i: [] for i in range(len(tn))}
            for ti, col in cn:
                if ti >= 0: by_table.setdefault(ti, []).append(col)
            lines = [f'Database: {db_id}', 'Tables and columns (reduced via lexical schema linking):']
            for idx in selected_idx:
                lines.append(f'- {tn[idx]}(' + ', '.join(by_table.get(idx, [])) + ')')
            return '\n'.join(lines)

        def make_b1_prompt(item, link):
            return textwrap.dedent(f'''
            You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
            Use only the given schema. Return SQL only, no markdown and no explanation.

            {build_reduced_schema(item["db_id"], link["selected_table_indexes"])}

            Question: {item["question"]}
            SQL:
            ''').strip()

        def extract_sql(text):
            text = text.strip()
            text = re.sub(r'^```(?:sql)?', '', text, flags=re.I).strip()
            text = re.sub(r'```$', '', text).strip()
            m = re.search(r'(?is)(select\b.*)', text)
            if m: text = m.group(1).strip()
            text = text.split('\n\n')[0].strip()
            if ';' in text: text = text.split(';', 1)[0].strip()
            return text.rstrip(';') + ';'

        def execute_sql(db_path, sql, timeout=8):
            def _run():
                con = sqlite3.connect(db_path); cur = con.cursor()
                cur.execute(sql); rows = cur.fetchall(); con.close(); return rows
            return func_timeout(timeout, _run)

        # ===== ensure Qwen-Coder-7B is loaded =====
        import torch
        cur_model = mm.__dict__.get('model')
        cur_id = getattr(cur_model, 'name_or_path', '') if cur_model else ''
        if cur_id != MODEL_ID:
            task_log(f'swapping model: {cur_id or "none"} -> {MODEL_ID}')
            for k in ('model','tokenizer'):
                if k in mm.__dict__: del mm.__dict__[k]
            del cur_model
            gc.collect(); torch.cuda.empty_cache()
            try: torch.cuda.synchronize()
            except Exception: pass
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
            tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
            qcfg = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                                      bnb_4bit_compute_dtype=torch.float16,
                                      bnb_4bit_use_double_quant=True)
            new_model = AutoModelForCausalLM.from_pretrained(
                MODEL_ID, trust_remote_code=True, device_map='auto',
                quantization_config=qcfg)
            new_model.eval()
            mm.__dict__['model'] = new_model; mm.__dict__['tokenizer'] = tok
            task_log(f'loaded {MODEL_ID}; VRAM={torch.cuda.memory_allocated()//(1024*1024)} MB')

        model = mm.__dict__['model']; tokenizer = mm.__dict__['tokenizer']

        # import b2v2 module
        eval_path = str(REPO / 'src' / 'evaluation')
        if eval_path not in sys.path: sys.path.insert(0, eval_path)
        for mod in ('baselines_b2_v2', 'baselines_b3_v2'):
            if mod in sys.modules: del sys.modules[mod]
        import baselines_b2_v2 as b2v2

        def gen(prompt, max_new=192):
            messages = [{'role':'user','content':prompt}]
            rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(rendered, return_tensors='pt')
            inputs = {k: v.to(model.device) for k,v in inputs.items()}
            with torch.no_grad():
                out = model.generate(**inputs, max_new_tokens=max_new, do_sample=False,
                                     pad_token_id=tokenizer.eos_token_id)
            return tokenizer.decode(out[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)

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

        def _md(rows, cols):
            lines = ['|'+'|'.join(cols)+'|', '|'+'|'.join(['---']*len(cols))+'|']
            for r in rows:
                v = []
                for c in cols:
                    x = r.get(c, '')
                    if isinstance(x, (list, dict)): x = json.dumps(x, ensure_ascii=False)
                    v.append(str(x).replace('|','\\|').replace('\n','<br>')[:700])
                lines.append('|'+'|'.join(v)+'|')
            return '\n'.join(lines)+'\n'

        def write_run(prefix, records, started, subset_name, extra_kvs):
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
            ex = match_count/total if total else 0.0
            base = {'run_id': prefix, 'model': MODEL_ID, 'subset': subset_name,
                    'n': total, 'execution_match_count': match_count, 'ex': ex,
                    'executable_count': exec_count}
            base.update(extra_kvs)
            with metr_p.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=list(base.keys())); w.writeheader(); w.writerow(base)
            with sum_p.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=['metric','value']); w.writeheader()
                for k,v in [('completed','true'),('EX',ex),('executable_count',exec_count),
                            ('total',total),('model',MODEL_ID),('subset',subset_name)] + list(extra_kvs.items()):
                    w.writerow({'metric':k,'value':v})
            run_p.write_text(textwrap.dedent(f'''
            {prefix} run log
            checked_at: {dt.datetime.now(dt.timezone.utc).isoformat()}
            model: {MODEL_ID}
            subset: {subset_name}
            total: {total}
            executable_count: {exec_count}
            execution_match_count: {match_count}
            EX: {ex}
            elapsed_seconds: {time.time()-started:.2f}
            ''').strip()+'\n', encoding='utf-8')
            cols = ['idx','question','db_id','generated_sql','executable','execution_match','error_type','path']
            err_p.write_text(f'# {prefix} Error Cases\n\n' +
                             _md([records[i] for i in range(len(records)) if not records[i]['execution_match']], cols),
                             encoding='utf-8')
            ex_p.write_text(f'# {prefix} Examples\n\n' + _md(records[:5], cols), encoding='utf-8')
            return base

        def b1_fallback(item):
            link = lex_link(item['question'], item['db_id'])
            raw = gen(make_b1_prompt(item, link))
            return extract_sql(raw)

        def run_b2v2(items, subset_name, prefix):
            task_log(f'=== B2_v2 {subset_name} ===')
            t0 = time.time(); recs = []
            for i, item in enumerate(items):
                full_schema = build_full_schema(item['db_id'])
                path = ''; plan_obj = None; plan_err = ''
                sql = ''
                try:
                    plan_prompt = b2v2.make_b2v2_plan_prompt(item['question'], full_schema)
                    raw_plan = gen(plan_prompt, max_new=256)
                    plan_obj, plan_err = b2v2.parse_plan_json(raw_plan)
                    if plan_obj is not None:
                        try:
                            plan_validator.validate(plan_obj)
                        except Exception as exc:
                            plan_err = f'schema_validation:{type(exc).__name__}:{str(exc)[:100]}'
                            plan_obj = None
                    if plan_obj is None:
                        path = 'b1_fallback_invalid_plan'
                        sql = b1_fallback(item)
                    else:
                        sql_prompt = b2v2.make_b2v2_sql_prompt(item['question'], plan_obj, full_schema)
                        raw = gen(sql_prompt, max_new=192)
                        sql = extract_sql(raw)
                        path = 'plan_then_sql'
                    ex, match, et, em = evaluate(item, sql)
                except Exception as exc:
                    sql = ''; ex, match = False, False
                    et, em = 'gen_failed', f'{type(exc).__name__}: {exc}'
                rec = {'idx': i, 'question': item['question'], 'db_id': item['db_id'],
                       'gold_sql': item['query'], 'plan': plan_obj, 'plan_error': plan_err,
                       'generated_sql': sql, 'executable': ex, 'execution_match': match,
                       'error_type': et, 'error_message': em, 'path': path}
                recs.append(rec)
                (OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl').write_text(
                    ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in recs), encoding='utf-8')
                task_log(f'  B2v2 {i:>2} {item["db_id"]:<25} path={path:<26} exec={ex} match={match} err={et!r}')
            return write_run(prefix, recs, t0, subset_name,
                             {'schema_strategy':'full_schema_planner_full_schema_synth',
                              'plan_validator':'plan_schema_v1',
                              'fallback_policy':'b1_on_invalid_plan',
                              'patches':'distinct_cue,superlative_subquery,anti_overengineering'})

        s10 = run_b2v2(smoke10, 'smoke_10', 'b2v2_spider_smoke10')
        mdb = run_b2v2(multidb30, 'multidb_30', 'b2v2_multidb30')
        task_log(f'B2v2_smoke10 EX={s10["ex"]:.4f}  B2v2_multidb30 EX={mdb["ex"]:.4f}')
        task_log('B2V2_BG_DONE')
    except Exception:
        task_log('B2V2_BG_FAILED')
        task_log(traceback.format_exc())


B2V2_BG_THREAD = threading.Thread(target=background_main, name='b2v2-bg', daemon=True)
B2V2_BG_THREAD.start()
print('STARTED=True thread=b2v2-bg')
print(f'TASK_LOG={TASK_LOG}')
