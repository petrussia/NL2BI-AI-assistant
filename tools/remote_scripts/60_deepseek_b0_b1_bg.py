# Self-contained BG: bootstrap helpers, attempt to load
# DeepSeek-Coder-V2-Lite-Instruct in 4-bit, run B0+B1 smoke10. Records full
# feasibility data either way.

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
for sub in ['logs', 'metrics', 'predictions', 'tables']:
    (OUTPUTS / sub).mkdir(parents=True, exist_ok=True)

MODEL_ID = 'deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct'
PREFIX_SAFE = MODEL_ID.replace('/', '_').replace('-', '_').replace('.', '_').lower()

TASK_LOG = OUTPUTS / 'logs' / 'deepseek_bg_task_log.txt'
ATTEMPT_LOG = OUTPUTS / 'logs' / 'deepseek_runtime_attempt.md'
FEAS_CSV = OUTPUTS / 'tables' / 'deepseek_feasibility_details.csv'
BLOCKER = OUTPUTS / 'logs' / 'deepseek_blocker_final.md'

mm = sys.modules['__main__']
if 'DEEPSEEK_BG_THREAD' in globals() and DEEPSEEK_BG_THREAD.is_alive():
    print('BG already running')
    raise SystemExit(0)


def task_log(msg):
    line = f'[{dt.datetime.now(dt.timezone.utc).isoformat()}] {msg}'
    print(line)
    with TASK_LOG.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def background_main():
    feasibility = {
        'model_id': MODEL_ID,
        'attempted_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'gpu_total_gb': '',
        'gpu_free_before_load_gb': '',
        'load_status': 'not_attempted',
        'load_error_class': '',
        'load_error_message': '',
        'load_seconds': '',
        'vram_after_load_gb': '',
        'vram_after_b0_gb': '',
        'b0_run_status': 'not_attempted',
        'b1_run_status': 'not_attempted',
        'b0_ex': '',
        'b1_ex': '',
    }
    try:
        TASK_LOG.write_text('', encoding='utf-8')
        task_log('DEEPSEEK_BG_START')

        # ===== ensure deps =====
        import importlib
        if importlib.util.find_spec('func_timeout') is None:
            subprocess.run([sys.executable, '-m', 'pip', 'install', '-q',
                            'func_timeout', 'transformers>=4.45.0', 'accelerate>=0.34.0',
                            'bitsandbytes>=0.43.3', 'sentencepiece', 'safetensors'],
                           check=True)
        from func_timeout import FunctionTimedOut, func_timeout

        # ===== bootstrap helpers =====
        dev = json.loads((SPIDER_DIR / 'dev.json').read_text(encoding='utf-8'))
        tables_map = {row['db_id']: row for row in
                      json.loads((SPIDER_DIR / 'tables.json').read_text(encoding='utf-8'))}
        db_paths = {p.stem: p for p in (SPIDER_DIR / 'database').rglob('*.sqlite')}
        smoke10 = json.loads((SPIDER_DIR / 'subsets' / 'smoke_10.json').read_text(encoding='utf-8'))

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

        def make_b0_prompt(item):
            schema = build_full_schema(item['db_id'])
            return textwrap.dedent(f'''
            You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
            Use only the given schema. Return SQL only, no markdown and no explanation.

            {schema}

            Question: {item["question"]}
            SQL:
            ''').strip()

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

        # ===== free any existing model =====
        import torch
        for k in ('model','tokenizer'):
            if k in mm.__dict__: del mm.__dict__[k]
        gc.collect(); torch.cuda.empty_cache()
        try: torch.cuda.synchronize()
        except Exception: pass
        free, total = torch.cuda.mem_get_info(0)
        feasibility['gpu_total_gb'] = round(total/1e9, 2)
        feasibility['gpu_free_before_load_gb'] = round(free/1e9, 2)
        task_log(f'gpu free={free/1e9:.2f} total={total/1e9:.2f} GB')

        # ===== try to load DeepSeek =====
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        feasibility['load_status'] = 'attempting'
        t_load = time.time()
        try:
            tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
            qcfg = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                                      bnb_4bit_compute_dtype=torch.float16,
                                      bnb_4bit_use_double_quant=True)
            new_model = AutoModelForCausalLM.from_pretrained(
                MODEL_ID, trust_remote_code=True, device_map='auto',
                quantization_config=qcfg, torch_dtype=torch.float16)
            new_model.eval()
            mm.__dict__['model'] = new_model
            mm.__dict__['tokenizer'] = tok
            feasibility['load_status'] = 'ok'
            feasibility['load_seconds'] = round(time.time()-t_load, 2)
            feasibility['vram_after_load_gb'] = round(torch.cuda.memory_allocated()/1e9, 2)
            task_log(f'LOADED {MODEL_ID} in {feasibility["load_seconds"]}s '
                     f'VRAM={feasibility["vram_after_load_gb"]} GB')
        except Exception as exc:
            feasibility['load_status'] = 'failed'
            feasibility['load_error_class'] = type(exc).__name__
            feasibility['load_error_message'] = str(exc)[:500]
            feasibility['load_seconds'] = round(time.time()-t_load, 2)
            task_log(f'LOAD_FAILED {type(exc).__name__}: {str(exc)[:300]}')

        # ===== always write feasibility CSV =====
        with FEAS_CSV.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(feasibility.keys()))
            w.writeheader(); w.writerow(feasibility)

        if feasibility['load_status'] != 'ok':
            BLOCKER.write_text(textwrap.dedent(f'''
            # DeepSeek-Coder-V2-Lite-Instruct — final blocker

            **Model:** `{MODEL_ID}`
            **Attempted:** {feasibility["attempted_at"]}
            **Runtime:** NVIDIA L4, {feasibility["gpu_total_gb"]} GB VRAM total,
            {feasibility["gpu_free_before_load_gb"]} GB free before load.
            **Quantization:** 4-bit nf4 bitsandbytes, double-quant, fp16 compute.

            ## Outcome
            - load_status = `{feasibility["load_status"]}`
            - load_error_class = `{feasibility["load_error_class"]}`
            - load_error_message = `{feasibility["load_error_message"]}`
            - load_seconds = {feasibility["load_seconds"]}

            ## Why this is final
            We attempted a real load with the standard production config used for
            Qwen-Coder. The model either OOMed, failed to download, or failed at
            the framework level. Without a different runtime (A100 80 GB or a
            multi-GPU box), we cannot run B0/B1 evaluations on this model from
            this Colab L4 kernel.

            ## What it would take to unblock
            - A100 40+ GB or H100 (single-GPU runtime), OR
            - CPU-offload run (orders of magnitude slower; not productive),
            - OR a distilled / Lite-Int4 community release that fits in 24 GB.

            ## Honest classification
            Mandatory model from the proposal — **not evaluated this iteration**.
            Documented as a *runtime blocker*, not skipped silently.
            ''').strip()+'\n', encoding='utf-8')
            ATTEMPT_LOG.write_text(textwrap.dedent(f'''
            # DeepSeek-Coder-V2-Lite-Instruct runtime attempt log

            - Model: `{MODEL_ID}`
            - Attempt: {feasibility["attempted_at"]}
            - GPU: NVIDIA L4 ({feasibility["gpu_total_gb"]} GB total, {feasibility["gpu_free_before_load_gb"]} GB free)
            - Quant config: 4-bit nf4 bnb, double-quant, fp16 compute
            - Outcome: **{feasibility["load_status"]}**
            - Error: `{feasibility["load_error_class"]}: {feasibility["load_error_message"]}`
            - Elapsed: {feasibility["load_seconds"]}s
            - Decision: emit `deepseek_blocker_final.md` and continue to next priority.
            ''').strip()+'\n', encoding='utf-8')
            task_log('DEEPSEEK_BG_DONE_BLOCKED')
            return

        # ===== generation helper =====
        model = mm.__dict__['model']; tokenizer = mm.__dict__['tokenizer']
        def gen(prompt, max_new=192):
            messages = [{'role':'user','content':prompt}]
            rendered = tokenizer.apply_chat_template(messages, tokenize=False,
                                                     add_generation_prompt=True)
            inputs = tokenizer(rendered, return_tensors='pt')
            inputs = {k: v.to(model.device) for k,v in inputs.items()}
            with torch.no_grad():
                out = model.generate(**inputs, max_new_tokens=max_new, do_sample=False,
                                     pad_token_id=tokenizer.eos_token_id)
            return tokenizer.decode(out[0][inputs['input_ids'].shape[1]:],
                                    skip_special_tokens=True)

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

        def write_run(prefix, records, started, extra_kvs):
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
            base = {'run_id': prefix, 'model': MODEL_ID, 'subset': 'smoke_10',
                    'n': total, 'execution_match_count': match_count, 'ex': ex,
                    'executable_count': exec_count}
            base.update(extra_kvs)
            with metr_p.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=list(base.keys())); w.writeheader(); w.writerow(base)
            with sum_p.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=['metric','value']); w.writeheader()
                for k,v in [('completed','true'),('EX',ex),('executable_count',exec_count),
                            ('total',total),('model',MODEL_ID),('subset','smoke_10')] + list(extra_kvs.items()):
                    w.writerow({'metric': k, 'value': v})
            run_p.write_text(textwrap.dedent(f'''
            {prefix} run log
            checked_at: {dt.datetime.now(dt.timezone.utc).isoformat()}
            model: {MODEL_ID}
            subset: smoke_10
            total: {total}
            executable_count: {exec_count}
            execution_match_count: {match_count}
            EX: {ex}
            elapsed_seconds: {time.time()-started:.2f}
            ''').strip()+'\n', encoding='utf-8')
            cols = ['idx','question','db_id','generated_sql','executable','execution_match','error_type']
            err_p.write_text(f'# {prefix} Error Cases\n\n' +
                             _md([records[i] for i in range(len(records)) if not records[i]['execution_match']], cols),
                             encoding='utf-8')
            ex_p.write_text(f'# {prefix} Examples\n\n' + _md(records[:5], cols), encoding='utf-8')
            return base

        # ===== B0 =====
        task_log(f'=== B0 smoke10 with {MODEL_ID} ===')
        b0_records = []; t0 = time.time()
        for i, item in enumerate(smoke10):
            try:
                p = make_b0_prompt(item)
                raw = gen(p, max_new=192)
                sql = extract_sql(raw)
                ex, match, et, em = evaluate(item, sql)
            except Exception as exc:
                raw, sql = '', ''
                ex, match = False, False
                et, em = 'gen_failed', f'{type(exc).__name__}: {exc}'
            rec = {'idx': i, 'question': item['question'], 'db_id': item['db_id'],
                   'gold_sql': item['query'], 'generated_raw': raw, 'generated_sql': sql,
                   'executable': ex, 'execution_match': match,
                   'error_type': et, 'error_message': em}
            b0_records.append(rec)
            (OUTPUTS/'predictions'/f'deepseek_b0_smoke10_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in b0_records),
                encoding='utf-8')
            task_log(f'  B0 {i:>2} {item["db_id"]:<25} exec={ex} match={match} err={et!r}')
        b0_summary = write_run('deepseek_b0_smoke10', b0_records, t0,
                               {'quantization':'4bit_bitsandbytes_config',
                                'schema_strategy':'full_schema',
                                'comparator_role':'cross_model_baseline_deepseek'})
        feasibility['b0_run_status'] = 'ok'
        feasibility['b0_ex'] = b0_summary['ex']
        feasibility['vram_after_b0_gb'] = round(torch.cuda.memory_allocated()/1e9, 2)
        task_log(f'B0_DONE EX={b0_summary["ex"]:.4f}')

        # ===== B1 =====
        task_log(f'=== B1 smoke10 with {MODEL_ID} ===')
        b1_records = []; t0 = time.time()
        for i, item in enumerate(smoke10):
            link = lex_link(item['question'], item['db_id'])
            try:
                p = make_b1_prompt(item, link)
                raw = gen(p, max_new=192)
                sql = extract_sql(raw)
                ex, match, et, em = evaluate(item, sql)
            except Exception as exc:
                raw, sql = '', ''
                ex, match = False, False
                et, em = 'gen_failed', f'{type(exc).__name__}: {exc}'
            rec = {'idx': i, 'question': item['question'], 'db_id': item['db_id'],
                   'gold_sql': item['query'], 'generated_raw': raw, 'generated_sql': sql,
                   'executable': ex, 'execution_match': match,
                   'error_type': et, 'error_message': em,
                   'selected_tables': link['selected_tables'],
                   'schema_reduction_ratio': link['reduction_ratio'],
                   'fallback_used': link['fallback_used']}
            b1_records.append(rec)
            (OUTPUTS/'predictions'/f'deepseek_b1_smoke10_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in b1_records),
                encoding='utf-8')
            task_log(f'  B1 {i:>2} {item["db_id"]:<25} sel={len(link["selected_tables"])} '
                     f'exec={ex} match={match} err={et!r}')
        avg_red = sum(r['schema_reduction_ratio'] for r in b1_records)/len(b1_records)
        b1_summary = write_run('deepseek_b1_smoke10', b1_records, t0,
                               {'quantization':'4bit_bitsandbytes_config',
                                'schema_strategy':'lexical_schema_linking',
                                'avg_reduction_ratio':avg_red,
                                'comparator_role':'cross_model_baseline_deepseek'})
        feasibility['b1_run_status'] = 'ok'
        feasibility['b1_ex'] = b1_summary['ex']
        task_log(f'B1_DONE EX={b1_summary["ex"]:.4f}')

        # ===== finalize =====
        with FEAS_CSV.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(feasibility.keys()))
            w.writeheader(); w.writerow(feasibility)

        ATTEMPT_LOG.write_text(textwrap.dedent(f'''
        # DeepSeek-Coder-V2-Lite-Instruct runtime attempt log

        - Model: `{MODEL_ID}`
        - Attempt: {feasibility["attempted_at"]}
        - GPU: NVIDIA L4 ({feasibility["gpu_total_gb"]} GB total, {feasibility["gpu_free_before_load_gb"]} GB free before load)
        - Quant config: 4-bit nf4 bnb, double-quant, fp16 compute
        - Load: **OK** in {feasibility["load_seconds"]}s, VRAM after load = {feasibility["vram_after_load_gb"]} GB
        - VRAM after B0 run: {feasibility["vram_after_b0_gb"]} GB
        - B0 smoke10 EX: **{feasibility["b0_ex"]}**
        - B1 smoke10 EX: **{feasibility["b1_ex"]}**
        - Decision: model successfully evaluated; mandatory model block extended to DeepSeek.
        ''').strip()+'\n', encoding='utf-8')

        task_log('DEEPSEEK_BG_DONE_OK')
    except Exception:
        task_log('DEEPSEEK_BG_FAILED')
        task_log(traceback.format_exc())


DEEPSEEK_BG_THREAD = threading.Thread(target=background_main, name='deepseek-bg', daemon=True)
DEEPSEEK_BG_THREAD.start()
print('STARTED=True thread=deepseek-bg')
print(f'TASK_LOG={TASK_LOG}')
