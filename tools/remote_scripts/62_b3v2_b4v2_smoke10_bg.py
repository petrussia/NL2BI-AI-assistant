# BG: free DeepSeek (or whatever is loaded) -> load Qwen-Coder ->
# run B3_v2 + B4_v2 on smoke10 (and on multidb_30 if smoke10 is sane).

import csv
import datetime as dt
import gc
import json
import os
import re
import sqlite3
import subprocess
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
for sub in ['logs', 'metrics', 'predictions', 'tables']:
    (OUTPUTS / sub).mkdir(parents=True, exist_ok=True)

MODEL_ID = 'Qwen/Qwen2.5-Coder-7B-Instruct'
TASK_LOG = OUTPUTS / 'logs' / 'b3v2_b4v2_bg_task_log.txt'

# Threshold to decide whether to expand to multidb_30 after smoke10
SANITY_MIN_EX = 0.40

mm = sys.modules['__main__']
if 'B3V2_B4V2_BG_THREAD' in globals() and B3V2_B4V2_BG_THREAD.is_alive():
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
        task_log('B3V2_B4V2_BG_START')

        # ===== ensure deps =====
        import importlib
        for pkg in ('func_timeout', 'jsonschema'):
            if importlib.util.find_spec(pkg) is None:
                subprocess.run([sys.executable, '-m', 'pip', 'install', '-q',
                                'func_timeout', 'jsonschema'], check=True)
                break
        from func_timeout import FunctionTimedOut, func_timeout
        try:
            from jsonschema import Draft202012Validator
        except Exception:
            from jsonschema import Draft7Validator as Draft202012Validator

        # ===== bootstrap helpers =====
        dev = json.loads((SPIDER_DIR / 'dev.json').read_text(encoding='utf-8'))
        tables_map = {row['db_id']: row for row in
                      json.loads((SPIDER_DIR / 'tables.json').read_text(encoding='utf-8'))}
        db_paths = {p.stem: p for p in (SPIDER_DIR / 'database').rglob('*.sqlite')}
        smoke10 = json.loads((SPIDER_DIR / 'subsets' / 'smoke_10.json').read_text(encoding='utf-8'))
        multidb30 = json.loads((SPIDER_DIR / 'subsets' / 'multidb_30.json').read_text(encoding='utf-8'))
        plan_schema_v1_path = REPO / 'docs' / 'plan_schema_v1.json'
        plan_schema_v1 = json.loads(plan_schema_v1_path.read_text(encoding='utf-8')) \
            if plan_schema_v1_path.exists() else None
        plan_validator = Draft202012Validator(plan_schema_v1) if plan_schema_v1 else None

        STOP = {'a','an','the','of','in','on','at','for','to','from','by','with',
                'is','are','was','were','what','which','who','whom','whose','how',
                'many','much','show','list','find','give','me','all','each','every',
                'any','do','does','did'}
        def _toks(s):
            parts = re.split(r'[\s_]+', str(s).lower())
            return {p for p in parts if p and p not in STOP and len(p) > 1}

        def build_full_schema(db_id):
            t = tables_map[db_id]
            tn = t.get('table_names_original') or t.get('table_names')
            cn = t.get('column_names_original') or t.get('column_names')
            by_table = {i: [] for i in range(len(tn))}
            for ti, col in cn:
                if ti >= 0:
                    by_table.setdefault(ti, []).append(col)
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
                if ti >= 0:
                    scores[ti] += len(qt & _toks(col)) * 1.0
            above = [(i, s) for i, s in scores.items() if s >= min_score]
            above.sort(key=lambda x: -x[1])
            if not above:
                selected = list(range(len(tn))); fallback = True
            else:
                selected = sorted([i for i, _ in above]); fallback = False
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
                if ti >= 0:
                    by_table.setdefault(ti, []).append(col)
            lines = [f'Database: {db_id}',
                     'Tables and columns (reduced via lexical schema linking):']
            for idx in selected_idx:
                lines.append(f'- {tn[idx]}(' + ', '.join(by_table.get(idx, [])) + ')')
            return '\n'.join(lines)

        def make_b1_prompt(item, link):
            schema = build_reduced_schema(item['db_id'], link['selected_table_indexes'])
            return textwrap.dedent(f'''
            You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
            Use only the given schema. Return SQL only, no markdown and no explanation.

            {schema}

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

        # ===== load (or swap to) Qwen-Coder =====
        import torch
        cur_model = mm.__dict__.get('model'); cur_tok = mm.__dict__.get('tokenizer')
        cur_model_id = getattr(cur_model, 'name_or_path', '') if cur_model else None
        if cur_model_id != MODEL_ID:
            task_log(f'swapping model: {cur_model_id} -> {MODEL_ID}')
            for k in ('model', 'tokenizer'):
                if k in mm.__dict__: del mm.__dict__[k]
            del cur_model, cur_tok
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
        else:
            task_log(f'model already {MODEL_ID}; skipping swap')

        model = mm.__dict__['model']; tokenizer = mm.__dict__['tokenizer']

        # ===== import b3_v2/b4_v2 modules =====
        eval_path = str(REPO / 'src' / 'evaluation')
        if eval_path not in sys.path: sys.path.insert(0, eval_path)
        for mod in ('baselines_b3_v2', 'baselines_b4_v2', 'baselines_b4_final'):
            if mod in sys.modules: del sys.modules[mod]
        import baselines_b3_v2 as b3v2
        import baselines_b4_v2 as b4v2

        # ===== generation =====
        def gen(prompt, max_new=192, num_return_sequences=1, do_sample=False,
                temperature=1.0, top_p=1.0):
            messages = [{'role': 'user', 'content': prompt}]
            rendered = tokenizer.apply_chat_template(messages, tokenize=False,
                                                     add_generation_prompt=True)
            inputs = tokenizer(rendered, return_tensors='pt')
            inputs = {k: v.to(model.device) for k, v in inputs.items()}
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

        def evaluate(item, sql):
            executable, match = False, False
            err_t, err_m, rows = '', '', None
            try:
                rows = execute_sql(db_paths[item['db_id']], sql)
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
                    if isinstance(x, (list, dict)): x = json.dumps(x, ensure_ascii=False)
                    v.append(str(x).replace('|','\\|').replace('\n','<br>')[:700])
                lines.append('|'+'|'.join(v)+'|')
            return '\n'.join(lines)+'\n'

        def write_run(prefix, records, started, subset_name, total_n, extra_kvs):
            pred_p = OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl'
            metr_p = OUTPUTS/'metrics'/f'{prefix}_metrics.csv'
            sum_p = OUTPUTS/'tables'/f'{prefix}_summary.csv'
            run_p = OUTPUTS/'logs'/f'{prefix}_runlog.txt'
            err_p = OUTPUTS/'tables'/f'{prefix}_error_cases.md'
            ex_p = OUTPUTS/'tables'/f'{prefix}_examples.md'
            pred_p.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in records),
                              encoding='utf-8')
            total = len(records)
            exec_count = sum(1 for r in records if r['executable'])
            match_count = sum(1 for r in records if r['execution_match'])
            ex = match_count/total if total else 0.0
            base = {'run_id': prefix, 'model': MODEL_ID, 'subset': subset_name,
                    'n': total, 'execution_match_count': match_count, 'ex': ex,
                    'executable_count': exec_count}
            base.update(extra_kvs)
            with metr_p.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=list(base.keys()))
                w.writeheader(); w.writerow(base)
            with sum_p.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=['metric','value']); w.writeheader()
                for k,v in [('completed','true'),('EX',ex),('executable_count',exec_count),
                            ('total',total),('model',MODEL_ID),('subset',subset_name)] + list(extra_kvs.items()):
                    w.writerow({'metric': k, 'value': v})
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

        def b1_fallback_sql(item, link):
            p = make_b1_prompt(item, link)
            raw = gen(p, max_new=192)[0]
            return extract_sql(raw)

        def run_b3v2(items, subset_name, prefix):
            task_log(f'=== B3_v2 {subset_name} ===')
            t0 = time.time(); recs = []
            for i, item in enumerate(items):
                link = lex_link(item['question'], item['db_id'])
                full_schema = build_full_schema(item['db_id'])
                reduced_schema = build_reduced_schema(item['db_id'], link['selected_table_indexes'])
                path = ''
                plan_obj = None; plan_err = ''
                sql = ''; raw = ''
                try:
                    plan_prompt = b3v2.make_b3v2_plan_prompt(item['question'], reduced_schema)
                    raw_plan = gen(plan_prompt, max_new=256)[0]
                    plan_obj, plan_err = b3v2.parse_plan_json(raw_plan)
                    if plan_obj is not None and plan_validator is not None:
                        try:
                            plan_validator.validate(plan_obj)
                        except Exception as exc:
                            plan_err = f'schema_validation:{type(exc).__name__}:{str(exc)[:100]}'
                            plan_obj = None
                    if plan_obj is None:
                        path = 'b1_fallback_invalid_plan'
                        sql = b1_fallback_sql(item, link)
                    else:
                        sql_prompt = b3v2.make_b3v2_sql_prompt(item['question'], plan_obj, full_schema)
                        raw = gen(sql_prompt, max_new=192)[0]
                        sql = extract_sql(raw)
                        path = 'plan_then_sql'
                    ex, match, et, em, rows = evaluate(item, sql)
                except Exception as exc:
                    sql = ''; ex, match = False, False
                    et, em = 'gen_failed', f'{type(exc).__name__}: {exc}'
                rec = {'idx': i, 'question': item['question'], 'db_id': item['db_id'],
                       'gold_sql': item['query'], 'plan': plan_obj, 'plan_error': plan_err,
                       'generated_sql': sql, 'executable': ex, 'execution_match': match,
                       'error_type': et, 'error_message': em,
                       'selected_tables': link['selected_tables'],
                       'reduction_ratio': link['reduction_ratio'],
                       'path': path}
                recs.append(rec)
                (OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl').write_text(
                    ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in recs), encoding='utf-8')
                task_log(f'  B3v2 {i:>2} {item["db_id"]:<25} path={path:<26} exec={ex} match={match} err={et!r}')
            avg_red = sum(r['reduction_ratio'] for r in recs)/len(recs) if recs else 0.0
            return write_run(prefix, recs, t0, subset_name, len(items),
                             {'schema_strategy':'lex_linker_planner_full_schema_synth',
                              'plan_validator':'plan_schema_v1',
                              'fallback_policy':'b1_on_invalid_plan',
                              'avg_reduction_ratio':avg_red})

        def run_b4v2(items, subset_name, prefix):
            task_log(f'=== B4_v2 {subset_name} ===')
            t0 = time.time(); recs = []
            for i, item in enumerate(items):
                link = lex_link(item['question'], item['db_id'])
                full_schema = build_full_schema(item['db_id'])
                reduced_schema = build_reduced_schema(item['db_id'], link['selected_table_indexes'])
                path = ''; plan_obj = None; plan_err = ''
                sql = ''; cand_raw_sqls = []
                try:
                    plan_prompt = b3v2.make_b3v2_plan_prompt(item['question'], reduced_schema)
                    raw_plan = gen(plan_prompt, max_new=256)[0]
                    plan_obj, plan_err = b3v2.parse_plan_json(raw_plan)
                    if plan_obj is not None and plan_validator is not None:
                        try:
                            plan_validator.validate(plan_obj)
                        except Exception as exc:
                            plan_err = f'schema_validation:{type(exc).__name__}:{str(exc)[:100]}'
                            plan_obj = None
                    if plan_obj is None:
                        path = 'b1_fallback_invalid_plan'
                        sql = b1_fallback_sql(item, link)
                    else:
                        sql_prompt = b3v2.make_b3v2_sql_prompt(item['question'], plan_obj, full_schema)
                        raw_cands = gen(sql_prompt, max_new=192,
                                        num_return_sequences=3, do_sample=True,
                                        temperature=0.7, top_p=0.95)
                        cand_results = []
                        for raw in raw_cands:
                            cand = extract_sql(raw)
                            cand_raw_sqls.append(cand)
                            ok, reason = b4v2.is_safe_select(cand)
                            if not ok:
                                cand_results.append((cand, False, [], f'unsafe:{reason}'))
                                continue
                            try:
                                rows = execute_sql(db_paths[item['db_id']], cand)
                                cand_results.append((cand, True, rows, ''))
                            except Exception as exc:
                                cand_results.append((cand, False, [], f'{type(exc).__name__}:{exc}'))
                        chosen, why = b4v2.consistency_pick_v2(cand_results)
                        if chosen is None:
                            # repair attempt depth=1 on first candidate
                            first_sql = cand_raw_sqls[0] if cand_raw_sqls else ''
                            first_err = cand_results[0][3] if cand_results else 'no_candidate'
                            rep_prompt = b4v2.make_repair_prompt_v2(item['question'], plan_obj,
                                                                     full_schema, first_sql, first_err)
                            rep_raw = gen(rep_prompt, max_new=192)[0]
                            rep_sql = extract_sql(rep_raw)
                            ok_r, _ = b4v2.is_safe_select(rep_sql)
                            try:
                                if ok_r:
                                    execute_sql(db_paths[item['db_id']], rep_sql)
                                    chosen, why = rep_sql, 'repaired'
                            except Exception:
                                pass
                            if chosen is None:
                                path = 'b1_fallback_no_executable'
                                sql = b1_fallback_sql(item, link)
                            else:
                                sql = chosen; path = f'multicand_repair:{why}'
                        else:
                            sql = chosen; path = f'multicand:{why}'
                    ex, match, et, em, rows = evaluate(item, sql)
                except Exception as exc:
                    sql = ''; ex, match = False, False
                    et, em = 'gen_failed', f'{type(exc).__name__}: {exc}'
                rec = {'idx': i, 'question': item['question'], 'db_id': item['db_id'],
                       'gold_sql': item['query'], 'plan': plan_obj, 'plan_error': plan_err,
                       'candidates': cand_raw_sqls,
                       'generated_sql': sql, 'executable': ex, 'execution_match': match,
                       'error_type': et, 'error_message': em,
                       'selected_tables': link['selected_tables'],
                       'reduction_ratio': link['reduction_ratio'],
                       'path': path}
                recs.append(rec)
                (OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl').write_text(
                    ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in recs), encoding='utf-8')
                task_log(f'  B4v2 {i:>2} {item["db_id"]:<25} path={path:<32} exec={ex} match={match} err={et!r}')
            avg_red = sum(r['reduction_ratio'] for r in recs)/len(recs) if recs else 0.0
            return write_run(prefix, recs, t0, subset_name, len(items),
                             {'schema_strategy':'lex_linker_planner_full_schema_synth',
                              'plan_validator':'plan_schema_v1',
                              'fallback_policy':'b1_on_invalid_or_no_executable',
                              'multi_candidate':'k=3,T=0.7,top_p=0.95',
                              'repair_depth':1,
                              'avg_reduction_ratio':avg_red})

        # ===== smoke10 =====
        b3v2_s10 = run_b3v2(smoke10, 'smoke_10', 'b3v2_spider_smoke10')
        b4v2_s10 = run_b4v2(smoke10, 'smoke_10', 'b4v2_spider_smoke10')
        task_log(f'B3v2_smoke10 EX={b3v2_s10["ex"]:.4f}  B4v2_smoke10 EX={b4v2_s10["ex"]:.4f}')

        # ===== multidb_30 if smoke10 EX >= sanity threshold =====
        if max(b3v2_s10['ex'], b4v2_s10['ex']) >= SANITY_MIN_EX:
            b3v2_mdb = run_b3v2(multidb30, 'multidb_30', 'b3v2_multidb30')
            b4v2_mdb = run_b4v2(multidb30, 'multidb_30', 'b4v2_multidb30')
            task_log(f'B3v2_multidb30 EX={b3v2_mdb["ex"]:.4f}  B4v2_multidb30 EX={b4v2_mdb["ex"]:.4f}')
        else:
            task_log(f'SKIPPING multidb_30 — smoke10 below sanity threshold {SANITY_MIN_EX}')

        task_log('B3V2_B4V2_BG_DONE')
    except Exception:
        task_log('B3V2_B4V2_BG_FAILED')
        task_log(traceback.format_exc())


B3V2_B4V2_BG_THREAD = threading.Thread(target=background_main, name='b3v2-b4v2-bg', daemon=True)
B3V2_B4V2_BG_THREAD.start()
print('STARTED=True thread=b3v2-b4v2-bg')
print(f'TASK_LOG={TASK_LOG}')
