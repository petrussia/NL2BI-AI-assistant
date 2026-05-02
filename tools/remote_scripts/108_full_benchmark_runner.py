# Full-benchmark resumable BG runner.
# Critical-evidence subset (Qwen-Coder-7B): B0/B1_v3/B3_v4 × Spider full + BIRD full + Spider2-Lite full structural,
# plus B2_v4 × BIRD full. 9 cells total, ~3500 generations, ~3-4 h on A100 BF16.

import os
import subprocess
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
RUNNER = Path('/tmp/full_benchmark_runner.py')

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

TASK_LOG = OUTPUTS / 'logs' / 'full_benchmark_runner_log.txt'
HEARTBEAT = OUTPUTS / 'logs' / 'full_run_heartbeat.json'

def task_log(msg):
    line = f'[{dt.datetime.now(dt.timezone.utc).isoformat()}] {msg}'
    print(line, flush=True)
    with TASK_LOG.open('a', encoding='utf-8') as f:
        f.write(line+'\\n')

def heartbeat(state):
    HEARTBEAT.write_text(json.dumps(state, indent=2), encoding='utf-8')

try:
    if not TASK_LOG.exists() or TASK_LOG.stat().st_size == 0:
        TASK_LOG.write_text('', encoding='utf-8')
    task_log('FULL_BENCHMARK_RUNNER_START')

    from func_timeout import FunctionTimedOut, func_timeout
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        from jsonschema import Draft7Validator as Draft202012Validator

    sys.path.insert(0, str(REPO/'src'/'evaluation'))
    import retrieval_hybrid
    import schema_linking_bidirectional
    import baselines_b1_v3 as b1v3
    import baselines_b3_v4 as b3v4
    import baselines_b2_v4 as b2v4
    import external_benchmark_adapters as ext

    plan_schema_v4 = json.loads((REPO/'docs'/'plan_schema_v4.json').read_text(encoding='utf-8'))
    plan_v4_validator = Draft202012Validator(plan_schema_v4)

    # ===== Data =====
    tables_map = {row['db_id']: row for row in
                  json.loads((SPIDER_DIR/'tables.json').read_text(encoding='utf-8'))}
    db_paths = {p.stem: p for p in (SPIDER_DIR/'database').rglob('*.sqlite')}
    spider_dev = json.loads((SPIDER_DIR/'dev.json').read_text(encoding='utf-8'))
    bird_full = json.loads((EXT/'bird_mini_dev/raw/minidev/minidev/MINIDEV/mini_dev_sqlite.json').read_text(encoding='utf-8'))
    bird_tables_meta = {row['db_id']: row for row in
                        json.loads((EXT/'bird_mini_dev/raw/minidev/minidev/MINIDEV/dev_tables.json').read_text(encoding='utf-8'))}
    s2_full = [json.loads(l) for l in open(EXT/'spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl', encoding='utf-8') if l.strip()]
    task_log(f'data: spider_dev={len(spider_dev)} bird_full={len(bird_full)} s2_full={len(s2_full)}')

    # ===== Helpers =====
    def build_full_spider(db_id):
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

    def build_reduced_spider(db_id, selected_idx):
        t = tables_map[db_id]
        tn = t.get('table_names_original') or t.get('table_names')
        cn = t.get('column_names_original') or t.get('column_names')
        by_table = {i: [] for i in range(len(tn))}
        for ti, col in cn:
            if ti >= 0: by_table.setdefault(ti, []).append(col)
        lines = [f'Database: {db_id}', 'Tables and columns (reduced via v3+ linking):']
        for idx in selected_idx:
            lines.append(f'- {tn[idx]}(' + ', '.join(by_table.get(idx, [])) + ')')
        return '\\n'.join(lines)

    def build_full_bird(db_id):
        return ext.bird_full_schema(db_id)
    def build_reduced_bird(db_id, selected_idx):
        return ext.bird_reduced_schema(db_id, selected_idx)

    def build_full_spider2(db):
        return ext.spider2_full_schema_proxy(db)
    def build_reduced_spider2(db, selected_idx):
        # spider2 doesn't have indexed tables; just use the proxy
        return ext.spider2_full_schema_proxy(db)

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

    # ===== Model loader (BF16 on A100) =====
    import torch
    MODEL = {'tok': None, 'm': None, 'id': None}
    def free_model():
        MODEL['tok']=None; MODEL['m']=None
        gc.collect(); torch.cuda.empty_cache()

    def load_model(model_id, gated=False):
        from transformers import AutoTokenizer, AutoModelForCausalLM
        token = os.environ.get('HF_TOKEN') if gated else None
        free_model()
        free, total = torch.cuda.mem_get_info(0)
        task_log(f'loading {model_id}: gpu_free={free/1e9:.2f} GB total={total/1e9:.2f} GB')
        t0 = time.time()
        kwargs = dict(device_map='auto', low_cpu_mem_usage=True,
                      torch_dtype=torch.bfloat16, trust_remote_code=True)
        if gated and token: kwargs['token'] = token
        tok = AutoTokenizer.from_pretrained(model_id, token=token if gated else None,
                                             trust_remote_code=True)
        m = AutoModelForCausalLM.from_pretrained(model_id, **kwargs)
        m.eval()
        MODEL['tok']=tok; MODEL['m']=m; MODEL['id']=model_id
        task_log(f'LOADED {model_id} in {time.time()-t0:.1f}s VRAM={torch.cuda.memory_allocated()//(1024*1024)} MB')

    def gen_with_metrics(prompt, max_new=256):
        m = MODEL['m']; tok = MODEL['tok']
        messages = [{'role':'user','content':prompt}]
        try:
            rendered = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        except Exception:
            rendered = prompt
        inputs = tok(rendered, return_tensors='pt')
        prompt_tokens = inputs['input_ids'].shape[1]
        prompt_chars = len(rendered)
        inputs = {k: v.to(m.device) for k,v in inputs.items()}
        t0 = time.time()
        with torch.no_grad():
            out = m.generate(**inputs, max_new_tokens=max_new, do_sample=False,
                             pad_token_id=tok.eos_token_id)
        elapsed_ms = (time.time() - t0) * 1000
        n_in = inputs['input_ids'].shape[1]
        out_tokens = out.shape[1] - n_in
        text = tok.decode(out[0][n_in:], skip_special_tokens=True)
        return {'text': text, 'prompt_tokens': prompt_tokens,
                'completion_tokens': out_tokens, 'prompt_chars': prompt_chars,
                'latency_ms': elapsed_ms}

    # gen() returns just text, with side-channel last_metrics
    LAST = {'metrics': {}}
    def gen(prompt, max_new=256):
        out = gen_with_metrics(prompt, max_new=max_new)
        LAST['metrics'] = out
        return out['text']

    def evaluate_spider(item, sql):
        executable, match = False, False
        err_t, err_m = '', ''; rows = None
        try:
            rows = execute_sql(db_paths[item['db_id']], sql); executable = True
            gold = execute_sql(db_paths[item['db_id']], item['query'])
            match = sorted(rows) == sorted(gold)
            if not match: err_t = 'result_mismatch'
        except FunctionTimedOut as exc:
            err_t, err_m = 'timeout', repr(exc)
        except Exception as exc:
            err_t, err_m = type(exc).__name__, str(exc)
        return executable, match, err_t, err_m, rows

    def evaluate_bird(item, sql):
        executable, match = False, False
        err_t, err_m = '', ''; rows = None
        try:
            db_path = ext.bird_db_path(item['db_id'])
            rows = execute_sql(db_path, sql); executable = True
            gold_text = item.get('SQL') or item.get('gold_sql') or item.get('query')
            gold = execute_sql(db_path, gold_text) if gold_text else None
            if gold is not None:
                match = sorted(rows) == sorted(gold)
                if not match: err_t = 'result_mismatch'
            else:
                err_t = 'no_gold'
        except FunctionTimedOut as exc:
            err_t, err_m = 'timeout', repr(exc)
        except Exception as exc:
            err_t, err_m = type(exc).__name__, str(exc)
        return executable, match, err_t, err_m, rows

    def structural_metrics(sql):
        return ext.structural_features(sql)

    # ===== Resumable per-item writer =====
    def append_jsonl(p, rec):
        with p.open('a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False)+'\\n')

    def already_done_count(p):
        if not p.exists(): return 0
        return sum(1 for line in open(p, encoding='utf-8') if line.strip())

    # ===== Run loop =====
    def run_baseline(items, bench_kind, bench_name, bench_size, baseline, prefix,
                     bird_meta_lookup=None, model_id=None):
        pred_p = OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl'
        n_done = already_done_count(pred_p)
        task_log(f'=== {baseline} {bench_name} ({prefix}): {n_done}/{bench_size} already done ===')
        if n_done >= bench_size:
            task_log(f'  SKIP — already complete')
            return
        t_start = time.time()

        for i in range(n_done, bench_size):
            item = items[i]
            db_id = item.get('db_id') or item.get('db') or '?'
            t_item = time.time()
            try:
                # Build schema by bench_kind
                if bench_kind == 'spider':
                    if db_id not in tables_map:
                        task_log(f'  WARN db_id {db_id} not in tables_map; skipping')
                        continue
                    full_schema = build_full_spider(db_id)
                elif bench_kind == 'bird':
                    full_schema = build_full_bird(db_id)
                elif bench_kind == 'spider2':
                    full_schema = build_full_spider2(db_id)
                # Run baseline
                if baseline == 'B0':
                    p = make_b0_prompt(item.get('question',''), full_schema)
                    raw = gen(p, max_new=256)
                    sql = extract_sql(raw)
                    sel_tables = []; link_conf = 1.0; reduction_ratio = 1.0; fb = False
                    planner_used = False; plan_obj = None; plan_valid = False
                    fallback_reason = ''; repair_count = 0
                    selected_source = 'b0_direct'
                elif baseline == 'B1_v3':
                    if bench_kind == 'spider':
                        tmeta = tables_map[db_id]; build_full = build_full_spider; build_red = build_reduced_spider
                    elif bench_kind == 'bird':
                        tmeta = bird_tables_meta.get(db_id, {}); build_full = build_full_bird; build_red = build_reduced_bird
                    else:
                        tmeta = {}
                        # Spider2: skip B1_v3 (no real schema metadata)
                        p = make_b0_prompt(item.get('question',''), full_schema)
                        raw = gen(p, max_new=256); sql = extract_sql(raw)
                        sel_tables = []; link_conf = 1.0; reduction_ratio = 1.0; fb = True
                        planner_used = False; plan_obj = None; plan_valid = False
                        fallback_reason = 'spider2_no_meta'; repair_count = 0
                        selected_source = 'b0_direct_spider2_fallback'
                    if bench_kind in ('spider','bird') and tmeta:
                        prompt, info = b1v3.make_b1v3_prompt(item.get('question',''), db_id, tmeta,
                                                              build_full, build_red)
                        raw = gen(prompt, max_new=256); sql = extract_sql(raw)
                        sel_tables = info.get('selected_table_indexes',[])
                        link_conf = info.get('link_confidence',0.0)
                        reduction_ratio = info.get('reduction_ratio',1.0)
                        fb = info.get('fallback_used',False)
                        planner_used = False; plan_obj = None; plan_valid = False
                        fallback_reason = info.get('mode_decision','')
                        repair_count = 0; selected_source = 'b1v3'
                elif baseline == 'B3_v4':
                    if bench_kind == 'spider':
                        tmeta = tables_map[db_id]; build_full = build_full_spider; build_red = build_reduced_spider
                    elif bench_kind == 'bird':
                        tmeta = bird_tables_meta.get(db_id, {}); build_full = build_full_bird; build_red = build_reduced_bird
                    else:
                        tmeta = {}
                        p = make_b0_prompt(item.get('question',''), full_schema)
                        raw = gen(p, max_new=256); sql = extract_sql(raw)
                        sel_tables = []; link_conf = 1.0; reduction_ratio = 1.0; fb = True
                        planner_used = False; plan_obj = None; plan_valid = False
                        fallback_reason = 'spider2_no_meta'; repair_count = 0
                        selected_source = 'b0_direct_spider2_fallback'
                    if bench_kind in ('spider','bird') and tmeta:
                        evidence = item.get('evidence','') if bench_kind == 'bird' else ''
                        prompt, info = b3v4.make_b3v4_prompt(item.get('question',''), db_id, tmeta,
                                                              build_full, build_red, evidence=evidence)
                        raw = gen(prompt, max_new=256); sql = extract_sql(raw)
                        sel_tables = info.get('selected_table_indexes',[])
                        link_conf = info.get('confidence',0.0)
                        reduction_ratio = info.get('reduction_ratio',1.0)
                        fb = info.get('fallback_used',False)
                        planner_used = False; plan_obj = None; plan_valid = False
                        fallback_reason = info.get('prompt_strategy','')
                        repair_count = 0; selected_source = 'b3v4'
                elif baseline == 'B2_v4':
                    # only on bird (and spider; not spider2)
                    if bench_kind == 'spider':
                        tmeta = tables_map[db_id]; build_full = build_full_spider; build_red = build_reduced_spider
                        evaluator_callback = lambda s: evaluate_spider(item, s)
                    elif bench_kind == 'bird':
                        tmeta = bird_tables_meta.get(db_id, {}); build_full = build_full_bird; build_red = build_reduced_bird
                        evaluator_callback = lambda s: evaluate_bird(item, s)
                    else:
                        sql = ''; sel_tables=[]; link_conf=0; reduction_ratio=1; fb=True
                        planner_used=False; plan_obj=None; plan_valid=False
                        fallback_reason='spider2_no_planner'; repair_count=0
                        selected_source='b0_direct_spider2_fallback'
                        executable=None; match=None; et='no_planner_for_spider2'; em=''
                        rec_extra = {}
                    if bench_kind in ('spider','bird') and tmeta:
                        def executor(sql):
                            ex_b, _, _, em, rows = evaluator_callback(sql)
                            return ex_b, rows, em
                        def b0_fallback(question, db_id, tables_meta, *, build_full_schema, gen):
                            return extract_sql(gen(make_b0_prompt(question, build_full_schema(db_id))))
                        def b1v3_fallback(question, db_id, tables_meta, *, build_full_schema, build_reduced_schema, gen):
                            p, info = b1v3.make_b1v3_prompt(question, db_id, tables_meta, build_full_schema, build_reduced_schema)
                            return extract_sql(gen(p))
                        evidence = item.get('evidence','') if bench_kind == 'bird' else ''
                        step = b2v4.run_b2v4_step(item.get('question',''), db_id, tmeta,
                                                   build_full_schema=build_full,
                                                   build_reduced_schema=build_red,
                                                   gen=gen, validator=plan_v4_validator,
                                                   executor=executor, evidence=evidence,
                                                   repair_depth=(2 if bench_kind=='bird' else 1),
                                                   b0_fallback=b0_fallback, b1v3_fallback=b1v3_fallback)
                        sql = step['sql']
                        sel_tables = step.get('selected_tables',[])
                        link_conf = step.get('link_confidence',0.0)
                        reduction_ratio = 1.0  # not tracked
                        fb = step.get('fallback_used',False)
                        planner_used = step.get('planner_used',False)
                        plan_obj = step.get('plan'); plan_valid = step.get('plan_valid',False)
                        fallback_reason = step.get('fallback_reason','')
                        repair_count = step.get('repair_count',0)
                        selected_source = 'b2v4_' + step.get('path','unknown')[:30]
                else:
                    sql = ''; selected_source = 'unknown_baseline'
                    sel_tables=[]; link_conf=0; reduction_ratio=1; fb=True
                    planner_used=False; plan_obj=None; plan_valid=False
                    fallback_reason=''; repair_count=0

                # Evaluate
                if bench_kind == 'spider':
                    executable, match, et, em, _ = evaluate_spider(item, sql)
                elif bench_kind == 'bird':
                    executable, match, et, em, _ = evaluate_bird(item, sql)
                else:
                    executable, match = None, None; et, em = 'no_execution_engine', ''

                gold_sql = item.get('query') or item.get('SQL') or item.get('sql') or item.get('gold_sql', '')
                rec = {
                    'idx': i, 'benchmark': bench_name, 'db_id': db_id,
                    'question': item.get('question',''), 'gold_sql': gold_sql,
                    'model': model_id, 'baseline': baseline,
                    'generated_sql': sql, 'executable': executable, 'execution_match': match,
                    'error_type': et, 'error_message': em,
                    'latency_ms': round(LAST['metrics'].get('latency_ms',0), 2),
                    'prompt_tokens': LAST['metrics'].get('prompt_tokens',0),
                    'completion_tokens': LAST['metrics'].get('completion_tokens',0),
                    'prompt_chars': LAST['metrics'].get('prompt_chars',0),
                    'selected_tables': sel_tables, 'selected_columns': [],
                    'link_confidence': link_conf, 'selected_schema_ratio': reduction_ratio,
                    'planner_used': planner_used, 'plan_valid': plan_valid, 'plan_json': plan_obj,
                    'fallback_used': fb, 'fallback_reason': fallback_reason,
                    'repair_used': repair_count > 0, 'repair_count': repair_count,
                    'candidate_count': 1, 'selected_candidate_source': selected_source,
                    'safe_select': bool(re.match(r'^\\s*(?:with|select)\\b', (sql or '').strip(), re.I)),
                    'structural_metrics': structural_metrics(sql) if bench_kind == 'spider2' else None,
                }
                append_jsonl(pred_p, rec)
                if (i + 1) % 10 == 0 or i + 1 == bench_size:
                    elapsed = time.time() - t_start
                    rate = (i + 1 - n_done) / max(1, elapsed) * 60
                    eta = (bench_size - (i+1)) / max(0.001, rate/60) if rate > 0 else 0
                    task_log(f'  {baseline} {i+1}/{bench_size} db={db_id[:20]:<20} '
                             f'exec={executable} match={match} err={et[:20]!r:<22} '
                             f'lat={rec["latency_ms"]:.0f}ms (~{rate:.1f}/min, eta~{eta/60:.1f}h)')
                    heartbeat({'prefix': prefix, 'i': i+1, 'n': bench_size,
                               'rate_per_min': round(rate,2),
                               'updated': dt.datetime.now(dt.timezone.utc).isoformat()})
            except Exception as exc:
                rec = {'idx': i, 'benchmark': bench_name, 'db_id': db_id,
                       'question': item.get('question',''),
                       'generated_sql': '', 'executable': False, 'execution_match': False,
                       'error_type': 'item_failed', 'error_message': f'{type(exc).__name__}: {exc}',
                       'baseline': baseline, 'model': model_id}
                append_jsonl(pred_p, rec)
                task_log(f'  ITEM_FAILED {i}: {type(exc).__name__}: {str(exc)[:200]}')

        # Write metrics CSV from predictions
        records = []
        for line in open(pred_p, encoding='utf-8'):
            line = line.strip()
            if not line: continue
            try: records.append(json.loads(line))
            except Exception: pass
        total = len(records)
        exec_count = sum(1 for r in records if r.get('executable'))
        match_count = sum(1 for r in records if r.get('execution_match'))
        ex = match_count / total if total else 0
        latencies = [r.get('latency_ms',0) for r in records if r.get('latency_ms')]
        latencies.sort()
        def pct(arr, p):
            if not arr: return 0
            k = (len(arr)-1) * p / 100
            lo = int(k); hi = lo + 1 if lo < len(arr)-1 else lo
            return arr[lo] * (hi-k) + arr[hi] * (k-lo)
        prompt_tokens = [r.get('prompt_tokens',0) for r in records if r.get('prompt_tokens')]
        completion_tokens = [r.get('completion_tokens',0) for r in records if r.get('completion_tokens')]
        fallback_count = sum(1 for r in records if r.get('fallback_used'))
        repair_total = sum(r.get('repair_count',0) for r in records)
        plan_valid_count = sum(1 for r in records if r.get('plan_valid'))
        planner_used_count = sum(1 for r in records if r.get('planner_used'))
        base = {'run_id': prefix, 'model': MODEL['id'], 'subset': bench_name,
                'benchmark_group': 'internal_core' if bench_kind=='spider' else 'external_validation',
                'baseline_version': 'v4',
                'n': total, 'execution_match_count': match_count, 'ex': ex,
                'executable_count': exec_count,
                'plan_valid_count': plan_valid_count,
                'planner_used_count': planner_used_count,
                'fallback_rate': fallback_count/total if total else 0,
                'repair_rate': repair_total/total if total else 0,
                'latency_p50_ms': round(pct(latencies, 50), 1),
                'latency_p95_ms': round(pct(latencies, 95), 1),
                'avg_prompt_tokens': round(sum(prompt_tokens)/len(prompt_tokens), 1) if prompt_tokens else 0,
                'avg_completion_tokens': round(sum(completion_tokens)/len(completion_tokens), 1) if completion_tokens else 0,
                'baseline_name': baseline, 'evaluation_mode':
                    ('full_ex' if bench_kind != 'spider2' else 'structural_only')}
        with (OUTPUTS/'metrics'/f'{prefix}_metrics.csv').open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(base.keys())); w.writeheader(); w.writerow(base)
        with (OUTPUTS/'tables'/f'{prefix}_summary.csv').open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['metric','value']); w.writeheader()
            for k, v in base.items(): w.writerow({'metric': k, 'value': v})
        task_log(f'  {prefix} DONE: EX={ex:.4f} ({match_count}/{total}) '
                 f'lat_p50={base["latency_p50_ms"]}ms p95={base["latency_p95_ms"]}ms '
                 f'fallback={base["fallback_rate"]:.2f} elapsed={time.time()-t_start:.0f}s')

    # ===== Plan: critical-evidence subset (Qwen-Coder-7B × 9 cells) =====
    MODEL_ID = 'Qwen/Qwen2.5-Coder-7B-Instruct'
    load_model(MODEL_ID, gated=False)

    PLAN = [
        # bench_kind, bench_name, items, baseline, prefix
        ('spider', 'spider_dev', spider_dev, 'B0', 'b0_qwen2p5_coder_7b_spider_dev_full'),
        ('spider', 'spider_dev', spider_dev, 'B1_v3', 'b1v3_qwen2p5_coder_7b_spider_dev_full'),
        ('spider', 'spider_dev', spider_dev, 'B3_v4', 'b3v4_qwen2p5_coder_7b_spider_dev_full'),
        ('bird',   'bird_full',  bird_full,  'B0', 'b0_qwen2p5_coder_7b_bird_full'),
        ('bird',   'bird_full',  bird_full,  'B1_v3', 'b1v3_qwen2p5_coder_7b_bird_full'),
        ('bird',   'bird_full',  bird_full,  'B3_v4', 'b3v4_qwen2p5_coder_7b_bird_full'),
        ('bird',   'bird_full',  bird_full,  'B2_v4', 'b2v4_qwen2p5_coder_7b_bird_full'),
        ('spider2','spider2lite_full', s2_full, 'B0', 'b0_qwen2p5_coder_7b_spider2lite_full'),
        ('spider2','spider2lite_full', s2_full, 'B3_v4', 'b3v4_qwen2p5_coder_7b_spider2lite_full'),
    ]

    for i, (bk, bn, items, bl, prefix) in enumerate(PLAN, 1):
        task_log(f'>>> CELL [{i}/{len(PLAN)}] baseline={bl} bench={bn} prefix={prefix}')
        try:
            run_baseline(items, bk, bn, len(items), bl, prefix, model_id=MODEL_ID)
        except Exception as exc:
            task_log(f'CELL_FAILED {prefix}: {type(exc).__name__}: {str(exc)[:300]}')
            task_log(traceback.format_exc()[-700:])

    task_log('FULL_BENCHMARK_RUNNER_DONE')
except Exception:
    task_log('FULL_BENCHMARK_RUNNER_FAILED')
    task_log(traceback.format_exc())
'''))

# Spawn detached
proc = subprocess.Popen([sys.executable, str(RUNNER)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        start_new_session=True,
                        env={**os.environ})
print(f'STARTED subprocess pid={proc.pid}')
print(f'TASK_LOG={PROJECT_ROOT/"outputs/logs/full_benchmark_runner_log.txt"}')
print(f'HEARTBEAT={PROJECT_ROOT/"outputs/logs/full_run_heartbeat.json"}')
print(f'RUNNER_PATH={RUNNER}')
