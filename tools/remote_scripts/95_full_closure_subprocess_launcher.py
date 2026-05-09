# Phase B+E: launch unified subprocess that closes ~52 missing P0/P1 cells.
# Lane A: Qwen-Coder-7B   ext fill (6 runs)
# Lane B: Llama-3.1-8B    internal layered (9) + ext fill (6) = 15 runs
# Lane C: Qwen-Coder-14B  internal layered (9) + ext full (10) = 19 runs
# Lane D: Qwen-7B-Instruct comparator B0/B1/B2_v2 × 4 missing benches = 12 runs
# Total ~52 runs on A100 BF16. Subprocess to bypass kernel state corruption.

import os
import subprocess
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
RUNNER = Path('/tmp/full_closure_runner.py')

RUNNER.write_text(textwrap.dedent('''\
import csv
import datetime as dt
import gc
import json
import os
import re
import sqlite3
import sys
import textwrap
import time
import traceback
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
SPIDER_DIR = PROJECT_ROOT / 'data' / 'spider'
EXT = PROJECT_ROOT / 'external_benchmarks'
OUTPUTS = PROJECT_ROOT / 'outputs'
REPO = PROJECT_ROOT / 'repo'
for sub in ['logs','metrics','predictions','tables']:
    (OUTPUTS/sub).mkdir(parents=True, exist_ok=True)

TASK_LOG = OUTPUTS / 'logs' / 'full_closure_subproc_log.txt'

def task_log(msg):
    line = f'[{dt.datetime.now(dt.timezone.utc).isoformat()}] {msg}'
    print(line, flush=True)
    with TASK_LOG.open('a', encoding='utf-8') as f:
        f.write(line+'\\n')

try:
    TASK_LOG.write_text('', encoding='utf-8')
    task_log('FULL_CLOSURE_SUBPROC_START')

    from func_timeout import FunctionTimedOut, func_timeout
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        from jsonschema import Draft7Validator as Draft202012Validator

    sys.path.insert(0, str(REPO/'src'/'evaluation'))
    import baselines_b2_v2 as b2v2
    import baselines_b3_v2 as b3v2
    import baselines_b4_v2 as b4v2
    import external_benchmark_adapters as ext

    plan_schema_v1 = json.loads((REPO/'docs'/'plan_schema_v1.json').read_text(encoding='utf-8'))
    plan_validator = Draft202012Validator(plan_schema_v1)

    # Spider data
    tables_map = {row['db_id']: row for row in
                  json.loads((SPIDER_DIR/'tables.json').read_text(encoding='utf-8'))}
    db_paths = {p.stem: p for p in (SPIDER_DIR/'database').rglob('*.sqlite')}
    smoke10 = json.loads((SPIDER_DIR/'subsets'/'smoke_10.json').read_text(encoding='utf-8'))
    smoke25 = json.loads((SPIDER_DIR/'subsets'/'smoke_25.json').read_text(encoding='utf-8'))
    multidb30 = json.loads((SPIDER_DIR/'subsets'/'multidb_30.json').read_text(encoding='utf-8'))

    # External slices
    bird_slice = ext.bird_load(EXT/'bird_mini_dev/processed/bird_minidev_30_diverse.json')
    s2_slice = ext.spider2_load(EXT/'spider2_lite/processed/spider2lite_30_diverse.json')
    task_log(f'data loaded: smoke10={len(smoke10)} smoke25={len(smoke25)} multidb30={len(multidb30)} bird={len(bird_slice)} s2={len(s2_slice)}')

    # ===== Spider helpers =====
    STOP = {'a','an','the','of','in','on','at','for','to','from','by','with','is','are','was','were','what','which','who','whom','whose','how','many','much','show','list','find','give','me','all','each','every','any','do','does','did'}
    def _toks(s):
        parts = re.split(r'[\\s_]+', str(s).lower())
        return {p for p in parts if p and p not in STOP and len(p) > 1}

    def build_full_schema_spider(db_id):
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

    def lex_link_spider(question, db_id, min_score=0.5):
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

    def build_reduced_schema_spider(db_id, selected_idx):
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
            con = sqlite3.connect(str(db_path)); cur = con.cursor()
            cur.execute(sql); rows = cur.fetchall(); con.close(); return rows
        return func_timeout(timeout, _run)

    def make_b0_prompt(question, full_schema):
        return textwrap.dedent(f"""
        You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
        Use only the given schema. Return SQL only, no markdown and no explanation.

        {full_schema}

        Question: {question}
        SQL:
        """).strip()

    def make_b1_prompt(question, reduced_schema):
        return textwrap.dedent(f"""
        You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
        Use only the given schema. Return SQL only, no markdown and no explanation.

        {reduced_schema}

        Question: {question}
        SQL:
        """).strip()

    # Model loader
    import torch
    MODEL = {'tok': None, 'm': None, 'id': None}
    def free_model():
        MODEL['tok']=None; MODEL['m']=None
        gc.collect(); torch.cuda.empty_cache()
        try: torch.cuda.synchronize()
        except Exception: pass

    def load_model(model_id, gated=False):
        from transformers import AutoTokenizer, AutoModelForCausalLM
        token = os.environ.get('HF_TOKEN') if gated else None
        free_model()
        free, total = torch.cuda.mem_get_info(0)
        task_log(f'loading {model_id}: gpu_free={free/1e9:.2f} GB total={total/1e9:.2f} GB')
        t0 = time.time()
        kwargs = dict(device_map='auto', low_cpu_mem_usage=True, torch_dtype=torch.bfloat16,
                      trust_remote_code=True)
        if gated and token: kwargs['token'] = token
        tok = AutoTokenizer.from_pretrained(model_id, token=token if gated else None,
                                             trust_remote_code=True)
        m = AutoModelForCausalLM.from_pretrained(model_id, **kwargs)
        m.eval()
        MODEL['tok']=tok; MODEL['m']=m; MODEL['id']=model_id
        task_log(f'LOADED {model_id} in {time.time()-t0:.1f}s VRAM={torch.cuda.memory_allocated()//(1024*1024)} MB')

    def gen(prompt, max_new=192, num_return_sequences=1, do_sample=False, temperature=1.0, top_p=1.0, top_k=50):
        m = MODEL['m']; tok = MODEL['tok']
        messages = [{'role':'user','content':prompt}]
        rendered = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tok(rendered, return_tensors='pt')
        inputs = {k: v.to(m.device) for k,v in inputs.items()}
        kwargs = dict(max_new_tokens=max_new, pad_token_id=tok.eos_token_id)
        if do_sample:
            kwargs.update(do_sample=True, temperature=temperature, top_p=top_p, top_k=top_k,
                          num_return_sequences=num_return_sequences)
        else:
            kwargs.update(do_sample=False)
        with torch.no_grad():
            out = m.generate(**inputs, **kwargs)
        n_in = inputs['input_ids'].shape[1]
        return [tok.decode(seq[n_in:], skip_special_tokens=True) for seq in out]

    def evaluate_spider(item, sql):
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

    def evaluate_bird(item, sql):
        executable, match = False, False
        err_t, err_m = '', ''
        try:
            db_path = ext.bird_db_path(item['db_id'])
            pred = execute_sql(db_path, sql)
            executable = True
            gold = execute_sql(db_path, item['gold_sql']) if item.get('gold_sql') else None
            if gold is not None:
                match = sorted(pred) == sorted(gold)
                if not match: err_t = 'result_mismatch'
            else:
                err_t = 'no_gold'
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

    def write_run(prefix, records, started, subset_name, bench_group, extra):
        pred_p = OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl'
        metr_p = OUTPUTS/'metrics'/f'{prefix}_metrics.csv'
        sum_p = OUTPUTS/'tables'/f'{prefix}_summary.csv'
        run_p = OUTPUTS/'logs'/f'{prefix}_runlog.txt'
        err_p = OUTPUTS/'tables'/f'{prefix}_error_cases.md'
        ex_p = OUTPUTS/'tables'/f'{prefix}_examples.md'
        pred_p.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\\n' for r in records), encoding='utf-8')
        total = len(records)
        exec_count = sum(1 for r in records if r.get('executable'))
        match_count = sum(1 for r in records if r.get('execution_match'))
        ex = match_count/total if total else 0.0
        struct = ext.aggregate_structural(records)
        base = {'run_id': prefix, 'model': MODEL['id'], 'subset': subset_name,
                'benchmark_group': bench_group,
                'n': total, 'execution_match_count': match_count, 'ex': ex,
                'executable_count': exec_count}
        base.update({f'struct_{k}': f'{v:.4f}' if isinstance(v,float) else v for k,v in struct.items()})
        base.update(extra)
        with metr_p.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(base.keys())); w.writeheader(); w.writerow(base)
        with sum_p.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['metric','value']); w.writeheader()
            for k,v in [('completed','true'),('EX',ex),('executable_count',exec_count),
                        ('total',total),('model',MODEL['id']),('subset',subset_name),
                        ('benchmark_group',bench_group)] + list(extra.items()) + list(struct.items()):
                w.writerow({'metric':k,'value':v})
        run_p.write_text(textwrap.dedent(f"""
        {prefix} run log
        checked_at: {dt.datetime.now(dt.timezone.utc).isoformat()}
        model: {MODEL['id']}
        subset: {subset_name}
        benchmark_group: {bench_group}
        total: {total}
        executable_count: {exec_count}
        execution_match_count: {match_count}
        EX: {ex}
        elapsed_seconds: {time.time()-started:.2f}
        """).strip()+'\\n', encoding='utf-8')
        cols = ['idx','question','db_id','generated_sql','executable','execution_match','error_type','path']
        err_p.write_text(f'# {prefix} Error Cases\\n\\n' +
                         _md([records[i] for i in range(len(records)) if not records[i].get('execution_match')], cols),
                         encoding='utf-8')
        ex_p.write_text(f'# {prefix} Examples\\n\\n' + _md(records[:5], cols), encoding='utf-8')
        return base

    # Generic baseline runners parametrised by (bench_kind, items)
    def run_b0(items, bench_kind, subset_name, prefix):
        task_log(f'=== B0 {prefix} ===')
        t0 = time.time(); recs = []
        for i, item in enumerate(items):
            try:
                if bench_kind == 'spider':
                    full_schema = build_full_schema_spider(item['db_id'])
                elif bench_kind == 'bird':
                    full_schema = ext.bird_full_schema(item['db_id'])
                else:  # spider2
                    full_schema = ext.spider2_full_schema_proxy(item['db_id'])
                p = make_b0_prompt(item['question'], full_schema)
                raw = gen(p, max_new=256)[0]
                sql = extract_sql(raw)
                if bench_kind == 'spider':
                    exb, match, et, em = evaluate_spider(item, sql)
                elif bench_kind == 'bird':
                    exb, match, et, em = evaluate_bird(item, sql)
                else:
                    exb, match, et, em = None, None, 'no_execution_engine', ''
            except Exception as exc:
                raw, sql = '', ''; exb, match = False, False
                et, em = 'gen_failed', f'{type(exc).__name__}: {exc}'
            rec = {'idx': i, 'question': item['question'], 'db_id': item['db_id'],
                   'gold_sql': item.get('query', item.get('gold_sql','')),
                   'generated_raw': raw, 'generated_sql': sql,
                   'executable': exb, 'execution_match': match,
                   'error_type': et, 'error_message': em, 'path': 'direct_full_schema',
                   'structural': ext.structural_features(sql)}
            recs.append(rec)
            (OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\\n' for r in recs), encoding='utf-8')
            task_log(f'  B0 {i:>2} {item["db_id"][:24]:<24} exec={exb} match={match}')
        bg = 'internal_core' if bench_kind == 'spider' else 'external_validation'
        em_extra = {'evaluation_mode':'prediction_only_structural_metrics'} if bench_kind == 'spider2' else {}
        return write_run(prefix, recs, t0, subset_name, bg,
                         {'quantization':'bf16','schema_strategy':'full_schema', **em_extra})

    def run_b1(items, bench_kind, subset_name, prefix):
        task_log(f'=== B1 {prefix} ===')
        t0 = time.time(); recs = []
        for i, item in enumerate(items):
            if bench_kind == 'spider':
                link = lex_link_spider(item['question'], item['db_id'])
                reduced = build_reduced_schema_spider(item['db_id'], link['selected_table_indexes'])
            elif bench_kind == 'bird':
                link = ext.bird_lex_link(item['question'], item['db_id'])
                reduced = ext.bird_reduced_schema(item['db_id'], link['selected_table_indexes'])
            else:
                link = ext.spider2_lex_link_proxy(item['question'], item['db_id'])
                reduced = ext.spider2_full_schema_proxy(item['db_id'])
            try:
                p = make_b1_prompt(item['question'], reduced)
                raw = gen(p, max_new=256)[0]
                sql = extract_sql(raw)
                if bench_kind == 'spider':
                    exb, match, et, em = evaluate_spider(item, sql)
                elif bench_kind == 'bird':
                    exb, match, et, em = evaluate_bird(item, sql)
                else:
                    exb, match, et, em = None, None, 'no_execution_engine', ''
            except Exception as exc:
                raw, sql = '', ''; exb, match = False, False
                et, em = 'gen_failed', f'{type(exc).__name__}: {exc}'
            rec = {'idx': i, 'question': item['question'], 'db_id': item['db_id'],
                   'gold_sql': item.get('query', item.get('gold_sql','')),
                   'generated_raw': raw, 'generated_sql': sql,
                   'executable': exb, 'execution_match': match,
                   'error_type': et, 'error_message': em,
                   'selected_tables': link['selected_tables'],
                   'schema_reduction_ratio': link.get('reduction_ratio',0.0),
                   'fallback_used': link.get('fallback_used',False),
                   'path': 'lex_linker',
                   'structural': ext.structural_features(sql)}
            recs.append(rec)
            (OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\\n' for r in recs), encoding='utf-8')
            task_log(f'  B1 {i:>2} {item["db_id"][:24]:<24} sel={len(link["selected_tables"])} exec={exb} match={match}')
        avg_red = sum(r.get('schema_reduction_ratio',0) for r in recs)/len(recs) if recs else 0.0
        bg = 'internal_core' if bench_kind == 'spider' else 'external_validation'
        em_extra = {'evaluation_mode':'prediction_only_structural_metrics'} if bench_kind == 'spider2' else {}
        return write_run(prefix, recs, t0, subset_name, bg,
                         {'quantization':'bf16','schema_strategy':'lexical_schema_linking',
                          'avg_reduction_ratio':avg_red, **em_extra})

    def b1_fallback_sql(item, bench_kind):
        if bench_kind == 'spider':
            link = lex_link_spider(item['question'], item['db_id'])
            reduced = build_reduced_schema_spider(item['db_id'], link['selected_table_indexes'])
        elif bench_kind == 'bird':
            link = ext.bird_lex_link(item['question'], item['db_id'])
            reduced = ext.bird_reduced_schema(item['db_id'], link['selected_table_indexes'])
        else:
            reduced = ext.spider2_full_schema_proxy(item['db_id'])
        return extract_sql(gen(make_b1_prompt(item['question'], reduced), max_new=256)[0])

    def run_baseline_v2(items, bench_kind, subset_name, prefix, baseline_kind):
        task_log(f'=== {baseline_kind} {prefix} ===')
        t0 = time.time(); recs = []
        for i, item in enumerate(items):
            if bench_kind == 'spider':
                full_schema = build_full_schema_spider(item['db_id'])
                link = lex_link_spider(item['question'], item['db_id'])
                reduced = build_reduced_schema_spider(item['db_id'], link['selected_table_indexes'])
            elif bench_kind == 'bird':
                full_schema = ext.bird_full_schema(item['db_id'])
                link = ext.bird_lex_link(item['question'], item['db_id'])
                reduced = ext.bird_reduced_schema(item['db_id'], link['selected_table_indexes'])
            else:
                full_schema = ext.spider2_full_schema_proxy(item['db_id'])
                link = ext.spider2_lex_link_proxy(item['question'], item['db_id'])
                reduced = full_schema
            path=''; plan_obj=None; plan_err=''; sql=''; cand_raw_sqls=[]
            try:
                # Plan prompt: B2_v2 uses full_schema, B3_v2/B4_v2 use reduced for plan
                if baseline_kind == 'B2_v2':
                    plan_prompt = b2v2.make_b2v2_plan_prompt(item['question'], full_schema)
                else:
                    plan_prompt = b3v2.make_b3v2_plan_prompt(item['question'], reduced)
                raw_plan = gen(plan_prompt, max_new=256)[0]
                if baseline_kind == 'B2_v2':
                    plan_obj, plan_err = b2v2.parse_plan_json(raw_plan)
                else:
                    plan_obj, plan_err = b3v2.parse_plan_json(raw_plan)
                if plan_obj is not None:
                    try:
                        plan_validator.validate(plan_obj)
                    except Exception as exc:
                        plan_err = f'schema_validation:{type(exc).__name__}:{str(exc)[:100]}'
                        plan_obj = None
                if plan_obj is None:
                    path = 'b1_fallback_invalid_plan'
                    sql = b1_fallback_sql(item, bench_kind)
                else:
                    if baseline_kind == 'B2_v2':
                        sql_prompt = b2v2.make_b2v2_sql_prompt(item['question'], plan_obj, full_schema)
                    else:
                        sql_prompt = b3v2.make_b3v2_sql_prompt(item['question'], plan_obj, full_schema)
                    if baseline_kind == 'B4_v2':
                        # Multi-cand
                        raw_cands = gen(sql_prompt, max_new=256, num_return_sequences=3,
                                        do_sample=True, temperature=0.7, top_p=0.95, top_k=50)
                        cand_results = []
                        for raw in raw_cands:
                            cand = extract_sql(raw); cand_raw_sqls.append(cand)
                            ok, reason = b4v2.is_safe_select(cand)
                            if not ok:
                                cand_results.append((cand, False, [], f'unsafe:{reason}')); continue
                            try:
                                if bench_kind == 'spider':
                                    rows = execute_sql(db_paths[item['db_id']], cand)
                                elif bench_kind == 'bird':
                                    rows = execute_sql(ext.bird_db_path(item['db_id']), cand)
                                else:
                                    rows = []  # no execution
                                cand_results.append((cand, True, rows, ''))
                            except Exception as exc:
                                cand_results.append((cand, False, [], f'{type(exc).__name__}:{exc}'))
                        chosen, why = b4v2.consistency_pick_v2(cand_results)
                        if chosen is None:
                            # Repair
                            first_sql = cand_raw_sqls[0] if cand_raw_sqls else ''
                            first_err = cand_results[0][3] if cand_results else 'no_candidate'
                            rep_prompt = b4v2.make_repair_prompt_v2(item['question'], plan_obj,
                                                                     full_schema, first_sql, first_err)
                            rep_raw = gen(rep_prompt, max_new=256)[0]
                            rep_sql = extract_sql(rep_raw)
                            ok_r, _ = b4v2.is_safe_select(rep_sql)
                            try:
                                if ok_r and bench_kind in ('spider','bird'):
                                    if bench_kind == 'spider':
                                        execute_sql(db_paths[item['db_id']], rep_sql)
                                    else:
                                        execute_sql(ext.bird_db_path(item['db_id']), rep_sql)
                                    chosen, why = rep_sql, 'repaired'
                            except Exception:
                                pass
                            if chosen is None:
                                path = 'b1_fallback_no_executable'
                                sql = b1_fallback_sql(item, bench_kind)
                            else:
                                sql = chosen; path = f'multicand_repair:{why}'
                        else:
                            sql = chosen; path = f'multicand:{why}'
                    else:
                        raw = gen(sql_prompt, max_new=256)[0]
                        sql = extract_sql(raw)
                        path = 'plan_then_sql'
                if bench_kind == 'spider':
                    exb, match, et, em = evaluate_spider(item, sql)
                elif bench_kind == 'bird':
                    exb, match, et, em = evaluate_bird(item, sql)
                else:
                    exb, match, et, em = None, None, 'no_execution_engine', ''
            except Exception as exc:
                sql=''; exb,match = False, False
                et, em = 'gen_failed', f'{type(exc).__name__}: {exc}'
            rec = {'idx': i, 'question': item['question'], 'db_id': item['db_id'],
                   'gold_sql': item.get('query', item.get('gold_sql','')),
                   'plan': plan_obj, 'plan_error': plan_err,
                   'candidates': cand_raw_sqls if baseline_kind == 'B4_v2' else None,
                   'generated_sql': sql, 'executable': exb, 'execution_match': match,
                   'error_type': et, 'error_message': em,
                   'selected_tables': link.get('selected_tables',[]),
                   'reduction_ratio': link.get('reduction_ratio',0.0),
                   'path': path, 'structural': ext.structural_features(sql)}
            recs.append(rec)
            (OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\\n' for r in recs), encoding='utf-8')
            task_log(f'  {baseline_kind} {i:>2} {item["db_id"][:24]:<24} path={path[:24]:<24} exec={exb} match={match}')
        avg_red = sum(r.get('reduction_ratio',0) for r in recs)/len(recs) if recs else 0.0
        bg = 'internal_core' if bench_kind == 'spider' else 'external_validation'
        em_extra = {'evaluation_mode':'prediction_only_structural_metrics'} if bench_kind == 'spider2' else {}
        extra = {'quantization':'bf16',
                 'plan_validator':'plan_schema_v1',
                 'fallback_policy': ('b1_on_invalid_or_no_executable' if baseline_kind == 'B4_v2'
                                     else 'b1_on_invalid_plan'),
                 'avg_reduction_ratio':avg_red,
                 **em_extra}
        if baseline_kind == 'B2_v2':
            extra['schema_strategy'] = 'full_schema_planner_full_schema_synth'
            extra['patches'] = 'distinct_cue,superlative_subquery,anti_overengineering'
        elif baseline_kind == 'B3_v2':
            extra['schema_strategy'] = 'lex_linker_planner_full_schema_synth'
        elif baseline_kind == 'B4_v2':
            extra['schema_strategy'] = 'lex_linker_planner_full_schema_synth'
            extra['multi_candidate'] = 'k=3,T=0.7,top_p=0.95,top_k=50'
            extra['repair_depth'] = 1
        return write_run(prefix, recs, t0, subset_name, bg, extra)

    # Subset short → (items, bench_kind, subset_name)
    SUBSETS = {
        'smoke_10':       (smoke10,   'spider',  'smoke_10'),
        'smoke_25':       (smoke25,   'spider',  'smoke_25'),
        'multidb_30':     (multidb30, 'spider',  'multidb_30'),
        'bird_minidev_30':(bird_slice,'bird',    'bird_minidev_30'),
        'spider2lite_30': (s2_slice,  'spider2', 'spider2lite_30'),
    }

    # Prefix builder for new internal Spider runs (model-tagged)
    def spider_prefix(bl_compact, model_slug, subset_short):
        # Use new naming: <bl>_<model_slug>_<bench>
        if subset_short == 'smoke_10': bench = 'smoke10'
        elif subset_short == 'smoke_25': bench = 'smoke25'
        elif subset_short == 'multidb_30': bench = 'multidb30'
        elif subset_short == 'bird_minidev_30': bench = 'bird_minidev_30'
        elif subset_short == 'spider2lite_30': bench = 'spider2lite_30'
        return f'{bl_compact}_{model_slug}_{bench}'

    def run_cell(model_id, gated, model_slug, subset_short, baseline):
        items, bench_kind, subset_name = SUBSETS[subset_short]
        bl_compact = baseline.lower().replace('_','')
        prefix = spider_prefix(bl_compact, model_slug, subset_short)
        # Skip if already exists
        if (OUTPUTS/'metrics'/f'{prefix}_metrics.csv').exists():
            task_log(f'SKIP {prefix} (already exists)')
            return
        if MODEL['id'] != model_id:
            load_model(model_id, gated=gated)
        if baseline == 'B0':
            run_b0(items, bench_kind, subset_name, prefix)
        elif baseline == 'B1':
            run_b1(items, bench_kind, subset_name, prefix)
        else:
            run_baseline_v2(items, bench_kind, subset_name, prefix, baseline)

    # =====================================================================
    # Manifest of cells to close (P0 + P1, ~52 runs)
    # =====================================================================
    PLAN = []

    # ===== Lane A: Qwen-Coder-7B fill (6 runs)
    M = ('Qwen/Qwen2.5-Coder-7B-Instruct', False, 'qwen2p5_coder_7b')
    for sub in ['bird_minidev_30','spider2lite_30']:
        for bl in ['B1','B3_v2','B4_v2']:
            PLAN.append((*M, sub, bl))

    # ===== Lane B: Llama-3.1-8B fill (15 runs)
    M = ('meta-llama/Llama-3.1-8B-Instruct', True, 'llama_3p1_8b')
    # Internal layered B2_v2/B3_v2/B4_v2 on smoke10/25/multidb30
    for sub in ['smoke_10','smoke_25','multidb_30']:
        for bl in ['B2_v2','B3_v2','B4_v2']:
            PLAN.append((*M, sub, bl))
    # External fill: B1, B3_v2, B4_v2 on bird, spider2lite
    for sub in ['bird_minidev_30','spider2lite_30']:
        for bl in ['B1','B3_v2','B4_v2']:
            PLAN.append((*M, sub, bl))

    # ===== Lane C: Qwen-Coder-14B fill (19 runs)
    M = ('Qwen/Qwen2.5-Coder-14B-Instruct', False, 'qwen2p5_coder_14b')
    # Internal layered
    for sub in ['smoke_10','smoke_25','multidb_30']:
        for bl in ['B2_v2','B3_v2','B4_v2']:
            PLAN.append((*M, sub, bl))
    # External full
    for sub in ['bird_minidev_30','spider2lite_30']:
        for bl in ['B0','B1','B2_v2','B3_v2','B4_v2']:
            PLAN.append((*M, sub, bl))

    # ===== Lane D: Qwen2.5-7B-Instruct comparator (12 runs: B0/B1/B2_v2 × 4 missing benches)
    M = ('Qwen/Qwen2.5-7B-Instruct', False, 'qwen_qwen2.5_7b_instruct')
    for sub in ['smoke_25','multidb_30','bird_minidev_30','spider2lite_30']:
        for bl in ['B0','B1','B2_v2']:
            PLAN.append((*M, sub, bl))

    task_log(f'PLAN_TOTAL_RUNS={len(PLAN)}')

    # Execute
    for i, (model_id, gated, model_slug, sub, bl) in enumerate(PLAN):
        task_log(f'>>> RUN [{i+1}/{len(PLAN)}] model={model_id} bl={bl} sub={sub}')
        try:
            run_cell(model_id, gated, model_slug, sub, bl)
        except Exception as exc:
            task_log(f'CELL_FAILED: {type(exc).__name__}: {str(exc)[:300]}')
            task_log(traceback.format_exc())

    task_log('FULL_CLOSURE_SUBPROC_DONE')
except Exception:
    task_log('FULL_CLOSURE_SUBPROC_FAILED')
    task_log(traceback.format_exc())
'''))

# Spawn detached subprocess
proc = subprocess.Popen([sys.executable, str(RUNNER)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        start_new_session=True,
                        env={**os.environ})
print(f'STARTED subprocess pid={proc.pid}')
print(f'TASK_LOG={PROJECT_ROOT/"outputs/logs/full_closure_subproc_log.txt"}')
print(f'RUNNER_PATH={RUNNER}')
