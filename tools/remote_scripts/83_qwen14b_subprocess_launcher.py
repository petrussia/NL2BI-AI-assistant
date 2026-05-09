# Launch Qwen-14B B0/B1 × smoke10/multidb30 as a TRUE subprocess.
# This bypasses the kernel's corrupted bnb-detection state by running the
# whole workload in a fresh Python process.

import subprocess
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
RUNNER_PATH = Path('/tmp/qwen14b_runner.py')

RUNNER_PATH.write_text(textwrap.dedent('''\
import csv
import datetime as dt
import json
import os
import re
import sqlite3
import textwrap
import time
import traceback
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
SPIDER_DIR = PROJECT_ROOT / 'data' / 'spider'
OUTPUTS = PROJECT_ROOT / 'outputs'
for sub in ['logs','metrics','predictions','tables']:
    (OUTPUTS/sub).mkdir(parents=True, exist_ok=True)

MODEL_ID = 'Qwen/Qwen2.5-Coder-14B-Instruct'
PREFIX_SAFE = 'qwen2p5_coder_14b_instruct'
TASK_LOG = OUTPUTS / 'logs' / 'qwen14b_bg_task_log.txt'

def task_log(msg):
    line = f'[{dt.datetime.now(dt.timezone.utc).isoformat()}] {msg}'
    print(line, flush=True)
    with TASK_LOG.open('a', encoding='utf-8') as f:
        f.write(line+'\\n')

try:
    TASK_LOG.write_text('', encoding='utf-8')
    task_log('QWEN14B_SUBPROC_START')

    from func_timeout import FunctionTimedOut, func_timeout

    tables_map = {row['db_id']: row for row in
                  json.loads((SPIDER_DIR/'tables.json').read_text(encoding='utf-8'))}
    db_paths = {p.stem: p for p in (SPIDER_DIR/'database').rglob('*.sqlite')}
    smoke10 = json.loads((SPIDER_DIR/'subsets'/'smoke_10.json').read_text(encoding='utf-8'))
    multidb30 = json.loads((SPIDER_DIR/'subsets'/'multidb_30.json').read_text(encoding='utf-8'))

    STOP = {'a','an','the','of','in','on','at','for','to','from','by','with','is','are','was','were','what','which','who','whom','whose','how','many','much','show','list','find','give','me','all','each','every','any','do','does','did'}
    def _toks(s):
        parts = re.split(r'[\\s_]+', str(s).lower())
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
        return '\\n'.join(lines)

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
        return '\\n'.join(lines)

    def make_b0_prompt(item):
        return textwrap.dedent(f"""
        You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
        Use only the given schema. Return SQL only, no markdown and no explanation.

        {build_full_schema(item['db_id'])}

        Question: {item['question']}
        SQL:
        """).strip()

    def make_b1_prompt(item, link):
        return textwrap.dedent(f"""
        You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
        Use only the given schema. Return SQL only, no markdown and no explanation.

        {build_reduced_schema(item['db_id'], link['selected_table_indexes'])}

        Question: {item['question']}
        SQL:
        """).strip()

    def extract_sql(text):
        text = text.strip()
        text = re.sub(r'^```(?:sql)?', '', text, flags=re.I).strip()
        text = re.sub(r'```$', '', text).strip()
        m = re.search(r'(?is)(select\\b.*)', text)
        if m: text = m.group(1).strip()
        text = text.split('\\n\\n')[0].strip()
        if ';' in text: text = text.split(';', 1)[0].strip()
        return text.rstrip(';') + ';'

    def execute_sql(db_path, sql, timeout=8):
        def _run():
            con = sqlite3.connect(db_path); cur = con.cursor()
            cur.execute(sql); rows = cur.fetchall(); con.close(); return rows
        return func_timeout(timeout, _run)

    import torch
    free, total = torch.cuda.mem_get_info(0)
    task_log(f'gpu free={free/1e9:.2f} GB total={total/1e9:.2f} GB')

    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    t_load = time.time()
    tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    qcfg = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                              bnb_4bit_compute_dtype=torch.float16,
                              bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, trust_remote_code=True,
                                                  device_map='auto', quantization_config=qcfg)
    model.eval()
    task_log(f'LOADED {MODEL_ID} in {time.time()-t_load:.1f}s VRAM={torch.cuda.memory_allocated()//(1024*1024)} MB')

    def gen(prompt, max_new=192):
        messages = [{'role':'user','content':prompt}]
        rendered = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tok(rendered, return_tensors='pt')
        inputs = {k: v.to(model.device) for k,v in inputs.items()}
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=max_new, do_sample=False,
                                 pad_token_id=tok.eos_token_id)
        return tok.decode(out[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)

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
                v.append(str(x).replace('|','\\\\|').replace('\\n','<br>')[:700])
            lines.append('|'+'|'.join(v)+'|')
        return '\\n'.join(lines)+'\\n'

    def write_run(prefix, records, started, subset_name, extra):
        pred_p = OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl'
        metr_p = OUTPUTS/'metrics'/f'{prefix}_metrics.csv'
        sum_p = OUTPUTS/'tables'/f'{prefix}_summary.csv'
        run_p = OUTPUTS/'logs'/f'{prefix}_runlog.txt'
        err_p = OUTPUTS/'tables'/f'{prefix}_error_cases.md'
        ex_p = OUTPUTS/'tables'/f'{prefix}_examples.md'
        pred_p.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\\n' for r in records), encoding='utf-8')
        total = len(records)
        exec_count = sum(1 for r in records if r['executable'])
        match_count = sum(1 for r in records if r['execution_match'])
        ex = match_count/total if total else 0.0
        base = {'run_id': prefix, 'model': MODEL_ID, 'subset': subset_name,
                'n': total, 'execution_match_count': match_count, 'ex': ex,
                'executable_count': exec_count}
        base.update(extra)
        with metr_p.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(base.keys())); w.writeheader(); w.writerow(base)
        with sum_p.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['metric','value']); w.writeheader()
            for k,v in [('completed','true'),('EX',ex),('executable_count',exec_count),
                        ('total',total),('model',MODEL_ID),('subset',subset_name)] + list(extra.items()):
                w.writerow({'metric':k,'value':v})
        run_p.write_text(textwrap.dedent(f"""
        {prefix} run log
        checked_at: {dt.datetime.now(dt.timezone.utc).isoformat()}
        model: {MODEL_ID}
        subset: {subset_name}
        total: {total}
        executable_count: {exec_count}
        execution_match_count: {match_count}
        EX: {ex}
        elapsed_seconds: {time.time()-started:.2f}
        """).strip()+'\\n', encoding='utf-8')
        cols = ['idx','question','db_id','generated_sql','executable','execution_match','error_type']
        err_p.write_text(f'# {prefix} Error Cases\\n\\n' +
                         _md([records[i] for i in range(len(records)) if not records[i]['execution_match']], cols),
                         encoding='utf-8')
        ex_p.write_text(f'# {prefix} Examples\\n\\n' + _md(records[:5], cols), encoding='utf-8')
        return base

    def run_b0(items, subset_name, prefix):
        task_log(f'=== B0 {subset_name} {MODEL_ID} ===')
        t0 = time.time(); recs = []
        for i, item in enumerate(items):
            try:
                p = make_b0_prompt(item); raw = gen(p)
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
            recs.append(rec)
            (OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\\n' for r in recs), encoding='utf-8')
            task_log(f'  B0 {i:>2} {item["db_id"]:<25} exec={ex} match={match} err={et!r}')
        return write_run(prefix, recs, t0, subset_name,
                         {'quantization':'4bit_bitsandbytes_config',
                          'schema_strategy':'full_schema',
                          'comparator_role':'larger_qwen_coder'})

    def run_b1(items, subset_name, prefix):
        task_log(f'=== B1 {subset_name} {MODEL_ID} ===')
        t0 = time.time(); recs = []
        for i, item in enumerate(items):
            link = lex_link(item['question'], item['db_id'])
            try:
                p = make_b1_prompt(item, link); raw = gen(p)
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
            recs.append(rec)
            (OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\\n' for r in recs), encoding='utf-8')
            task_log(f'  B1 {i:>2} {item["db_id"]:<25} sel={len(link["selected_tables"])} exec={ex} match={match} err={et!r}')
        avg_red = sum(r['schema_reduction_ratio'] for r in recs)/len(recs) if recs else 0.0
        return write_run(prefix, recs, t0, subset_name,
                         {'quantization':'4bit_bitsandbytes_config',
                          'schema_strategy':'lexical_schema_linking',
                          'avg_reduction_ratio':avg_red,
                          'comparator_role':'larger_qwen_coder'})

    b0_s10 = run_b0(smoke10, 'smoke_10', f'b0_{PREFIX_SAFE}_smoke10')
    b1_s10 = run_b1(smoke10, 'smoke_10', f'b1_{PREFIX_SAFE}_smoke10')
    task_log(f'b0_s10 EX={b0_s10["ex"]:.4f}  b1_s10 EX={b1_s10["ex"]:.4f}')
    b0_md = run_b0(multidb30, 'multidb_30', f'b0_{PREFIX_SAFE}_multidb30')
    b1_md = run_b1(multidb30, 'multidb_30', f'b1_{PREFIX_SAFE}_multidb30')
    task_log(f'b0_md EX={b0_md["ex"]:.4f}  b1_md EX={b1_md["ex"]:.4f}')

    task_log('QWEN14B_SUBPROC_DONE')
except Exception:
    task_log('QWEN14B_SUBPROC_FAILED')
    task_log(traceback.format_exc())
'''))

# Launch the runner in a detached subprocess
proc = subprocess.Popen([sys.executable, str(RUNNER_PATH)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        start_new_session=True)
print(f'STARTED subprocess pid={proc.pid}')
print(f'TASK_LOG={PROJECT_ROOT/"outputs/logs/qwen14b_bg_task_log.txt"}')
print(f'RUNNER_PATH={RUNNER_PATH}')
